#!/usr/bin/env python3
"""Fail-closed admission for an external customer archive and tenant payload."""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import hmac
import importlib.util
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[2]
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MODULE_RE = re.compile(r"^[a-z][a-z0-9_]{1,62}$")
TENANT_RE = re.compile(r"^[a-z][a-z0-9_]{2,62}$")
PACKAGE_SCHEMA_VERSION = "sce.tenant_customer_addon_package.v1"
PACKAGE_KIND = "tenant_customer_addon"


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


def canonical_package_manifest_bytes(payload: dict) -> bytes:
    canonical = json.loads(json.dumps(payload))
    signature = canonical.get("signature")
    if isinstance(signature, dict):
        signature["value"] = ""
    return json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def verify_package_signature(payload: dict) -> None:
    signature = payload.get("signature")
    if not isinstance(signature, dict) or set(signature) != {"algorithm", "key_id", "value"}:
        raise ValueError("CUSTOMER_PACKAGE_SIGNATURE_INVALID")
    algorithm = str(signature.get("algorithm") or "")
    supplied = str(signature.get("value") or "")
    canonical = canonical_package_manifest_bytes(payload)
    if algorithm == "hmac-sha256":
        if os.environ.get("SC_CUSTOMER_PACKAGE_TEST_MODE") != "1":
            raise ValueError("CUSTOMER_PACKAGE_HMAC_TEST_MODE_REQUIRED")
        key = os.environ.get("SC_CUSTOMER_PACKAGE_HMAC_KEY", "").encode("utf-8")
        expected = hmac.new(key, canonical, hashlib.sha256).hexdigest() if key else ""
        if not SHA256_RE.fullmatch(supplied) or not hmac.compare_digest(supplied, expected):
            raise ValueError("CUSTOMER_PACKAGE_SIGNATURE_INVALID")
        return
    if algorithm != "ed25519":
        raise ValueError("CUSTOMER_PACKAGE_SIGNATURE_ALGORITHM_UNSUPPORTED")
    public_key_value = os.environ.get("SC_CUSTOMER_PACKAGE_PUBLIC_KEY", "").strip()
    public_key = Path(public_key_value).expanduser().resolve() if public_key_value else None
    if not public_key or not public_key.is_file() or public_key.is_symlink():
        raise ValueError("CUSTOMER_PACKAGE_PUBLIC_KEY_REQUIRED")
    try:
        signature_bytes = base64.b64decode(supplied, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("CUSTOMER_PACKAGE_SIGNATURE_INVALID") from exc
    with tempfile.TemporaryDirectory(prefix="customer-package-signature-") as temporary:
        message_path = Path(temporary) / "manifest.canonical"
        signature_path = Path(temporary) / "signature"
        message_path.write_bytes(canonical)
        signature_path.write_bytes(signature_bytes)
        result = subprocess.run(
            [
                "openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(public_key),
                "-rawin", "-in", str(message_path), "-sigfile", str(signature_path),
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    if result.returncode != 0:
        raise ValueError("CUSTOMER_PACKAGE_SIGNATURE_INVALID")


def load_package_manifest(path: Path, expected_archive_sha: str, product_version: str) -> dict:
    if not path.is_file() or path.is_symlink():
        raise ValueError("CUSTOMER_PACKAGE_MANIFEST_MISSING")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("CUSTOMER_PACKAGE_MANIFEST_INVALID") from exc
    required = {
        "schema_version", "package_kind", "tenant_id", "modules", "product_compatibility",
        "archive_sha256", "signature",
    }
    if set(payload) != required or payload.get("schema_version") != PACKAGE_SCHEMA_VERSION:
        raise ValueError("CUSTOMER_PACKAGE_MANIFEST_SCHEMA_INVALID")
    if payload.get("package_kind") != PACKAGE_KIND:
        raise ValueError("CUSTOMER_PACKAGE_KIND_INVALID")
    if not TENANT_RE.fullmatch(str(payload.get("tenant_id") or "")):
        raise ValueError("CUSTOMER_PACKAGE_TENANT_INVALID")
    modules = payload.get("modules")
    if (
        not isinstance(modules, list)
        or not modules
        or len(modules) != len(set(modules))
        or any(not MODULE_RE.fullmatch(str(item or "")) for item in modules)
    ):
        raise ValueError("CUSTOMER_PACKAGE_MODULES_INVALID")
    if payload.get("archive_sha256") != expected_archive_sha:
        raise ValueError("CUSTOMER_PACKAGE_ARCHIVE_DECLARATION_MISMATCH")
    verify_package_signature(payload)
    validator = load_module("sce_tenant_delivery_manifest", "addons/smart_core/utils/tenant_delivery_manifest.py")
    validator._verify_product_range(payload.get("product_compatibility"), product_version)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-dir", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    package_manifest_value = os.environ.get("SC_CUSTOMER_PACKAGE_MANIFEST", "").strip()
    if not package_manifest_value:
        raise SystemExit("CUSTOMER_PACKAGE_MANIFEST_MISSING")
    package_manifest_path = Path(package_manifest_value).expanduser().resolve()
    customer_root_value = os.environ.get("SC_CUSTOMER_ADDONS_ROOT", "").strip()
    if not customer_root_value:
        raise SystemExit("CUSTOMER_ADDONS_ROOT_MISSING")
    customer_root = Path(customer_root_value).expanduser().resolve()
    expected_archive_sha = os.environ.get("SC_CUSTOMER_ARCHIVE_SHA256", "").strip()
    if not SHA256_RE.fullmatch(expected_archive_sha):
        raise SystemExit("CUSTOMER_ARCHIVE_SHA256_INVALID")
    product_release = json.loads((ROOT / "config" / "product_release.v1.json").read_text(encoding="utf-8"))
    try:
        package_manifest = load_package_manifest(
            package_manifest_path,
            expected_archive_sha,
            product_release["product_version"],
        )
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc
    tenant_id = str(package_manifest["tenant_id"])
    module_names = [str(item) for item in package_manifest["modules"]]

    archive = archive_from_root(customer_root)
    actual_archive_sha = sha256_file(archive)
    if actual_archive_sha != expected_archive_sha:
        raise SystemExit("CUSTOMER_ARCHIVE_CHECKSUM_MISMATCH")
    safe_extract(archive, args.prepare_dir)
    module_roots = [locate_module_root(args.prepare_dir, module_name) for module_name in module_names]
    addons_roots = {module_root.parent.resolve() for module_root in module_roots}
    if len(addons_roots) != 1:
        raise SystemExit("CUSTOMER_PACKAGE_ADDONS_LAYOUT_INVALID")
    discovered = {
        path.parent.name
        for path in args.prepare_dir.rglob("__manifest__.py")
        if path.parent.parent.name == "addons"
    }
    if discovered != set(module_names):
        raise SystemExit("CUSTOMER_PACKAGE_MODULE_SET_MISMATCH")
    module_versions = {}
    module_contracts = {}
    module_contract_validator = load_module(
        "sce_tenant_delivery_module_manifest",
        "addons/smart_core/utils/tenant_delivery_manifest.py",
    )
    for module_root in module_roots:
        module_manifest = ast.literal_eval((module_root / "__manifest__.py").read_text(encoding="utf-8"))
        module_versions[module_root.name] = str(module_manifest.get("version") or "")
        if not module_versions[module_root.name]:
            raise SystemExit("CUSTOMER_PACKAGE_MODULE_VERSION_MISSING")
        module_contract_path = module_root / "customer_module_manifest.json"
        if module_contract_path.is_file():
            module_contract = json.loads(module_contract_path.read_text(encoding="utf-8"))
            module_contract_validator.validate_customer_module_manifest(module_contract)
            if (
                module_contract.get("module_name") != module_root.name
                or module_contract.get("tenant_key") != tenant_id
            ):
                raise SystemExit("CUSTOMER_MODULE_TENANT_MISMATCH")
            if module_contract.get("module_version") != module_versions[module_root.name]:
                raise SystemExit("CUSTOMER_MODULE_VERSION_MISMATCH")
            module_contracts[module_root.name] = module_contract

    payload_checksum = None
    payload_manifest_value = os.environ.get("SC_PAYLOAD_MANIFEST", "").strip()
    if payload_manifest_value:
        payload_manifest_path = Path(payload_manifest_value).expanduser().resolve()
        payload_root = payload_manifest_path.parent
        if not payload_manifest_path.is_file() or payload_manifest_path.name != "manifest.json":
            raise SystemExit("PAYLOAD_MANIFEST_MISSING")
        payload_validator = load_module("sce_tenant_payload_v1", "addons/smart_core/utils/tenant_payload_v1.py")
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
        payload_module = str(payload_manifest.get("customer_module") or "")
        if payload_module not in module_names:
            raise SystemExit("PAYLOAD_CUSTOMER_MODULE_MISMATCH")
        module_contract = module_contracts.get(payload_module) or {}
        if module_contract and payload_manifest.get("customer_module_version") != module_contract.get("module_version"):
            raise SystemExit("PAYLOAD_CUSTOMER_VERSION_MISMATCH")
        allowed_companies = set(
            module_contract.get("payload_company_keys")
            if "payload_company_keys" in module_contract
            else module_contract.get("company_keys") or []
        )
        if allowed_companies:
            company_file = payload_root / "records" / "companies.jsonl"
            payload_companies = {
                json.loads(line).get("external_key")
                for line in company_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            }
            if not payload_companies or not payload_companies.issubset(allowed_companies):
                raise SystemExit("PAYLOAD_COMPANY_MISMATCH")
        payload_checksum = payload_manifest.get("payload_checksum")

    addons_mount = addons_roots.pop()
    tenant_fingerprint = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()[:12]
    payload = {
        "schema_version": "sce.customer_package_admission.v1",
        "status": "PASS",
        "tenant_fingerprint": tenant_fingerprint,
        "modules": module_names,
        "module_versions": module_versions,
        "archive_sha256": actual_archive_sha,
        "payload_checksum": payload_checksum,
        "prepared_addons_root": str(addons_mount.resolve()),
        "database_write_count": 0,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "tenant_fingerprint": tenant_fingerprint,
        "module_count": len(module_names),
        "database_write_count": 0,
    }, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
