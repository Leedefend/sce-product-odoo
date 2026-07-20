#!/usr/bin/env python3
"""Fail-closed Gitee WebHook receiver and single-host CI queue.

The HTTP handler validates a Gitee HMAC signature, timestamp, repository,
sender, event type, and exact commit SHA before persisting a minimal job.  A
single background worker executes a server-owned runner without passing any
branch name or command from the request.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import sqlite3
import subprocess
import threading
import time
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MAX_BODY_BYTES = 1_048_576
SUPPORTED_HOOKS = {"push_hooks", "merge_request_hooks"}


class Rejected(ValueError):
    """A request that must not enter the CI queue."""


def expected_signature(timestamp: str, secret: str) -> str:
    message = f"{timestamp}\n{secret}".encode()
    digest = hmac.new(secret.encode(), message, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def verify_signature(timestamp: str, token: str, secret: str) -> bool:
    # Preserve a literal base64 '+' while still accepting percent encoding.
    decoded = urllib.parse.unquote(token)
    return hmac.compare_digest(decoded, expected_signature(timestamp, secret))


def authentication_values(headers: Any, query: dict[str, list[str]]) -> tuple[str, str]:
    """Accept Gitee's documented headers and its API-created query transport."""
    unknown = set(query) - {"timestamp", "sign"}
    if unknown:
        raise Rejected("unexpected query parameter")
    for name, values in query.items():
        if len(values) != 1 or not values[0]:
            raise Rejected(f"invalid {name} parameter")

    header_timestamp = headers.get("X-Gitee-Timestamp", "")
    header_token = headers.get("X-Gitee-Token", "")
    query_timestamp = query.get("timestamp", [""])[0]
    query_token = query.get("sign", [""])[0]
    if bool(header_timestamp) != bool(header_token):
        raise Rejected("incomplete header authentication")
    if bool(query_timestamp) != bool(query_token):
        raise Rejected("incomplete query authentication")
    if header_timestamp and query_timestamp:
        if header_timestamp != query_timestamp or header_token != query_token:
            raise Rejected("conflicting authentication")
    timestamp = header_timestamp or query_timestamp
    token = header_token or query_token
    if not timestamp or not token:
        raise Rejected("missing authentication")
    return timestamp, token


def require_fresh_timestamp(timestamp: str, now_ms: int, max_skew_seconds: int) -> None:
    if not timestamp.isdigit():
        raise Rejected("invalid timestamp")
    skew_ms = abs(now_ms - int(timestamp))
    if skew_ms > max_skew_seconds * 1000:
        raise Rejected("expired timestamp")


def nested(data: dict[str, Any], *path: str) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def normalized_job(
    payload: dict[str, Any],
    *,
    allowed_repository: str,
    allowed_sender: str,
) -> dict[str, Any]:
    hook_name = payload.get("hook_name")
    if hook_name not in SUPPORTED_HOOKS:
        raise Rejected("unsupported event")

    repository = nested(payload, "repository", "full_name") or nested(
        payload, "project", "full_name"
    )
    if repository != allowed_repository:
        raise Rejected("repository not allowed")

    sender = (
        nested(payload, "sender", "login")
        or nested(payload, "sender", "username")
        or nested(payload, "sender", "user_name")
    )
    if sender != allowed_sender:
        raise Rejected("sender not allowed")

    pr_number: int | None = None
    if hook_name == "push_hooks":
        if payload.get("deleted") is True:
            raise Rejected("deleted ref has no build")
        sha = payload.get("after")
    else:
        action = str(payload.get("action") or "").lower()
        if action in {"merge", "close", "merged", "closed"}:
            raise Rejected("closed pull request has no build")
        source_repository = (
            nested(payload, "pull_request", "head", "repo", "full_name")
            or nested(payload, "pull_request", "head", "repository", "full_name")
            or nested(payload, "pull_request", "source_repo", "full_name")
        )
        if source_repository != allowed_repository:
            raise Rejected("fork pull request denied")
        sha = (
            nested(payload, "pull_request", "head", "sha")
            or nested(payload, "pull_request", "last_commit", "id")
            or nested(payload, "pull_request", "head", "commit", "id")
        )
        number = payload.get("number") or nested(payload, "pull_request", "number")
        if not isinstance(number, int) or number < 1:
            raise Rejected("invalid pull request number")
        pr_number = number

    if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
        raise Rejected("invalid commit sha")

    return {
        "sha": sha,
        "hook_name": hook_name,
        "repository": repository,
        "sender": sender,
        "pr_number": pr_number,
    }


