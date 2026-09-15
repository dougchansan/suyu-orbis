// SPDX-License-Identifier: GPL-2.0-or-later
// Original AArch64 diagnostic. ALL displayed pixels are written by this code.
// 0xf000..0xf002 are a PRIVATE TEST protocol, not Horizon SVC implementations.
// Acquire: in x0=phase; out x0=buffer guest VA, x1=width, x2=height.
// Present: x0=phase. Finish: no output. Unexpected calls are fatal in the host.
.text
.global _start
_start:
    cmp x0, #42
    b.ne .Lfail
    mov w20, #0
.Lframe:
    mov x0, x20
    svc #0xf000
    mov x19, x0
    mov w21, w1
    mov w22, w2
    mov w3, #0
.Lrow:
    mov w4, #0
.Lpixel:
    lsr w5, w4, #7
    eor w5, w5, w20
    and w5, w5, #1
    lsl w6, w5, #8
    sub w5, w6, w5          // red: 0 or 255
    lsr w6, w4, #8
    and w6, w6, #1
    lsl w7, w6, #8
    sub w6, w7, w6          // green: 0 or 255
    lsr w7, w3, #7
    and w7, w7, #1
    lsl w8, w7, #8
    sub w7, w8, w7          // blue: 0 or 255
    mov w8, #0xff000000
    orr w8, w8, w5, lsl #16
    orr w8, w8, w6, lsl #8
    orr w8, w8, w7
    str w8, [x19], #4
    add w4, w4, #1
    cmp w4, w21
    b.lo .Lpixel
    add w3, w3, #1
    cmp w3, w22
    b.lo .Lrow
    mov x0, x20
    svc #0xf001
    add w20, w20, #1
    cmp w20, #4
    b.lo .Lframe
    svc #0xf002
.Lstopped:
    b .Lstopped
.Lfail:
    svc #0xf0ff
    b .Lstopped
