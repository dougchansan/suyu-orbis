#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Reassemble the original fixture and compare/update its checked-in words."""
import argparse
import re
import struct
import subprocess
import tempfile
from pathlib import Path

def text_bytes(elf):
    if elf[:6] != b'\x7fELF\x02\x01':
        raise ValueError('Expected ELF64 little endian object')
    shoff = struct.unpack_from('<Q', elf, 40)[0]
    stride, count, names_idx = struct.unpack_from('<HHH', elf, 58)
    sections = [struct.unpack_from('<IIQQQQIIQQ', elf, shoff+i*stride) for i in range(count)]
    ns=sections[names_idx]
    names=elf[ns[4]:ns[4]+ns[5]]
    if any(s[1] in (4,9) and s[5] for s in sections):
        raise ValueError('Fixture contains unresolved relocations')
    for s in sections:
        if names[s[0]:].split(b'\0')[0]==b'.text':
            return elf[s[4]:s[4]+s[5]]
    raise ValueError('No .text section')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--clang',default='clang')
    p.add_argument('--update',action='store_true')
    a=p.parse_args(); here=Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix='suyu-process-asm-') as tmp:
        obj=Path(tmp)/'program.o'
        subprocess.run([a.clang,'--target=aarch64-none-elf','-c',str(here/'program.S'),'-o',str(obj)],check=True)
        text=text_bytes(obj.read_bytes())
    if len(text)%4: raise ValueError('Unaligned AArch64 code')
    words=struct.unpack('<'+'I'*(len(text)//4),text)
    array=f'inline constexpr std::array<std::uint32_t, {len(words)}> kMain = {{\n'
    for i in range(0,len(words),4):array+='    '+', '.join(f'0x{x:08x}u' for x in words[i:i+4])+',\n'
    array+='};';target=here/'program.h';s=target.read_text()
    if a.update:
        updated,n=re.subn(r'inline constexpr std::array<std::uint32_t, \d+> kMain = \{.*?\};',lambda _:array,s,flags=re.S)
        if n!=1: raise ValueError('Expected one kMain array')
        target.write_text(updated)
    elif array not in s: raise ValueError('program.h disagrees with assembly; update deliberately')
    print(f'Original AArch64 verified: {len(words)} instructions, {len(text)} bytes')
if __name__=='__main__':main()
