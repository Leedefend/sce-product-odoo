# Gitee Self-Hosted WebHook CI v1

Chinese: [gitee_webhook_ci_v1.md](gitee_webhook_ci_v1.md)

## Boundary

- Gitee is the primary code and PR entry point; GitHub is temporarily a mirror.
- Huawei node `1.95.2.123` runs the lightweight public guard. Professional gates remain a later step.
- This design does not use Gitee Go, consume hosted build minutes, or trigger RC, attachment, or production deployment work.
- WebHook CI only accepts `leegege/sce-product-odoo`, sender `leegege`, same-repository Push/PR events, and a full 40-character SHA.

## Security chain

1. Accept only JSON at `POST /hooks/gitee`, capped at 1 MiB.
2. Verify `X-Gitee-Timestamp` and `X-Gitee-Token` with Gitee's documented algorithm and a 300-second clock skew.
3. Reject reuse of a consumed signature timestamp.
4. Validate repository, sender, and event; deny fork PRs, deleted refs, and closed/merged PR events.
5. Persist only normalized SHA, event, and PR number in SQLite; never persist raw requests or plaintext secrets.
6. Execute each SHA once and recover incomplete queue entries after service restart.
7. Do not export the WebHook secret or reporting token to the worker.
8. Use only the fixed Gitee URL and verify the detached HEAD SHA before running gates.
9. Use an isolated temporary directory per run and retain logs/reports outside the repository.

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
```

The secret and private key remain server-local `0400/0440` files. They are not committed or printed in logs.

## Remaining platform configuration

All of the following are required before real events are enabled:

1. Provide publicly trusted HTTPS on `1.95.2.123`, reverse-proxied to `127.0.0.1:9080`.
2. Register the generated public key as a read-only repository Deploy Key.
3. Create a Gitee WebHook in signing-secret mode with only Push and Pull Request enabled.
4. Protect `main`: deny direct pushes, force pushes, and deletion; require PRs.
5. Store a least-privilege bot token on the server for result comments/status reporting; build jobs must not receive repository write access.

Without HTTPS and Gitee administrative authorization, the service remains loopback-only and must not be exposed over plain HTTP.

## Verification

```bash
make verify.gitee.webhook.ci
make gitee.ci.server.status
```

The negative matrix covers invalid signatures, expired requests, replay, wrong repository, wrong sender, fork PRs, branch/command injection, deleted/closed events, and secret isolation.
