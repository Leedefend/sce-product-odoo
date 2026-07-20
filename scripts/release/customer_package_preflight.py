#!/usr/bin/env python3
"""Fail-closed admission for an external customer archive and tenant payload."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import os
import re
import sys
import tarfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[2]
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MODULE_RE = re.compile(r"^sce_customer_[a-z0-9_]+$")
TENANT_RE = re.compile(r"^[a-z][a-z0-9_]{2,62}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_module(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("tenant delivery validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def archive_from_root(root: Path) -> Path:
    if not root.is_dir():
        raise ValueError("SC_CUSTOMER_ADDONS_ROOT must be a directory")
    archives = sorted(path for path in root.iterdir() if path.is_file() and path.name.endswith(".tar.gz"))
    if len(archives) != 1:
        raise ValueError("SC_CUSTOMER_ADDONS_ROOT must contain exactly one .tar.gz archive")
    return archives[0]


def safe_extract(archive: Path, destination: Path) -> None:
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("prepared customer directory must be empty")
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as handle:
        members = handle.getmembers()
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk() or member.isdev():
                raise ValueError(f"unsafe archive member: {member.name}")
        handle.extractall(destination, members=members, filter="data")


def locate_module_root(prepared: Path, module_name: str) -> Path:
    candidates = sorted(
        path.parent
        for path in prepared.rglob("__manifest__.py")
        if path.parent.name == module_name and path.parent.parent.name == "addons"
    )
    if len(candidates) != 1:
        raise ValueError("customer archive must contain exactly one requested module")
    return candidates[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-dir", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    customer_root = Path(os.environ.get("SC_CUSTOMER_ADDONS_ROOT", "")).expanduser().resolve()
    module_name = os.environ.get("SC_CUSTOMER_MODULE", "").strip()
    expected_archive_sha = os.environ.get("SC_CUSTOMER_ARCHIVE_SHA256", "").strip()
    tenant_id = os.environ.get("SC_TENANT_ID", "").strip()
    payload_manifest_path = Path(os.environ.get("SC_PAYLOAD_MANIFEST", "")).expanduser().resolve()
    if not MODULE_RE.fullmatch(module_name):
        raise SystemExit("CUSTOMER_MODULE_INVALID")
    if not SHA256_RE.fullmatch(expected_archive_sha):
        raise SystemExit("CUSTOMER_ARCHIVE_SHA256_INVALID")
    if not TENANT_RE.fullmatch(tenant_id):
        raise SystemExit("TENANT_ID_INVALID")
    if not payload_manifest_path.is_file():
        raise SystemExit("PAYLOAD_MANIFEST_MISSING")

    archive = archive_from_root(customer_root)
    actual_archive_sha = sha256_file(archive)
    if actual_archive_sha != expected_archive_sha:
        raise SystemExit("CUSTOMER_ARCHIVE_CHECKSUM_MISMATCH")
    safe_extract(archive, args.prepare_dir)
    module_root = locate_module_root(args.prepare_dir, module_name)

    validator = load_module(
        "sce_tenant_delivery_manifest",
        "addons/smart_core/utils/tenant_delivery_manifest.py",
    )
    customer_manifest_path = module_root / "customer_module_manifest.json"
    if not customer_manifest_path.is_file():
        raise SystemExit("CUSTOMER_MODULE_MANIFEST_MISSING")
    customer_manifest = json.loads(customer_manifest_path.read_text(encoding="utf-8"))
    validator.validate_customer_module_manifest(customer_manifest)
    product_release = json.loads((ROOT / "config" / "product_release.v1.json").read_text(encoding="utf-8"))
    validator._verify_product_range(
        customer_manifest.get("product_version_range"), product_release["product_version"]
    )
    module_manifest = ast.literal_eval((module_root / "__manifest__.py").read_text(encoding="utf-8"))
    if customer_manifest.get("module_name") != module_name or customer_manifest.get("tenant_key") != tenant_id:
        raise SystemExit("CUSTOMER_MODULE_TENANT_MISMATCH")
    if str(module_manifest.get("version") or "") != customer_manifest.get("module_version"):
        raise SystemExit("CUSTOMER_MODULE_VERSION_MISMATCH")

    payload_root = payload_manifest_path.parent
    if payload_manifest_path.name != "manifest.json":
        raise SystemExit("PAYLOAD_MANIFEST_NAME_INVALID")
    payload_validator = load_module(
        "sce_tenant_payload_v1",
        "addons/smart_core/utils/tenant_payload_v1.py",
    )
    hmac_key = os.environ.get("SC_TENANT_PAYLOAD_HMAC_KEY", "").encode("utf-8") or None
    public_key_value = os.environ.get("SC_TENANT_PAYLOAD_PUBLIC_KEY", "").strip()
    public_key = Path(public_key_value).expanduser().resolve() if public_key_value else None
    payload_validator.validate_payload_directory(
        payload_root,
        expected_tenant_key=tenant_id,
        hmac_key=hmac_key,
        public_key=public_key,
    )
    payload_manifest = json.loads(payload_manifest_path.read_text(encoding="utf-8"))
    if payload_manifest.get("customer_module") != module_name:
        raise SystemExit("PAYLOAD_CUSTOMER_MODULE_MISMATCH")
    if payload_manifest.get("customer_module_version") != customer_manifest.get("module_version"):
        raise SystemExit("PAYLOAD_CUSTOMER_VERSION_MISMATCH")
    allowed_companies = set(customer_manifest.get("company_keys") or [])
    if allowed_companies:
        company_file = payload_root / "records" / "companies.jsonl"
        payload_companies = {
            json.loads(line).get("external_key")
            for line in company_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        if not payload_companies or not payload_companies.issubset(allowed_companies):
            raise SystemExit("PAYLOAD_COMPANY_MISMATCH")

    addons_mount = module_root.parent
    payload = {
        "schema_version": "sce.customer_package_admission.v1",
        "status": "PASS",
        "tenant_id": tenant_id,
        "customer_module": module_name,
        "customer_module_version": customer_manifest["module_version"],
        "archive": archive.name,
        "archive_sha256": actual_archive_sha,
        "payload_manifest": payload_manifest_path.name,
        "payload_checksum": payload_manifest.get("payload_checksum"),
        "prepared_addons_root": str(addons_mount.resolve()),
        "database_write_count": 0,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
