#!/usr/bin/env python3
"""Compress a file with the system libzstd without requiring the zstd CLI."""

from __future__ import annotations

import argparse
import ctypes
import ctypes.util
from pathlib import Path


def library() -> ctypes.CDLL:
    name = ctypes.util.find_library("zstd")
    if not name:
        raise RuntimeError("libzstd is not available")
    lib = ctypes.CDLL(name)
    lib.ZSTD_compressBound.argtypes = (ctypes.c_size_t,)
    lib.ZSTD_compressBound.restype = ctypes.c_size_t
    lib.ZSTD_compress.argtypes = (
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.c_int,
    )
    lib.ZSTD_compress.restype = ctypes.c_size_t
    lib.ZSTD_isError.argtypes = (ctypes.c_size_t,)
    lib.ZSTD_isError.restype = ctypes.c_uint
    lib.ZSTD_getErrorName.argtypes = (ctypes.c_size_t,)
    lib.ZSTD_getErrorName.restype = ctypes.c_char_p
    return lib


def compress(source: Path, target: Path, level: int = 19) -> int:
    data = source.read_bytes()
    lib = library()
    source_buffer = ctypes.create_string_buffer(data)
    capacity = lib.ZSTD_compressBound(len(data))
    target_buffer = ctypes.create_string_buffer(capacity)
    size = lib.ZSTD_compress(target_buffer, capacity, source_buffer, len(data), level)
    if lib.ZSTD_isError(size):
        message = lib.ZSTD_getErrorName(size).decode("utf-8", errors="replace")
        raise RuntimeError(f"zstd compression failed: {message}")
    target.write_bytes(target_buffer.raw[:size])
    return int(size)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--level", type=int, default=19)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    size = compress(args.source, args.target, args.level)
    print(f"[zstd_compress] PASS bytes={size} level={args.level}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
