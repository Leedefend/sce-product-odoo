#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import github_actions_security_guard as guard


PIN = "11bd71901bbe5b1630ceea73d27597364c9af683"


class GitHubActionsSecurityGuardTests(unittest.TestCase):
    def write(self, root: Path, name: str, content: str) -> None:
        target = root / ".github/workflows" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def test_safe_public_guard_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(
                root,
                "public_guard.yml",
                f"""name: public_guard
on:
  pull_request:
permissions:
  contents: read
jobs:
  public_guard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@{PIN}
""",
            )
            self.assertEqual(guard.scan(root), [])

    def test_pull_request_target_and_floating_action_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(
                root,
                "public_guard.yml",
                """name: unsafe
on:
  pull_request_target:
permissions:
  contents: write
jobs:
  public_guard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
""",
            )
            classes = {item.classification for item in guard.scan(root)}
            self.assertIn("PULL_REQUEST_TARGET_FORBIDDEN", classes)
            self.assertIn("ACTION_NOT_PINNED_TO_SHA", classes)
            self.assertIn("MISSING_READ_ONLY_PERMISSIONS", classes)

    def test_self_hosted_fork_boundary_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(
                root,
                "professional_quality_gate.yml",
                """name: unsafe professional
on:
  pull_request:
permissions:
  contents: read
jobs:
  professional_quality_gate:
    runs-on: [self-hosted]
    steps:
      - run: make ci
""",
            )
            classes = {item.classification for item in guard.scan(root)}
            self.assertIn("SELF_HOSTED_REPOSITORY_GATE_MISSING", classes)
            self.assertIn("SELF_HOSTED_ACTOR_GATE_MISSING", classes)
            self.assertIn("SELF_HOSTED_FORK_GATE_MISSING", classes)
            self.assertIn("PROFESSIONAL_TRUST_BOUNDARY_INCOMPLETE", classes)


if __name__ == "__main__":
    unittest.main()
