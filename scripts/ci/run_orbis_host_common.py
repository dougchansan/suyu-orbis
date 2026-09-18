#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Run the real-Common Orbis executable under shadPS4; require fresh guest proof."""
from __future__ import annotations
import argparse, hashlib, json, os, signal, subprocess, time
from pathlib import Path

def stop(p):
    if p is None:return
    try:os.killpg(p.pid,signal.SIGTERM)
    except ProcessLookupError:return
    try:p.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:os.killpg(p.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        p.wait(timeout=3)

def validate(r):
    if not isinstance(r,dict):raise ValueError('Guest report is not an object')
    required={'test':'real_suyu_common_host_adaptation','passed':True,
              'orbis_apis':True,'fiber_roundtrips':4096,'cross_thread_hops':32,
              'live_page_allocations':0,'full_core_linked':False,
              'scheduler_dispatch':False,'guest_fastmem':False,'game_tested':False}
    for k,v in required.items():
        if type(r.get(k)) is not type(v) or r[k]!=v:raise ValueError(f'Unexpected {k}: {r.get(k)!r}')
    if type(r.get('checks')) is not int or r['checks']<1000000:raise ValueError('Missing component checks')
    if type(r.get('sleep_ns')) is not int or not 10000000<=r['sleep_ns']<5000000000:raise ValueError('Wrong native counter/sleep units')

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--emulator',type=Path,required=True)
    p.add_argument('--executable',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=a.output.resolve();exe=a.executable.resolve(strict=True);emu=a.emulator.resolve(strict=True)
    if out.exists() and any(out.iterdir()):p.error('Use an empty output directory; stale reports cannot pass')
    profile=out/'profile';data=profile/'user/data';data.mkdir(parents=True)
    for n in range(1000,1004):
        for d in ('savedata','trophy','inputs'):(profile/f'user/home/{n}'/d).mkdir(parents=True)
    runtime=profile/'xdg';runtime.mkdir(mode=0o700)
    env=os.environ.copy();env.update(DISPLAY=':96',XDG_RUNTIME_DIR=str(runtime),SDL_VIDEODRIVER='x11',
        SDL_AUDIODRIVER='dummy',ALSOFT_DRIVERS='null',APPIMAGE_EXTRACT_AND_RUN='1')
    env.pop('SHADPS4_ENABLE_IPC',None)
    display=guest=None
    try:
        with (out/'xvfb.log').open('w') as xf,(out/'shadps4.log').open('w') as sf:
            display=subprocess.Popen(['Xvfb',':96','-screen','0','1280x720x24','-nolisten','tcp'],
                env=env,stdout=xf,stderr=subprocess.STDOUT,start_new_session=True)
            time.sleep(1)
            if display.poll() is not None:raise RuntimeError('Xvfb failed')
            guest=subprocess.Popen([str(emu),'--config-clean',str(exe)],cwd=profile,env=env,
                stdout=sf,stderr=subprocess.STDOUT,start_new_session=True)
            deadline=time.monotonic()+90
            report=None
            while time.monotonic()<deadline:
                path=data/'orbis-host-common.json'
                if path.exists():
                    report=json.loads(path.read_text());break
                if guest.poll() is not None:break
                time.sleep(0.1)
            if report is None:
                s=data/'orbis-host-stage.txt'
                raise RuntimeError('No completed guest report; last stage: '+(s.read_text() if s.exists() else 'before guest entry'))
            validate(report)
            evidence={'passed':True,'environment':'shadPS4_on_Linux','physical_ps4_tested':False,
                'source_commit':os.environ.get('GITHUB_SHA'),'executable_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),
                'guest':report}
            (out/'validation.json').write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps(evidence,indent=2))
        return 0
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:
        (out/'failure.txt').write_text(str(e)+'\n');print(f'Orbis Common test FAILED: {e}');return 1
    finally:stop(guest);stop(display)
if __name__=='__main__':raise SystemExit(main())
