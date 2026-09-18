#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Verify pinned Common inputs; create a build-local overlay, never modify upstream."""
from __future__ import annotations
import argparse, hashlib
from pathlib import Path
PINS = {
 'fiber.cpp':'b9be4a257f99331e21b0d2955a557ff8f345259e',
 'fiber.h':'9c46ee4788b914a2f6fb398af209985a53d51ff3',
 'virtual_buffer.h':'26d3aa0710daea47afe5e8aa39223c414d9fb541',
 'host_memory.cpp':'fd06b061512bc0807b6328d81aa718371a48bda6',
 'host_memory.h':'0657a78e32fbe04e0d91132d9df118102526ff9f',
 'steady_clock.h':'dbd0e251313936e08ef060ffadaced0065c2405e',
}
CONTEXT_PINS = {
 'jump_x86_64_sysv_elf_gas.S':'58f0e241d70ff756a2434a35352b05a881c3c901',
 'make_x86_64_sysv_elf_gas.S':'4294398a2edc2d0805640f5a54698e2812b54dda',
}
def check(path:Path,expected:str)->None:
    data=path.read_bytes()
    got=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    if got!=expected: raise ValueError(f'Unreviewed dependency: {path} ({got})')
def prepare(source:Path,context:Path,output:Path)->None:
    for name,digest in PINS.items(): check(source/'src/common'/name,digest)
    for name,digest in CONTEXT_PINS.items(): check(context/'src/asm'/name,digest)
    directory=output/'common'; directory.mkdir(parents=True,exist_ok=True)
    # __FreeBSD__ is defined by Clang's target even when compiling for Orbis.
    # The host OS branch must not take precedence over the specific platform.
    memory=(source/'src/common/host_memory.cpp').read_text()
    memory=memory.replace('#elif defined(__FreeBSD__)\n','#elif defined(__FreeBSD__) && !defined(__OPENORBIS__)\n',1)
    (directory/'host_memory.cpp').write_text(memory)
    header=(source/'src/common/virtual_buffer.h').read_text()
    old="""    VirtualBuffer& operator=(VirtualBuffer&& other) noexcept {
        alloc_size = std::exchange(other.alloc_size, 0);
        base_ptr = std::exchange(other.base_ptr, nullptr);
        return *this;
    }"""
    new="""    // Orbis adaptation: release the previous owner and preserve self-move.
    VirtualBuffer& operator=(VirtualBuffer&& other) noexcept {
        if (this != &other) {
            FreeMemoryPages(base_ptr, alloc_size);
            alloc_size = std::exchange(other.alloc_size, 0);
            base_ptr = std::exchange(other.base_ptr, nullptr);
        }
        return *this;
    }"""
    if old not in header: raise ValueError('VirtualBuffer move-assignment context changed')
    (directory/'virtual_buffer.h').write_text(header.replace(old,new,1))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--suyu',type=Path,required=True)
    p.add_argument('--context',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    try: prepare(a.suyu,a.context,a.output)
    except (OSError,ValueError) as exc: p.exit(1,f'{exc}\n')
