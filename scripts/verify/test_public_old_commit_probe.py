#!/usr/bin/env python3
from __future__ import annotations

import io
import unittest
import urllib.error
from unittest import mock

import public_old_commit_probe as probe


class PublicOldCommitProbeTests(unittest.TestCase):
    def test_http_404_is_returned_as_status(self) -> None:
        error = urllib.error.HTTPError("https://example.invalid/commit/old", 404, "not found", {}, io.BytesIO())
        with mock.patch.object(probe.urllib.request, "urlopen", side_effect=error):
            self.assertEqual(probe.status_for("https://example.invalid/commit/old", 1), 404)

    def test_main_fails_when_old_commit_is_still_public(self) -> None:
        with mock.patch.object(probe, "status_for", return_value=200):
            self.assertEqual(probe.main(["--url", "https://example.invalid/commit/old"]), 1)


if __name__ == "__main__":
    unittest.main()
