# Gitee Self-Hosted WebHook CI v1

Chinese: [gitee_webhook_ci_v1.md](gitee_webhook_ci_v1.md)

## Boundary

- Gitee is the primary code and PR entry point; GitHub is temporarily a mirror.
- Huawei node `1.95.2.123` runs the lightweight public guard for same-repository events. PR events continue with `pnpm install` and the full `make ci` professional gate after the public guard passes.
- This design does not use Gitee Go, consume hosted build minutes, or trigger RC, attachment, or production deployment work.
- WebHook CI only accepts `leegege/sce-product-odoo`, sender `leegege`, same-repository Push/PR events, and a full 40-character SHA.

## Security chain

1. Accept only JSON at `POST /hooks/gitee`, capped at 1 MiB.
2. Verify the signature and timestamp with Gitee's documented algorithm, accepting both the documented headers and the API-created hook's `sign`/`timestamp` query transport. A complete query signature is authoritative when present; otherwise use the headers. The clock skew is 300 seconds, and query signatures are excluded from access logs.
3. Reject reuse of a consumed signature timestamp.
4. Validate repository, sender, and event; deny fork PRs, deleted refs, and closed/merged PR events.
5. Persist only normalized SHA, event, and PR number in SQLite; never persist raw requests or plaintext secrets.
6. Execute duplicate events for a SHA once. If a PR event arrives after Push, upgrade the job from public to professional; even a running public job is followed by the professional gate. Recover incomplete queue entries after service restart.
7. Do not export the WebHook secret or reporting token to the worker.
8. Use only the fixed Gitee URL and verify the detached HEAD SHA before running gates.
9. Use an isolated temporary directory per run and retain logs/reports outside the repository.
10. Push events run only the public guard; only same-repository, owner-sent PR events run the professional gate, while forks are rejected before enqueue.

## Server state

Service: `gitee-webhook-ci.service`

```text
USER=gitee-ci
BIND=127.0.0.1:9080
HEALTH=http://127.0.0.1:9080/healthz
DB=/var/lib/gitee-ci/jobs.sqlite3
LOG=/var/log/gitee-ci
ARTIFACT=/var/lib/gitee-ci/artifacts
DEPLOY_KEY=/etc/gitee-ci/id_ed25519
SECRET=/etc/gitee-ci/sce-product-odoo.env
PUBLIC_HEALTH=https://1.95.2.123/healthz
WEBHOOK=https://1.95.2.123/hooks/gitee
```

The secret and private key remain server-local `0400/0440` files. They are not committed or printed in logs.
Nginx proxies only the exact WebHook path to the loopback service. Certbot obtains a
Let's Encrypt short-lived IP certificate and a systemd timer renews it automatically.

## Platform configuration status

Publicly trusted HTTPS, the read-only Deploy Key, signed WebHook, `main` protection, and the governance PR are complete. The configurator can verify these states idempotently. Gitee's built-in WebHook test uses a simulated payload for a different repository, so the repository allowlist correctly denies it; acceptance must use an exact SHA from a real same-repository Push or PR.

1. To recheck configuration, run `make gitee.ci.repository.configure GITEE_TOKEN_FILE=<0600-file>` with a temporary administrative token carrying `keys`, `hook`, `pull_requests`, and repository-management permissions.
2. Revoke the temporary administrative token after configuration; never copy it to the CI server.
3. Result comments/status reporting still require a separate least-privilege bot token; build jobs must not receive repository write access.

The command probes all required permissions before its first write. If permissions are insufficient, it lists all missing scopes and leaves the repository unchanged.

## Initial end-to-end evidence

A real same-repository event for governance PR `#1` completed at exact SHA
`736a310ab4f5a0844797d8178a34e3b92cc3320a`: read-only Deploy Key checkout succeeded,
history/secret/personal-data/customer-boundary and the 12/12 release scan passed, the job exited 0,
the temporary workspace was removed, and CI logs contained no credential markers.

## Verification

```bash
make verify.gitee.webhook.ci
make gitee.ci.server.status
make gitee.ci.https.status
```

The 13-case matrix covers positive header/query signature transport, API dual-transport precedence, Push-to-PR queue upgrades, invalid signatures, unexpected or repeated query parameters, expiry, replay, wrong repository, wrong sender, fork PRs, branch/command injection, deleted/closed events, and secret isolation.
