// SPDX-License-Identifier: GPL-2.0-or-later
// Original diagnostic bootstrap, not Nintendo rtld or a replacement NSO loader.
.text
.global _start
_start:
    mov x0, #40
    add x0, x0, #2
    br x16                  // host supplied relocated main entry
