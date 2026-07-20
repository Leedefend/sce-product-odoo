#!/usr/bin/env python3
"""Fail-closed personal-data scanner for the worktree and all reachable blobs.

Diagnostics intentionally contain only rule IDs, repository paths, short blob
prefixes, and classifications. Matching values are never printed or persisted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEXT_SUFFIXES = {
    ".cjs", ".conf", ".csv", ".css", ".env", ".html", ".ini", ".js",
    ".json", ".md", ".mjs", ".properties", ".py", ".scss", ".sh",
    ".sql", ".toml", ".ts", ".tsx", ".txt", ".vue", ".xml", ".yaml", ".yml",
}
TEXT_NAMES = {"Dockerfile", "Makefile", ".dockerignore", ".gitignore"}
MAX_TEXT_BLOB_BYTES = 8 * 1024 * 1024

RULES: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "PD001",
        "GOVERNMENT_ID_PATTERN",
        re.compile(r"(?<!\d)[1-9]\d{5}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[0-9Xx](?!\d)"),
    ),
    (
        "PD002",
        "MOBILE_PHONE_PATTERN",
        re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    ),
    (
        "PD003",
        "BANK_ACCOUNT_PATTERN",
        re.compile(
            r"(?i)(?:account(?:_no|_number)?|bank(?:_account)?|card(?:_no|_number)?|"
            r"receiving_account_no|payer_account|payee_account|银行(?:卡|账号)|账号)"
            r"[^\d\n]{0,80}(?P<value>\d{12,24})(?!\d)"
        ),
    ),
)


@dataclass(frozen=True, order=True)
class Finding:
    rule_id: str
    path: str
    blob_prefix: str
    classification: str


def git(*args: str, input_text: str | None = None, check: bool = True) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    ).stdout


def is_text_path(path: str) -> bool:
    item = Path(path)
    return item.suffix.lower() in TEXT_SUFFIXES or item.name in TEXT_NAMES or item.name.startswith(".env")


def git_blob_id(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def decode_text(data: bytes) -> str | None:
    if len(data) > MAX_TEXT_BLOB_BYTES or b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def scan_text(text: str, path: str, blob_id: str) -> list[Finding]:
    findings: list[Finding] = []
    for rule_id, classification, pattern in RULES:
        if pattern.search(text):
            findings.append(Finding(rule_id, path, blob_id[:12], classification))
    return findings


def worktree_findings() -> list[Finding]:
    if (ROOT / ".git").exists():
        paths = git("ls-files", "--cached", "--others", "--exclude-standard").splitlines()
    else:
        excluded = {".git", "node_modules", "__pycache__", "artifacts"}
        paths = [
            str(path.relative_to(ROOT))
            for path in ROOT.rglob("*")
            if path.is_file() and not excluded.intersection(path.parts)
        ]
    findings: list[Finding] = []
    for relative in paths:
        if not is_text_path(relative):
            continue
        path = ROOT / relative
        try:
            data = path.read_bytes()
        except OSError:
            continue
        text = decode_text(data)
        if text is not None:
            findings.extend(scan_text(text, relative, git_blob_id(data)))
    return findings


def history_objects() -> list[tuple[str, str, int]]:
    if not (ROOT / ".git").exists():
        return []
    rev_list = git("rev-list", "--objects", "--all", check=False)
    if not rev_list.strip():
        return []
    result = subprocess.run(
        ["git", "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize) %(rest)"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        input=rev_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout
    objects: list[tuple[str, str, int]] = []
    for line in result.splitlines():
        parts = line.split(" ", 3)
        if len(parts) == 4 and parts[1] == "blob" and parts[2].isdigit() and parts[3]:
            objects.append((parts[0], parts[3], int(parts[2])))
    return objects


def read_blob(blob_id: str) -> bytes:
    return subprocess.run(
        ["git", "cat-file", "blob", blob_id],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout


def history_findings() -> list[Finding]:
    by_blob: dict[str, list[str]] = {}
    for blob_id, path, size in history_objects():
        if size <= MAX_TEXT_BLOB_BYTES and is_text_path(path):
            by_blob.setdefault(blob_id, []).append(path)
    findings: list[Finding] = []
    for blob_id, paths in by_blob.items():
        text = decode_text(read_blob(blob_id))
        if text is None:
            continue
        for path in sorted(set(paths)):
            findings.extend(scan_text(text, path, blob_id))
    return findings


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=("worktree", "history", "all"), default="all")
    parser.add_argument("--report", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    findings: set[Finding] = set()
    if args.scope in {"worktree", "all"}:
        findings.update(worktree_findings())
    if args.scope in {"history", "all"}:
        findings.update(history_findings())
    ordered = sorted(findings)
    report = {
        "schema_version": 1,
        "scope": args.scope,
        "confirmed_matches": len(ordered),
        "matches": [asdict(item) for item in ordered],
        "personal_data_values_recorded": False,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if ordered:
        print("[personal_data_scan] FAIL", file=sys.stderr)
        for item in ordered:
            print(
                f"- rule={item.rule_id} path={item.path} blob={item.blob_prefix} classification={item.classification}",
                file=sys.stderr,
            )
        print("personal_data_values_recorded=false", file=sys.stderr)
        return 1
    print("[personal_data_scan] PASS confirmed_matches=0 values_recorded=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
