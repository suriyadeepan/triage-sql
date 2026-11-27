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
