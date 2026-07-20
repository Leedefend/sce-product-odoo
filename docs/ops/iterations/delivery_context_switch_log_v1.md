# Delivery context switch log v1

This log records current product-repository implementation context only. Historical
customer delivery evidence belongs in private customer or payload repositories.

## 2026-07-18 — TENANT-SEC-01

- Branch: `feature/security-product-history-customer-payload-closure`
- Starting product commit: `28d453420371b1a92f3401551834f32866955540`
- Formal Product Layer: P4 operations delivery governance
- Layer Target: product payload boundary, build/release defaults, and CI gates
- Module: repository-wide delivery tooling; no customer module is embedded
- Reason: remove customer payload from the public product tree and prevent reintroduction
- Standard vs User-Specific: generic product guard only; customer facts remain external
- Why Here: the public product repository owns its build and release boundary
- Why Not Elsewhere: a private customer module cannot enforce the public repository boundary
- Blast Radius: tracked payload paths, product/demo defaults, Docker context, release defaults, and CI

## 2026-07-18 — TENANT-PRO-03

- Branch: `feature/tenant-demo-seed-fixture-boundary`
- Starting product commit: `6b296068d6062c5f5f537a6ca813a6fe0c3c02ce`
- Formal Product Layer: P1 industry product reference baseline plus P4 initialization, demo, and acceptance tooling
- Layer Target: `smart_construction_seed`, `smart_construction_demo`, acceptance fixture carriers, and authoritative module sets
- Module: product seed/demo modules and repository delivery verification; no customer payload module
- Reason: separate production reference data, explicit demo data, and disposable acceptance fixtures
- Standard vs User-Specific: generic product and non-production test responsibilities only; customer baselines remain external P2 modules
- Why Here: these carriers own install triggers, environment guards, idempotency, and uninstall scope
- Why Not Elsewhere: P0 must not gain construction data, P2 remains private, and P3 is not an initialization carrier
- Blast Radius: manifests, data files, hooks, seed migration, Compose/Make/release module sets, and acceptance runners

## 2026-07-19 — TENANT-PRO-04

- Branch: `feature/tenant-historical-payload-import-v1`
- Starting product commit: `6b7ec6a667f297cca4d3788f0fd3b0633097b94e`
- Formal Product Layer: P4 operations delivery mechanism with a P2 private customer adapter
- Layer Target: generic payload schema, offline validation, database plan/import/verify, audit checkpoints, and filestore integrity
- Module: `smart_core` generic protocol plus repository delivery tooling; no customer facts or payload bytes are embedded
- Reason: separate customer configuration from signed, encrypted, repeatable historical data delivery
- Standard vs User-Specific: product-neutral mechanism in the product repository; field mappings and source compatibility in the private customer module
- Why Here: the product owns the fail-closed import protocol, audit state, stable external identity, and CI boundary
- Why Not Elsewhere: customer adapters cannot redefine product security or filestore semantics, and real payloads cannot enter Git or public CI
- Blast Radius: one platform audit model, external identity mapping, Make operations, synthetic customer fixture, private adapter declaration, and Gitee main mirroring guard
- System-bound verification: offline tamper matrix, read-only conflict plans,
  four checkpoint interruption stages, dedicated-role denial, paired
  database/filestore recovery, pure-product installation, and a second
  anonymous synthetic tenant using the same engine
- Containment decision: monetary precision normalization and implied-role
  expansion require explicit adapter policies; defaults remain exact and
  fail-closed

## 2026-07-19 — TENANT-BOUNDARY-06

