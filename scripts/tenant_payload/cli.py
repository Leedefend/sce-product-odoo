#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LIBRARY = ROOT / "addons/smart_core/utils/tenant_payload_v1.py"
SPEC = importlib.util.spec_from_file_location("tenant_payload_v1", LIBRARY)
payload_v1 = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = payload_v1
SPEC.loader.exec_module(payload_v1)


def _validate(args: argparse.Namespace) -> int:
    key = os.environ.get("SC_TENANT_PAYLOAD_HMAC_KEY", "").encode("utf-8") or None
    public_key_value = os.environ.get("SC_TENANT_PAYLOAD_PUBLIC_KEY", "")
    public_key = Path(public_key_value) if public_key_value else None
    try:
        summary = payload_v1.validate_payload_directory(
            Path(args.payload),
            expected_tenant_key=args.tenant_key,
            hmac_key=key,
            public_key=public_key,
        )
    except payload_v1.TenantPayloadError as exc:
        print(json.dumps({"schema_version": payload_v1.SCHEMA_VERSION, "status": "BLOCKER", "rule": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(summary.as_dict(), sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed tenant payload v1 operations")
    subparsers = parser.add_subparsers(dest="action", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--payload", required=True)
    validate.add_argument("--tenant-key")
    validate.set_defaults(handler=_validate)
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
