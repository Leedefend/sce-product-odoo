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
- Standard vs User-Specific: the repository owns only the generic product and delivery protocol; synthetic payloads are test-only and `<PRIVATE_CUSTOMER_MODULE>` code/data remain in authorized private storage
- Why Here / Why Not Elsewhere: image assembly and admission checks are P4 responsibilities; P0/P1 modules remain the product facts, and no customer semantics enter platform, industry, frontend, or low-code layers
- Blast Radius: product module closure, production static assets, candidate container contents, isolated databases, external read-only mounts, release reports, and no production or 175GB attachment writes

## 2026-07-20 — NAV-PRO-01 Product Navigation Exposure

- Branch: `release/tenant-rc-01-product-image`
- Starting product commit: `43a30985a4eb`
- Formal Product Layer: P1 construction-product exposure policy, P0 generic authorization projection, P4 verification
- Layer Target: matrix-derived primary navigation, contextual route authority, and fail-closed native-menu intersection
- Module: `smart_construction_core`, `smart_core` delivery/identity services, shared frontend router/session, and NAV-PRO-01 audit/verification tooling
- Reason: replace historical 70/80 menu-count assumptions with the 324-row authoritative role/menu matrix and expose only task- or journey-backed primary entries
- Standard vs User-Specific: standard construction role policy; no customer identity, preference, payload, production data, or low-code override
- Why Here: P1 owns role/menu product decisions, P0 owns identifier-only projection and contract transport, the frontend consumes the delivered authority without inferring business semantics, and P4 proves the result
- Why Not Elsewhere: platform code must not encode construction roles or XML-ID sets, the frontend must not infer authorization from labels/models, customer modules must not repair the standard product, and ops scripts must not become runtime policy
- Blast Radius: four formal roles, 138 authorized role/menu assignments, 31 primary/home assignments, 100 contextual assignments, 7 explicit denials, two stale legacy action domains, shared route admission, and no ACL or record-rule expansion
- Validation: deterministic matrix regeneration, Python syntax, frontend lint/strict typecheck, Odoo role-surface tests, native visibility, HTTP contract/data probes, browser primary/contextual navigation smoke, and zero HTTP 5xx
- Browser closure: contextual authorities carry native action metadata and seed `currentAction` before route rendering, preventing an async metadata transition from trapping hidden contextual actions in a blank-page render loop while keeping those menus out of the primary tree.
- RC gate closure: replace the stale 70/80-leaf page-audit constants with the NAV-PRO-01 primary/home denominator (finance 10, project member 7, PM 10, owner 4; total 31). The audit accepts both demo and fixture login prefixes but fails closed on unknown roles, while the tenant RC verifier requires the exact four fixture-role counts and 31/31 identity/reachability evidence.
- RC journey closure: J02 proves the released payment entry by exact database-exported action/menu IDs because the wire navigation does not carry action XML-IDs. RC page-identity evidence remains external under `CANDIDATE_ARTIFACTS`; the runner no longer rewrites the repository's versioned demo inventory.
- J03 scope closure: the project-member journey opens the released project-ledger action resolved from `menu_sc_project_project`, rather than bypassing the primary navigation contract through the legacy `/s/projects.list` scene route.
- Shared acceptance closure: page identity, financial workspace, My Work, delivery hardening, and core-form journeys resolve released targets by stable menu XML-ID and consume the delivered action/menu IDs. Runtime target exporters use the menu's formal action directly instead of substituting the retired generic payment action.
### 2026-07-21 — RC runtime mutable-fixture isolation

