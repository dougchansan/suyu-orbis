#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Compile-only audit of the SDK's C++ features used by the pinned Suyu core.

Missing features are reported, not disguised as available. A green audit-tool
exit means the report was produced, NOT that the SDK can build the full core.
"""
from __future__ import annotations
import argparse, json, os, re, subprocess
from pathlib import Path
CASES={
    'stop_token':'#include <stop_token>\nstd::stop_source source;\n',
    'jthread':'#include <thread>\nvoid f(){std::jthread t([]{});}\n',
    'stop_aware_condition_variable':'#include <thread>\n#include <condition_variable>\nvoid f(std::stop_token st){ std::mutex m; std::unique_lock lock(m); std::condition_variable_any cv; cv.wait(lock,st,[]{return true;});}\n',
    'atomic_ref':'#include <atomic>\nvoid f(int& value){std::atomic_ref<int>(value).fetch_add(1);}\n',
    'bit_cast':'#include <bit>\nfloat f(unsigned x){return std::bit_cast<float>(x);}\n',
    'ranges':'#include <algorithm>\nvoid f(){int a[]={1,2};(void)std::ranges::find(a,2);}\n',
    'span':'#include <span>\nvoid f(int* p){std::span<int> s(p,2);}\n',
    'barrier':'#include <barrier>\nvoid f(){std::barrier b(1);b.arrive_and_wait();}\n',
    'common_polyfill_thread':'#include "common/polyfill_thread.h"\n',
}
def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sdk',type=Path,default=Path(os.environ.get('OO_PS4_TOOLCHAIN','')))
    p.add_argument('--suyu',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--cxx',default='clang++')
    a=p.parse_args();sdk=a.sdk.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    cfg=sdk/'include/c++/v1/__config'
    if not cfg.is_file():p.error('A complete public OpenOrbis SDK is required')
    version=re.search(r'#define\s+_LIBCPP_VERSION\s+(\d+)',cfg.read_text())
    results=[]
    for name,code in CASES.items():
        src=out/(name+'.cpp');src.write_text(code)
        argv=[a.cxx,'--target=x86_64-pc-freebsd12-elf',f'--sysroot={sdk}',
              '-nostdinc++','-isystem',str(sdk/'include/c++/v1'),
              '-isystem',str(sdk/'include'),'-I',str(a.suyu.resolve()/'src'),
              '-std=c++20','-D_GNU_SOURCE=1','-DPS4=1','-D__OPENORBIS__=1','-fsyntax-only',str(src)]
        r=subprocess.run(argv,text=True,capture_output=True,timeout=30)
        (out/(name+'.log')).write_text(r.stdout+r.stderr)
        results.append({'feature':name,'available':r.returncode==0,'returncode':r.returncode})
    report={'scope':'compile_only_CXX20_requirements','sdk_libcpp_version':int(version[1]) if version else None,
            'full_core_build_ready':all(r['available'] for r in results),
            'native_runtime_tested':False,'results':results}
    (out/'cxx-capabilities.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
