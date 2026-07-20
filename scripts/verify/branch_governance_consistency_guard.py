#!/usr/bin/env python3
"""Fail when documented and executable write-branch policy diverges."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CANONICAL_REGEX = "^(feature|fix|refactor|audit|release|codex)/.+"
CANONICAL_PREFIXES = (
    "feature/*",
    "fix/*",
    "refactor/*",
    "audit/*",
    "release/*",
    "codex/*",
)
MARKER = f"CANONICAL_ALLOWED_WRITE_BRANCH_REGEX={CANONICAL_REGEX}"

DOCUMENTS = (
    Path("AGENTS.md"),
    Path("docs/ops/codex_execution_allowlist.md"),
    Path("docs/ops/codex_workspace_execution_rules.md"),
)
MAKEFILE = Path("make/codex.mk")
SHELL_GUARDS = (
    Path("scripts/ops/git_safe_push.sh"),
    Path("scripts/ops/branch_cleanup_safe.sh"),
)


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    for relative in DOCUMENTS:
        path = root / relative
        text = path.read_text(encoding="utf-8")
        if text.count(MARKER) != 1:
            errors.append(f"{relative}: canonical regex marker must appear exactly once")

    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    expected_agents = "Canonical allowed write branches: " + ", ".join(
        f"`{prefix}`" for prefix in CANONICAL_PREFIXES
    ) + "."
    if expected_agents not in agents:
        errors.append("AGENTS.md: canonical human-readable prefix list is missing or reordered")

    allowlist = (root / DOCUMENTS[1]).read_text(encoding="utf-8")
    expected_bullets = "\n".join(f"* `{prefix}`" for prefix in CANONICAL_PREFIXES)
    if expected_bullets not in allowlist:
        errors.append("codex_execution_allowlist.md: allowed branch bullet list diverges")

    workspace_rules = (root / DOCUMENTS[2]).read_text(encoding="utf-8")
    expected_workspace = "、".join(f"`{prefix}`" for prefix in CANONICAL_PREFIXES)
    if expected_workspace not in workspace_rules:
        errors.append("codex_workspace_execution_rules.md: allowed branch list diverges")

    make_text = (root / MAKEFILE).read_text(encoding="utf-8")
    regex_match = re.search(r"^CODEX_ALLOWED_WRITE_BRANCH_REGEX\s*:=\s*(\S+)\s*$", make_text, re.MULTILINE)
    if not regex_match or regex_match.group(1) != CANONICAL_REGEX:
        errors.append("make/codex.mk: CODEX_ALLOWED_WRITE_BRANCH_REGEX diverges")
    prefix_match = re.search(r"^CODEX_ALLOWED_WRITE_BRANCH_PREFIXES\s*:=\s*(.+?)\s*$", make_text, re.MULTILINE)
    if not prefix_match or tuple(prefix_match.group(1).split()) != CANONICAL_PREFIXES:
        errors.append("make/codex.mk: CODEX_ALLOWED_WRITE_BRANCH_PREFIXES diverges")
    if make_text.count("$(CODEX_ALLOWED_WRITE_BRANCH_REGEX)") < 3:
        errors.append("make/codex.mk: branch-changing targets do not reuse the canonical regex")

    for relative in SHELL_GUARDS:
        shell_text = (root / relative).read_text(encoding="utf-8")
        expected = f"CANONICAL_ALLOWED_WRITE_BRANCH_REGEX='{CANONICAL_REGEX}'"
        if expected not in shell_text:
            errors.append(f"{relative}: canonical shell regex diverges")
        if "$CANONICAL_ALLOWED_WRITE_BRANCH_REGEX" not in shell_text:
            errors.append(f"{relative}: canonical shell regex is not enforced")

    combined = "\n".join((root / path).read_text(encoding="utf-8") for path in (*DOCUMENTS, MAKEFILE))
    for retired in ("feat/*", "experiment/*"):
        if retired in combined:
            errors.append(f"retired branch prefix remains: {retired}")
    return errors


def main() -> int:
    errors = validate(ROOT)
    if errors:
        print("[branch_governance_consistency_guard] FAIL", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(
        "[branch_governance_consistency_guard] PASS "
        f"regex={CANONICAL_REGEX} documents={len(DOCUMENTS)} makefile=1 shell_guards={len(SHELL_GUARDS)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
