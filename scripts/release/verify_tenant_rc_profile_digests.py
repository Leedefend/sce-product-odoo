#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profiles", required=True)
    root = Path(parser.parse_args().profiles)
    required = ("RC-C01", "RC-C03", "RC-C04")
    rows = [json.loads((root / f"{name}.json").read_text(encoding="utf-8")) for name in required]
    digests = {row.get("product_image_digest") for row in rows}
    if len(digests) != 1 or not all(row.get("pass") for row in rows):
        raise SystemExit("TENANT_RC_PROFILE_DIGEST_MISMATCH")
    print(f"SAME_PRODUCT_IMAGE_DIGEST=true digest={next(iter(digests))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
