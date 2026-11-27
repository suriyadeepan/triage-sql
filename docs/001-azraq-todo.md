# FS-01 — Azraq Data, Schema & Evaluation TODO

Tasks are the canonical status source. Lineage: requirement → plan → task → implementation/tests.

## T001 — Inventory, safe data handling, and snapshot manifest [x]

**Requirements:** R001.1–R001.2, R003.1–R003.4
**Plan:** P001.1–P001.3
**Files:** `data/raw/azraq/*` (read-only inputs), `.gitignore`, new dataset manifest and data-safety/inventory script, `docs/001-azraq.md`
**Depends on:** none

- [x] **T001.1** Inspect all CSV headers against all 26 DDL tables/columns; record row counts, schema/dataset identifiers, checksums, and any subset definition without logging source values. **Accept:** machine-readable manifest identifies every table and discrepancies; no column/value secrets appear in logs. **Depends on:** none.
- [x] **T001.2** Exclude `users.password` from loaded/indexed/generated content, replacing it with a safe placeholder only if required by DDL; record user confirmation of anonymization in manifest provenance. **Accept:** automated checks demonstrate password values are absent from outputs and logs. **Depends on:** T001.1.
- [x] **T001.3** Resolve Git ignore/storage handling for reproducibility artifacts and approved anonymized data without staging the full raw tree blindly. **Accept:** exact versioned artifacts are narrow-allowlisted and sized; raw inputs remain reproducible via recorded checksums or a documented storage mechanism. **Depends on:** T001.1.

## T002 — PostgreSQL initialization [x]

**Requirements:** R001.1–R001.2, R002.1, R003.3–R003.4, A001–A002
**Plan:** P002.1–P002.3
**Files:** new `scripts/` initializer, PostgreSQL configuration, `pyproject.toml`, `uv.lock`, database-related tests, manifest from T001
**Depends on:** T001

- [x] **T002.1** Add deterministic DDL-driven PostgreSQL loading with explicit CSV encoding, NULL/type handling, batched import, and failure reporting. **Accept:** repeatable initialization reproduces table/column types and row counts; DDL remains free of PK/FK constraints. **Depends on:** T001.1.
- [x] **T002.2** Pin and configure PostgreSQL server and Python driver compatible with the project `uv` environment. **Accept:** automated setup starts pinned PostgreSQL and executes a schema-load smoke check on supported host/CI runtime. **Depends on:** T002.1.
- [x] **T002.3** Record database snapshot ID, source checksums, versions, counts, and subsetting in output. **Accept:** same source and config yield verifiable manifest identity and counts. **Depends on:** T002.1.

## T003 — Full relationship validation and JOIN eligibility [x]

**Requirements:** R002.1–R002.7, A002–A003
**Plan:** P003.1–P003.4
**Files:** `data/raw/azraq-relationships.yaml`, `scripts/validate_azraq_relationships_pg.py`, `data/manifest/azraq-relationships-validation.{json,md}`, relationship eligibility code and tests, database snapshot
**Depends on:** T002

- [x] **T003.1** Extend relationship validation to report target uniqueness, source/target nulls, matched/orphan counts, and subtype mismatches with explicit sample/full coverage. **Accept:** machine-readable and human-readable reports disclose exact coverage and never call sample results full integrity. **Depends on:** T002.1.
- [x] **T003.2** Preserve endpoints, cardinality, status, confidence, evidence/provenance and filters; retain four client ID ranges and original sample/full-validation history as evidence; distinguish the initial `not_performed` state from the current full report. **Accept:** metadata regression tests protect all existing relationships/evidence and required profiling details. **Depends on:** T003.1.
- [x] **T003.3** Gate JOIN generation on reviewed `validated` status only and apply subtype predicates to target `clients.type`, including no subtype restriction for collaterals. **Accept:** tests prove inferred/needs_review/rejected edges are excluded and each required subtype predicate is exact. **Depends on:** T003.2.
- [x] **T003.4** Promote any relationship only after full checks and semantic review. **Accept:** each promoted edge has uniqueness, null, orphan, subtype, and semantic evidence; otherwise status remains unvalidated. **Depends on:** T003.1, T003.2.

## T004 — Fixed-snapshot NL evaluation set [x]

**Requirements:** R004.1–R004.3, A004
**Plan:** P004.1–P004.3
**Files:** new evaluation data/schema and generator/validator scripts, fixed database manifest, tests
**Depends on:** T002, T003

- [x] **T004.1** Create 100–200 questions covering filters, dates, aggregations, validated joins, subtype-aware joins, and supported multi-table questions. **Accept:** every item includes reference SQL, expected result, execution outcome, and fixed snapshot ID, or an explicit unsupported/ambiguous label with no fabricated SQL. **Depends on:** T003.3.
- [x] **T004.2** Store evaluation questions/results using anonymized data only and record provenance. **Accept:** schema and automated content checks exclude password/secrets and identify the immutable database snapshot. **Depends on:** T001.2, T002.3.

## T005 — Text-to-SQL and correction examples [x]

**Requirements:** R003.1–R003.2, R005.1–R005.4, A005
**Plan:** P005.1–P005.3
**Files:** new example generation/validation scripts and datasets, tests, validated schema/relationship metadata
**Depends on:** T003, T004

- [x] **T005.1** Generate separate synthetic Text-to-SQL and SQL-correction examples grounded in actual schema and validated edges. **Accept:** every example has provenance and excludes unvalidated joins and secrets. **Depends on:** T003.3.
- [x] **T005.2** Parse generated SQL and execute it read-only against the fixed PostgreSQL snapshot. **Accept:** independently recorded parse/execution result exists for every example; invalid or unsafe SQL is rejected. **Depends on:** T002.2, T002.3.
- [x] **T005.3** Separate train/validation/held-out partitions and add duplicate/template/question/SQL/result leakage detection. **Accept:** automated regression fixtures detect deliberate held-out leaks and the generated partitions pass the checker. **Depends on:** T005.1.

## T006 — Automated validation, compatibility, and smoke checks [ ]

**Requirements:** R001.2, R002.1–R002.7, R003.1–R003.4, R004.1–R004.3, R005.1–R005.4, A001–A005
**Plan:** P001.1–P005.3
**Files:** `tests/`, PostgreSQL service configuration, scripts, CI/deployment configuration if present
**Depends on:** T001–T005

- [ ] **T006.1** Add unit/integration checks for schema coverage, DDL constraints, data safety, relationship validation/eligibility, evaluation execution, example execution, and leakage. **Accept:** tests pass through prescribed `uv` environment. **Depends on:** T002–T005.
- [ ] **T006.2** Add deployment/runtime smoke validation for pinned PostgreSQL and Python 3.14; report real-world verification separately from automated tests. **Accept:** actual service start, import, and read-only query evidence recorded; limitations reported if host cannot run it. **Depends on:** T002.2.

## T007 — User documentation and implementation journal [ ]

**Requirements:** R003.3–R003.4, R004.3, R005.2–R005.4
**Plan:** P006.1–P006.2
**Files:** `docs/001-azraq.md`, tutorial on completion if appropriate, README if needed
**Depends on:** T001–T006

- [ ] **T007.1** Document setup, source/snapshot identity, safe data handling, validation policy, evaluation format, generation, and leakage checks. **Accept:** instructions reproduce initialization and explain unsupported/ambiguous labeling and JOIN eligibility. **Depends on:** T002–T005.
- [ ] **T007.2** Record implementation decisions, commands, results, failures, and evidence in the journal without duplicating task statuses. **Accept:** journal distinguishes implementation, automated tests, and deployment/live verification. **Depends on:** T001–T006.
