#!/usr/bin/env python3
"""Emit the frozen product module/version matrix from repository manifests."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ALLOWLIST = ROOT / "config" / "product_addons_allowlist.txt"
OPTIONAL_ALLOWLIST = ROOT / "config" / "product_optional_addons_allowlist.txt"


def matrix() -> dict[str, str]:
    modules = [
        line.strip()
        for path in (ALLOWLIST, OPTIONAL_ALLOWLIST)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    result: dict[str, str] = {}
    for module in modules:
        manifest_path = ROOT / "addons" / module / "__manifest__.py"
        manifest = ast.literal_eval(manifest_path.read_text(encoding="utf-8"))
        version = str(manifest.get("version") or "").strip()
        if not version:
            raise SystemExit(f"product module version missing: {module}")
        result[module] = version
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = matrix()
    if args.json:
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    else:
        for module, version in payload.items():
            print(f"{module}={version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
