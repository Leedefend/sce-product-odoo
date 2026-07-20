#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import repository_clean_history_guard as guard


SCRIPT = Path(__file__).with_name("repository_clean_history_guard.py")


class RepositoryCleanHistoryGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.git("init", "-b", "main")
        self.git("remote", "add", "origin", "https://example.invalid/new-product.git")
        self.policy = self.root / "policy.json"
        self.policy.write_text(
            json.dumps(
                {
                    "schema_version": "sce.repository_clean_history_policy.v1",
                    "allowed_remotes": {"origin": "https://example.invalid/new-product.git"},
                    "forbidden_repository_tokens": ["old-private-repository"],
                    "forbidden_commit_objects": [],
                    "forbidden_path_prefixes": ["filestore/", "attachments/", "artifacts/migration/"],
                    "forbidden_archive_suffixes": [".dump", ".tar", ".zip", ".zst"],
                    "maximum_blob_bytes": 1024 * 1024,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        self.write("README.md", "clean product\n")
        self.commit("initial clean root")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def git(
        self,
        *args: str,
        input_text: str | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            text=True,
            encoding="utf-8",
            errors="replace",
            input=input_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=check,
        )

    def write(self, relative: str, content: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def commit(self, message: str) -> str:
        self.git("add", "-A")
        self.git(
            "-c",
            "user.name=Guard Test",
            "-c",
            "user.email=guard@example.invalid",
            "commit",
            "-m",
            message,
        )
        return self.git("rev-parse", "HEAD").stdout.strip()

    def run_guard(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(SCRIPT), "--root", str(self.root), "--policy", str(self.policy), *extra],
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_clean_reachable_history_passes(self) -> None:
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("reachable_scan=all", result.stdout)

    def test_policy_requires_expected_schema(self) -> None:
        self.policy.write_text('{"schema_version":"wrong"}\n', encoding="utf-8")
        with self.assertRaises(ValueError):
            guard.load_policy(self.policy)

    def test_reachable_customer_module_is_rejected(self) -> None:
        self.write("addons/sce_customer_acme/__manifest__.py", "{}\n")
        self.commit("add forbidden customer module")
        result = self.run_guard()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CUSTOMER_MODULE_PATH", result.stderr)

    def test_current_tree_clean_but_history_dirty_is_rejected(self) -> None:
        self.write(".env.prod", "DB_PASSWORD=not-a-real-password\n")
        self.commit("add runtime environment")
        (self.root / ".env.prod").unlink()
        self.commit("clean current tree")
        result = self.run_guard()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TRACKED_RUNTIME_ENV_FILE", result.stderr)

    def test_tag_pointing_to_sensitive_commit_is_rejected(self) -> None:
        self.write(".env.prod", "DB_PASSWORD=not-a-real-password\n")
        sensitive_commit = self.commit("sensitive tagged commit")
        (self.root / ".env.prod").unlink()
        self.commit("remove runtime environment")
        self.git("tag", "legacy-sensitive", sensitive_commit)
        result = self.run_guard("--local-hygiene")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TAG_REF_PRESENT", result.stderr)
        self.assertIn("TRACKED_RUNTIME_ENV_FILE", result.stderr)

    def test_remote_tracking_ref_to_old_object_is_rejected(self) -> None:
        self.write(".env.prod", "DB_PASSWORD=not-a-real-password\n")
        sensitive_commit = self.commit("old remote commit")
        (self.root / ".env.prod").unlink()
        self.commit("remove old remote content")
        self.git("update-ref", "refs/remotes/origin/legacy", sensitive_commit)
        result = self.run_guard("--local-hygiene")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("STALE_REMOTE_TRACKING_REF", result.stderr)

    def test_reflog_only_sensitive_blob_is_rejected_without_value_disclosure(self) -> None:
        secret_value = "ghp_" + "A" * 36
        self.write("temporary-secret.txt", f"TOKEN={secret_value}\n")
        self.commit("temporary sensitive commit")
        self.git("reset", "--hard", "HEAD^")
        result = self.run_guard("--local-hygiene")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("REFLOG_ONLY_COMMIT", result.stderr)
        self.assertIn("SECRET_MATERIAL", result.stderr)
        self.assertNotIn(secret_value, result.stdout + result.stderr)
        self.assertIn("sensitive_values_recorded=false", result.stderr)

    def test_unreachable_env_prod_is_rejected(self) -> None:
        blob_id = self.git("hash-object", "-w", "--stdin", input_text="DB_PASSWORD=ephemeral\n").stdout.strip()
        tree_id = self.git(
            "mktree",
            input_text=f"100644 blob {blob_id}\t.env.prod\n",
        ).stdout.strip()
        self.git(
            "-c",
            "user.name=Guard Test",
            "-c",
            "user.email=guard@example.invalid",
            "commit-tree",
            tree_id,
            "-m",
            "unreachable environment",
        )
        result = self.run_guard("--local-hygiene")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("UNREACHABLE_OBJECT", result.stderr)
        self.assertIn("TRACKED_RUNTIME_ENV_FILE", result.stderr)


if __name__ == "__main__":
    unittest.main()
