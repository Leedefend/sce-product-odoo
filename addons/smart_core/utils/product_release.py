from __future__ import annotations

import os
import re
from pathlib import Path


_VERSION_RE = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
_VERSION_PATHS = (
    Path(__file__).resolve().parents[3] / "VERSION",
    Path("/opt/sce-product/VERSION"),
)


def _product_version() -> str:
    environment_value = str(os.getenv("SC_PRODUCT_VERSION") or "").strip()
    candidates = [environment_value] if environment_value else []
    for path in _VERSION_PATHS:
        try:
            candidates.append(path.read_text(encoding="utf-8").strip())
        except OSError:
            continue
    for value in candidates:
        if _VERSION_RE.fullmatch(value):
            return value
    raise RuntimeError("product version unavailable")


def _source_revision() -> str:
    value = str(os.getenv("SC_SOURCE_REVISION") or "").strip().lower()
    return value if _REVISION_RE.fullmatch(value) else "unknown"


def runtime_product_identity() -> dict[str, str]:
    return {
        "product_version": _product_version(),
        "source_revision": _source_revision(),
    }
