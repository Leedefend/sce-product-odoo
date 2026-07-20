#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ops" / "gitee_to_github_mirror.sh"
RULESET_SCRIPT = ROOT / "scripts" / "ops" / "configure_github_mirror_ruleset.sh"
WORKER_UNIT = ROOT / "deploy" / "gitee-ci" / "gitee-ci-worker.service"
CI_INSTALL = ROOT / "deploy" / "gitee-ci" / "install.sh"
OLD = "1" * 40
NEW = "2" * 40


class MirrorGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.source = root / "source.git"
        self.source.mkdir()
        self.key = root / "github_ed25519"
        self.hosts = root / "known_hosts"
        self.key.write_text("test-only-key", encoding="utf-8")
        self.hosts.write_text("test-only-host", encoding="utf-8")
        self.log = root / "git.log"
        fake_git = root / "git"
        fake_git.write_text(
            """#!/bin/sh
set -eu
printf '%s\\n' "$*" >> "$FAKE_GIT_LOG"
case " $* " in
  *" rev-parse refs/heads/main "*) printf '%s\\n' "$FAKE_CANDIDATE" ;;
  *" cat-file -e "*) exit 0 ;;
  *" ls-remote "*) if test -f "$FAKE_PUSHED"; then sha="$(cat "$FAKE_PUSHED")"; else sha="$FAKE_GITHUB"; fi; printf '%s\\trefs/heads/main\\n' "$sha" ;;
  *" merge-base --is-ancestor "*) test "${FAKE_FAST_FORWARD:-1}" = 1 ;;
  *" push "*) printf '%s\\n' "$FAKE_CANDIDATE" > "$FAKE_PUSHED" ;;
  *) echo "unexpected git invocation" >&2; exit 91 ;;
esac
""",
            encoding="utf-8",
        )
        fake_git.chmod(0o700)
        self.environment = {
            **os.environ,
            "PATH": f"{root}:{os.environ['PATH']}",
            "GITEE_MIRROR_SOURCE_REPOSITORY": "leegege/sce-product-odoo",
            "GITEE_MIRROR_SOURCE_REPO": str(self.source),
            "GITHUB_MIRROR_KEY_FILE": str(self.key),
            "GITHUB_MIRROR_KNOWN_HOSTS": str(self.hosts),
            "FAKE_GIT_LOG": str(self.log),
            "FAKE_PUSHED": str(root / "pushed.sha"),
            "FAKE_CANDIDATE": NEW,
            "FAKE_GITHUB": OLD,
            "FAKE_FAST_FORWARD": "1",
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_gate(self, **overrides: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(SCRIPT)],
            env={**self.environment, **overrides},
            text=True,
            capture_output=True,
            check=False,
        )

    def test_fast_forward_pushes_only_exact_sha(self) -> None:
        result = self.run_gate()
        self.assertEqual(0, result.returncode, result.stderr)
        log = self.log.read_text(encoding="utf-8")
        self.assertIn(f"push git@github.com:Leedefend/sce-product-odoo.git {NEW}:refs/heads/main", log)
        self.assertNotIn("--force", log)
        self.assertNotIn("--force-with-lease", log)

    def test_non_fast_forward_is_denied_before_push(self) -> None:
        result = self.run_gate(FAKE_FAST_FORWARD="0")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("BLOCKED non_fast_forward", result.stderr)
        pushes = [line for line in self.log.read_text().splitlines() if " push " in f" {line} "]
        self.assertEqual([], pushes)

    def test_aligned_sha_is_noop(self) -> None:
        result = self.run_gate(FAKE_GITHUB=NEW)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("already_aligned", result.stdout)
        self.assertNotIn(" push ", f" {self.log.read_text()} ")

    def test_repository_allowlist_is_fail_closed(self) -> None:
        result = self.run_gate(GITEE_MIRROR_SOURCE_REPOSITORY="attacker/repo")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("source_repository_not_allowed", result.stderr)
        self.assertFalse(self.log.exists())

    def test_ruleset_uses_deploy_key_without_role_bypass(self) -> None:
        text = RULESET_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('actor_type: "DeployKey"', text)
        self.assertIn("actor_id: null", text)
        self.assertNotIn('actor_type: "RepositoryRole"', text)
        self.assertNotIn('actor_type: "User"', text)
        self.assertLess(
            text.index('select(.enforcement == "active")'),
            text.index('branches/main/protection'),
        )

    def test_worker_sandbox_allows_only_the_credential_free_handoff(self) -> None:
        text = WORKER_UNIT.read_text(encoding="utf-8")
        read_write = next(
            line for line in text.splitlines() if line.startswith("ReadWritePaths=")
        )
        self.assertIn("/var/lib/gitee-mirror/source.git", read_write.split())
        self.assertNotIn("/etc/gitee-mirror", read_write)
        self.assertNotIn("github_ed25519", text)
        install_text = CI_INSTALL.read_text(encoding="utf-8")
        self.assertIn(
            "GITEE_MIRROR_SOURCE_REPO=/var/lib/gitee-mirror/source.git",
            install_text,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
