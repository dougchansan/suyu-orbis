# SPDX-License-Identifier: GPL-2.0-or-later
import unittest
from run_probe import EXPECTED, validate

class ReportTests(unittest.TestCase):
    def test_valid(self):
        validate(dict(EXPECTED, checks=50))
    def test_reject_each_missing_field(self):
        for field in EXPECTED:
            with self.subTest(field=field):
                r=dict(EXPECTED,checks=50); del r[field]
                with self.assertRaises(ValueError): validate(r)
    def test_reject_wrong_types_and_counts(self):
        for k,v in [('passed',1),('checks',True),('checks',0),('libcpp_version',11000),
                    ('tls_destructors',1),('atomic_ref_total',4095),('full_core_linked',True)]:
            with self.subTest(field=k):
                r=dict(EXPECTED,checks=50);r[k]=v
                with self.assertRaises(ValueError):validate(r)
    def test_not_an_object(self):
        for v in (None,[],True,'passed'):
            with self.assertRaises(ValueError):validate(v)

if __name__=='__main__':unittest.main()