- Branch: `refactor/product-customer-legacy-boundary`
- Starting product commit: `fc948924c31cb5b9184ef465d718433ad42914da`
- Formal Product Layer: P1 standard construction product plus external P2 customer legacy extension
- Layer Target: `smart_construction_core` ownership inventory and generic history-count evidence tooling
- Module: product audit tooling; the concrete legacy bridge remains in the private customer repository
- Reason: move customer historical facts, views, ACL, navigation, and source metadata out of the standard product without rebuilding historical tables
- Standard vs User-Specific: generic migration protocol remains product-owned; legacy carriers are external customer-owned
- Why Here: the product repository must prove that its own runtime and install closure are customer-neutral
- Why Not Elsewhere: customer code cannot enforce the product repository boundary, while concrete customer module names and rules must not enter product code
- Blast Radius: model registration, standard-model legacy fields, XML records, ACL/rules, navigation, seeds, reports, migrations, and historical upgrade compatibility
- First checkpoint: 64 direct carrier models counted on an isolated frozen history copy; private Bridge V1 installed with zero copied schema or records and zero pending modules
- Second ownership batch checkpoint: move four self-contained P2 history facts (`business.fact.residual`, `finance.auxiliary.fact`, `payment.adjustment.fact`, and `workflow.detail.fact`) with their views and ACL into the private legacy carrier; retain exact model/table/field names and use the neutral handoff namespace during upgrade.
- Formal Product Layer: P2 customer legacy carrier with a P4 ownership-transfer migration; no customer fact implementation remains in the P1 module for this batch.
- Why Here / Why Not Elsewhere: the facts encode old-source tables and audit payloads that are not construction standards; only the product migration stages existing XML identities so the private module can claim them without copying tables or records.
- Blast Radius: four model registrations, five customer view files, eleven ACL entries, related actions/menus, and their Odoo metadata identities; containment is proven by pure-product static checks and isolated history-copy double upgrade fingerprints.
- Third ownership batch checkpoint: move the customer-only old-source staging fact and user-priority menu-plan model, views, ACL, and navigation into the private P2 legacy carrier.
- Formal Product Layer / Layer Target: P2 customer history configuration with P4 in-place XML-ID handoff; P1 no longer registers these two models.
- Blast Radius: two model/table identities, their dedicated UI carriers, three ACL entries, and one audit-list inheritance; product migration `17.0.0.64` transfers metadata ownership without record writes.
- Fourth ownership batch checkpoint: move the customer migration inventory and historical income-invoice fact into the private P2 legacy carrier while retaining their existing tables and technical identities.
- Formal Product Layer / Layer Target: P2 customer migration evidence and historical finance fact; the P1 product keeps neither implementation nor navigation for these carriers.
- Blast Radius: two model/table identities, three dedicated view files, ten ACL entries, actions/menus, and inventory seed XML identities; product migration `17.0.0.65` stages metadata ownership only and performs no business-record writes.
- Fifth ownership batch checkpoint: remove the historical financing fact and its legacy ledger navigation while retaining the canonical product `sc.financing.loan` capability.
- Formal Product Layer / Layer Target: P1 keeps the standard financing workflow; P2 owns the customer historical financing table, read-only views, and compatibility actions.
- Blast Radius: one model/table identity, two dedicated view carriers, three ACL entries, legacy actions/menus, and audit-list metadata; product migration `17.0.0.66` transfers ownership without copying records.
- Frozen-history correction: `sc.legacy.legacy_source.fact.staging` has no physical table and no customer-adapter consumer, so it is `DEAD_OR_UNUSED`, not an owned historical carrier. Product migration `17.0.0.67` retires only its metadata and fails closed if any target database actually contains the table.
- Sixth ownership batch checkpoint: move both historical invoice report facts and their two SQL-ID-specific summary projections to the private customer carrier.
- Formal Product Layer / Layer Target: these projections encode old-source SQL identities and read only customer history tables, so they are P2 reports rather than P1 canonical analytics.
- Blast Radius: four model/view identities, three XML view carriers, eighteen ACL entries, and four compatibility actions; product migration `17.0.0.68` performs an in-place metadata handoff without record copies.
- Seventh ownership batch checkpoint: move the two old-source tender facts and their customer-history guarantee summary out of P1 while retaining canonical `tender.bid` and `tender.guarantee` product workflows.
- Formal Product Layer / Layer Target: P2 owns old tender source codes, raw-fact administration, and the history-only projection; raw history navigation is restricted to customer configuration administrators.
- Blast Radius: three model/view identities, three dedicated XML carriers, customer-scoped ACLs, one legacy menu, and compatibility actions; product migration `17.0.0.69` stages metadata only.
- Overnight Q10 correction: an older Odoo registry pass may materialize the already classified dead material-map table with zero rows. Migration `17.0.0.70` therefore fails closed on records, not mere empty-table existence, and deliberately performs no table or column drop.
- Formal Product Layer / Layer Target: P4 isolated upgrade guard for the P1-to-P2 ownership handoff.
- Why Here / Why Not Elsewhere: zero-row registry residue is upgrade orchestration state, not a customer business fact; the private adapter must not delete product-era schema and the product must not reinterpret any non-empty history.
- Blast Radius: one fixed legacy table existence/count probe; containment is proven by the frozen carrier fingerprint, schema-copy/record-copy counters, and two isolated upgrades.
- Q10 registry ordering correction: the product-owned `sc.optional.customer.projection` protocol is registered before all P1 projections that inherit it; no projection formula, SQL body, or customer adapter behavior changes.
- The package root also loads the projection package before importing any support submodule, because importing a support child executes the support package initializer and its projection consumers.
- Final placement: the abstract protocol lives at the `models` package root and is imported before `core`; this avoids Python package-initializer side effects while keeping all concrete reports in their existing P1 packages.
- Mixed partner split correction: the canonical product extension explicitly retains `_name = "res.partner"` while adding the generic delete-guard mixin, preventing Odoo from registering an accidental parallel `ResPartner` model and duplicate inherited many-to-many fields.
- Projection handoff guard: an explicit isolated-upgrade environment flag preserves existing non-view projection relations until the external P2 module takes ownership. Outside that audited handoff, the P1 empty-projection mechanism fails closed on relation-type conflicts.
- Contract mixed-file closure: automatic category text now uses canonical `subject`, `name`, and `note` only. The module-init legacy amount fallback writer is removed rather than recalculating frozen historical amounts, so P1 no longer reads P2 evidence fields and Q10 can prove zero amount drift.
- Settlement formal identity closure: record-name search and display dependencies use canonical project, partner, settlement unit, contract subject/name, and formal amounts only; customer history text is no longer a P1 fallback.
- Formal form-contract closure: remove 51 `legacy_*` field entries from the P1 view-orchestration seed. Standard sections and canonical fields remain; P2 history fields are available only through the private audit surface.
- Product XML surface closure: remove 319 customer-history field widgets across 40 P1 view files, including two inline project audit labels; model/table columns and historical records are untouched.
- Partner view split: remove private history-derived `sc_business_role_label` and `sc_business_fact_basis` widgets/groupings from P1 customer and supplier views. Canonical Odoo ranks and P1 supplier types remain the standard product identity surface.
- Expense-claim form closure: remove the customer migration-source notebook page after its P2-owned identity field left the product view. Canonical responsibility and attachment pages remain unchanged.
- Receipt-income form closure: retain the canonical treasury-ledger page while removing its customer migration-source visibility dependency and label.
- Remaining P1 source-surface closure: remove four migration-only notebook pages and stop loading the customer-confirmed historical form extensions from the standard product manifest; canonical business pages remain loaded.
- Mixed seed split correction: restore P1 approval-policy seeds and canonical contract tier callbacks for fresh installs; only the retired historical purchase policy and callbacks remain in the private legacy carrier.
- Reference-closure split correction: return the standard material-outbound category and canonical contract callback group restrictions to P1; the P2 closure no longer owns or references those product identities.
- Partner-import review closure: remove its ACL and generated form-orchestration record from P1; both belong to the private customer legacy carrier with the unchanged model and XML identities.
- Q11 released-navigation closure: My Work and financial relationship links now use the P1 canonical payment semantic route or a record-authoritative route instead of coupling to removed raw menu/action entries. P4 browser fixtures resolve their targets from the released navigation contract.
- Formal Product Layer / Layer Target: P1 construction navigation contract with P4 acceptance adapters; module `smart_construction_core` and generic verification scripts.
- Standard vs User-Specific / Why Here: every standard construction deployment consumes the same released navigation and ORM authorization result; no customer identity, path, or preference is introduced.
- Why Not Elsewhere / Blast Radius: P0 does not own payment semantics and P2 must not repair standard navigation. The change is limited to payment quick links, financial relationship links, and acceptance target resolution; released-navigation, page-identity, finance, My Work, boundary, build, and role-journey gates contain it.
- Q11 role-semantics correction: J12 contract editing now uses an acceptance-only contract operator carrying the existing P1 `group_sc_role_operation_user`; PM remains contract-read-only as required by the authoritative role matrix. No ACL, record rule, production seed, or customer role changes.
- Q11 low-code acceptance closure: two acceptance-only users carry the existing P1 business-configuration administrator role so change-set preview, atomic publish, isolation, rollback, and ordinary-user denial are exercised without legacy accounts or fixed production credentials. Runtime targets are the current canonical contract action/menu resolved from product XML-IDs.

