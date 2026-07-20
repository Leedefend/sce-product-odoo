#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import personal_data_scan


class PersonalDataScanTests(unittest.TestCase):
    def test_rules_report_metadata_without_values(self) -> None:
        samples = (
            ("PD001", "110105" + "19491231" + "002X"),
            ("PD002", "139" + "1234" + "5678"),
            ("PD003", "bank_account=" + "622202" + "1234567890123"),
        )
        for expected_rule, value in samples:
            findings = personal_data_scan.scan_text(value, "fixture.txt", "a" * 40)
            self.assertIn(expected_rule, [item.rule_id for item in findings])
            self.assertNotIn(value, repr(findings))

    def test_clean_placeholders_pass(self) -> None:
        text = "id=DEMO-ID-001 phone=DEMO-PHONE-001 bank_account=DEMO-ACCOUNT-001"
        self.assertEqual(personal_data_scan.scan_text(text, "fixture.txt", "b" * 40), [])

    def test_main_never_prints_match_values(self) -> None:
        sensitive = "139" + "1234" + "5678"
        finding = personal_data_scan.scan_text(sensitive, "fixture.txt", "c" * 40)[0]
        stderr = io.StringIO()
        with (
            mock.patch.object(personal_data_scan, "worktree_findings", return_value=[finding]),
            mock.patch.object(personal_data_scan, "history_findings", return_value=[]),
            contextlib.redirect_stderr(stderr),
        ):
            self.assertEqual(personal_data_scan.main(["--scope", "all"]), 1)
        self.assertNotIn(sensitive, stderr.getvalue())
        self.assertIn("rule=PD002", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
