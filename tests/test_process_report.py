# SPDX-License-Identifier: GPL-2.0-or-later
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('process_runner', ROOT / 'scripts/run_process_smoke.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def good():
    svcs = runner.EXPECTED_SVCS
    return {
        'test': runner.TEST, 'passed': True, 'scheduler_dispatch': True,
        'normal_svc_dispatch': True, 'same_cpu_instance': True,
        'pending_svc_cleared_on_resume': True, 'guest_memory_verified': True,
        'thread_exited': True, 'observed_waiting': True, 'clean_shutdown': True,
        'jit_available': False, 'real_title_loader': False, 'orbis_execution': False,
        'game_tested': False, 'renderer': 'none', 'jit_transitions': 0,
        'static_blocks': 8, 'svcs': svcs, 'tls': 0x40000, 'thread_id': 13,
        'process_id': 81, 'thread_handle': 0x8001,
        'sleep_resume_interval_ns': 20_000_000,
        'guest_values': [42, 0x40000, 0x8001, 100, 0, 13, 0, 81, 0, 58369,
                         200, 0x40000, 0x600d, 0x50000],
        'trace': [
            {'pc': i * 4, 'resume_pc': i * 4 + 4, 'pending_svc': svc,
             'thread_id': 13, 'process_id': 81, 'core': 0}
            for i, svc in enumerate(svcs)
        ],
    }


class ReportTests(unittest.TestCase):
    def test_accepts_complete_report(self):
        runner.validate_report(good())

    def test_rejects_unproved_flag(self):
        for key in ('scheduler_dispatch', 'normal_svc_dispatch', 'same_cpu_instance',
                    'observed_waiting', 'clean_shutdown'):
            report = good()
            report[key] = False
            with self.subTest(key=key), self.assertRaises(ValueError):
                runner.validate_report(report)

    def test_rejects_fallback(self):
        report = good()
        report['jit_transitions'] = 1
        with self.assertRaises(ValueError):
            runner.validate_report(report)

    def test_rejects_identity_mismatch(self):
        report = good()
        report['guest_values'][5] += 1
        with self.assertRaises(ValueError):
            runner.validate_report(report)

    def test_rejects_fake_success_error(self):
        report = good()
        report['guest_values'][9] = 0
        with self.assertRaises(ValueError):
            runner.validate_report(report)

    def test_rejects_missing_trace(self):
        report = good()
        report['trace'] = []
        with self.assertRaises(ValueError):
            runner.validate_report(report)

    def test_rejects_different_trace(self):
        report = good()
        report['trace'][0]['pending_svc'] = 123
        with self.assertRaises(ValueError):
            runner.validate_report(report)

    def test_rejects_game_or_orbis_claim(self):
        for key in ('real_title_loader', 'orbis_execution', 'game_tested'):
            report = good()
            report[key] = True
            with self.subTest(key=key), self.assertRaises(ValueError):
                runner.validate_report(report)


if __name__ == '__main__':
    unittest.main()
