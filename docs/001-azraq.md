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
