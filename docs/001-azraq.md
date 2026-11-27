# FS-01 — Azraq Data, Schema & Evaluation Journal

## Implementation record

### 2026-11-27 — Source inventory and safe-data foundation

- The approved plan uses PostgreSQL. Work is on `feat/azraq-data`; user confirmed the source CSV data is anonymized. `users.password` remains excluded from loaded, prompted, indexed, and generated content.
- Added `scripts/azraq_manifest.py` to inventory DDL/table/column coverage, CSV row counts, malformed row widths, and SHA-256 hashes without emitting row values. Command: `uv run python scripts/azraq_manifest.py`.
- Result: 26 DDL tables and 26 CSVs; 99,297,521 data rows; no missing/extra CSV tables or columns; no malformed row widths. Snapshot ID: `c4f4be61cad2d091708747193e61b7e8dfa702a6210bffb9fce51495878fc780`. Manifest: `data/manifest/azraq-snapshot.json`.
- Dataset size is about 5.1 GB expanded and 1.5 GB in the ignored archive. The raw tree remains excluded from regular Git. Schema, relationship YAML, observations, importer, and checksummed/count manifest are versioned; consuming environments must supply files matching the manifest. Git LFS is unavailable locally and no dataset artifact store is configured.
- Updated `.gitignore` with narrow exceptions for the small schema, relationship metadata, and source observations. Added safe-column and row-sanitization helpers in `src/triage_sql/data_safety.py`; the loader will replace `users.password` with NULL-compatible empty data, and prompt/index consumers can omit it.
- Automated checks: `uv run pytest tests/test_azraq_manifest.py tests/test_data_safety.py` — 6 passed. An earlier manifest test failed because its fixture put an extra field in a data row but expected an extra header; corrected the fixture, reran, and all 6 passed.
- Runtime evidence: Python 3.14.10 through `uv`; Docker server 29.5.2 is available. Docker Compose plugin is unavailable. PostgreSQL image pull and database smoke test are pending.

## Verification record

- Implementation evidence: see dated implementation entries above.
- Automated testing: commands/results recorded above and per subsequent implementation entry.
- Deployment/live verification: not yet performed.


### 2026-11-27 — PostgreSQL initialization

- Added Psycopg 3.3.9 binary dependency and locked it with `uv`. Added `scripts/azraq_postgres.sh` using Docker Engine to start/stop a loopback-only PostgreSQL 18.7 container pinned by image digest; Docker Compose is unavailable, so the service uses the Docker CLI directly.
- Added `scripts/azraq_init.py`. It verifies schema, relationship, and CSV checksums against the source manifest, creates a snapshot-named schema without constraints, streams CSVs via PostgreSQL COPY, writes NULL to `users.password`, validates row counts, and records a database snapshot manifest. Database initialization is idempotent for an already loaded snapshot.
- First direct invocation (`uv run python scripts/azraq_init.py`) failed because `scripts` is a namespace package; documented invocation is `uv run python -m scripts.azraq_init`. The first module invocation exposed a SQL splitter bug: semicolons inside DDL comments were treated as statement boundaries. Comment stripping before splitting fixed it; a rolled-back PostgreSQL smoke test then created all 26 tables.
- A temporary-table COPY smoke test caught an unsupported `Copy.rowcount` API assumption; removed the return value and rely on actual PostgreSQL row-count checks. The users COPY integration check confirms the sensitive source field becomes NULL.
- Full initialization: `uv run python -m scripts.azraq_init` — PostgreSQL 18.7 schema `azraq_c4f4be61cad2d091`, 26 tables, 99,297,521 rows. Running the initializer again recognized the same snapshot and did not duplicate it. Database manifest: `data/manifest/azraq-postgres.json`.
- Live checks compared every column name/type to the DDL and found no mismatches; PK/FK constraints=0; non-NULL `users.password` rows=0.
- Automated tests: `AZRAQ_TEST_DSN=... uv run pytest tests/test_azraq_postgres_integration.py` — 2 passed. `uv run pytest` — 11 passed, 2 PostgreSQL integration tests skipped unless `AZRAQ_TEST_DSN` is set.
- Deployment/live verification: Docker Engine 29.5.2 with the pinned PostgreSQL image started successfully on `127.0.0.1:55432`; full import, schema/type/row-count/password checks, and idempotent rerun succeeded.

