from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


SCHEMA_VERSION = "tenant_payload_v1"
PRODUCT_INTERFACE_VERSION = "1"
MANIFEST_NAME = "manifest.json"
CHECKSUMS_NAME = "checksums.sha256"
SIGNATURE_NAME = "signature"
ALLOWED_TOP_LEVEL = {MANIFEST_NAME, CHECKSUMS_NAME, SIGNATURE_NAME, "records", "filestore"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
KEY_RE = re.compile(r"^[a-z][a-z0-9_.:-]{2,191}$")
REFERENCE_RE = re.compile(r"^[a-z][a-z0-9_]{2,62}::[a-z][a-z0-9_.:-]{2,191}$")
TENANT_RE = re.compile(r"^[a-z][a-z0-9_]{2,62}$")
SNAPSHOT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")
FORBIDDEN_FIELD_NAMES = {
    "password",
    "passwd",
    "token",
    "access_token",
    "refresh_token",
    "cookie",
    "session",
    "session_id",
    "private_key",
    "database_password",
    "db_password",
    "connection_string",
    "database_url",
    "server_url",
}


class TenantPayloadError(ValueError):
    """A redacted, operator-safe payload validation failure."""


@dataclass(frozen=True)
class ValidationSummary:
    tenant_key: str
    source_snapshot_id: str
    payload_checksum: str
    record_count: int
    filestore_file_count: int
    filestore_bytes: int
    resource_counts: dict[str, int]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "PASS",
            "tenant_key": self.tenant_key,
            "source_snapshot_id": self.source_snapshot_id,
            "payload_checksum": self.payload_checksum,
            "record_count": self.record_count,
            "filestore_file_count": self.filestore_file_count,
            "filestore_bytes": self.filestore_bytes,
            "resource_counts": dict(sorted(self.resource_counts.items())),
        }


def canonical_manifest_bytes(manifest: dict[str, Any]) -> bytes:
    return json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def safe_relative_path(value: Any) -> str:
    text = str(value or "")
    path = PurePosixPath(text)
    if (
        not text
        or path.is_absolute()
        or ".." in path.parts
        or "." in path.parts
        or text != path.as_posix()
        or path.parts[0] not in {"records", "filestore"}
    ):
        raise TenantPayloadError("TPV1_PATH_UNSAFE")
    return text


def _require_string(payload: dict[str, Any], key: str, pattern: re.Pattern[str] | None = None) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise TenantPayloadError(f"TPV1_MANIFEST_FIELD_INVALID:{key}")
    if pattern and not pattern.fullmatch(value):
        raise TenantPayloadError(f"TPV1_MANIFEST_FIELD_INVALID:{key}")
    return value


def _require_non_negative_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise TenantPayloadError(f"TPV1_MANIFEST_FIELD_INVALID:{key}")
    return value


