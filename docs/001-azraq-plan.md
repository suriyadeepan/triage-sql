# FS-01 — Azraq Data, Schema & Evaluation Plan

## Scope and approach

Implement the approved requirements in [001-azraq-requirements.md](001-azraq-requirements.md) on PostgreSQL. Use the existing local `data/raw/azraq/` CSVs, `azraq-schema.sql`, `azraq-relationships.yaml`, and `azraq.md` as source artifacts. Keep DDL free of PK/FK constraints and keep relationship metadata external. Preserve all 26 source table and column names and the inferred PostgreSQL-compatible types; do not fabricate missing schema or relationship facts.

The current raw files total about 5.1 GB (about 99 million CSV rows, plus headers). The user confirms the current CSV data is anonymized; this is user-provided assurance and was not independently audited during planning. Build a safe, reproducible dataset snapshot and record its identity/counts before generating examples. Use only synthetic/anonymized rows in prompts, indexes, examples, and evaluation. Exclude `users.password` from all generated content and search indexes, and replace it with a safe placeholder if a loader needs the column. **Storage decision:** version the schema, relationship metadata, observations, importer, and a manifest with per-file hashes/counts; keep the 5.1 GB CSV tree and source archive ignored by regular Git. Git LFS is not installed and no external dataset artifact store is configured. Reinitialization therefore requires the same locally supplied CSV snapshot and the initializer must verify it against the manifest; the manifest does not distribute the rows.

## Plan

### P001 — Secure and identify source artifacts

- **P001.1** Inventory CSV headers, row counts, source/schema versions, and checksums without exposing values; verify all 26 tables and every DDL column are represented.
- **P001.2** Make an explicit loading allowlist and sanitize credentials before data reaches PostgreSQL, generated artifacts, logs, prompts, or indexes. Record the user confirmation that the source rows are anonymized; preserve this provenance in the dataset manifest.
- **P001.3** Resolve the current `.gitignore` conflict with the versioning requirement: version safe schema/relationship/import/manifest artifacts and approved anonymized derived fixtures; keep the large source tree ignored, and verify supplied source checksums against the versioned manifest.

### P002 — Reproducible PostgreSQL initialization

- **P002.1** Add a versioned initializer/import command using the authoritative DDL and raw CSV directory, with deterministic encoding, NULL handling, type handling, and clear row-count/error reporting.
- **P002.2** Record dataset/schema versions, per-table row counts, source checksums, snapshot ID, and any sampling/subsetting in a manifest.
- **P002.3** Provide a repeatable local PostgreSQL environment with a pinned server version and documented configuration; do not add PK/FK constraints.

### P003 — Relationship validation and JOIN eligibility

- **P003.1** Preserve all existing YAML relationships, candidates, endpoints, cardinality, status, confidence, provenance/evidence, and filters. Correct any evidence wording that could imply full null/orphan coverage when the recorded policy says `not_performed`.
- **P003.2** Produce machine-readable and human-readable validation reports with referenced-key uniqueness, source/target nulls, matched/orphan counts, and subtype mismatch counts where filtered. Clearly label sample versus full coverage.
- **P003.3** Keep relationships `inferred` or `needs_review` unless uniqueness, nulls, orphans, subtype consistency, and semantics have all been checked and reviewed. Generate JOIN paths only from `validated` YAML edges.
- **P003.4** Keep the four client-type ID ranges as evidence only. Preserve the four specified subtype-aware links and filters, including no subtype filter for `collaterals.owner_id`.

### P004 — Fixed-snapshot evaluation set

- **P004.1** Create 100–200 NL questions with reference SQL, expected results, and execution outcomes on a named immutable PostgreSQL snapshot; cover filters, dates, joins, subtype-aware joins, aggregations, and supported multi-table questions.
- **P004.2** Label unsupported or ambiguous questions without fabricating SQL; only use questions whose data is synthetic/anonymized.
- **P004.3** Store snapshot identity and query/result provenance with each item so outcomes are reproducible.

### P005 — Training and SQL-correction data

- **P005.1** Generate Text-to-SQL and SQL-correction examples separately, grounded only in the actual schema and validated relationships.
- **P005.2** Parse generated statements and execute read-only SQL against the fixed snapshot; reject unsafe statements and invalid results.
- **P005.3** Split by query/template pattern where practical. Add automated checks for duplicate or near-duplicate held-out questions, SQL, and results across train/validation/held-out partitions.