- Continued the tenant RC runtime gate after navigation-target alignment.
- Root cause for the J07 failure: J06 submitted the same `FE-JOURNEY-PAYMENT-001` row that J07 subsequently expected to remain in draft.
- Added a dedicated J06 settlement/payment-request pair and kept J07 on its original deterministic row. This is acceptance-fixture isolation only; no production domain, permission, or workflow semantics changed.
- J07 then passed and exposed a separate J08 navigation-contract defect: the settlement entry action carried the payment action with the settlement menu context, which the released navigation authority correctly denied.
- Corrected the projected entry route to use the released payment menu and that menu's own action. This changes P1 navigation context only; it does not change create ACLs, finance capability checks, defaults, or payment workflow semantics.
- Updated the FE-B05 static guard from the retired native-dialog ref marker to the current shared `ScDialog` open-state marker; the guard continues to assert confirmation behavior without pinning an obsolete implementation detail.
- On the rebuilt candidate, J08 reached the authorized create form and exposed duplicate native field projections. Scoped the browser assertions to the first rendered project/contract/settlement field instance; no form values or production rendering behavior changed.
- The next rebuilt-candidate J08 run confirmed that the payment request form consistently projects multiple amount inputs as well. Scoped the post-refresh amount assertion to the first rendered projection so Playwright strict mode does not reject equivalent field instances.
- The following J08 run completed create/save/refresh/submit, then exposed that the shell's empty-menu guard hid `/my-work` from the executive approval role even though My Work is a shell-native route. Allowed the My Work route and its scene alias to render with an empty menu tree; backend approval capabilities, record rules, and menu authority remain unchanged.
- With the shell route fixed, J08 reached the executive decision and exposed a split authority check: the intent handler and approval policy admitted executive/finance-approver roles while `payment.request` admitted only the finance-manager capability. Aligned the model guard to the same three explicit approval authorities and added negative coverage for ordinary internal users; record scope and workflow prerequisites remain unchanged.
- After J07/J08 passed, J10 exposed a fixture sequencing collision: J07 had already submitted the draft record that J10 expected in the todo section. Added a dedicated draft payment request for delivery-hardening journeys and made the browser assertions consume its exported display identity, isolating J09-J11 from prior workflow mutations.
- The isolated J09-J11 record passed the prior collision point; the responsive matrix then hit the same repeated amount-field projection already observed in J08. Scoped every delivery-hardening amount readiness probe to the first equivalent projection, including the optional accessibility and performance paths.
- The rebuilt candidate passed J09-J11 with all 72 responsive checks and zero blocking accessibility findings, then exposed that J12 pinned the retired merged contract menu XML-ID. The contract operator's released tree still exposes the same authoritative contract action through its role-projected entry, so J12 now resolves that delivered action/menu pair by action XML-ID; payment journeys retain exact menu XML-ID selection where multiple payment entries share an action.
- The action-based probe then confirmed that release-navigation wire nodes intentionally omit action XML-IDs. J12 now selects the contract operator's actual primary `menu_sc_contract_center` node by menu XML-ID and consumes its delivered numeric action/menu pair; it no longer depends on either the retired child menu or absent wire action metadata.
- J12 then passed its dirty guard, save, and authoritative reload checks. J13 exposed one final fixture collision: the existing-record conflict scenario reused the J06 payment request after J06 had submitted it, leaving no editable amount input. Added a dedicated draft core-form request and exported it separately so J13 conflict recovery is isolated from financial-workspace and approval mutations.

## 2026-07-21 — NAV-PRO-01R Explicit Route Authority

