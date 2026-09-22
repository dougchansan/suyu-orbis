#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Execute the C++ runtime probe under unmodified shadPS4; require fresh proof."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

# Audited libcxx/include/__config at 87f0227cb60147a26a1eeb4fb06e3b505e9c7261:
# _LIBCPP_VERSION is 200100 even though the release tag is llvmorg-20.1.8.
EXPECTED = {'test': 'orbis_modern_cxx_runtime', 'passed': True, 'libcpp_version': 200100,
    'math_locale_ranges': True, 'exception_unwind_rtti': True, 'atomic_ref_total': 4096,
    'tls_destructors': 2, 'barrier_phases': 8, 'atomic_wait_notify': True,
    'jthread_stop_wait': True, 'filesystem': True, 'random_reads': 4,
    'full_core_linked': False, 'game_tested': False}

def validate(report: object) -> None:
    if not isinstance(report, dict):
        raise ValueError('Report must be an object')
    for key, value in EXPECTED.items():
        if type(report.get(key)) is not type(value) or report[key] != value:
            raise ValueError(f'Invalid {key}: {report.get(key)!r}')
    if type(report.get('checks')) is not int or report['checks'] < 35:
        raise ValueError('Incomplete test assertion count')

def stop(process: subprocess.Popen | None) -> None:
    if process is None:
        return
    try: os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError: return
    try: process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try: os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        process.wait(timeout=3)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emulator', type=Path, required=True)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists() and any(out.iterdir()):
        parser.error('Use a fresh output directory; stale reports cannot pass')
    executable = args.executable.resolve(strict=True)
    emulator = args.emulator.resolve(strict=True)
    profile = out/'profile'
    data = profile/'user/data'; data.mkdir(parents=True)
    for n in range(1000,1004):
        for directory in ('savedata','trophy','inputs'):
            (profile/f'user/home/{n}'/directory).mkdir(parents=True)
    runtime = profile/'xdg'; runtime.mkdir(mode=0o700)
    env = os.environ.copy()
    env.update(DISPLAY=':95', XDG_RUNTIME_DIR=str(runtime), SDL_VIDEODRIVER='x11',
               SDL_AUDIODRIVER='dummy', ALSOFT_DRIVERS='null', APPIMAGE_EXTRACT_AND_RUN='1')
    env.pop('SHADPS4_ENABLE_IPC', None)
    display = guest = None
    try:
        with (out/'xvfb.log').open('w') as xf, (out/'shadps4.log').open('w') as sf:
            display = subprocess.Popen(['Xvfb', ':95', '-screen', '0', '1280x720x24', '-nolisten', 'tcp'],
                env=env, stdout=xf, stderr=subprocess.STDOUT, start_new_session=True)
            time.sleep(1)
            if display.poll() is not None:
                raise RuntimeError('Xvfb failed')
            guest = subprocess.Popen([str(emulator), '--config-clean', str(executable)],
                cwd=profile, env=env, stdout=sf, stderr=subprocess.STDOUT, start_new_session=True)
            deadline = time.monotonic()+45
            report = None
            while time.monotonic()<deadline:
                marker = data/'orbis-cxx20.json'
                if marker.exists():
                    try: report = json.loads(marker.read_text())
                    except json.JSONDecodeError: pass # Writer may not have closed yet.
                    else: break
                if guest.poll() is not None: break
                time.sleep(0.1)
            if report is None:
                stage = data/'orbis-cxx20-stage.txt'
                detail = 'last stage: '+(stage.read_text() if stage.exists() else 'before guest entry')
                log_path = out/'shadps4.log'
                if log_path.exists():
                    failures = [line.strip() for line in log_path.read_text(errors='replace').splitlines()
                                if 'FAIL [' in line]
                    if failures:
                        detail += '; guest failure: '+failures[-1]
                raise RuntimeError('No completed report; '+detail)
            validate(report)
            result = {'passed':True, 'environment':'shadPS4_on_Linux',
                'physical_ps4_tested':False, 'source_commit':os.environ.get('GITHUB_SHA'),
                'executable_sha256':hashlib.sha256(executable.read_bytes()).hexdigest(), 'guest':report}
            (out/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps(result,indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        (out/'failure.txt').write_text(str(error)+'\n')
        print(f'Orbis C++ runtime FAILED: {error}')
        return 1
    finally:
        stop(guest); stop(display)

if __name__ == '__main__':
    raise SystemExit(main())
