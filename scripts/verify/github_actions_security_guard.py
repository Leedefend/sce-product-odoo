#!/usr/bin/env python3
"""Enforce the public/self-hosted GitHub Actions trust boundary."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"
PINNED_ACTION = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s@]+)@([0-9a-f]{40})\s*$", re.MULTILINE)
ANY_ACTION = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s]+)\s*$", re.MULTILINE)


@dataclass(frozen=True, order=True)
class Finding:
    rule_id: str
    path: str
    classification: str


def scan(root: Path) -> list[Finding]:
    workflow_dir = root / ".github/workflows"
    findings: set[Finding] = set()
    files = sorted((*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")))
    if not files:
        return [Finding("GA000", ".github/workflows", "NO_WORKFLOWS")]

    for path in files:
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        if not re.search(r"(?m)^permissions:\s*\n\s{2}contents:\s*read\s*$", text):
            findings.add(Finding("GA001", relative, "MISSING_READ_ONLY_PERMISSIONS"))
        if re.search(r"(?m)^\s+[a-z_-]+:\s*write\s*$", lowered):
            findings.add(Finding("GA002", relative, "WRITE_TOKEN_PERMISSION"))
        if "pull_request_target:" in text:
            findings.add(Finding("GA003", relative, "PULL_REQUEST_TARGET_FORBIDDEN"))
        if re.search(r"(?m)^\s*git\s+push(?:\s|$)", text):
            findings.add(Finding("GA004", relative, "WORKFLOW_PUSH_FORBIDDEN"))

        pinned_lines = {match.group(0).strip() for match in PINNED_ACTION.finditer(text)}
        for action_match in ANY_ACTION.finditer(text):
            line = action_match.group(0).strip()
            reference = action_match.group(1)
            if line not in pinned_lines:
                findings.add(Finding("GA005", f"{relative}:{reference}", "ACTION_NOT_PINNED_TO_SHA"))
            elif not reference.startswith(("actions/", "github/")):
                findings.add(Finding("GA006", f"{relative}:{reference}", "UNAPPROVED_ACTION_OWNER"))

        if "self-hosted" in text:
            if "github.repository == 'Leedefend/sce-product-odoo'" not in text:
                findings.add(Finding("GA007", relative, "SELF_HOSTED_REPOSITORY_GATE_MISSING"))
            if "github.actor == 'Leedefend'" not in text:
                findings.add(Finding("GA008", relative, "SELF_HOSTED_ACTOR_GATE_MISSING"))
            if "pull_request:" in text and "github.event.pull_request.head.repo.full_name == github.repository" not in text:
                findings.add(Finding("GA009", relative, "SELF_HOSTED_FORK_GATE_MISSING"))

        if path.name == "public_guard.yml":
            if "runs-on: ubuntu-latest" not in text or "self-hosted" in text:
                findings.add(Finding("GA010", relative, "PUBLIC_GUARD_NOT_GITHUB_HOSTED"))
            if "secrets." in text or "CI_REMOTE_URL" in text:
                findings.add(Finding("GA011", relative, "PUBLIC_GUARD_SECRET_OR_PRIVATE_REMOTE"))

        if path.name == "professional_quality_gate.yml":
            required = (
                "professional_authorization",
                "github.event.pull_request.head.repo.full_name == github.repository",
                "needs: professional_authorization",
                "scripts/ci/self_hosted_runner_cleanup.sh",
            )
            if any(item not in text for item in required):
                findings.add(Finding("GA012", relative, "PROFESSIONAL_TRUST_BOUNDARY_INCOMPLETE"))
    return sorted(findings)


def main() -> int:
    findings = scan(ROOT)
    if findings:
        print("[github_actions_security_guard] FAIL", file=sys.stderr)
        for finding in findings:
            print(
                f"- rule={finding.rule_id} path={finding.path} classification={finding.classification}",
                file=sys.stderr,
            )
        return 1
    print("[github_actions_security_guard] PASS permissions=read fork_self_hosted=denied actions=pinned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
