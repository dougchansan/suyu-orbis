# SPDX-License-Identifier: GPL-2.0-or-later
"""Negative validation cases; no SDK or emulator required."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
RUN=load("orbis_host_runner","scripts/ci/run_orbis_host_common.py")
PREPARE=load("orbis_host_overlay","scripts/prepare_orbis_common.py")

class ReportTests(unittest.TestCase):
    def setUp(self):
        self.report={"test":"real_suyu_common_host_adaptation","passed":True,
            "orbis_apis":True,"fiber_roundtrips":4096,"cross_thread_hops":32,
            "live_page_allocations":0,"full_core_linked":False,
            "scheduler_dispatch":False,"guest_fastmem":False,"game_tested":False,
            "checks":1185923,"sleep_ns":20000000}
    def test_complete_report(self): RUN.validate(self.report)
    def test_missing_fields(self):
        for key in self.report:
            with self.subTest(key=key):
                r=dict(self.report);del r[key]
                with self.assertRaises(ValueError):RUN.validate(r)
    def test_wrong_scope(self):
        for key in ("full_core_linked","scheduler_dispatch","guest_fastmem","game_tested"):
            with self.subTest(key=key):
                r=dict(self.report);r[key]=True
                with self.assertRaises(ValueError):RUN.validate(r)
    def test_host_result_is_not_native_proof(self):
        self.report["orbis_apis"]=False
        with self.assertRaises(ValueError):RUN.validate(self.report)
    def test_boolean_not_integer(self):
        for key,value in (("passed",1),("live_page_allocations",False),("checks",True),("sleep_ns",True)):
            with self.subTest(key=key):
                r=dict(self.report);r[key]=value
                with self.assertRaises(ValueError):RUN.validate(r)
    def test_incomplete_work(self):
        for key,value in (("fiber_roundtrips",4095),("cross_thread_hops",31),("checks",999999),("live_page_allocations",1)):
            with self.subTest(key=key):
                r=dict(self.report);r[key]=value
                with self.assertRaises(ValueError):RUN.validate(r)
    def test_bad_clock_units(self):
        for value in (-1,20000,9999999,5000000000,20000000.0):
            with self.subTest(value=value):
                self.report["sleep_ns"]=value
                with self.assertRaises(ValueError):RUN.validate(self.report)
    def test_non_object(self):
        for value in (None,True,[],42):
            with self.assertRaises(ValueError):RUN.validate(value)

class SourcePins(unittest.TestCase):
    def test_modified_source_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/"fiber.cpp";file.write_text("not the reviewed source")
            with self.assertRaisesRegex(ValueError,"Unreviewed dependency"):
                PREPARE.check(file,PREPARE.PINS["fiber.cpp"])
    def test_missing_source_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(OSError):
                PREPARE.check(Path(directory)/"missing",PREPARE.PINS["fiber.cpp"])

if __name__=="__main__":unittest.main()
