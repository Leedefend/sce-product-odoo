#!/usr/bin/env python3
"""Idempotently configure the Gitee side of the self-hosted CI boundary."""

from __future__ import annotations

import argparse
import json
import stat
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


API = "https://gitee.com/api/v5"
OWNER = "leegege"
REPO = "sce-product-odoo"
BRANCH = "fix/clean-repository-ci-governance"
WEBHOOK_URL = "https://1.95.2.123/hooks/gitee"
SERVER = "root@1.95.2.123"


class ApiError(RuntimeError):
    def __init__(self, method: str, path: str, status: int, message: str = "") -> None:
        self.method = method
        self.path = path
        self.status = status
        self.message = message
        detail = f" status={status}"
        if message:
            detail += f" message={message}"
        super().__init__(f"Gitee API {method} {path} failed{detail}")


def read_token(path: Path) -> str:
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode not in {0o400, 0o600}:
        raise RuntimeError(f"token file mode must be 400 or 600, got {mode:o}")
    value = path.read_text(encoding="utf-8").strip()
    if "\n" in value or len(value) < 20:
        raise RuntimeError("token file must contain exactly one token")
    return value


def server_file(path: str) -> str:
    completed = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", SERVER, "cat", path],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def webhook_secret() -> str:
    env_text = server_file("/etc/gitee-ci/sce-product-odoo.env")
    for line in env_text.splitlines():
        if line.startswith("GITEE_WEBHOOK_SECRET="):
            value = line.split("=", 1)[1]
            if len(value) >= 32:
                return value
    raise RuntimeError("server WebHook secret is missing")


def api(
    method: str,
    path: str,
    token: str,
    fields: dict[str, Any] | None = None,
) -> Any:
    fields = {key: str(value).lower() if isinstance(value, bool) else str(value) for key, value in (fields or {}).items()}
    if method == "GET":
        query = urllib.parse.urlencode(fields)
        url = f"{API}{path}"
        if query:
            url += f"?{query}"
        data = None
    else:
        url = f"{API}{path}"
        data = urllib.parse.urlencode(fields).encode()
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Accept", "application/json")
    request.add_header("Authorization", f"token {token}")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        message = ""
        if raw:
            try:
                decoded = json.loads(raw)
                if isinstance(decoded, dict):
                    message = str(decoded.get("message", ""))
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass
        raise ApiError(method, path, exc.code, message) from exc
    if not body:
        return None
    return json.loads(body)


def validate_required_scopes(token: str) -> None:
    """Fail before any write and report every missing granular Gitee scope."""
    probes = {
        "keys": f"/repos/{OWNER}/{REPO}/keys",
        "hook": f"/repos/{OWNER}/{REPO}/hooks",
        "pull_requests": f"/repos/{OWNER}/{REPO}/pulls",
    }
    missing: list[str] = []
    for scope, path in probes.items():
        try:
            api("GET", path, token, {"per_page": 1})
        except ApiError as exc:
            if exc.status in {401, 403}:
                missing.append(scope)
                continue
            raise
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            "Gitee token lacks required scopes: "
            f"{joined}. Regenerate the token with these scopes before retrying; "
            "no repository changes were made."
        )


def ensure_deploy_key(token: str, public_key: str) -> int:
    keys = api("GET", f"/repos/{OWNER}/{REPO}/keys", token, {"per_page": 100})
    for item in keys:
        if item.get("key") == public_key or item.get("title") == "sce-product-odoo-ci-readonly":
            return int(item["id"])
    created = api(
        "POST",
        f"/repos/{OWNER}/{REPO}/keys",
        token,
        {"key": public_key, "title": "sce-product-odoo-ci-readonly"},
    )
    return int(created["id"])


def ensure_webhook(token: str, secret: str) -> int:
    hooks = api("GET", f"/repos/{OWNER}/{REPO}/hooks", token, {"per_page": 100})
    existing = next((item for item in hooks if item.get("url") == WEBHOOK_URL), None)
    fields = {
        "url": WEBHOOK_URL,
        "title": "sce-product-odoo-self-hosted-ci",
        "encryption_type": 1,
        "password": secret,
        "push_events": True,
        "tag_push_events": False,
        "issues_events": False,
        "note_events": False,
        "merge_requests_events": True,
    }
    if existing:
        hook_id = int(existing["id"])
        api("PATCH", f"/repos/{OWNER}/{REPO}/hooks/{hook_id}", token, fields)
        return hook_id
    created = api("POST", f"/repos/{OWNER}/{REPO}/hooks", token, fields)
    return int(created["id"])


def ensure_protected_main(token: str) -> None:
    api("PUT", f"/repos/{OWNER}/{REPO}/branches/main/protection", token)


def ensure_pull_request(token: str) -> tuple[int, str]:
    pulls = api(
        "GET",
        f"/repos/{OWNER}/{REPO}/pulls",
        token,
        {"state": "open", "head": BRANCH, "base": "main", "per_page": 100},
    )
    if pulls:
        item = pulls[0]
        return int(item["number"]), str(item.get("html_url") or item.get("url"))
    body = """Architecture Impact: P4 CI governance only
Layer Target: Gitee WebHook admission and exact-SHA self-hosted verification
Affected Modules: scripts/ci, scripts/verify, deploy/gitee-ci, Make governance

No product feature, attachment, RC image, or production deployment change.
"""
    created = api(
        "POST",
        f"/repos/{OWNER}/{REPO}/pulls",
        token,
        {
            "title": "ci: establish clean repository governance and self-hosted Gitee CI",
            "head": BRANCH,
            "base": "main",
            "body": body,
            "prune_source_branch": False,
            "draft": False,
            "squash": True,
        },
    )
    return int(created["number"]), str(created.get("html_url") or created.get("url"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token-file", type=Path, required=True)
    args = parser.parse_args()
    token = read_token(args.token_file)
    user = api("GET", "/user", token)
    if user.get("login") != OWNER:
        raise RuntimeError("Gitee token owner mismatch")
    repository = api("GET", f"/repos/{OWNER}/{REPO}", token)
    if repository.get("full_name", "").lower() != f"{OWNER}/{REPO}":
        raise RuntimeError("Gitee repository mismatch")
    validate_required_scopes(token)

    public_key = server_file("/etc/gitee-ci/id_ed25519.pub")
    key_id = ensure_deploy_key(token, public_key)
    hook_id = ensure_webhook(token, webhook_secret())
    ensure_protected_main(token)
    pr_number, pr_url = ensure_pull_request(token)
    api("POST", f"/repos/{OWNER}/{REPO}/hooks/{hook_id}/tests", token)
    print(f"[gitee_ci_repository] PASS deploy_key_id={key_id} webhook_id={hook_id} main_protected=true")
    print(f"[gitee_ci_repository] PR={pr_number} url={pr_url}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ApiError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f"[gitee_ci_repository] FAIL {exc}", file=sys.stderr)
        raise SystemExit(2) from None