def _walk_keys(value: Any, path: str = "manifest") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, item in value.items():
            item_path = f"{path}.{key}"
            yield key.lower(), item_path
            yield from _walk_keys(item, item_path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_keys(item, f"{path}[{index}]")


def reject_secret_fields(value: Any, path: str) -> None:
    for key, item_path in _walk_keys(value, path):
        if key in FORBIDDEN_FIELD_NAMES or key.endswith("_password") or key.endswith("_token"):
            raise TenantPayloadError(f"TPV1_SECRET_FIELD_FORBIDDEN:{item_path}")


def validate_manifest(manifest: dict[str, Any], expected_tenant_key: str | None = None) -> None:
    if not isinstance(manifest, dict):
        raise TenantPayloadError("TPV1_MANIFEST_NOT_OBJECT")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise TenantPayloadError("TPV1_SCHEMA_INCOMPATIBLE")
    tenant_key = _require_string(manifest, "tenant_key", TENANT_RE)
    if expected_tenant_key and tenant_key != expected_tenant_key:
        raise TenantPayloadError("TPV1_TENANT_MISMATCH")
    customer_module = _require_string(manifest, "customer_module")
    if customer_module != f"sce_customer_{tenant_key}":
        raise TenantPayloadError("TPV1_CUSTOMER_MODULE_MISMATCH")
    for key in (
        "payload_id",
        "customer_module_version",
        "source_database_fingerprint",
        "created_at_utc",
        "source_version",
    ):
        _require_string(manifest, key)
    _require_string(manifest, "source_snapshot_id", SNAPSHOT_RE)
    if manifest.get("product_interface_version") != PRODUCT_INTERFACE_VERSION:
        raise TenantPayloadError("TPV1_PRODUCT_INTERFACE_INCOMPATIBLE")
    _require_string(manifest, "payload_checksum", SHA256_RE)
    for key in ("filestore_file_count", "filestore_bytes"):
        _require_non_negative_int(manifest, key)
    for key in ("record_counts", "amount_summaries", "relationship_summaries"):
        if not isinstance(manifest.get(key), dict):
            raise TenantPayloadError(f"TPV1_MANIFEST_FIELD_INVALID:{key}")
    if any(
        not KEY_RE.fullmatch(str(key))
        or not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
        for key, value in manifest["record_counts"].items()
    ):
        raise TenantPayloadError("TPV1_RECORD_COUNTS_INVALID")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise TenantPayloadError("TPV1_FILES_INVALID")
    paths: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            raise TenantPayloadError("TPV1_FILE_ENTRY_INVALID")
        path = safe_relative_path(item.get("path"))
        if path in paths:
            raise TenantPayloadError("TPV1_FILE_DUPLICATE")
        paths.add(path)
        if not SHA256_RE.fullmatch(str(item.get("sha256") or "")):
            raise TenantPayloadError(f"TPV1_FILE_CHECKSUM_INVALID:{path}")
        for key in ("bytes", "rows"):
            if not isinstance(item.get(key), int) or isinstance(item.get(key), bool) or item[key] < 0:
                raise TenantPayloadError(f"TPV1_FILE_METADATA_INVALID:{path}")
    order = manifest.get("import_order")
    record_paths = {path for path in paths if path.startswith("records/")}
    if not isinstance(order, list) or len(order) != len(set(order)):
        raise TenantPayloadError("TPV1_IMPORT_ORDER_INVALID")
    if {safe_relative_path(path) for path in order} != record_paths:
        raise TenantPayloadError("TPV1_IMPORT_ORDER_INCOMPLETE")
    encryption = manifest.get("encryption")
    if not isinstance(encryption, dict):
        raise TenantPayloadError("TPV1_ENCRYPTION_REQUIRED")
    if encryption.get("at_rest_encrypted") is not True:
        raise TenantPayloadError("TPV1_ENCRYPTION_REQUIRED")
    if encryption.get("algorithm") in {None, "", "none", "plaintext"} or not encryption.get("key_id"):
        raise TenantPayloadError("TPV1_ENCRYPTION_REQUIRED")
    if manifest.get("signature_algorithm") not in {"hmac-sha256", "ed25519"}:
        raise TenantPayloadError("TPV1_SIGNATURE_ALGORITHM_UNSUPPORTED")
    _require_string(manifest, "signature_key_id")
    reject_secret_fields(manifest, "manifest")


def _load_checksums(root: Path) -> tuple[bytes, dict[str, str]]:
    raw = (root / CHECKSUMS_NAME).read_bytes()
    if not raw or not raw.endswith(b"\n"):
        raise TenantPayloadError("TPV1_CHECKSUMS_FORMAT_INVALID")
    checksums: dict[str, str] = {}
    previous = ""
    for line_number, raw_line in enumerate(raw.splitlines(), 1):
        try:
            line = raw_line.decode("ascii")
        except UnicodeDecodeError as exc:
            raise TenantPayloadError("TPV1_CHECKSUMS_FORMAT_INVALID") from exc
        parts = line.split("  ", 1)
        if len(parts) != 2 or not SHA256_RE.fullmatch(parts[0]):
            raise TenantPayloadError(f"TPV1_CHECKSUMS_FORMAT_INVALID:{line_number}")
        path = safe_relative_path(parts[1])
        if path <= previous or path in checksums:
            raise TenantPayloadError("TPV1_CHECKSUMS_ORDER_INVALID")
        previous = path
        checksums[path] = parts[0]
    return raw, checksums


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _verify_tree(root: Path, declared_paths: set[str]) -> None:
    for path in root.rglob("*"):
        if path.is_symlink():
            raise TenantPayloadError(f"TPV1_SYMLINK_FORBIDDEN:{path.relative_to(root).as_posix()}")
        relative = path.relative_to(root).as_posix()
        if len(path.relative_to(root).parts) == 1 and path.name not in ALLOWED_TOP_LEVEL:
            raise TenantPayloadError(f"TPV1_UNEXPECTED_TOP_LEVEL:{relative}")
        if path.is_file() and relative not in declared_paths | {MANIFEST_NAME, CHECKSUMS_NAME, SIGNATURE_NAME}:
            raise TenantPayloadError(f"TPV1_UNDECLARED_FILE:{relative}")


def _validate_record_line(resource: str, line: Any, line_number: int) -> str:
    location = f"records/{resource}.jsonl:{line_number}"
    if not isinstance(line, dict):
        raise TenantPayloadError(f"TPV1_RECORD_NOT_OBJECT:{location}")
    allowed = {"external_key", "values", "relationships", "content_checksum", "file"}
    if set(line) - allowed:
        raise TenantPayloadError(f"TPV1_RECORD_FIELD_UNKNOWN:{location}")
    external_key = str(line.get("external_key") or "")
    if not KEY_RE.fullmatch(external_key):
        raise TenantPayloadError(f"TPV1_EXTERNAL_KEY_INVALID:{location}")
    if not isinstance(line.get("values"), dict) or not isinstance(line.get("relationships", {}), dict):
        raise TenantPayloadError(f"TPV1_RECORD_SHAPE_INVALID:{location}")
    reject_secret_fields(line["values"], location)
    for field_name, reference in line.get("relationships", {}).items():
        if not KEY_RE.fullmatch(str(field_name)):
            raise TenantPayloadError(f"TPV1_RELATION_FIELD_INVALID:{location}")
        references = reference if isinstance(reference, list) else [reference]
        if not references or any(not isinstance(item, str) or not REFERENCE_RE.fullmatch(item) for item in references):
            raise TenantPayloadError(f"TPV1_RELATION_REFERENCE_INVALID:{location}")
    file_meta = line.get("file")
    if file_meta is not None:
        if resource != "attachments" or not isinstance(file_meta, dict) or set(file_meta) != {"path", "sha256", "bytes"}:
            raise TenantPayloadError(f"TPV1_ATTACHMENT_FILE_INVALID:{location}")
        path = safe_relative_path(file_meta.get("path"))
        if not path.startswith("filestore/") or not SHA256_RE.fullmatch(str(file_meta.get("sha256") or "")):
            raise TenantPayloadError(f"TPV1_ATTACHMENT_FILE_INVALID:{location}")
        if not isinstance(file_meta.get("bytes"), int) or isinstance(file_meta.get("bytes"), bool) or file_meta["bytes"] < 0:
            raise TenantPayloadError(f"TPV1_ATTACHMENT_FILE_INVALID:{location}")
    expected = hashlib.sha256(
        json.dumps(
            {"values": line["values"], "relationships": line.get("relationships", {}), "file": file_meta},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if line.get("content_checksum") != expected:
        raise TenantPayloadError(f"TPV1_RECORD_CONTENT_CHECKSUM_MISMATCH:{location}")
    return external_key


def _verify_signature(manifest: dict[str, Any], signature: bytes, *, hmac_key: bytes | None, public_key: Path | None) -> None:
    algorithm = manifest["signature_algorithm"]
    canonical = canonical_manifest_bytes(manifest)
    if algorithm == "hmac-sha256":
        if os.environ.get("SC_TENANT_PAYLOAD_TEST_MODE") != "1":
            raise TenantPayloadError("TPV1_HMAC_TEST_MODE_REQUIRED")
        if not hmac_key:
            raise TenantPayloadError("TPV1_SIGNATURE_KEY_REQUIRED")
        supplied = signature.decode("ascii", errors="ignore").strip()
        expected = hmac.new(hmac_key, canonical, hashlib.sha256).hexdigest()
        if not SHA256_RE.fullmatch(supplied) or not hmac.compare_digest(supplied, expected):
            raise TenantPayloadError("TPV1_SIGNATURE_INVALID")
        return
    if not public_key or not public_key.is_file():
        raise TenantPayloadError("TPV1_PUBLIC_KEY_REQUIRED")
    with tempfile.TemporaryDirectory(prefix="tenant-payload-signature-") as tmp:
        message_path = Path(tmp) / "manifest.canonical"
        signature_path = Path(tmp) / "signature"
        message_path.write_bytes(canonical)
        signature_path.write_bytes(signature)
        result = subprocess.run(
            [
                "openssl",
                "pkeyutl",
                "-verify",
                "-pubin",
                "-inkey",
                str(public_key),
                "-rawin",
                "-in",
                str(message_path),
                "-sigfile",
                str(signature_path),
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    if result.returncode != 0:
        raise TenantPayloadError("TPV1_SIGNATURE_INVALID")


def validate_payload_directory(
    payload_root: Path,
    *,
    expected_tenant_key: str | None = None,
    hmac_key: bytes | None = None,
    public_key: Path | None = None,
) -> ValidationSummary:
    if payload_root.is_symlink() or not payload_root.is_dir():
        raise TenantPayloadError("TPV1_ROOT_INVALID")
    root = payload_root.resolve(strict=True)
    try:
        manifest = json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"))
        signature = (root / SIGNATURE_NAME).read_bytes()
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TenantPayloadError("TPV1_CONTROL_FILE_INVALID") from exc
    validate_manifest(manifest, expected_tenant_key)
    checksum_bytes, checksums = _load_checksums(root)
    payload_checksum = hashlib.sha256(checksum_bytes).hexdigest()
    if manifest["payload_checksum"] != payload_checksum:
        raise TenantPayloadError("TPV1_PAYLOAD_CHECKSUM_MISMATCH")
    files = {item["path"]: item for item in manifest["files"]}
    if set(files) != set(checksums):
        raise TenantPayloadError("TPV1_FILE_INVENTORY_MISMATCH")
    _verify_tree(root, set(files))
    resource_counts: dict[str, int] = {}
    amount_totals: dict[str, Decimal] = {key: Decimal() for key in manifest["amount_summaries"]}
    relationship_totals: dict[str, int] = {}
    all_external_keys: set[str] = set()
    attachment_files: set[str] = set()
    filestore_count = filestore_bytes = 0
    for relative, expected_digest in checksums.items():
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise TenantPayloadError(f"TPV1_FILE_TYPE_INVALID:{relative}")
        digest, size = _sha256_file(path)
        metadata = files[relative]
        if digest != expected_digest or digest != metadata["sha256"] or size != metadata["bytes"]:
            raise TenantPayloadError(f"TPV1_FILE_INTEGRITY_MISMATCH:{relative}")
        if relative.startswith("records/"):
            if not relative.endswith(".jsonl"):
                raise TenantPayloadError(f"TPV1_RECORD_FILE_EXTENSION_INVALID:{relative}")
            resource = Path(relative).stem
            count = 0
            with path.open("r", encoding="utf-8") as handle:
                for line_number, text in enumerate(handle, 1):
                    try:
                        item = json.loads(text)
                    except json.JSONDecodeError as exc:
                        raise TenantPayloadError(f"TPV1_JSONL_INVALID:{relative}:{line_number}") from exc
                    external_key = _validate_record_line(resource, item, line_number)
                    qualified = f"{resource}:{external_key}"
                    if qualified in all_external_keys:
                        raise TenantPayloadError(f"TPV1_EXTERNAL_KEY_DUPLICATE:{relative}:{line_number}")
                    all_external_keys.add(qualified)
                    for summary_key in amount_totals:
                        summary_resource, summary_field = summary_key.split(".", 1)
                        if summary_resource == resource and summary_field in item.get("values", {}):
                            try:
                                amount_totals[summary_key] += Decimal(str(item["values"][summary_field]))
                            except (InvalidOperation, TypeError, ValueError) as exc:
                                raise TenantPayloadError(f"TPV1_AMOUNT_SUMMARY_VALUE_INVALID:{summary_key}") from exc
                    for relation_name, reference_value in item.get("relationships", {}).items():
                        summary_key = f"{resource}.{relation_name}"
                        relationship_totals[summary_key] = relationship_totals.get(summary_key, 0) + (
                            len(reference_value) if isinstance(reference_value, list) else 1
                        )
                    if resource == "attachments" and item.get("file"):
                        file_meta = item["file"]
                        if file_meta["path"] not in files:
                            raise TenantPayloadError(f"TPV1_ATTACHMENT_FILE_MISSING:{relative}:{line_number}")
                        declared_file = files[file_meta["path"]]
                        if declared_file["sha256"] != file_meta["sha256"] or declared_file["bytes"] != file_meta["bytes"]:
                            raise TenantPayloadError(f"TPV1_ATTACHMENT_FILE_MISMATCH:{relative}:{line_number}")
                        attachment_files.add(file_meta["path"])
                    count += 1
            if count != metadata["rows"] or manifest["record_counts"].get(resource) != count:
                raise TenantPayloadError(f"TPV1_RECORD_COUNT_MISMATCH:{relative}")
            resource_counts[resource] = count
        else:
            if metadata["rows"] != 0:
                raise TenantPayloadError(f"TPV1_FILE_METADATA_INVALID:{relative}")
            filestore_count += 1
            filestore_bytes += size
    if set(resource_counts) != set(manifest["record_counts"]):
        raise TenantPayloadError("TPV1_RECORD_RESOURCE_MISMATCH")
    for key, total in amount_totals.items():
        try:
            expected = Decimal(str(manifest["amount_summaries"][key]))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise TenantPayloadError(f"TPV1_AMOUNT_SUMMARY_INVALID:{key}") from exc
        if total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) != expected.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ):
            raise TenantPayloadError(f"TPV1_AMOUNT_SUMMARY_MISMATCH:{key}")
    if dict(sorted(relationship_totals.items())) != dict(sorted(manifest["relationship_summaries"].items())):
        raise TenantPayloadError("TPV1_RELATIONSHIP_SUMMARY_MISMATCH")
    if filestore_count != manifest["filestore_file_count"] or filestore_bytes != manifest["filestore_bytes"]:
        raise TenantPayloadError("TPV1_FILESTORE_SUMMARY_MISMATCH")
    if attachment_files != {path for path in files if path.startswith("filestore/")}:
        raise TenantPayloadError("TPV1_FILESTORE_ATTACHMENT_INDEX_MISMATCH")
    _verify_signature(manifest, signature, hmac_key=hmac_key, public_key=public_key)
    return ValidationSummary(
        tenant_key=manifest["tenant_key"],
        source_snapshot_id=manifest["source_snapshot_id"],
        payload_checksum=payload_checksum,
        record_count=sum(resource_counts.values()),
        filestore_file_count=filestore_count,
        filestore_bytes=filestore_bytes,
        resource_counts=resource_counts,
    )
