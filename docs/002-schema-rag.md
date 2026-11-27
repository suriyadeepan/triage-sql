# FS-02 — Lightweight Hybrid Schema RAG Journal

## Implementation evidence

- The approved runtime is Python 3.14 on ARM64. Local verification reports Python 3.14.10 and `arm64`.
- `uv add sentence-transformers chromadb rank-bm25 sqlglot` resolved SentenceTransformers 6.3.0, PyTorch 2.15.0, Chroma 1.5.9, rank-bm25 0.2.2, and sqlglot 30.35.0. Cohere and OpenAI SDKs are optional extras.
- CPU inference with `sentence-transformers/all-MiniLM-L6-v2` succeeded. The immutable model revision recorded in the local index manifest is `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`.
- A local index build represented 26 tables and 27 validated relationship records. It records DDL/YAML/observation hashes, the fixed dataset snapshot ID, model revision, runtime/library versions, record format, and deterministic record ID digest. The generated Chroma index is ignored local state under `data/index/`.
- Focused schema, relationship, index, and retrieval-label tests passed under `uv run pytest`. Index rebuild tests produce equivalent manifests, and changed relationship metadata triggers stale-index detection.
- Derived labels cover all 120 fixed queries. Current label generation reports no unresolved SQL columns or relationships; the generator flags unvalidated relationships and missing subtype filters in regression fixtures.
- The full retrieval benchmark used `top_k=5`, `candidate_k=20`, one warm-up and three measured repetitions for each query/mode. Detailed ranked results, category failures, and per-query latency are in `data/evaluation/azraq-retrieval-results.json`. The rerank comparison and completed SQL-prompt metrics are recorded below.

## Retrieval benchmark results

On the fixed 120-query set, macro Recall@5 / MRR and warm-query latency were:

| Mode | Recall@5 | MRR | Average | P50 | P95 |
|---|---:|---:|---:|---:|---:|
| Dense | 0.581 | 0.707 | 10.29 ms | 10.27 ms | 11.04 ms |
| BM25 | 0.356 | 0.397 | 1.43 ms | 1.41 ms | 1.58 ms |
| Hybrid RRF | 0.526 | 0.541 | 10.51 ms | 10.51 ms | 11.31 ms |

Failures by overlapping query tag (`misses / queries`): dense had exact-identifier `24/85`, semantic `0/25`, and multi-table `0/50`; BM25 had `33/85`, `15/25`, and `3/50`; hybrid had `24/85`, `5/25`, and `0/50`. The persisted results include every ranked record, not only failures.

Cohere reranking was evaluated on a deterministic 10-query sample spanning exact-identifier, semantic, and multi-table tags. On that same sample, hybrid measured Recall@5 `0.437` / MRR `0.495`; hybrid plus reranking measured `0.850` / `0.900`. Total latency (hybrid retrieval plus Cohere) averaged `629.8 ms` (P50 `622.4 ms`, P95 `719.3 ms`); the Cohere call itself averaged `619.5 ms` (P50 `613.1 ms`, P95 `708.6 ms`) with zero service failures. The quality gain supports retaining reranking as an explicit opt-in experiment; it remains disabled by default because of added latency, external service dependence, the small sample, and the trial key's observed 10-calls-per-minute limit.

## SQL prompt benchmark results

Both strategies ran on all 120 supported questions and the fixed snapshot `ba058d581b04d1d75f63ac0a4705d98ea0d8ea54dcf577ee90b58222d082dddc`. The caller-configured generator was OpenAI Responses model `gpt-6-luna` with reasoning effort `low`. The results are preserved per query in `data/evaluation/azraq-sql-prompt-results.json`.

| Strategy | Execution accuracy | Mean input tokens | E2E average | E2E P50 | E2E P95 |
|---|---:|---:|---:|---:|---:|
| Retrieved schema | 55.8% (67/120) | 1,559.7 | 3,148 ms | 2,816 ms | 6,250 ms |
| Full schema | 71.7% (86/120) | 13,376.9 | 3,011 ms | 2,618 ms | 6,994 ms |

Retrieved context reduced average input tokens by 88.3%, while execution accuracy was 15.8 percentage points lower. Full-schema prompts were 137 ms faster on average end to end because retrieval work is included in that measure. These results do not establish a universal winner; they record the configured model, effort, query set, snapshot, and current retrieval ranking.

Accuracy by query category (retrieved schema / full schema): aggregation 50.0% / 66.7%; date 26.7% / 33.3%; filter 52.0% / 76.0%; join 65.0% / 75.0%; multi-table 20.0% / 70.0%; subtype join 100% / 100%. Failures include result mismatches, five `UndefinedColumn` errors and two invalid SQL responses for retrieved context, plus one invalid SQL response for full schema. Two retrieved-context outputs were safely rejected by the SQL validator. The per-query artifact has exact categories and statuses.

