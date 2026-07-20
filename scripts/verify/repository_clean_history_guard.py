#!/usr/bin/env python3
"""Verify that this repository descends from one clean root and no old repo."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "config/security/repository_clean_history_policy.v1.json"


def git(*args: str, check: bool = True) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    ).stdout


def policy() -> dict[str, object]:
    payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "sce.repository_clean_history_policy.v1":
        raise ValueError("unsupported clean-history policy")
    return payload


def reachable_objects() -> list[tuple[str, str, int, str]]:
    rev_list = git("rev-list", "--objects", "--all", check=False)
    if not rev_list.strip():
        return []
    output = subprocess.run(
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
    rows: list[tuple[str, str, int, str]] = []
    for line in output.splitlines():
        parts = line.split(" ", 3)
        if len(parts) == 4 and parts[2].isdigit():
            rows.append((parts[0], parts[1], int(parts[2]), parts[3]))
    return rows


def blob_bytes(object_id: str) -> bytes:
    return subprocess.run(
        ["git", "cat-file", "blob", object_id],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout


def remote_errors(allowed_remotes: dict[str, object]) -> set[tuple[str, str, str]]:
    """Allow any non-empty subset of the approved new-repository remotes."""
    errors: set[tuple[str, str, str]] = set()
    configured = set(git("remote").splitlines())
    if not configured or not configured.issubset(allowed_remotes):
        errors.add(("RH002", "<repository>", "REMOTE_SET"))
    for name in configured:
        expected = allowed_remotes.get(name)
        actual = git("remote", "get-url", name, check=False).strip()
        if isinstance(expected, str):
            approved_urls = {expected}
        elif isinstance(expected, list) and all(isinstance(item, str) for item in expected):
            approved_urls = set(expected)
        else:
            approved_urls = set()
        if not actual or actual not in approved_urls:
            errors.add(("RH003", f"remote:{name}", "OLD_OR_UNEXPECTED_REMOTE"))
    return errors


def is_runtime_env_path(path: str) -> bool:
    name = Path(path).name
    return name.startswith(".env") and not name.endswith(".example")


def local_hygiene_errors() -> tuple[set[tuple[str, str, str]], int, int]:
    """Detect objects hidden from ordinary --all reachability scans."""
    errors: set[tuple[str, str, str]] = set()
    reachable = {line for line in git("rev-list", "--all", check=False).splitlines() if line}
    reflog = {
        line
        for line in git("reflog", "--all", "--format=%H", check=False).splitlines()
        if line
    }
    reflog_only = sorted(reflog - reachable)
    for object_id in reflog_only:
        errors.add(("RH009", f"object:{object_id[:12]}", "REFLOG_ONLY_COMMIT"))

    fsck_lines = [
        line.strip()
        for line in git("fsck", "--full", "--unreachable", "--no-reflogs", check=False).splitlines()
        if line.strip().startswith(("unreachable ", "dangling "))
    ]
    for line in fsck_lines:
        parts = line.split()
        object_type = parts[1] if len(parts) > 1 else "object"
        object_id = parts[-1] if parts else "unknown"
        errors.add(("RH010", f"{object_type}:{object_id[:12]}", "UNREACHABLE_OBJECT"))
    return errors, len(reflog_only), len(fsck_lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--local-hygiene",
        action="store_true",
        help="also fail on reflog-only and unreachable local objects",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        rules = policy()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[repository_clean_history_guard] FAIL rule=RH000 classification={type(exc).__name__}", file=sys.stderr)
        return 2

    errors: set[tuple[str, str, str]] = set()
    roots = [line for line in git("rev-list", "--max-parents=0", "--all", check=False).splitlines() if line]
    if len(roots) != 1:
        errors.add(("RH001", "<repository>", "ROOT_COMMIT_COUNT"))

    allowed_remotes = rules.get("allowed_remotes", {})
    if not isinstance(allowed_remotes, dict):
        errors.add(("RH000", str(POLICY_PATH.relative_to(ROOT)), "INVALID_POLICY"))
        allowed_remotes = {}
    errors.update(remote_errors(allowed_remotes))

    for commit_id in rules.get("forbidden_commit_objects", []):
        exists = subprocess.run(
            ["git", "cat-file", "-e", f"{commit_id}^{{commit}}"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
        if exists:
            errors.add(("RH004", f"object:{str(commit_id)[:12]}", "OLD_COMMIT_IMPORTED"))

    prefixes = tuple(str(item) for item in rules.get("forbidden_path_prefixes", []))
    suffixes = tuple(str(item).lower() for item in rules.get("forbidden_archive_suffixes", []))
    forbidden_repository_tokens = tuple(
        str(item).encode("utf-8") for item in rules.get("forbidden_repository_tokens", [])
    )
    maximum_blob_bytes = int(rules.get("maximum_blob_bytes", 0))
    policy_relative = str(POLICY_PATH.relative_to(ROOT))
    token_cache: dict[str, bool] = {}
    for object_id, object_type, size, path in reachable_objects():
        if not path:
            continue
        if path.startswith(prefixes):
            errors.add(("RH005", path, "FORBIDDEN_HISTORY_PATH"))
        if is_runtime_env_path(path):
            errors.add(("RH011", path, "TRACKED_RUNTIME_ENV_FILE"))
        if object_type == "blob" and path.lower().endswith(suffixes):
            errors.add(("RH006", path, "ARCHIVE_OR_BACKUP_BLOB"))
        if object_type == "blob" and size > maximum_blob_bytes:
            errors.add(("RH007", f"{path}@{object_id[:12]}", "OVERSIZED_BLOB"))
        if object_type == "blob" and size <= maximum_blob_bytes and path != policy_relative:
            if object_id not in token_cache:
                data = blob_bytes(object_id)
                token_cache[object_id] = any(token in data for token in forbidden_repository_tokens)
            if token_cache[object_id]:
                errors.add(("RH008", f"{path}@{object_id[:12]}", "OLD_REPOSITORY_REFERENCE"))

    reflog_only_count = 0
    unreachable_count = 0
    if args.local_hygiene:
        hygiene, reflog_only_count, unreachable_count = local_hygiene_errors()
        errors.update(hygiene)

    if errors:
        print("[repository_clean_history_guard] FAIL", file=sys.stderr)
        for rule_id, path, classification in sorted(errors):
            print(f"- rule={rule_id} path={path} classification={classification}", file=sys.stderr)
        return 1
    print(
        f"[repository_clean_history_guard] PASS roots={len(roots)} "
        f"old_commit_objects=0 old_repository_remotes=0 local_hygiene={args.local_hygiene} "
        f"reflog_only={reflog_only_count} unreachable={unreachable_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
