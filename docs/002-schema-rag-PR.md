# FS-02: Failure-Focused Schema Retrieval Experiments

## Summary

Adds a reproducible workflow for studying schema retrieval on the queries that failed in the original retrieved-schema SQL benchmark. It freezes the original 120-query baseline, extracts the 53 failures with their retrieval labels, and compares reranked candidate pools using Luna-low SQL generation and execution against the fixed database snapshot.

## Changes

- Added a deterministic failure-cohort extractor and regression tests. The cohort contains exactly 53 failed query IDs, in evaluation order, with categories, expected results, and retrieval labels.
- Extended the SQL benchmark to accept an explicit query set, candidate pool, optional Cohere reranking, and retrieved-schema-only runs. Results include SQL status, execution accuracy, input tokens, end-to-end latency, Recall@5, MRR, and Cohere latency.
- Added the Phase 1 runner for `candidate_k` values 20, 30, 40, and 53 at `top_k=5`.
- Saved per-query rankings and SQL results as separate experiment artifacts. The original baseline result files were not modified.
- Updated the plan and TODO with the completed Phase 1 work and the user-directed scope change.

## Phase 1 Results

All configurations used the same 53 queries, index, snapshot, `gpt-6-luna` model, `low` reasoning effort, and Cohere `rerank-v5.0-fast`.

| `candidate_k` | SQL accuracy | Mean input tokens | Mean end-to-end latency | Recall@5 | MRR |
|---:|---:|---:|---:|---:|---:|
| 20 | 11/53 (20.8%) | 1,304 | 4,292 ms | 0.957 | 1.000 |
| 30 | 10/53 (18.9%) | 1,302 | 4,161 ms | 0.957 | 1.000 |
| 40 | 13/53 (24.5%) | 1,302 | 4,367 ms | 0.957 | 1.000 |
| 53 | 11/53 (20.8%) | 1,302 | 5,031 ms | 0.957 | 1.000 |

Candidate 40 had the highest execution accuracy in this cohort. Recall@5 and MRR were tied across all four settings; larger candidate pools increased Cohere and end-to-end latency without improving those retrieval metrics.

## Scope and Results Notes

Phase 2 top-k optimization and its dependent full-set rerun were removed from the plan and TODO at the user's direction. Before the stop request, three top-k runs had completed; they are preserved as partial exploratory evidence and are not treated as a complete comparison. The `top_k=15` run was interrupted, `top_k=20` was not run, and no additional 120-query run was performed. The original full-schema and retrieved-schema baselines remain intact.

## Verification

- `uv run pytest -q`: 49 passed, 7 environment-gated PostgreSQL integration tests skipped.
- `uv lock --check`: passed.
- `git diff --check`: passed.
- Frozen baseline and cohort SHA256 checks: passed.
- Experiment artifacts contain no sensitive-field markers.

## Commit

`9c20faf` — `docs(schema-rag): record failure cohort experiments`
