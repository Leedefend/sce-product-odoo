#!/usr/bin/env python3
"""Fail closed when customer history implementation leaks into product runtime."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "addons" / "smart_construction_core"
RUNTIME_SUFFIXES = {".py", ".xml", ".csv", ".json"}
GENERIC_LEGACY_PREFIX_LINES = {
    'FILE_ATTACHMENT_ALLOWED_LEGACY_MODEL_PREFIXES = ("sc.legacy.",)',
    '"sc.legacy.",',
}
CUSTOMER_SOURCE_TOKENS = re.compile(
    r"\b(?:C_[A-Z0-9_]{3,}|CWGL_[A-Z0-9_]+|ZJGL_[A-Z0-9_]+|BGGL_[A-Z0-9_]+|"
    r"T_KK_[A-Z0-9_]+|UP_USP_[A-Z0-9_]+|LEGACY_DIRECT_DIRECT_[A-Z0-9_]+)\b"
)
CUSTOMER_IDENTITY_TOKENS = ("bao" + "sheng", "宝" + "盛")
CUSTOMER_REPORT_MODELS = {
    "sc.account.income.expense.summary",
    "sc.project.operation.summary",
}


def runtime_files():
    for path in MODULE.rglob("*"):
        if not path.is_file() or path.suffix not in RUNTIME_SUFFIXES:
            continue
        if "migrations" in path.parts or "tests" in path.parts or "__pycache__" in path.parts:
            continue
        yield path


def main() -> int:
    errors = []
    for path in runtime_files():
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT)
        lower = text.lower()
        if CUSTOMER_IDENTITY_TOKENS[0] in lower or CUSTOMER_IDENTITY_TOKENS[1] in text:
            errors.append(f"CUSTOMER_IDENTITY:{rel}")
        if "legacy_report_inventory_seed.xml" in text:
            errors.append(f"CUSTOMER_SEED:{rel}")
        if re.search(r"\bsc_legacy_[a-z0-9_]+\b", text):
            errors.append(f"CUSTOMER_TABLE:{rel}")
        if CUSTOMER_SOURCE_TOKENS.search(text):
            errors.append(f"CUSTOMER_SOURCE_TABLE:{rel}")
        if any(f'<field name="model">{model}</field>' in text for model in CUSTOMER_REPORT_MODELS):
            errors.append(f"CUSTOMER_REPORT_CONFIG:{rel}")
        for line in text.splitlines():
            if "sc.legacy." in line and line.strip() not in GENERIC_LEGACY_PREFIX_LINES:
                errors.append(f"CUSTOMER_MODEL_REFERENCE:{rel}")
                break
        if re.search(r"\blegacy_[a-z0-9_]+\s+or\s+[a-z_]", text) or re.search(
            r"\b[a-z_][a-z0-9_.]*\s+or\s+legacy_[a-z0-9_]", text
        ):
            errors.append(f"LEGACY_FALLBACK:{rel}")
        if path.suffix == ".py":
            tree = ast.parse(text, filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                for statement in node.body:
                    if not isinstance(statement, ast.Assign):
                        continue
                    if not any(isinstance(t, ast.Name) and t.id == "_name" for t in statement.targets):
                        continue
                    if isinstance(statement.value, ast.Constant) and str(statement.value.value).startswith("sc.legacy."):
                        errors.append(f"CUSTOMER_MODEL_IMPLEMENTATION:{rel}:{statement.value.value}")
    manifest = ast.literal_eval((MODULE / "__manifest__.py").read_text(encoding="utf-8"))
    if any("customer" in dep or CUSTOMER_IDENTITY_TOKENS[0] in dep for dep in manifest.get("depends", [])):
        errors.append("CUSTOMER_DEPENDENCY:addons/smart_construction_core/__manifest__.py")
    if errors:
        for item in sorted(set(errors)):
            print(item, file=sys.stderr)
        return 1
    print("[tenant_product_legacy_boundary] PASS customer_runtime_references=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