## 2026-07-20 — CLEAN-REPO-01G Gitee WebHook CI

- Branch: `fix/clean-repository-ci-governance`
- Starting product commit: `f01710c926188c4f7b482068bc491880c57a628d`
- Formal Product Layer: P4 operations delivery tool
- Layer Target: Gitee WebHook authentication, normalized CI queue, exact-SHA checkout, and server service isolation
- Module: `scripts/ci`, `scripts/verify`, `deploy/gitee-ci`, and Make governance entry points
- Reason: run repository guards on the existing Huawei CI node without GitHub billing or Gitee Go build minutes
- Standard vs User-Specific: product-neutral repository governance; no customer code, payload, credential, or business semantic is introduced
- Why Here: repository CI owns event admission, source identity, immutable checkout, cleanup, and evidence retention
- Why Not Elsewhere: Gitee must not execute builds, product modules must not own delivery orchestration, and production hosts must not accept ordinary Push events
- Blast Radius: one loopback service on `1.95.2.123` exposed only through an exact-path Nginx HTTPS proxy, a dedicated unprivileged account/deploy key, SQLite idempotency state, lightweight clean-history gates, and no RC/attachment/production entry point
- System-bound verification: 11 signed WebHook positive/negative tests covering header and query transport, server systemd activation, loopback and trusted public HTTPS health probes, unsigned public request denial, fixed repository/sender allowlist, replay denial, fork denial, SHA injection denial, secret environment isolation, and pre-write Gitee scope validation
- External state: Nginx 1.24 and Certbot 5.7 are active; Let's Encrypt issued the short-lived IP certificate and the renewal timer is enabled. Gitee Deploy Key `5932346`, signed WebHook `2106026`, protected `main`, and governance PR `#1` are configured. The built-in Gitee test payload is intentionally denied by the repository allowlist; a real same-repository Push is the authoritative end-to-end probe.
- End-to-end result: the real PR event for `736a310ab4f5a0844797d8178a34e3b92cc3320a` passed with exact-SHA checkout, release scan 12/12, exit code 0, workspace cleanup, and zero credential markers in retained CI logs.