## External service limits observed

- The configured Cohere trial key returned HTTP 429 after 10 requests, stating a limit of 10 calls per minute. The benchmark paces calls, and any rerank result must state its query count and sample selection. No API key or secret value is stored here.
- The local `.env` contains OpenAI and Cohere keys plus the caller-selected `OPENAI_MODEL=gpt-6-luna` and `OPENAI_REASONING_EFFORT=low`. No key or secret value is stored in the repository. The SQL-generation adapter remains model-neutral and does not choose a model implicitly.
- Both optional service adapters load project `.env` values with `python-dotenv` while preserving environment variables already set by the caller. The `.env` remains local and must never be committed.
- The optional OpenAI generator follows the official [Responses API Python quickstart](https://developers.openai.com/api/docs/quickstart), obtains its model from `OPENAI_MODEL` or an explicit argument, and passes configured effort through `reasoning.effort` ([reasoning guide](https://developers.openai.com/api/docs/guides/reasoning)). The Cohere reranker uses the documented `rerank-v5.0-fast` model name ([Cohere Rerank docs](https://docs.cohere.com/docs/rerank)).

## Reproduction and verification commands

The implementation was verified on Python 3.14.10 / ARM64. Install the core and development dependencies with `uv sync --dev`. Add optional service clients only for the relevant experiments with `uv sync --dev --extra rerank --extra openai-benchmark`.

```sh
uv run python scripts/schema_rag.py build
uv run python scripts/schema_rag.py query "Which tables connect clients to loans?" --mode hybrid --top-k 5
uv run python scripts/label_azraq_retrieval.py
uv run python scripts/benchmark_azraq_retrieval.py
uv run python scripts/benchmark_azraq_retrieval.py --rerank --rerank-limit 10 --rerank-delay-seconds 6.5
```

The Cohere trial key observed a quota of 10 calls per minute. The benchmark's paced 10-query sample is therefore the recorded safe trial run; allow at least 6.5 seconds between calls and verify the account quota before increasing the sample. Reranking remains opt-in.

For future SQL-generation runs, set `OPENAI_MODEL` explicitly in the local `.env` or the process environment, then run `uv run python -m scripts.benchmark_azraq_sql`. The module form is required because the script imports the project's `scripts` namespace. Omit `--limit` to run all 120 queries. The recorded full run used the caller-configured model and reasoning effort above; API keys alone do not satisfy the benchmark's model requirement.

Final verification on Python 3.14.10 / ARM64: with `AZRAQ_TEST_DSN` pointed at the local fixed snapshot, `uv run pytest` passed all 54 tests, including seven PostgreSQL integration checks, in 56.01 seconds. Focused adapter/retrieval tests passed 11 tests plus five subtests. Both service adapters initialized from `.env` while preserving the caller-configured model and effort. `uv lock --check` and `git diff --check` passed. One Chroma dependency deprecation warning remains; no test failed. The CLI help checks, hybrid query smoke, 120-query retrieval run, paced 10-query Cohere sample, and 120-query-per-strategy SQL prompt benchmark also completed. The SQL benchmark ran via `uv run python -m scripts.benchmark_azraq_sql`; all 240 generated SQL outputs were safety-validated before execution, and no password-bearing SQL was saved. Full query-level evidence is in `data/evaluation/azraq-sql-prompt-results.json`.

## Failure-focused experiment record

The original SQL and retrieval result artifacts remain unchanged. Their SHA256 identities were rechecked against the committed baseline values in T007.1. The fixed evaluation query-set SHA256 is `1cbe40d2d027a28d32fd39e91807e6427c6fad10d8a338a488b60bc7703dc87a`; the index manifest SHA256 is `e3e9c32aa1b62321e7dc3664061945e37bc3ffcad04b1fd1b33bad64586ce92b`, with 53 records, and the snapshot is `ba058d581b04d1d75f63ac0a4705d98ea0d8ea54dcf577ee90b58222d082dddc`. Baseline generation settings were `gpt-6-luna`, reasoning effort `low`, `candidate_k=20`, and `top_k=5`.

`uv run python scripts/extract_azraq_sql_failures.py` deterministically extracted the 53 retrieved-schema SQL failures and joined their query labels in evaluation source order. The frozen cohort is `data/evaluation/azraq-retrieval-failure-labels.jsonl` (SHA256 `150579fb833e209c6b66f1c7d4eca579116b5d6644514b4e8cce6c69f855f764`); its source baseline SQL SHA256 is `ee7beb0a1229fe8fad1985d1f37591054eb0feac082b7e2c2f7c72dffb6e09e1`. Regression tests verify that passing baseline queries are excluded and inconsistent failure summaries are rejected.

The approved follow-up compared reranked candidate pools at fixed `top_k=5`, with Luna-low SQL generation and execution on the fixed snapshot. The user later stopped the follow-up after Phase 1 and removed Phase 2 plus its dependent all-120 rerun from the plan and TODO. The original T005 120-query baselines remain unchanged. The index contained 53 records, and Cohere requests were spaced by at least 6.5 seconds. A retrieval-only candidate-20 diagnostic from before the scope change is retained separately and is not treated as a Phase 1 SQL result.

Phase 1 completed on the same 53 failed query IDs, Python 3.14.10 ARM64 index manifest, fixed snapshot, `gpt-6-luna`, and `low` effort. Each configuration had zero Cohere service errors. Results (execution accuracy; mean input tokens; mean end-to-end latency; Recall@5/MRR; pure Cohere latency average/P50/P95) were:

| candidate_k | Execution | Tokens | E2E ms | Recall@5 | MRR | Cohere ms avg/P50/P95 |
|---:|---:|---:|---:|---:|---:|---:|
| 20 | 11/53 (20.8%) | 1,304 | 4,292 | 0.957 | 1.000 | 617 / 603 / 757 |
| 30 | 10/53 (18.9%) | 1,302 | 4,161 | 0.957 | 1.000 | 661 / 649 / 807 |
| 40 | 13/53 (24.5%) | 1,302 | 4,367 | 0.957 | 1.000 | 700 / 672 / 915 |
| 53 | 11/53 (20.8%) | 1,302 | 5,031 | 0.957 | 1.000 | 781 / 754 / 939 |

Candidate pool 40 had the highest accuracy among the completed Phase 1 candidate pools. Recall@5 and MRR tied across the four candidate sizes, while average Cohere latency and end-to-end latency rose at candidate 53. The per-query SQL/status, expected labels, retrieval rankings, token use, and latency samples are saved in `data/evaluation/experiments/failure-sql-phase1/`. Candidate 40 is an observed winner for this fixed 53-query experiment, not evidence that larger pools generally improve retrieval.

Before the user stopped Phase 2, three top-k configurations had completed on the same cohort, model settings, and snapshot. These are retained as partial exploratory evidence only; the Phase 2 matrix is incomplete and no recommendation is based on it.

| candidate_k | top_k | Execution | Mean input tokens | E2E average ms | Recall@5 | MRR | Cohere average ms |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 5 | 8/53 (15.1%) | 1,304 | 4,809 | 0.957 | 1.000 | 619 |
| 40 | 5 | 15/53 (28.3%) | 1,302 | 27,798 | 0.957 | 1.000 | 812 |
| 40 | 10 | 14/53 (26.4%) | 2,595 | 5,044 | 0.957 | 1.000 | 781 |

The candidate-40/top-5 E2E average includes a pronounced latency outlier and should be interpreted from its per-query records. The same candidate/top-k setting completed twice with different SQL execution accuracy (13/53 in Phase 1 and 15/53 in the partial Phase 2 run), so fixed model and effort settings did not produce identical outcomes across runs. Increasing top_k from 5 to 10 doubled mean input tokens in the one completed candidate-40 comparison without improving accuracy. These limited observations do not settle the top-k question.

The three completed exploratory result files and their SHA256 values are:

- `candidate-k-20-top-k-5.json` — `2e7769ca8cccf12e203546518417c68a770f3a76d2c2cd4f53dd4575de1ace03`
- `candidate-k-40-top-k-5.json` — `5c2a0f20adcbf2ef8688996e0b0ffd329b0d84a17c9aac40536e2a1e141ca24a`
- `candidate-k-40-top-k-10.json` — `ae34dfe8872cffa0a94bec79fa939ab2ef5772bfcd388b1b2cd5e16bc109a2d4`

The candidate-40/top-15 run was interrupted before an artifact was written; top-20 was not started. No additional 120-query run was performed. The original SQL and retrieval baseline hashes remain unchanged, and the complete Phase 1 and partial exploratory outputs are separate from those baselines.

Final T007 verification on Python 3.14.10 / ARM64: `uv run pytest -q` passed 49 tests, skipped seven environment-gated PostgreSQL integration tests, and reported five subtests passed; `uv lock --check`, `git diff --check`, baseline/cohort SHA256 checks, and saved-artifact identity checks passed. No benchmark process remained active after the user stopped the top-k runs.
