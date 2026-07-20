#!/usr/bin/env python3
"""Verify that a deleted repository's old public commit URL returns 404."""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request


def status_for(url: str, timeout: float) -> int:
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "sce-clean-history-probe/1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--expected-status", type=int, default=404)
    parser.add_argument("--timeout", type=float, default=15.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        status = status_for(args.url, args.timeout)
    except OSError as exc:
        print(f"[public_old_commit_probe] FAIL network={type(exc).__name__}", file=sys.stderr)
        return 2
    if status != args.expected_status:
        print(
            f"[public_old_commit_probe] FAIL status={status} expected={args.expected_status}",
            file=sys.stderr,
        )
        return 1
    print(f"[public_old_commit_probe] PASS status={status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