## 2026-07-20 — CLEAN-REPO-01G Gitee-to-GitHub Mirror

- Branch: `fix/gitee-github-mirror-governance`
- Starting product commit: `a8b490da148b6926cb51a88be6131d0a9c7d5fea`
- Formal Product Layer: P4 operations delivery tool
- Layer Target: Gitee-authoritative, exact-SHA, fast-forward-only GitHub main mirroring
- Module: `scripts/ci`, `scripts/ops`, `scripts/verify`, `deploy/gitee-mirror`, Make governance, and ops documentation
- Reason: keep GitHub and Gitee on one commit history without permitting GitHub-side PR merges or ordinary direct pushes
- Standard vs User-Specific: repository governance only; no product function, customer module, attachment, RC image, or production deployment
- Why Here: the CI worker proves the Gitee main candidate, a credential-free bare repository hands it off, and a separate service exclusively owns the GitHub write key
- Why Not Elsewhere: the receiver must not hold repository credentials, build code must not read the GitHub key, and GitHub must not become an independent write path
- Blast Radius: one repository Ruleset, one write Deploy Key, one unprivileged mirror account, one oneshot/timer, the Gitee-only PR push guard, and fixed fresh-clone validation
- System-bound verification: exact repository allowlist, exact SHA push, ancestor check, force-free negative tests, active Ruleset readback, unique write Deploy Key, worker-key denial, mirror-key access, idempotent timer execution, dual fresh clones, identical SHA/tree/branches/tags, and 12/12 release scans

## 2026-07-20 — TENANT-RC-01 Pure Product Candidate

- Branch: `release/tenant-rc-01-product-image`
- Starting product commit: `db31271c286e3a898d8882242cac5c3940484a66`
- Formal Product Layer: P4 release delivery tooling assembling the P0/P1 product set
- Layer Target: immutable product image, formal lifecycle entry points, external customer package admission, isolated profile acceptance, and recovery evidence
- Module: `make/release.mk`, `scripts/release`, `scripts/verify`, candidate Dockerfiles, and the frozen product module-set configuration
- Reason: produce one customer-neutral image that can be installed and upgraded without hand-built module lists, while admitting customer modules and payloads only through a fail-closed external protocol
- Standard vs User-Specific: the repository owns only the generic product and delivery protocol; synthetic payloads are test-only and Baosheng code/data remain in authorized private storage
- Why Here / Why Not Elsewhere: image assembly and admission checks are P4 responsibilities; P0/P1 modules remain the product facts, and no customer semantics enter platform, industry, frontend, or low-code layers
- Blast Radius: product module closure, production static assets, candidate container contents, isolated databases, external read-only mounts, release reports, and no production or 175GB attachment writes
