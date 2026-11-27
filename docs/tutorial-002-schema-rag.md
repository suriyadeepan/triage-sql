# Tutorial: Retrieve Azraq Schema Context

This tutorial shows how to build the local schema index, retrieve validated JOIN guidance, and run the retrieval and SQL-generation evaluations.

## Requirements

Use Python 3.14 and `uv`. SentenceTransformers runs locally and Chroma stores the persistent index under the ignored `data/index/` directory. The first dense build downloads the configured embedding model. Optional Cohere and OpenAI client packages can be installed with:

```sh
uv sync --dev --extra rerank --extra openai-benchmark
```

The API adapters load `.env` without overriding values already exported by the shell. Keep `.env` local; never put API keys in source control. The OpenAI SQL evaluation also requires a caller-selected `OPENAI_MODEL`. `OPENAI_REASONING_EFFORT` is optional and model-dependent.

## Build and query

Build an index from the DDL, relationship YAML, safe source observations, and fixed snapshot manifest:

```sh
uv run python scripts/schema_rag.py build
```

Query any supported mode:

```sh
uv run python scripts/schema_rag.py query "Which tables connect clients to loans?" --mode hybrid --top-k 5
uv run python scripts/schema_rag.py query "groups_members.member_id" --mode bm25 --top-k 5
uv run python scripts/schema_rag.py query "Which client subtype owns NSG meetings?" --mode dense --top-k 5
```

Available modes are `dense`, `bm25`, `hybrid`, and opt-in `hybrid-rerank`. Retrieved relationship records retain endpoint direction, exact join predicate, subtype filter, cardinality, validation status, confidence, and provenance. Only validated relationships are eligible JOIN candidates. Group, Individual-member, and NSG joins carry their corresponding `clients.type` filters; collateral owners accept any client type. Sensitive columns such as `users.password` and row values are excluded.

The index manifest captures source hashes, dataset snapshot identity, encoder revision, record format, runtime, and relevant dependency versions. A changed source or model identity makes the index stale; rebuild it with the build command.

## Retrieval evaluation

Regenerate labels from reference SQL and run all fixed retrieval modes:

```sh
uv run python scripts/label_azraq_retrieval.py
uv run python scripts/benchmark_azraq_retrieval.py
```

The label and ranked-result artifacts are `data/evaluation/azraq-retrieval-labels.jsonl` and `data/evaluation/azraq-retrieval-results.json`. They contain 120 queries, per-mode rankings, Recall@5, MRR, latency percentiles, and category failures. The current warm-query results are documented in the [FS-02 journal](002-schema-rag.md).

## Optional Cohere reranking

Reranking is disabled unless `hybrid-rerank` is selected. The trial key used for the FS-02 evaluation reported a limit of 10 calls per minute. Start with the recorded stratified sample and pacing:

```sh
uv run python scripts/benchmark_azraq_retrieval.py --rerank --rerank-limit 10 --rerank-delay-seconds 6.5
```

Check the active account quota before increasing the sample. The service latency and failures are reported separately from local retrieval latency.

## Compare SQL prompts

Set `OPENAI_MODEL` in `.env` or the shell, and optionally set `OPENAI_REASONING_EFFORT` to a value supported by that model. Then run the module command against the fixed local PostgreSQL snapshot:

```sh
uv run python -m scripts.benchmark_azraq_sql
```

The module invocation is required for this script's `scripts` imports. The default run sends one retrieved-schema and one full-schema prompt for each of 120 questions. It validates each generated statement, runs only read-only SQL, limits query time and returned rows, and writes per-query results to `data/evaluation/azraq-sql-prompt-results.json`. This makes real provider calls and may incur API usage. Do not use reference SQL as a substitute for generated output.

In the recorded run, the caller-configured `gpt-6-luna` model with `low` effort achieved 55.8% execution accuracy with retrieved context and 71.7% with full-schema prompts. Retrieved context reduced mean input tokens by 88.3% (1,559.7 versus 13,376.9); mean end-to-end latency was 3,148 ms versus 3,011 ms. See the journal and result artifact for query categories, P50/P95, and individual failures.
