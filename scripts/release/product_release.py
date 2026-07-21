#!/usr/bin/env python3
"""Read and validate the repository's single product release identity."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
VERSION_FILE = ROOT / "VERSION"
RELEASE_FILE = ROOT / "release" / "product-release.yaml"
SEMVER_RE = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def parse_version(value: str) -> tuple[tuple[int, int, int], tuple[tuple[int, int | str], ...] | None]:
    text = str(value or "").strip()
    match = SEMVER_RE.fullmatch(text)
    if not match:
        raise ValueError("PRODUCT_VERSION_INVALID")
    prerelease = match.group(4)
    parsed_prerelease = None
    if prerelease is not None:
        identifiers = []
        for item in prerelease.split("."):
            if item.isdigit():
                if len(item) > 1 and item.startswith("0"):
                    raise ValueError("PRODUCT_VERSION_INVALID")
                identifiers.append((0, int(item)))
            else:
                identifiers.append((1, item))
        parsed_prerelease = tuple(identifiers)
    return (int(match.group(1)), int(match.group(2)), int(match.group(3))), parsed_prerelease


def compare_versions(left: str, right: str) -> int:
    left_release, left_pre = parse_version(left)
    right_release, right_pre = parse_version(right)
    if left_release != right_release:
        return -1 if left_release < right_release else 1
    if left_pre is None or right_pre is None:
        if left_pre is right_pre:
            return 0
        return 1 if left_pre is None else -1
    for left_item, right_item in zip(left_pre, right_pre):
        if left_item == right_item:
            continue
        if left_item[0] != right_item[0]:
            return -1 if left_item[0] < right_item[0] else 1
        return -1 if left_item[1] < right_item[1] else 1
    if len(left_pre) == len(right_pre):
        return 0
    return -1 if len(left_pre) < len(right_pre) else 1


def read_version() -> str:
    try:
        value = VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ValueError("PRODUCT_VERSION_SOURCE_MISSING") from exc
    parse_version(value)
    return value


def _yaml_scalar(value: str) -> str:
    text = value.strip()
    if text.startswith('"'):
        parsed = json.loads(text)
        if not isinstance(parsed, str):
            raise ValueError("PRODUCT_RELEASE_CONFIG_INVALID")
        return parsed
    if not text or any(marker in text for marker in ("[", "]", "{", "}", "#")):
        raise ValueError("PRODUCT_RELEASE_CONFIG_INVALID")
    return text


def load_release_config() -> dict[str, Any]:
    try:
        lines = RELEASE_FILE.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError("PRODUCT_RELEASE_CONFIG_MISSING") from exc
    payload: dict[str, Any] = {}
    section = ""
    for raw in lines:
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if ":" not in line or indent not in {0, 2}:
            raise ValueError("PRODUCT_RELEASE_CONFIG_INVALID")
        key, value = line.split(":", 1)
        if indent == 0:
            if not value.strip():
                if key != "contracts":
                    raise ValueError("PRODUCT_RELEASE_CONFIG_INVALID")
                payload[key] = {}
                section = key
            else:
                payload[key] = _yaml_scalar(value)
                section = ""
        elif section == "contracts":
            payload[section][key] = _yaml_scalar(value)
        else:
            raise ValueError("PRODUCT_RELEASE_CONFIG_INVALID")
    expected = {"product", "version_source", "odoo_series", "contracts", "customer_package_api"}
    if set(payload) != expected or payload.get("version_source") != "VERSION":
        raise ValueError("PRODUCT_RELEASE_CONFIG_INVALID")
    if payload.get("product") != "sce-product" or payload.get("odoo_series") != "17.0":
        raise ValueError("PRODUCT_RELEASE_CONFIG_INVALID")
    if payload.get("customer_package_api") != "v1" or payload.get("contracts") != {
        "tenant_payload": "tenant_payload_v1",
        "route_authority": "route_authority.v1",
    }:
        raise ValueError("PRODUCT_RELEASE_CONFIG_INVALID")
    payload["product_version"] = read_version()
    return payload


def verify_customer_compatibility(
    minimum: Any,
    maximum_exclusive: Any,
    required_contracts: Any,
) -> None:
    current = read_version()
    minimum_text = str(minimum or "").strip()
    maximum_text = str(maximum_exclusive or "").strip()
    parse_version(minimum_text)
    parse_version(maximum_text)
    if compare_versions(minimum_text, maximum_text) >= 0:
        raise ValueError("CUSTOMER_PACKAGE_PRODUCT_RANGE_INVALID")
    if compare_versions(current, minimum_text) < 0 or compare_versions(current, maximum_text) >= 0:
        raise ValueError("CUSTOMER_PACKAGE_PRODUCT_VERSION_INCOMPATIBLE")
    if (
        not isinstance(required_contracts, list)
        or not required_contracts
        or len(required_contracts) != len(set(required_contracts))
        or any(not isinstance(item, str) or not item.strip() for item in required_contracts)
    ):
        raise ValueError("CUSTOMER_PACKAGE_REQUIRED_CONTRACTS_INVALID")
    supported = set(load_release_config()["contracts"].values())
    if not set(required_contracts).issubset(supported):
        raise ValueError("CUSTOMER_PACKAGE_REQUIRED_CONTRACT_UNSUPPORTED")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = load_release_config()
    if args.version:
        print(payload["product_version"])
    elif args.json:
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    else:
        print("[product.release] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
