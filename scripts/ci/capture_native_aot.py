#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Execute the converted Orbis AOT diagnostic and verify four actual display captures."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import signal
import subprocess
import time
from pathlib import Path
from PIL import Image, ImageChops

def stop(process: subprocess.Popen | None) -> None:
    if process is None: return
    try: os.killpg(process.pid,signal.SIGTERM)
    except ProcessLookupError: pass
    try: process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try: os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError: pass
        process.wait(timeout=3)

def validate_image(path: Path,phase: int) -> dict:
    image=Image.open(path).convert('RGB')
    if image.size!=(1280,720): raise ValueError(f'Wrong capture dimensions {image.size}')
    checks=0
    for y in range(32,720,64):
        for x in range(32,1280,64):
            expected=((((x>>7)^phase)&1)*255,((x>>8)&1)*255,((y>>7)&1)*255)
            actual=image.getpixel((x,y))
            if any(abs(a-b)>16 for a,b in zip(actual,expected)):
                raise ValueError(f'Frame {phase}, pixel ({x},{y}): {actual}, expected {expected}')
            checks+=1
    return {'phase':phase,'file':path.name,'pattern_checks':checks,
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'passed':True}

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emulator',type=Path,required=True)
    parser.add_argument('--executable',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    executable=args.executable.resolve(strict=True)
    emulator=args.emulator.resolve(strict=True)
    output=args.output.resolve()
    if output.exists() and any(output.iterdir()): parser.error('Output must be empty; no stale evidence allowed')
    output.mkdir(parents=True,exist_ok=True)
    profile=output/'profile'; data=profile/'user/data'
    data.mkdir(parents=True)
    for user in range(1000,1004):
        for folder in ('savedata','trophy','inputs'):
            (profile/f'user/home/{user}'/folder).mkdir(parents=True,exist_ok=True)
    runtime=profile/'xdg'; runtime.mkdir(mode=0o700)
    env=os.environ.copy()
    env.update(DISPLAY=':98',XDG_RUNTIME_DIR=str(runtime),SDL_VIDEODRIVER='x11',
               SDL_AUDIODRIVER='dummy',ALSOFT_DRIVERS='null',APPIMAGE_EXTRACT_AND_RUN='1')
    env.pop('SHADPS4_ENABLE_IPC',None)
    display=guest=None
    try:
        with (output/'xvfb.log').open('w') as xlog, (output/'shadps4.log').open('w') as elog:
            display=subprocess.Popen(['Xvfb',':98','-screen','0','1280x720x24','-nolisten','tcp'],
                                     env=env,stdout=xlog,stderr=subprocess.STDOUT,start_new_session=True)
            time.sleep(2)
            if display.poll() is not None: raise RuntimeError('Xvfb failed to start')
            guest=subprocess.Popen([str(emulator),'--config-clean','--fullscreen','true',str(executable)],
                                   cwd=profile,env=env,stdout=elog,stderr=subprocess.STDOUT,start_new_session=True)
            def await_json(name: str, timeout: float=45) -> dict:
                end=time.monotonic()+timeout
                while time.monotonic()<end:
                    failure=data/'aot-failure.json'
                    if failure.is_file(): raise RuntimeError(f'Native failure: {failure.read_text()}')
                    target=data/name
                    if target.is_file():
                        try: return json.loads(target.read_text())
                        except json.JSONDecodeError: pass
                    if guest.poll() is not None: raise RuntimeError(f'shadPS4 exited {guest.returncode} before {name}')
                    time.sleep(0.05)
                raise TimeoutError(f'Guest did not produce {name}')
            frames=[]
            for phase in range(4):
                marker=await_json(f'aot-frame-{phase}.json')
                for key,value in {'passed':True,'phase':phase,'width':1280,'height':720,
                                  'runtime_selftests_passed':True,'host_draws_pixels':False,
                                  'full_suyu_hle':False,'switch_gpu':False,'cpu_jit':False}.items():
                    if marker.get(key)!=value: raise ValueError(f'Invalid guest report {key}: {marker}')
                if marker['guest_stores']!=(phase+1)*1280*720: raise ValueError(f'Wrong guest write count: {marker}')
                if marker['completed_flips']<phase+1: raise ValueError(f'Flip completion not established: {marker}')
                # The native diagnostic holds the COMPLETED frame until this capture is validated.
                time.sleep(0.25)
                path=output/f'frame-{phase}.png'
                subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','x11grab',
                                '-draw_mouse','0','-video_size','1280x720','-i',':98','-frames:v','1',str(path)],
                               env=env,check=True,timeout=15)
                frame=validate_image(path,phase); frame['guest']=marker; frames.append(frame)
                print(json.dumps(frame),flush=True)
                (data/f'aot-ack-{phase}').write_text('captured and validated\n')
            completion=await_json('aot-complete.json')
            if completion.get('passed') is not True or completion.get('frames_presented')!=4:
                raise ValueError(f'Invalid completion: {completion}')
            first=Image.open(output/'frame-0.png').convert('RGB')
            second=Image.open(output/'frame-1.png').convert('RGB')
            if ImageChops.difference(first,second).getbbox() is None:
                raise ValueError('Expected different frames, got identical captures')
            report={'passed':True,'execution_environment':'shadPS4_on_Linux',
                    'physical_ps4_tested':False,'full_suyu_hle':False,'switch_gpu':False,
                    'executable_sha256':hashlib.sha256(executable.read_bytes()).hexdigest(),
                    'source_commit':os.environ.get('GITHUB_SHA'),'frames':frames,'completion':completion}
            (output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
            print('Native Suyu-generated AArch64 execution and four presented frames verified.',flush=True)
        return 0
    except (OSError,ValueError,RuntimeError,TimeoutError,subprocess.SubprocessError) as error:
        print(f'Native capture FAILED: {error}',flush=True)
        (output/'failure.txt').write_text(str(error)+'\n')
        print((output/'shadps4.log').read_text(errors='replace')[-18000:] if (output/'shadps4.log').exists() else '')
        for log in (profile/'user/log').glob('*'):
            if log.is_file(): print(log.name,log.read_text(errors='replace')[-18000:])
        return 1
    finally:
        stop(guest); stop(display)
if __name__=='__main__': raise SystemExit(main())
