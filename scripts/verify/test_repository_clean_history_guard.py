#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import repository_clean_history_guard as guard


class RepositoryCleanHistoryGuardTests(unittest.TestCase):
    def test_policy_requires_expected_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text('{"schema_version":"wrong"}', encoding="utf-8")
            with mock.patch.object(guard, "POLICY_PATH", path):
                with self.assertRaises(ValueError):
                    guard.policy()

    def test_reachable_objects_parses_blob_metadata(self) -> None:
        batch = "a" * 40 + " blob 12 path/to/file.txt\n"
        with (
            mock.patch.object(guard, "git", return_value="a" * 40 + " path/to/file.txt\n"),
            mock.patch.object(guard.subprocess, "run") as run,
        ):
            run.return_value.stdout = batch
            self.assertEqual(
                guard.reachable_objects(),
                [("a" * 40, "blob", 12, "path/to/file.txt")],
            )

    def test_blob_bytes_never_decodes_or_logs_content(self) -> None:
        with mock.patch.object(guard.subprocess, "run") as run:
            run.return_value.stdout = b"opaque"
            self.assertEqual(guard.blob_bytes("a" * 40), b"opaque")
        self.assertEqual(run.call_args.args[0][:3], ["git", "cat-file", "blob"])

    def test_runtime_env_files_are_rejected_but_examples_are_allowed(self) -> None:
        self.assertTrue(guard.is_runtime_env_path(".env.prod"))
        self.assertTrue(guard.is_runtime_env_path("frontend/.env.production"))
        self.assertFalse(guard.is_runtime_env_path(".env.example"))
        self.assertFalse(guard.is_runtime_env_path("frontend/.env.production.example"))

    def test_local_hygiene_reports_reflog_only_and_unreachable_objects(self) -> None:
        reachable = "a" * 40
        reflog_only = "b" * 40
        unreachable = "c" * 40

        def fake_git(*args: str, check: bool = True) -> str:
            del check
            if args == ("rev-list", "--all"):
                return f"{reachable}\n"
            if args == ("reflog", "--all", "--format=%H"):
                return f"{reachable}\n{reflog_only}\n"
            if args == ("fsck", "--full", "--unreachable", "--no-reflogs"):
                return f"unreachable blob {unreachable}\n"
            raise AssertionError(args)

        with mock.patch.object(guard, "git", side_effect=fake_git):
            errors, reflog_count, unreachable_count = guard.local_hygiene_errors()
        self.assertEqual(reflog_count, 1)
        self.assertEqual(unreachable_count, 1)
        self.assertIn(("RH009", f"object:{reflog_only[:12]}", "REFLOG_ONLY_COMMIT"), errors)
        self.assertIn(("RH010", f"blob:{unreachable[:12]}", "UNREACHABLE_OBJECT"), errors)

    def test_remote_errors_accepts_single_approved_clone_remote(self) -> None:
        allowed = {
            "origin": "https://example.invalid/new-product.git",
            "mirror": "ssh://example.invalid/new-product.git",
        }

        def fake_git(*args: str, check: bool = True) -> str:
            del check
            if args == ("remote",):
                return "origin\n"
            if args == ("remote", "get-url", "origin"):
                return f"{allowed['origin']}\n"
            raise AssertionError(args)

        with mock.patch.object(guard, "git", side_effect=fake_git):
            self.assertEqual(guard.remote_errors(allowed), set())

    def test_remote_errors_accepts_approved_origin_alias(self) -> None:
        allowed = {
            "origin": [
                "https://example.invalid/new-product.git",
                "ssh://mirror.invalid/new-product.git",
            ],
        }

        def fake_git(*args: str, check: bool = True) -> str:
            del check
            if args == ("remote",):
                return "origin\n"
            if args == ("remote", "get-url", "origin"):
                return "ssh://mirror.invalid/new-product.git\n"
            raise AssertionError(args)

        with mock.patch.object(guard, "git", side_effect=fake_git):
            self.assertEqual(guard.remote_errors(allowed), set())

    def test_remote_errors_rejects_unapproved_remote(self) -> None:
        allowed = {"origin": "https://example.invalid/new-product.git"}

        def fake_git(*args: str, check: bool = True) -> str:
            del check
            if args == ("remote",):
                return "legacy\n"
            if args == ("remote", "get-url", "legacy"):
                return "https://example.invalid/old-product.git\n"
            raise AssertionError(args)

        with mock.patch.object(guard, "git", side_effect=fake_git):
            self.assertEqual(
                guard.remote_errors(allowed),
                {
                    ("RH002", "<repository>", "REMOTE_SET"),
                    ("RH003", "remote:legacy", "OLD_OR_UNEXPECTED_REMOTE"),
                },
            )


if __name__ == "__main__":
    unittest.main()
