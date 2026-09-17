#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Run the scheduled-process regression with a timeout and a fresh user profile."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import platform
import signal
import subprocess
from pathlib import Path
from typing import Any

TEST = 'real_suyu_scheduled_process_svc'
EXPECTED_SVCS = [30, 37, 36, 16, 37, 11, 30, 10]

def validate_report(report: dict[str, Any]) -> None:
    """Require the detailed evidence, not just a self-reported passed flag."""
    if report.get('test') != TEST:
        raise ValueError('Wrong test identity')
    for key in ('passed','scheduler_dispatch','normal_svc_dispatch','same_cpu_instance',
                'pending_svc_cleared_on_resume','guest_memory_verified','thread_exited',
                'observed_waiting','clean_shutdown'):
        if report.get(key) is not True:
            raise ValueError(f'{key} was not proved')
    for key in ('jit_available','real_title_loader','orbis_execution','game_tested'):
        if report.get(key) is not False:
            raise ValueError(f'Incorrect scope: {key}')
    if report.get('renderer') != 'none' or report.get('jit_transitions') != 0:
        raise ValueError('Unexpected renderer or fallback')
    if report.get('svcs') != EXPECTED_SVCS:
        raise ValueError('Unexpected syscall sequence')
    values = report.get('guest_values')
    if not isinstance(values,list) or len(values) != 14:
        raise ValueError('Missing guest memory results')
    if values[0] != 42 or values[4] != 0 or values[6] != 0 or values[8] != 0:
        raise ValueError('Guest arithmetic or syscall result mismatch')
    if values[1] != report.get('tls') or values[11] != report.get('tls'):
        raise ValueError('TLS was not preserved')
    if values[2] != report.get('thread_handle') or values[5] != report.get('thread_id') or values[7] != report.get('process_id'):
        raise ValueError('Process/thread identity mismatch')
    # Kernel result 114, module 1: must be the actual InvalidHandle error.
    if values[9] != (114 << 9 | 1) or values[12] != 0x600d or values[13] == 0:
        raise ValueError('Error handling, completion marker or stack mismatch')
    if values[3] <= 0 or values[10] < values[3]:
        raise ValueError('Invalid monotonic clock results')
    if report.get('sleep_resume_interval_ns',0) <= 0 or report.get('static_blocks',0) <= 0:
        raise ValueError('No timed resume or static execution evidence')
    trace = report.get('trace')
    if not isinstance(trace,list) or not trace:
        raise ValueError('Missing execution trace')
    trace_svcs=[]
    for block in trace:
        if block.get('thread_id') != report['thread_id'] or block.get('process_id') != report['process_id'] or block.get('core') != 0:
            raise ValueError('Trace did not run on the expected real process/thread/core')
        if block.get('pending_svc') != (1 << 64)-1:
            trace_svcs.append(block.get('pending_svc'))
    if trace_svcs != EXPECTED_SVCS:
        raise ValueError('Trace contradicts the reported syscall sequence')

def run(binary: Path, output: Path, timeout: float, library_path: str | None = None) -> dict[str, Any]:
    binary=binary.resolve(strict=True)
    output=output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('Evidence directory must be empty; use a fresh path')
    output.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy()
    for key,sub in [('HOME','home'),('XDG_CONFIG_HOME','config'),('XDG_DATA_HOME','data'),('XDG_CACHE_HOME','cache')]:
        path=output/'profile'/sub;path.mkdir(parents=True,exist_ok=True);env[key]=str(path)
    env['SUYU_RECOMP_STRICT']='1'
    if library_path:env['LD_LIBRARY_PATH']=library_path
    command=[str(binary)]
    process=subprocess.Popen(command,env=env,cwd=output,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                             start_new_session=True)
    timed_out=False
    try:
        stdout,stderr=process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out=True
        os.killpg(process.pid,signal.SIGKILL)
        stdout,stderr=process.communicate()
    (output/'stdout.log').write_bytes(stdout)
    (output/'stderr.log').write_bytes(stderr)
    reports=[]
    for line in (stdout+b'\n'+stderr).decode('utf-8',errors='replace').splitlines():
        try:item=json.loads(line)
        except json.JSONDecodeError:continue
        if isinstance(item,dict) and item.get('test')==TEST:reports.append(item)
    status={'test':TEST,'passed':False,'returncode':process.returncode,'timed_out':timed_out,
            'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
            'platform':platform.platform(),'command':command,'source_report_count':len(reports)}
    if len(reports)==1:
        report=reports[0];(output/'guest-report.json').write_text(json.dumps(report,indent=2)+'\n')
        try:
            validate_report(report)
            if timed_out or process.returncode!=0:raise ValueError('Executable did not finish successfully')
            status['passed']=True
        except (ValueError,TypeError,KeyError) as exc:status['error']=str(exc)
    else:status['error']='Expected exactly one complete process-test result'
    (output/'result.json').write_text(json.dumps(status,indent=2)+'\n')
    return status

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('binary',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--timeout',type=float,default=60)
    p.add_argument('--library-path')
    a=p.parse_args()
    if a.timeout<=0:p.error('timeout must be positive')
    result=run(a.binary,a.output,a.timeout,a.library_path)
    print(json.dumps(result,indent=2))
    return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
