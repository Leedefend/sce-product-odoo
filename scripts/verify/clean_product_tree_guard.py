#!/usr/bin/env python3
"""Validate the file-only product snapshot before repository recreation."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXCLUDED_PARTS = {".git", "node_modules", "__pycache__", "artifacts"}
ARCHIVE_SUFFIXES = (
    ".age", ".bak", ".backup", ".dump", ".rar", ".sql.gz",
    ".sqlite", ".tar", ".tar.gz", ".tgz", ".zip", ".zst",
)
CUSTOMER_MODULE_PATH = re.compile(
    r"(?:^|/)(?:smart_construction_custom|sce_customer_(?!sample(?:/|$)|template(?:/|$))[a-z0-9_]+)(?:/|$)",
    re.IGNORECASE,
)
CUSTOMER_SOURCE_TOKEN = re.compile(
    r"\b(?:C_[A-Z0-9_]{3,}|CWGL_[A-Z0-9_]+|ZJGL_[A-Z0-9_]+|BGGL_[A-Z0-9_]+|"
    r"T_KK_[A-Z0-9_]+|UP_USP_[A-Z0-9_]+|LEGACY_DIRECT_DIRECT_[A-Z0-9_]+)\b"
)
CUSTOMER_SQL_ID = re.compile(
    r"\blegacy_\d{8,}\b|\bsc_legacy_(?:legacy_source_[a-z0-9_]+|file_index)\b",
    re.IGNORECASE,
)
CUSTOMER_MODEL = re.compile(r"_name\s*=\s*['\"]sc\.legacy\.[^'\"]+['\"]")
DATABASE_URL_CREDENTIALS = re.compile(
    r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s/@:]+:[^\s/@]+@",
    re.IGNORECASE,
)
SENSITIVE_KEY = re.compile(r"(?:PASSWORD|PASSWD|SECRET|TOKEN|API_KEY|PRIVATE_KEY|ACCESS_KEY)", re.IGNORECASE)
TOKEN_KEY = re.compile(r"(?:SECRET|TOKEN|API_KEY|PRIVATE_KEY|ACCESS_KEY)", re.IGNORECASE)
PLACEHOLDER = re.compile(r"^<SET_[A-Z0-9_]+>$")


def files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and not EXCLUDED_PARTS.intersection(path.relative_to(root).parts)
    )


def text(path: Path) -> str | None:
    data = path.read_bytes()
    if b"\0" in data:
        return None
    return data.decode("utf-8", errors="ignore")


def scan(root: Path) -> dict[str, object]:
    all_files = files(root)
    runtime_env: list[str] = []
    env_examples: list[str] = []
    literal_passwords: list[str] = []
    literal_tokens: list[str] = []
    database_urls: list[str] = []
    customer_modules: list[str] = []
    customer_implementations: list[str] = []
    customer_ids: list[str] = []
    archives: list[str] = []

    for path in all_files:
        relative = path.relative_to(root).as_posix()
        name = path.name
        if name.startswith(".env"):
            if name.endswith(".example"):
                env_examples.append(relative)
            else:
                runtime_env.append(relative)
        if relative.lower().endswith(ARCHIVE_SUFFIXES):
            archives.append(relative)
        if CUSTOMER_MODULE_PATH.search(relative):
            customer_modules.append(relative)

        content = text(path)
        if content is None:
            continue
        if DATABASE_URL_CREDENTIALS.search(content):
            database_urls.append(relative)
        if name.startswith(".env") and name.endswith(".example"):
            for line_number, line in enumerate(content.splitlines(), 1):
                if not line or line.lstrip().startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if SENSITIVE_KEY.search(key) and not PLACEHOLDER.fullmatch(value.strip()):
                    target = literal_tokens if TOKEN_KEY.search(key) else literal_passwords
                    target.append(f"{relative}:{line_number}")
        if relative.startswith("addons/smart_construction_core/"):
            if CUSTOMER_MODEL.search(content):
                customer_implementations.append(relative)
            if CUSTOMER_SOURCE_TOKEN.search(content) or CUSTOMER_SQL_ID.search(content):
                customer_ids.append(relative)

    counts = {
        "TRACKED_RUNTIME_ENV_FILES": len(set(runtime_env)),
        "TRACKED_ENV_EXAMPLE_FILES": len(set(env_examples)),
        "LITERAL_PASSWORD_DEFAULTS": len(set(literal_passwords)),
        "LITERAL_TOKEN_DEFAULTS": len(set(literal_tokens)),
        "DATABASE_URL_WITH_CREDENTIALS": len(set(database_urls)),
        "CUSTOMER_MODULE_FILES": len(set(customer_modules)),
        "CUSTOMER_LEGACY_IMPLEMENTATIONS": len(set(customer_implementations)),
        "CUSTOMER_CONFIG_SQL_SOURCE_MATCHES": len(set(customer_ids)),
        "SENSITIVE_ARCHIVE_OR_DATABASE_FILES": len(set(archives)),
    }
    findings = {
        "runtime_env_files": sorted(set(runtime_env)),
        "literal_password_defaults": sorted(set(literal_passwords)),
        "literal_token_defaults": sorted(set(literal_tokens)),
        "database_url_with_credentials": sorted(set(database_urls)),
        "customer_module_files": sorted(set(customer_modules)),
        "customer_legacy_implementations": sorted(set(customer_implementations)),
        "customer_config_sql_source_matches": sorted(set(customer_ids)),
        "sensitive_archive_or_database_files": sorted(set(archives)),
    }
    blocking = [key for key, value in counts.items() if key != "TRACKED_ENV_EXAMPLE_FILES" and value]
    if counts["TRACKED_ENV_EXAMPLE_FILES"] < 1:
        blocking.append("TRACKED_ENV_EXAMPLE_FILES")
    return {
        "schema_version": "sce.clean_product_tree_scan.v1",
        "root": str(root),
        "file_count": len(all_files),
        "counts": counts,
        "findings": findings,
        "status": "PASS" if not blocking else "FAIL",
        "blocking_rules": sorted(blocking),
        "sensitive_values_recorded": False,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = scan(args.root.resolve())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    counts = report["counts"]
    for key in sorted(counts):
        print(f"{key}={counts[key]}")
    print(f"[clean_product_tree_guard] {report['status']} files={report['file_count']}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
