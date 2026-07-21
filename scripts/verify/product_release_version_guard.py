#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {path.relative_to(ROOT)}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tracked_files() -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        text=True,
    )
    return [ROOT / item for item in output.splitlines() if item]


def main() -> int:
    errors: list[str] = []
    release = load("sce_product_release_guard", ROOT / "scripts" / "release" / "product_release.py")
    try:
        config = release.load_release_config()
    except ValueError as exc:
        print(f"[product.release.version] FAIL {exc}")
        return 1
    version = config["product_version"]
    version_token = re.compile(
        rf"(?<![0-9A-Za-z.^~<>=]){re.escape(version)}(?![0-9A-Za-z.-])"
    )
    duplicates = []
    for path in tracked_files():
        if path == ROOT / "VERSION" or not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if version_token.search(content):
            duplicates.append(str(path.relative_to(ROOT)))
    if duplicates:
        errors.append(f"product version duplicated outside VERSION: {duplicates}")

    dockerfile = (ROOT / "Dockerfile.production-candidate").read_text(encoding="utf-8")
    for marker in (
        'ARG PRODUCT_VERSION',
        'org.opencontainers.image.title="sce-product"',
        'org.opencontainers.image.version="${PRODUCT_VERSION}"',
        'org.opencontainers.image.revision="${SOURCE_SHA}"',
        'org.opencontainers.image.created="${BUILD_TIME}"',
    ):
        if marker not in dockerfile:
            errors.append(f"Docker release label input missing: {marker}")
    build = (ROOT / "scripts" / "release" / "immutable_candidate_build.sh").read_text(encoding="utf-8")
    for marker in (
        "product_release.py --version",
        "sce-product:${product_version}",
        "sce-product:sha-${short_sha}",
        'PRODUCT_VERSION=$product_version',
    ):
        if marker not in build:
            errors.append(f"candidate build version binding missing: {marker}")

    runtime = load("sce_runtime_product_release_guard", ROOT / "addons" / "smart_core" / "utils" / "product_release.py")
    old_version = os.environ.get("SC_PRODUCT_VERSION")
    old_revision = os.environ.get("SC_SOURCE_REVISION")
    revision = "b" * 40
    try:
        os.environ["SC_PRODUCT_VERSION"] = version
        os.environ["SC_SOURCE_REVISION"] = revision
        identity = runtime.runtime_product_identity()
    finally:
        if old_version is None:
            os.environ.pop("SC_PRODUCT_VERSION", None)
        else:
            os.environ["SC_PRODUCT_VERSION"] = old_version
        if old_revision is None:
            os.environ.pop("SC_SOURCE_REVISION", None)
        else:
            os.environ["SC_SOURCE_REVISION"] = old_revision
    if identity != {"product_version": version, "source_revision": revision}:
        errors.append("runtime product identity does not match VERSION/revision")

    if errors:
        print("[product.release.version] FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"[product.release.version] PASS version={version} duplicates=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