### P006 — Documentation and evidence

- **P006.1** Document initialization, snapshot creation, relationship policy, evaluation format, safe-data rules, and generation/validation workflow.
- **P006.2** Record commands, results, and evidence in the feature journal; keep task status only in the canonical TODO.

## Affected files and dependencies

- Existing: `data/raw/azraq/*.csv`, `data/raw/azraq-schema.sql`, `data/raw/azraq-relationships.yaml`, `data/raw/azraq.md`, `.gitignore`, `pyproject.toml`, `uv.lock`, `scripts/validate_azraq_relationships.py`, `scripts/resolve_relationships_azraq.py`, and existing tests.
- Planned additions: PostgreSQL initialization/import and safe-data checks; full relationship validation/reporting; evaluation and example schemas/data; leakage checks; PostgreSQL service configuration; documentation and regression tests.
- Dependencies: Python 3.14 with `uv`; PostgreSQL server and a Python PostgreSQL driver (version choice to be pinned during implementation); existing pandas, polars, PyYAML, and pytest dependencies.

## Architecture compatibility matrix

| Area | Status | Evidence and action |
|---|---|---|
| Python | VERIFIED | `pyproject.toml` requires Python `>=3.14`; local `uv run --no-sync python --version` reports 3.14.10. Keep commands under `uv`. |
| Host CPU/OS | VERIFIED | Local host is macOS 15-era Darwin on ARM64; `uv` is native aarch64. |
| Existing Python dependencies | VERIFIED | Project dependencies are managed by `uv` and pinned in `uv.lock`; PostgreSQL driver is not currently declared. |
| PostgreSQL server/runtime | UNKNOWN | `psql` is unavailable. Docker CLI is installed, but daemon and PostgreSQL image/runtime compatibility have not been checked. Pin and verify a PostgreSQL image/server version during implementation. |
| Deployment target/CI | UNKNOWN | No deployment configuration or CI workflow is present in the inspected repository. Establish a repeatable PostgreSQL service and smoke check in the implementation plan execution. |
| Source dataset safety | USER-CONFIRMED | User confirms the current CSV data is anonymized; this was not independently audited during planning. Preserve that provenance, exclude `users.password`, and avoid exposing row values in logs or generated artifacts. |

## Risks and mitigations

- **Sensitive values:** use the user-confirmed anonymized dataset, omit passwords, and prevent row values from appearing in logs or generated artifacts.
- **Scale and local resources:** the CSVs total approximately 99 million lines and the ignored compressed archive is about 1.6 GB. Use streaming/batched loading, document resource requirements, and use a deterministic documented subset for iteration where necessary.
- **Sample evidence overstated as full integrity:** preserve the 1,000-row seed-20261127 sample evidence and manual subtype counts, but keep full null/orphan validation `not_performed` until full coverage is run.
- **Semantic errors from inferred edges:** require reviewed `validated` status and enforce subtype predicates in the generated JOIN metadata.
- **Ignored source files:** `.gitignore` excludes the large raw dataset. The versioned manifest verifies exact source files but does not distribute them; future deployment requires a source-artifact provider matching the manifest or another approved large-file storage mechanism.

## Acceptance criteria and validation

Mapped to requirements [R001–R005](001-azraq-requirements.md) and acceptance criteria A001–A005.

- Verify all 26 CSV headers and columns match the DDL; explicitly report missing/extra columns and documented exclusions.
- Initialize PostgreSQL from the versioned DDL/import workflow and compare row counts, type handling, and snapshot manifest values.
- Verify DDL contains no PK/FK constraints and relationship metadata stays separate.
- Validate that only `validated` relationships reach JOIN generation and each subtype filter is applied to the target `clients.type`; report sample/full coverage distinctly.
- Execute every supported evaluation query and record reference SQL, expected result, outcome, and snapshot ID; unsupported/ambiguous items carry explicit labels.
- Parse and execute generated examples independently and run automated held-out leakage checks.
- Automated compatibility checks: Python 3.14 `uv` environment; pinned PostgreSQL service; schema-load smoke check; table/column/row-count manifest check; read-only SQL execution; relationship eligibility/subtype tests; leakage-check fixtures.
