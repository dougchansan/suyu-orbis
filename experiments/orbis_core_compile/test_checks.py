# SPDX-License-Identifier: GPL-2.0-or-later
import struct
import tempfile
import unittest
from pathlib import Path
from verify_sources import fingerprint, verify
from report_objects import check_elf

class CompileGateTests(unittest.TestCase):
    def test_fingerprint_stable_and_sensitive(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'a.cpp').write_bytes(b'one');(root/'b.cpp').write_bytes(b'two')
            a=fingerprint(root,['a.cpp','b.cpp'])
            self.assertEqual(a,fingerprint(root,['b.cpp','a.cpp']))
            (root/'a.cpp').write_bytes(b'changed')
            self.assertNotEqual(a,fingerprint(root,['a.cpp','b.cpp']))
            self.assertNotEqual(a,fingerprint(root,['b.cpp']))
    def test_missing_source_fails_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); output=root/'selected.cmake'
            with self.assertRaises(OSError): verify(root,output)
            self.assertFalse(output.exists())
    def test_relocatable_x64_only(self):
        b=bytearray(64);b[:6]=b'\x7fELF\x02\x01';struct.pack_into('<HH',b,16,1,62)
        check_elf(bytes(b))
        for kind,machine in [(2,62),(3,62),(1,183)]:
            struct.pack_into('<HH',b,16,kind,machine)
            with self.assertRaises(ValueError):check_elf(bytes(b))
        for malformed in [b'',b'\x7fELF',b'x'*64]:
            with self.assertRaises(ValueError):check_elf(malformed)
if __name__=='__main__':unittest.main()
