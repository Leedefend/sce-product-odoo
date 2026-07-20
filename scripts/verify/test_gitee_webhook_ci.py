#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "ci" / "gitee_webhook_ci.py"
SPEC = importlib.util.spec_from_file_location("gitee_webhook_ci", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


SHA = "a" * 40
SECRET = "test-signing-secret"


class Headers(dict[str, str]):
    pass


def push_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "hook_name": "push_hooks",
        "after": SHA,
        "deleted": False,
        "repository": {"full_name": "leegege/sce-product-odoo"},
        "sender": {"login": "leegege"},
    }
    payload.update(overrides)
    return payload


def pr_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "hook_name": "merge_request_hooks",
        "action": "open",
        "number": 7,
        "repository": {"full_name": "leegege/sce-product-odoo"},
        "sender": {"login": "leegege"},
        "pull_request": {
            "number": 7,
            "head": {
                "sha": SHA,
                "repo": {"full_name": "leegege/sce-product-odoo"},
            },
        },
    }
    payload.update(overrides)
    return payload


class GiteeWebhookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        runner = root / "runner.sh"
        runner.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        runner.chmod(0o700)
        self.environment = {
            "GITEE_WEBHOOK_SECRET": SECRET,
            "GITEE_ALLOWED_REPOSITORY": "leegege/sce-product-odoo",
            "GITEE_ALLOWED_SENDER": "leegege",
            "GITEE_CI_RUNNER": str(runner),
            "GITEE_CI_DB": str(root / "jobs.sqlite3"),
            "GITEE_CI_LOG_DIR": str(root / "logs"),
        }
        self.patch = mock.patch.dict(os.environ, self.environment, clear=False)
        self.patch.start()
        self.application = MODULE.Application()

    def tearDown(self) -> None:
        self.patch.stop()
        self.temp.cleanup()

    def headers(self, timestamp: str | None = None, secret: str = SECRET) -> Headers:
        value = timestamp or str(int(time.time() * 1000))
        return Headers(
            {
                "X-Gitee-Timestamp": value,
                "X-Gitee-Token": MODULE.expected_signature(value, secret),
            }
        )

    def accept(self, payload: dict[str, object], headers: Headers | None = None) -> tuple[bool, str]:
        import json

        return self.application.accept(
            json.dumps(payload, separators=(",", ":")).encode(),
            headers or self.headers(),
        )

    def assert_rejected(self, payload: dict[str, object], headers: Headers | None = None) -> None:
        with self.assertRaises(MODULE.Rejected):
            self.accept(payload, headers)

    def test_signed_push_is_queued_once_per_sha(self) -> None:
        now = int(time.time() * 1000)
        inserted, sha = self.accept(push_payload(), self.headers(str(now)))
        self.assertTrue(inserted)
        self.assertEqual(SHA, sha)
        inserted, _sha = self.accept(push_payload(), self.headers(str(now + 1)))
        self.assertFalse(inserted)

    def test_replayed_signed_delivery_is_rejected(self) -> None:
        headers = self.headers()
        self.accept(push_payload(), headers)
        self.assert_rejected(push_payload(after="b" * 40), headers)

    def test_stale_timestamp_is_rejected(self) -> None:
        stale = str(int(time.time() * 1000) - 301_000)
        self.assert_rejected(push_payload(), self.headers(stale))

    def test_invalid_signature_is_rejected(self) -> None:
        self.assert_rejected(push_payload(), self.headers(secret="wrong"))

    def test_api_created_query_signature_is_accepted(self) -> None:
        import json

        timestamp = str(int(time.time() * 1000))
        signature = MODULE.expected_signature(timestamp, SECRET)
        inserted, sha = self.application.accept(
            json.dumps(push_payload(), separators=(",", ":")).encode(),
            Headers(),
            {"timestamp": [timestamp], "sign": [signature]},
        )
        self.assertTrue(inserted)
        self.assertEqual(SHA, sha)

    def test_ambiguous_or_unexpected_query_authentication_is_rejected(self) -> None:
        import json

        timestamp = str(int(time.time() * 1000))
        signature = MODULE.expected_signature(timestamp, SECRET)
        body = json.dumps(push_payload(), separators=(",", ":")).encode()
        rejected_queries = (
            {"timestamp": [timestamp], "sign": [signature, signature]},
            {"timestamp": [timestamp]},
            {"timestamp": [timestamp], "sign": [signature], "branch": ["main"]},
        )
        for query in rejected_queries:
            with self.subTest(query=set(query)):
                with self.assertRaises(MODULE.Rejected):
                    self.application.accept(body, Headers(), query)

    def test_valid_query_signature_precedes_auxiliary_headers(self) -> None:
        import json

        timestamp = str(int(time.time() * 1000))
        signature = MODULE.expected_signature(timestamp, SECRET)
        inserted, sha = self.application.accept(
            json.dumps(push_payload(), separators=(",", ":")).encode(),
            self.headers(str(int(timestamp) - 1), secret="independent-header-secret"),
            {"timestamp": [timestamp], "sign": [signature]},
        )
        self.assertTrue(inserted)
        self.assertEqual(SHA, sha)

    def test_wrong_repository_and_sender_are_rejected(self) -> None:
        self.assert_rejected(push_payload(repository={"full_name": "other/repo"}))
        self.assert_rejected(push_payload(sender={"login": "attacker"}))

    def test_fork_pull_request_is_rejected(self) -> None:
        payload = pr_payload()
        payload["pull_request"] = {
            "number": 7,
            "head": {"sha": SHA, "repo": {"full_name": "attacker/fork"}},
        }
        self.assert_rejected(payload)

    def test_branch_or_command_cannot_replace_sha(self) -> None:
        self.assert_rejected(push_payload(after="main; touch /tmp/owned"))
        self.assert_rejected(push_payload(after="refs/heads/main"))

    def test_closed_pull_request_and_deleted_ref_are_rejected(self) -> None:
        self.assert_rejected(push_payload(deleted=True))
        self.assert_rejected(pr_payload(action="merge"))

    def test_worker_does_not_export_webhook_secret(self) -> None:
        marker = Path(self.temp.name) / "secret-exported"
        runner = Path(self.environment["GITEE_CI_RUNNER"])
        runner.write_text(
            f"#!/bin/sh\nif test -n \"${{GITEE_WEBHOOK_SECRET:-}}\"; then touch '{marker}'; fi\n",
            encoding="utf-8",
        )
        self.accept(push_payload())
        self.assertTrue(self.application.execute_once())
        self.assertFalse(marker.exists())
        log = (Path(self.environment["GITEE_CI_LOG_DIR"]) / f"{SHA}.log").read_text()
        self.assertNotIn(SECRET, log)


if __name__ == "__main__":
    unittest.main(verbosity=2)
