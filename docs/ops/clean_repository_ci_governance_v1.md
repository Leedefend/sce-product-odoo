# Clean Repository CI Governance

## Scope

This control applies to the public `Leedefend/sce-product-odoo` repository and
implements CLEAN-REPO-01F/01G only. It does not authorize attachment recovery,
release-candidate image construction, or production deployment.

## Trust boundary

Public pull-request code is untrusted. Approval of a fork workflow is not a
sandbox boundary and must never authorize that code to execute on a
self-hosted runner. Unknown external fork workflows must not be manually
approved for self-hosted execution.

CI is split into two layers:

1. `public_guard` uses a fresh GitHub-hosted runner, read-only `GITHUB_TOKEN`,
   no repository secrets, no private checkout, and no persisted credentials.
   It performs history, secret, personal-data, product/customer-boundary, and
   workflow-policy checks.
2. `professional_quality_gate` first executes
   `professional_authorization` on GitHub-hosted infrastructure. The
   self-hosted job is eligible only when the repository is
   `Leedefend/sce-product-odoo`, the actor is `Leedefend`, and a pull request's
   head repository is the same repository. A fork fails authorization and
   never receives a self-hosted job.

The self-hosted runner must be single-purpose. Prefer an ephemeral runner for
each professional run. A persistent runner must be treated as replaceable and
must not contain production credentials, production SSH keys, user passwords,
or reusable credentials outside the minimum read-only CI scope.

## Repository Actions settings

Required repository settings under **Settings → Actions → General**:

- Actions are restricted to repository-local actions and GitHub-authored
  actions.
- Every referenced action is pinned to a full 40-character commit SHA.
- Default `GITHUB_TOKEN` permission is read-only contents/packages.
- GitHub Actions cannot create or approve pull requests.
- All external contributors require workflow approval.
- No unknown external workflow may be approved to use self-hosted runners.
- Artifact and log retention is seven days unless an audit requirement
  explicitly establishes a shorter period.

Every workflow explicitly declares:

```yaml
permissions:
  contents: read
```

`pull_request_target`, workflow pushes to `main`, floating action tags, fork
access to secrets, and production credentials are prohibited.

## Secrets and credentials

The clean repository starts with no Actions secrets or variables. Add only a
credential that an enabled job demonstrably needs:

- Gitee checkout: use anonymous public HTTPS where possible. If rate or policy
  constraints require credentials, use a repository-scoped read-only key.
- Private customer package: use a read-only deploy key limited to that single
  private repository; it must not write any branch and must be rotatable.
- Test secrets: generate ephemeral values inside the job when possible.
- Notification credentials: add only after a corresponding approved workflow
  exists.

Do not restore old-system credentials, production database passwords,
production SSH keys, real user passwords, or caches exported from the deleted
repository. Logs and diagnostic output must not print credential-bearing
remote URLs.

## History guards

`make verify.repository.clean_history` is a normal development and public CI
gate. It scans all reachable refs with `git rev-list --objects --all`, verifies
the object database with `git fsck --full --no-reflogs`, and rejects forbidden
paths, customer runtime carriers, customer identifiers in product runtime,
secret and personal-data patterns, real `.env` files, archives, database or
filestore payload paths, and oversized blobs.

`make verify.repository.release_hygiene` is intentionally restricted to
release/RC entry points. In addition to reachable history it rejects reflog-only
commits, unreachable objects, tags, and stale remote-tracking refs. Harmless
dangling objects therefore do not block `make ci.local.quick`, but they must be
removed by using a fresh clone before release or RC construction.

Diagnostics report only rule IDs, paths, object prefixes, and classifications;
matching secret or personal-data values are never printed.

## Main protection

The `main` branch must require pull requests, a current branch, and these
checks:

- `public_guard`
- `professional_authorization`
- `professional_quality_gate`

Force pushes and deletion are disabled, and administrators are subject to the
same protection. Because this owner-only public repository cannot require the
author to approve their own pull request, the pull-request approval count is
zero; required CI checks and strict up-to-date enforcement remain mandatory.

If GitHub rejects any rule because of the account plan, record the API response
in the external CLEAN-REPO evidence directory and retain `make pr.push` plus
the clean-history gates as compensating controls. A missing protection must
never be silently accepted.

## Self-hosted cleanup

The professional job uses a run-specific Compose project name. Its final step
removes only containers, volumes, and networks bearing that exact project
label, removes run-specific temporary files, and wipes the job workspace. It
does not access production projects, databases, images, or attachment stores.

## Recovery checklist

1. Confirm Actions restrictions, token permissions, fork approval policy, and
   artifact retention through the GitHub API.
2. Register a clean, single-purpose ephemeral runner with only the required
   labels.
3. Push the governance branch to GitHub and Gitee at the same SHA.
4. Open the pull request and require all three checks.
5. Merge through the protected branch; do not push directly to `main`.
6. Fast-forward Gitee `main` to the merged GitHub `main` SHA.
7. Clone both remotes into new directories and run the 12/12 product release
   scan again.
