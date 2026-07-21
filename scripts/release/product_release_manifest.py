#!/usr/bin/env python3
"""Generate the repository-external manifest for a scanned product image."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_release_module():
    path = ROOT / "scripts" / "release" / "product_release.py"
    spec = importlib.util.spec_from_file_location("sce_product_release_manifest_source", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("product release reader unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-manifest", required=True, type=Path)
    parser.add_argument("--sbom", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    image = json.loads(args.image_manifest.read_text(encoding="utf-8"))
    release = load_release_module().load_release_config()
    if image.get("product_version") != release["product_version"]:
        raise SystemExit("RELEASE_MANIFEST_PRODUCT_VERSION_MISMATCH")
    payload = {
        "product_version": release["product_version"],
        "source_sha": image["source_sha"],
        "source_tree_sha": image["source_tree_sha"],
        "image_digest": image["image_digest"],
        "frontend_sha256": image["frontend_build_sha256"],
        "sbom_sha256": sha256_file(args.sbom),
        "module_version_matrix": image["module_version_matrix"],
        "tenant_payload_contract": release["contracts"]["tenant_payload"],
        "route_authority_contract": release["contracts"]["route_authority"],
        "built_at": image["build_time"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_sha = sha256_file(args.output)
    args.output.with_name("product-release-manifest.sha256").write_text(
        f"{manifest_sha}  {args.output.name}\n", encoding="utf-8"
    )
    print(f"[product.release.manifest] PASS sha256={manifest_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
