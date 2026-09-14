// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "suyu_orbis/registry.h"
namespace SuyuOrbis {
// Invoke once before loading the process, with no guest threads running.
SoResult AttachStaticBundle();
// Invoke only after the process has stopped and all guest threads have joined.
void DetachStaticBundle();
}
