#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import clean_product_tree_guard as guard


class CleanProductTreeGuardTests(unittest.TestCase):
    def test_placeholder_only_tree_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env.example").write_text(
                "DB_PASSWORD=<SET_DATABASE_PASSWORD>\nJWT_SECRET=<SET_JWT_SECRET>\n",
                encoding="utf-8",
            )
            report = guard.scan(root)
            self.assertEqual(report["status"], "PASS")

    def test_runtime_env_and_literal_secret_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env.prod").write_text("DB_PASSWORD=not-public\n", encoding="utf-8")
            (root / ".env.example").write_text("JWT_SECRET=literal\n", encoding="utf-8")
            report = guard.scan(root)
            self.assertEqual(report["status"], "FAIL")
            self.assertEqual(report["counts"]["TRACKED_RUNTIME_ENV_FILES"], 1)
            self.assertEqual(report["counts"]["LITERAL_TOKEN_DEFAULTS"], 1)


if __name__ == "__main__":
    unittest.main()