- Branch: `release/tenant-rc-01-product-image`
- Starting product commit: `2d9d187d391cfe2c1c6e085a0a96ba6d27f20793`
- Formal Product Layer: P0 generic route-authority transport/runtime enforcement, P1 construction role policy, shared frontend consumer, and P4 verification
- Layer Target: one fail-closed `route_authority.v1` contract separating `PRIMARY_NAV`, `ROLE_HOME_ACTION`, `CONTEXTUAL_ROUTE`, `ADMIN_ROUTE`, and `DENIED`
- Module: `smart_core` identity/delivery/intent handlers, `smart_construction_core` policy declarations, frontend session/router/shell, and NAV-PRO-01R verification tooling
- Reason: backend execution permission alone does not authorize a frontend page; administrator-only and context-only pages require explicit, stable route authority without entering the business menu tree
- Standard vs User-Specific: generic product mechanism plus standard construction role declarations; no customer model, payload, login identity, production record, attachment, or private module enters the contract
- Why Here: P1 declares role/action XML-IDs and context requirements, P0 intersects declarations with native visibility and model ACLs and validates record scope, and the frontend consumes only the delivered principal-scoped authority
- Why Not Elsewhere: the frontend must not infer authorization from numeric IDs, labels, models, usernames, roles, menus, or successful data requests; test tooling must not become runtime policy
- Blast Radius: system/configuration administrator access to the existing user-and-role page, PM access to the existing contract-income-execution relation route, session/context/policy-refresh cache invalidation, and no ACL, record-rule, workflow, amount, status, or primary-navigation expansion
- Validation: route-authority unit and policy split guards, 13 Odoo post-tests, 31/31 primary browser regression, 100/100 contextual contract checks, administrator and context direct-route browser probes, four-role administrator denial, cross-company/project/contract denial, zero unauthorized page-data requests, zero HTTP 500, production frontend build, and repository diff checks
- New-image runtime correction: J08 proved that the valid shell-only `executive` role received an empty principal scope when it intentionally declared no action exposure. The contract now binds an empty action/menu set to the authenticated user, company, and role, allowing session bootstrap without granting any implicit route; backend and frontend regressions reject every mismatched principal.

## 2026-07-21 — TENANT-RC-01B1 Product Payload Boundary

- Branch: `release/tenant-rc-01-product-image`
- Starting product commit: `2d9d187d391cfe2c1c6e085a0a96ba6d27f20793`
- Formal Product Layer: P4 generic external tenant-package admission and RC profile execution
- Layer Target: remove fixed tenant identity while retaining fail-closed, signed, manifest-declared external add-on and payload admission
- Module: product lifecycle, authorized payload exporter, generic RC profile runner, package preflight, repository boundary Guard, and their negative tests
- Reason: a product repository and candidate image must understand only the external tenant-package protocol, never a named tenant, fixed archive, fixed snapshot, or module inferred from a local prefix scan
- Standard vs User-Specific: only generic schema, signature, compatibility, checksum, module-set, extraction, and zero-write admission behavior remain; every tenant value and private profile stays outside the product repository
- Why Here / Why Not Elsewhere: P4 owns package admission and release orchestration; customer identities and execution profiles belong to signed external manifests or private delivery storage, not product code or public history
- Blast Radius: five existing boundary findings, one narrowly scoped negative-test allowance, lifecycle module counting from the signed declaration, and no product ACL, business data, production database, attachment, or customer payload mutation
- Validation: fixed module/tenant/archive rejection, signed arbitrary module admission, tampered signature rejection, missing-manifest pre-I/O failure, redacted logs, generic-prefix placeholder allowance, release tooling tests, and product payload boundary Guard

## 2026-07-21 — REL-VERSION-01M Product Release Baseline

- Branch: `release/tenant-rc-01-product-image`
- Formal Product Layer: P4 release identity, immutable image metadata, external customer-package compatibility admission, and runtime information projection
- Layer Target: one repository `VERSION` source feeding release configuration, OCI labels/tags, runtime identity, customer compatibility, SBOM-linked release manifest, and lightweight release gates
- Scope Boundary: no database release ledger, schema field, workflow/state change, customer identity, private package content, production write, attachment mutation, or deployment
- Runtime Contract: `system.init` exposes only `product_version` and `source_revision`; the frontend system HUD reads both without exposing internal paths or environment variables
- Build Contract: one versioned source SHA produces the human version tag and short-SHA tag in one Docker build; deployment remains digest-addressed and save/remove/load must preserve both tags and the image ID
- Customer Compatibility: the signed external manifest declares an inclusive minimum, exclusive maximum, and required generic contracts; incompatibility fails before archive extraction or database access
