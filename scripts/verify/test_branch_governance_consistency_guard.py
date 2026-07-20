#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import branch_governance_consistency_guard as guard


class BranchGovernanceConsistencyGuardTests(unittest.TestCase):
    def fixture(self, root: Path, *, make_regex: str = guard.CANONICAL_REGEX) -> None:
        (root / "docs/ops").mkdir(parents=True)
        (root / "make").mkdir()
        (root / "scripts/ops").mkdir(parents=True)
        prefixes = ", ".join(f"`{item}`" for item in guard.CANONICAL_PREFIXES)
        bullets = "\n".join(f"* `{item}`" for item in guard.CANONICAL_PREFIXES)
        workspace = "、".join(f"`{item}`" for item in guard.CANONICAL_PREFIXES)
        (root / "AGENTS.md").write_text(
            f"Canonical allowed write branches: {prefixes}.\n{guard.MARKER}\n",
            encoding="utf-8",
        )
        (root / "docs/ops/codex_execution_allowlist.md").write_text(
            f"{guard.MARKER}\n{bullets}\n",
            encoding="utf-8",
        )
        (root / "docs/ops/codex_workspace_execution_rules.md").write_text(
            f"{guard.MARKER}\n{workspace}\n",
            encoding="utf-8",
        )
        (root / "make/codex.mk").write_text(
            "\n".join(
                (
                    f"CODEX_ALLOWED_WRITE_BRANCH_REGEX := {make_regex}",
                    "CODEX_ALLOWED_WRITE_BRANCH_PREFIXES := " + " ".join(guard.CANONICAL_PREFIXES),
                    "a: ; test $(CODEX_ALLOWED_WRITE_BRANCH_REGEX)",
                    "b: ; test $(CODEX_ALLOWED_WRITE_BRANCH_REGEX)",
                    "c: ; test $(CODEX_ALLOWED_WRITE_BRANCH_REGEX)",
                )
            ),
            encoding="utf-8",
        )
        for relative in guard.SHELL_GUARDS:
            (root / relative).write_text(
                f"CANONICAL_ALLOWED_WRITE_BRANCH_REGEX='{guard.CANONICAL_REGEX}'\n"
                "test $CANONICAL_ALLOWED_WRITE_BRANCH_REGEX\n",
                encoding="utf-8",
            )

    def test_consistent_policy_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            self.assertEqual(guard.validate(root), [])

    def test_make_regex_drift_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root, make_regex="^(feature|fix)/.+")
            self.assertIn(
                "make/codex.mk: CODEX_ALLOWED_WRITE_BRANCH_REGEX diverges",
                guard.validate(root),
            )


if __name__ == "__main__":
    unittest.main()