class Queue:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    sha TEXT PRIMARY KEY,
                    hook_name TEXT NOT NULL,
                    repository TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    pr_number INTEGER,
                    status TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    started_at INTEGER,
                    completed_at INTEGER,
                    exit_code INTEGER
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS deliveries (
                    signature_timestamp TEXT PRIMARY KEY,
                    received_at INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                "UPDATE jobs SET status = 'pending', started_at = NULL "
                "WHERE status = 'running'"
            )

    def enqueue(self, job: dict[str, Any], signature_timestamp: str) -> bool:
        with self.connect() as connection:
            delivery = connection.execute(
                "INSERT OR IGNORE INTO deliveries (signature_timestamp, received_at) VALUES (?, ?)",
                (signature_timestamp, int(time.time())),
            )
            if delivery.rowcount != 1:
                raise Rejected("replayed request")
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO jobs
                (sha, hook_name, repository, sender, pr_number, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'pending', ?)
                """,
                (
                    job["sha"],
                    job["hook_name"],
                    job["repository"],
                    job["sender"],
                    job["pr_number"],
                    int(time.time()),
                ),
            )
            return cursor.rowcount == 1

    def claim(self) -> dict[str, Any] | None:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM jobs WHERE status = 'pending' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            connection.execute(
                "UPDATE jobs SET status = 'running', started_at = ? WHERE sha = ?",
                (int(time.time()), row["sha"]),
            )
            connection.commit()
            return dict(row)

    def complete(self, sha: str, exit_code: int) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE jobs SET status = ?, completed_at = ?, exit_code = ? WHERE sha = ?",
                ("passed" if exit_code == 0 else "failed", int(time.time()), exit_code, sha),
            )


class Application:
    def __init__(self) -> None:
        self.secret = required_env("GITEE_WEBHOOK_SECRET")
        self.allowed_repository = required_env("GITEE_ALLOWED_REPOSITORY")
        self.allowed_sender = required_env("GITEE_ALLOWED_SENDER")
        self.endpoint = os.environ.get("GITEE_WEBHOOK_PATH", "/hooks/gitee")
        self.max_skew_seconds = int(os.environ.get("GITEE_WEBHOOK_MAX_SKEW_SECONDS", "300"))
        self.runner = Path(required_env("GITEE_CI_RUNNER"))
        self.log_dir = Path(os.environ.get("GITEE_CI_LOG_DIR", "/var/log/gitee-ci"))
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.queue = Queue(Path(os.environ.get("GITEE_CI_DB", "/var/lib/gitee-ci/jobs.sqlite3")))

    def accept(
        self,
        body: bytes,
        headers: Any,
        query: dict[str, list[str]] | None = None,
    ) -> tuple[bool, str]:
        timestamp, token = authentication_values(headers, query or {})
        require_fresh_timestamp(timestamp, int(time.time() * 1000), self.max_skew_seconds)
        if not verify_signature(timestamp, token, self.secret):
            raise Rejected("invalid signature")
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Rejected("invalid json") from exc
        if not isinstance(payload, dict):
            raise Rejected("invalid payload")
        job = normalized_job(
            payload,
            allowed_repository=self.allowed_repository,
            allowed_sender=self.allowed_sender,
        )
        inserted = self.queue.enqueue(job, timestamp)
        return inserted, job["sha"]

    def execute_once(self) -> bool:
        job = self.queue.claim()
        if job is None:
            return False
        sha = job["sha"]
        log_path = self.log_dir / f"{sha}.log"
        safe_env = {
            key: value
            for key, value in os.environ.items()
            if key not in {"GITEE_WEBHOOK_SECRET", "GITEE_STATUS_TOKEN"}
        }
        with log_path.open("ab") as log:
            completed = subprocess.run(
                [str(self.runner), sha, job["hook_name"], str(job["pr_number"] or "")],
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=safe_env,
                check=False,
            )
        self.queue.complete(sha, completed.returncode)
        return True


def required_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"missing required environment: {name}")
    return value


def handler_factory(application: Application) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "gitee-ci/1"

        def log_message(self, format: str, *args: Any) -> None:
            # The request target may contain a signature. Never log it.
            return

        def respond(self, status: HTTPStatus, message: str) -> None:
            data = json.dumps({"status": message}, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/healthz":
                self.respond(HTTPStatus.OK, "ok")
            else:
                self.respond(HTTPStatus.NOT_FOUND, "not_found")

        def do_POST(self) -> None:  # noqa: N802
            target = urllib.parse.urlsplit(self.path)
            if target.path != application.endpoint:
                self.respond(HTTPStatus.NOT_FOUND, "not_found")
                return
            try:
                query = urllib.parse.parse_qs(
                    target.query,
                    keep_blank_values=True,
                    strict_parsing=True,
                )
            except ValueError:
                self.respond(HTTPStatus.FORBIDDEN, "rejected")
                return
            content_type = self.headers.get("Content-Type", "")
            if not content_type.lower().startswith("application/json"):
                self.respond(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "rejected")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length < 2 or length > MAX_BODY_BYTES:
                self.respond(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "rejected")
                return
            try:
                inserted, sha = application.accept(self.rfile.read(length), self.headers, query)
            except Rejected as exc:
                print(
                    f"[gitee_webhook] peer={self.client_address[0]} "
                    f"status=rejected reason={exc}",
                    flush=True,
                )
                self.respond(HTTPStatus.FORBIDDEN, "rejected")
                return
            print(
                f"[gitee_webhook] peer={self.client_address[0]} "
                f"status={'queued' if inserted else 'duplicate'} sha={sha}",
                flush=True,
            )
            self.respond(HTTPStatus.ACCEPTED, "queued" if inserted else "duplicate")

    return Handler


def worker(application: Application, stop: threading.Event) -> None:
    while not stop.is_set():
        if not application.execute_once():
            stop.wait(1)


def serve(application: Application, bind: str, port: int) -> None:
    stop = threading.Event()
    thread = threading.Thread(target=worker, args=(application, stop), daemon=True)
    thread.start()
    server = ThreadingHTTPServer((bind, port), handler_factory(application))
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        stop.set()
        server.server_close()
        thread.join(timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bind", default=os.environ.get("GITEE_CI_BIND", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("GITEE_CI_PORT", "9080")))
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    application = Application()
    if args.once:
        application.execute_once()
        return 0
    serve(application, args.bind, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
