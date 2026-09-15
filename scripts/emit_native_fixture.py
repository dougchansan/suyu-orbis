#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Assemble original AArch64 then run the locked Suyu exporter, without guest assets."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import struct
import subprocess
from pathlib import Path
from fetch_upstream import verify
from import_modules import import_modules
ROOT=Path(__file__).resolve().parents[1]

def extract_text(path: Path) -> bytes:
    data=path.read_bytes()
    if len(data)<64 or data[:6]!=b'\x7fELF\x02\x01':
        raise ValueError('Expected ELF64 little-endian relocatable assembler output')
    if struct.unpack_from('<HH',data,16)!=(1,183):
        raise ValueError('Expected AArch64 ET_REL object')
    offset=struct.unpack_from('<Q',data,40)[0]
    entry_size,count,names_index=struct.unpack_from('<HHH',data,58)
    if entry_size!=64 or names_index>=count or offset+count*entry_size>len(data):
        raise ValueError('Invalid ELF section headers')
    sections=[struct.unpack_from('<IIQQQQIIQQ',data,offset+i*entry_size) for i in range(count)]
    names=sections[names_index]
    strings=data[names[4]:names[4]+names[5]]
    text=None
    for section in sections:
        if section[1] in (4,9) and section[5]:
            raise ValueError('Assembly must contain no unresolved relocations')
        start,size=section[4],section[5]
        if section[1]!=8 and start+size>len(data): raise ValueError('Invalid section extent')
        name=strings[section[0]:].split(b'\0',1)[0]
        if name==b'.text': text=data[start:start+size]
    if not text or len(text)%4: raise ValueError('Missing/unaligned .text')
    return text

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--suyu',type=Path,default=ROOT/'vendor/suyu')
    p.add_argument('--work',type=Path,default=ROOT/'build/native-fixture')
    p.add_argument('--cc',default='clang')
    p.add_argument('--cxx',default='clang++')
    args=p.parse_args()
    try:
        verify(args.suyu)
        work=args.work.resolve()
        if work.exists() and any(work.iterdir()): raise ValueError('Choose an empty --work directory')
        work.mkdir(parents=True,exist_ok=True)
        texts={}
        for name in ('rtld','main'):
            source=ROOT/'experiments/orbis_aot_render'/f'{name}.S'
            obj=work/f'{name}.o'
            subprocess.run([args.cc,'--target=aarch64-none-elf','-c',str(source),'-o',str(obj)],check=True)
            text=extract_text(obj)
            (work/f'{name}.bin').write_bytes(text)
            texts[name]={'instructions':len(text)//4,'text_sha256':hashlib.sha256(text).hexdigest(),
                         'assembly_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
        emitter=work/'emit'
        subprocess.run([args.cxx,'-std=c++20','-O1','-I',str(args.suyu/'src/core/recompiler'),
                        str(ROOT/'experiments/orbis_aot_render/emit.cpp'),'-o',str(emitter)],check=True)
        subprocess.run([str(emitter),str(work/'rtld.bin'),str(work/'main.bin'),str(work/'exefs')],check=True)
        import_modules(work/'exefs',work/'bundle')
        (work/'fixture.json').write_text(json.dumps({'source':'original_assembly','modules':texts,
            'horizon_service_emulation':False,'svc_protocol':'private_test_only'},indent=2)+'\n')
        return 0
    except (OSError,ValueError,subprocess.CalledProcessError) as error:
        p.exit(1,f'Native fixture error: {error}\n')
if __name__=='__main__': raise SystemExit(main())
