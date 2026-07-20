# Tenant payload v1

`tenant_payload_v1` is the product-neutral exchange contract for importing an
authorized historical tenant snapshot. Product code owns validation,
checkpointing, audit, conflict handling and verification. A separately mounted
customer module owns source-version compatibility and declarative field and
relationship mappings. Neither repository owns the historical records or file
content.

## Package and encrypted envelope

The logical, decrypted staging directory is:

```text
tenant_payload_v1/
├── manifest.json
├── records/<resource>.jsonl
├── filestore/<content-addressed-file>
├── checksums.sha256
└── signature
```

The directory is transient plaintext. It must live outside every repository,
be readable only by the operator, be mounted read-only for validation/import,
and be securely removed after the controlled run. The durable artifact is an
encrypted envelope held in approved private artifact storage. Decryption keys
and signing private keys are never mounted together and are never written into
the package, Git, CI artifacts or logs.

`manifest.encryption` describes that durable envelope; it does not claim that a
decrypted staging directory is encrypted. Public CI may use only a synthetic
HMAC-signed package with `SC_TENANT_PAYLOAD_TEST_MODE=1`. Real packages require
an Ed25519 signature and the corresponding separately supplied public key.

## Manifest contract

The manifest identifies the schema, tenant, customer adapter version, product
interface version, source snapshot and a redacted source database fingerprint.
It freezes per-resource record counts, amount and relationship summaries,
distinct filestore file count and bytes, full file inventory, checksum-list
digest, encryption metadata and signature algorithm/key identifier. It must not
contain credentials, tokens, cookies, sessions, private keys, server addresses
or source connection strings.

Each JSONL row contains a stable external key, explicitly mapped values,
qualified relationships (`resource::external_key`), a canonical content
checksum and, for attachments, a content-addressed file reference. Names are
data, never identity. Multiple attachment records may safely reference the same
immutable content file; the manifest counts distinct files and the verifier
reports attachment-record and distinct-file counts separately.

## Command semantics

- `make tenant.payload.validate`: offline schema, signature, checksum, tree,
  JSONL, reference-shape, secret-field, record-count, amount-summary and
  relationship-summary validation.
- `make tenant.payload.plan`: read-only target comparison with create, exact
  bootstrap match, update, skip and conflict counts. It writes neither database
  nor filestore.
- `make tenant.payload.import`: explicit tenant/database/operator allowlists,
  stable-key upserts, chunk checkpoints, resumable interruption and explicit
  checksum approval for updates.
- `make tenant.payload.verify`: stable identities, mapped values, declared
  relationships, amount/relationship summaries, attachment bytes, company
  scope and pending-module verification.
- `make tenant.payload.filestore.reconcile`: an explicitly confirmed recovery
  operation that rehydrates only missing or checksum-mismatched attachment
  bytes from the already validated signed package, then requires a full verify
  before committing an aggregate reconciliation audit.

Plan, import and verify repeat the complete offline validation inside the Odoo
process. This closes the gap between preflight validation and database work.
Completed `tenant + payload checksum` imports are verified no-ops. A different
payload touching an existing external key is a blocker until its exact payload
checksum is approved.

Mapped scalar values and relationships are exact by default. A customer
adapter may explicitly declare currency rounding for a monetary source field;
verification then reports both the signed source summary and normalized target
summary, and emits a rule-only warning for any non-zero aggregate delta. A
many-to-many relationship may explicitly use `contains` verification only when
the product expands effective membership (for example, implied groups); every
declared identity must still be present. All other relationships remain exact.

An import that wrote every checkpoint but failed its first final verification
remains `failed`. A later explicit full verification may close it as
`completed` only after all records, fields, relationships, summaries and files
pass; the prior safe failure rule is retained in the acceptance report. A
failed import cannot otherwise resume without the explicit resume flag.

## Security and failure rules

The root and every file must be regular, declared and contained. Symlinks,
absolute paths, traversal, undeclared files, incompatible versions, signature
or checksum failures, unresolved relations, wrong tenant/company/database and
unmapped fields fail closed with rule identifiers only. No matching is done by
display name, login alias or fuzzy business fields.

The operator is a dedicated internal service user in the minimum importer
group, not a system administrator. The engine does not use global `sudo`.
The sole elevated boundary is a field-allowlisted `res.users` create/update
operation required by Odoo's protected user internals; it rejects passwords
and TOTP material and immediately returns to the operator-scoped environment.
Customer ACLs grant only the declared model operations and no unlink. Odoo owns
filestore placement; failed attachment transactions remove newly written
content, while confirmed checkpoints commit database and filestore as a pair.

Reports and batch records retain identifiers, checksums, states, checkpoints
and aggregate counters only. They never retain the record payload or sensitive
field values.

Database and filestore recovery is always paired. Backup and restore commands
use an explicit database allowlist, checksum both artifacts, compare a safe
pre-import fingerprint after restore, record RTO, and never treat a database or
filestore-only restore as success.
