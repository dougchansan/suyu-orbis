# SPDX-License-Identifier: GPL-2.0-or-later
"""Compile the exact injected remove adapter and test syscall error forwarding."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from prepare_filesystem import CHANGES

class RemoveAdapterTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('c++'), 'host C++ compiler required')
    def test_directory_errors_and_passthrough(self):
        patches = CHANGES['libcxx/src/filesystem/posix_compat.h'][1]
        replacement = next(new for old, new in patches if old == 'using ::remove;\n')
        start = replacement.index('inline int remove(')
        end = replacement.index('#  else', start)
        function = replacement[start:end].replace('::unlink(', 'fake_unlink(').replace('::rmdir(', 'fake_rmdir(')
        code = '''#include <cerrno>
int unlink_rc, unlink_errno, rmdir_rc, rmdir_errno, unlink_calls, rmdir_calls;
int fake_unlink(const char*) { ++unlink_calls; errno=unlink_errno; return unlink_rc; }
int fake_rmdir(const char*) { ++rmdir_calls; errno=rmdir_errno; return rmdir_rc; }
namespace candidate {
''' + function + '''}
int main() {
 const int errors[] = {EPERM,EISDIR,EACCES,ENOENT,EIO};
 for (int e: errors) {
  unlink_rc=-1; unlink_errno=e; rmdir_rc=0; rmdir_errno=0;
  unlink_calls=rmdir_calls=0;
  int r=candidate::remove("fixture"); bool retry=e==EPERM || e==EISDIR;
  if (r!=(retry?0:-1) || unlink_calls!=1 || rmdir_calls!=(retry?1:0)) return 1;
  if (!retry && errno!=e) return 2;
 }
 unlink_rc=0; unlink_calls=rmdir_calls=0;
 if (candidate::remove("file-or-symlink") || unlink_calls!=1 || rmdir_calls) return 3;
 for (int e: {ENOTEMPTY,EACCES,ENOTDIR}) {
  unlink_rc=-1;unlink_errno=EPERM;rmdir_rc=-1;rmdir_errno=e;
  if (candidate::remove("unremovable")!=-1 || errno!=e) return 4;
 }
}
'''
        code='#include <initializer_list>\n'+code
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'probe.cpp'; exe=Path(d)/'probe'; source.write_text(code)
            subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror',str(source),'-o',str(exe)],check=True,capture_output=True)
            subprocess.run([str(exe)],check=True,timeout=10)

if __name__=='__main__': unittest.main()