### 2026-11-27 — Relationship validation and JOIN eligibility

- Decoupled the database snapshot ID from the relationship YAML hash. The data snapshot is now `ba058d581b04d1d75f63ac0a4705d98ea0d8ea54dcf577ee90b58222d082dddc`; relationship metadata changes are checked separately by SHA-256 and do not require a database reload. Updated the source and PostgreSQL manifests accordingly.
- Added `src/triage_sql/relationships.py` to load relationship metadata without dropping its fields, select only non-candidate `validated` edges, and render SQL JOIN clauses with subtype predicates on the target alias. The four client links retain their required filters; `collaterals.owner_id` remains unfiltered. The two officer-to-user edges remain `needs_review` because domain semantics are unresolved.
- Added `scripts/validate_azraq_relationships_pg.py`. It checks full source and target coverage in a read-only transaction, reporting source/target nulls, matched and orphan rows, target key duplicates, filtered key duplicates, and subtype mismatches. It emits JSON and a detailed Markdown table at `data/manifest/azraq-relationships-validation.{json,md}`. The YAML preserves the original randomized 1,000-row evidence and baseline `not_performed` state separately from the current full report.
- Full validation command: `uv run python -m scripts.validate_azraq_relationships_pg`. Result on the fixed snapshot: 29 declared relationships, 0 integrity findings, 27 JOIN-eligible relationships; every checked link had zero source/target nulls, duplicate target keys, orphans, and subtype mismatches. All 27 promoted edges include full-validation and semantic-review evidence. Candidates are not JOIN-eligible.
- Automated checks: focused unit tests — 10 passed; PostgreSQL integration tests with `AZRAQ_TEST_DSN='postgresql://azraq:azraq_local_only@127.0.0.1:55432/azraq'` — 4 passed, covering exact subtype JOIN SQL and validation counts for nulls, duplicates, orphans, and subtype mismatch. Full `uv run pytest` — 16 passed, 4 PostgreSQL tests skipped because that invocation had no integration DSN.
- Live verification: PostgreSQL 18.7 full scan completed against all records in the fixed snapshot. The JSON report hash matches both the current relationship YAML and source manifest. The report is snapshot-specific and does not turn inferred relationships into database constraints.

### 2026-11-27 — Fixed-snapshot NL evaluation set

- Added `src/triage_sql/evaluation.py` and `scripts/generate_azraq_evaluation.py`. The deterministic catalogue yields 120 NL questions from 24 SQL templates and five phrasings per template, covering filters, dates, aggregation, validated joins, the four subtype-aware client links, and multi-table questions.
- Generated `data/evaluation/azraq-evaluation.jsonl` on the immutable PostgreSQL snapshot `ba058d581b04d1d75f63ac0a4705d98ea0d8ea54dcf577ee90b58222d082dddc`. Every entry records SQL, expected result, successful execution/row count, pattern/category, provenance, and snapshot ID. Queries run in a read-only transaction. No query references `users.password`; output is drawn from the user-confirmed anonymized dataset.
- Verification: `uv run pytest tests/test_evaluation.py` — 3 passed. `AZRAQ_TEST_DSN='postgresql://azraq:azraq_local_only@127.0.0.1:55432/azraq' uv run pytest tests/test_evaluation.py tests/test_azraq_postgres_integration.py` — 8 passed, including an integration regeneration and execution of all evaluation templates against PostgreSQL 18.7.
- Deployment/live verification: the generator completed against the running pinned PostgreSQL container and emitted 120 successful outcomes. The collateral-owner example joins to clients without a subtype filter; group, individual-member, and NSG links apply their required `clients.type` predicates.
