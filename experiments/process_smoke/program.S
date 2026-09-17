// SPDX-License-Identifier: GPL-2.0-or-later
// Original fixture. main+0 preserves the previous direct-call smoke.
.text
main_entry:
    add x0, x0, #2
    svc #0x1e
    ret
    // Keep the process-only entry at 0x100, but make it an explicit control-flow
    // target so the static exporter emits a lookup boundary at that address.
    b process_entry
.p2align 8
process_entry:
    adr x19, main_entry
    add x19, x19, #3, lsl #12
    mov x20, x1
    adr x30, after_rtld
    adr x9, main_entry
    sub x9, x9, #4, lsl #12
    br x9
 after_rtld:
    add x0, x0, #2
    str x0, [x19, #0]
    mrs x21, tpidrro_el0
    str x21, [x19, #8]
    str x20, [x19, #16]
    mov x9, sp
    str x9, [x19, #104]
    svc #0x1e
    str x0, [x19, #24]
    mov x1, x20
    svc #0x25
    str x0, [x19, #32]
    str x1, [x19, #40]
    mov w1, #0x8001
    movk w1, #0xffff, lsl #16
    svc #0x24
    str x0, [x19, #48]
    str x1, [x19, #56]
    svc #0x10
    str x0, [x19, #64]
    mov x1, #0
    svc #0x25
    str x0, [x19, #72]
    mov x0, #0x2d00
    movk x0, #0x131, lsl #16 // 20,000,000 ns
    svc #0x0b
 after_sleep:
    svc #0x1e
    str x0, [x19, #80]
    mrs x21, tpidrro_el0
    str x21, [x19, #88]
    mov x9, #0x600d
    str x9, [x19, #96]
    svc #0x0a
    b . // Failure/timeout if ExitThread returns.
program_end:
