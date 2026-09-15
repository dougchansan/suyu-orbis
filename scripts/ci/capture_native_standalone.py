#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Prove the native Orbis app completes without any host capture acknowledgments."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from capture_native_aot import stop, validate_image


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emulator', type=Path, required=True)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    emulator = args.emulator.resolve(strict=True)
    executable = args.executable.resolve(strict=True)
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error('Output must be empty; stale completion is not evidence')
    data = output / 'profile/user/data'
    data.mkdir(parents=True)
    profile = output / 'profile'
    for user in range(1000, 1004):
        for folder in ('savedata', 'trophy', 'inputs'):
            (profile / f'user/home/{user}' / folder).mkdir(parents=True, exist_ok=True)
    runtime = profile / 'xdg'
    runtime.mkdir(mode=0o700)
    env = os.environ.copy()
    env.update(DISPLAY=':97', XDG_RUNTIME_DIR=str(runtime), SDL_VIDEODRIVER='x11',
               SDL_AUDIODRIVER='dummy', ALSOFT_DRIVERS='null', APPIMAGE_EXTRACT_AND_RUN='1')
    env.pop('SHADPS4_ENABLE_IPC', None)
    display = guest = None
    try:
        with (output/'xvfb.log').open('w') as xlog, (output/'shadps4.log').open('w') as elog:
            display = subprocess.Popen(['Xvfb', ':97', '-screen', '0', '1280x720x24', '-nolisten', 'tcp'],
                env=env, stdout=xlog, stderr=subprocess.STDOUT, start_new_session=True)
            time.sleep(2)
            if display.poll() is not None:
                raise RuntimeError('Xvfb failed')
            guest = subprocess.Popen([str(emulator), '--config-clean', '--fullscreen', 'true', str(executable)],
                cwd=profile, env=env, stdout=elog, stderr=subprocess.STDOUT, start_new_session=True)
            deadline = time.monotonic()+90
            complete = None
            while time.monotonic() < deadline:
                failure = data/'aot-failure.json'
                if failure.exists():
                    raise RuntimeError(f'Guest failed: {failure.read_text()}')
                path = data/'aot-complete.json'
                if path.exists():
                    try:
                        complete = json.loads(path.read_text())
                        break
                    except json.JSONDecodeError:
                        pass
                if guest.poll() is not None:
                    raise RuntimeError(f'Emulator exited {guest.returncode} before completion')
                time.sleep(0.1)
            if not complete or complete.get('passed') is not True or complete.get('frames_presented') != 4:
                raise RuntimeError(f'No successful standalone completion: {complete}')
            if list(data.glob('aot-ack-*')):
                raise RuntimeError('Unexpected host acknowledgment in standalone test')
            reports = []
            for phase in range(4):
                report = json.loads((data/f'aot-frame-{phase}.json').read_text())
                expected = {'passed':True, 'phase':phase, 'width':1280, 'height':720,
                    'runtime_selftests_passed':True, 'host_draws_pixels':False,
                    'full_suyu_hle':False, 'switch_gpu':False, 'cpu_jit':False,
                    'guest_stores':(phase+1)*1280*720, 'svc_yields':2*(phase+1)}
                if any(report.get(k) != v for k,v in expected.items()):
                    raise ValueError(f'Unexpected guest report: {report}')
                if report.get('completed_flips', 0) < phase+1:
                    raise ValueError(f'Missing completed flips: {report}')
                reports.append(report)
            captures=[]
            for index in range(2):
                time.sleep(0.5)
                path=output/f'final-frame-{index}.png'
                subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'x11grab',
                    '-draw_mouse', '0', '-video_size', '1280x720', '-i', ':97', '-frames:v', '1', str(path)],
                    env=env, check=True, timeout=15)
                captures.append(validate_image(path, 3))
            result={'passed':True, 'mode':'standalone_no_capture_acknowledgments',
                'execution_environment':'shadPS4_on_Linux', 'physical_ps4_tested':False,
                'full_suyu_hle':False, 'switch_gpu':False, 'source_commit':os.environ.get('GITHUB_SHA'),
                'executable_sha256':hashlib.sha256(executable.read_bytes()).hexdigest(),
                'guest_reports':reports, 'completion':complete, 'final_frame_captures':captures,
                'note':'Four completed flips; only final phase 3 is externally captured in this test.'}
            (output/'validation.json').write_text(json.dumps(result, indent=2)+'\n')
            print(json.dumps(result, indent=2), flush=True)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        (output/'failure.txt').write_text(str(error)+'\n')
        print(f'Standalone Orbis test FAILED: {error}', flush=True)
        return 1
    finally:
        stop(guest)
        stop(display)


if __name__=='__main__':
    raise SystemExit(main())
