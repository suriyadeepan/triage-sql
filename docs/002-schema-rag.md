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
