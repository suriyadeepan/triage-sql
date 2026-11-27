# FS-02 — Lightweight Hybrid Schema RAG TODO

Tasks are the canonical status source. Lineage: requirement → plan → task → implementation/tests.

## T001 — Parse and protect structured schema records [x]

**Requirements:** R002.1–R002.4, R002.9, A001–A002
**Plan:** P001.1–P001.2
**Files:** new schema-record/parser module(s), `data/raw/azraq-schema.sql`, `data/raw/azraq.md`, tests, journal
**Depends on:** none

- [x] **T001.1** Parse all 26 DDL tables and columns into deterministic typed records and add safe descriptions from source observations. **Accept:** all source identifiers/types are represented; no sample row values enter retrieval records. **Depends on:** none.
- [x] **T001.2** Apply an explicit field allowlist and sensitive-name/value exclusions before record serialization. **Accept:** `users.password`, credential-like fields, and sensitive values cannot appear in indexed or prompt records; regression tests cover the exclusions. **Depends on:** T001.1.

## T002 — Relationship retrieval records and JOIN safety [x]

**Requirements:** R002.2–R002.7, A002–A003
**Plan:** P001.1, P001.3
**Files:** `src/triage_sql/relationships.py` integration or new relationship-record module, `data/raw/azraq-relationships.yaml`, tests, journal
**Depends on:** T001

- [x] **T002.1** Convert external relationship metadata to structured records retaining endpoints/direction, cardinality, subtype filter, confidence, evidence/provenance, status, and candidate marker. **Accept:** eligible records serialize exact JOIN predicates and their provenance/status. **Depends on:** T001.1.
- [x] **T002.2** Enforce validated-only eligibility at retrieval output, excluding `needs_review`, inferred, and unresolved candidate edges. **Accept:** none are returned as JOIN candidates; the Group, Individual, NSG, and any-client predicates are exact. **Depends on:** T002.1.

## T003 — Versioned dense, lexical, and hybrid retrieval [x]

**Requirements:** R001.1–R001.3, R002.8, R003.1–R003.3, R003.5, A004–A005
**Plan:** P002.1–P002.4
**Files:** retrieval/index modules, `pyproject.toml`, `uv.lock`, tests, journal
**Depends on:** T001, T002

- [x] **T003.1** Add configurable SentenceTransformer model/revision embeddings and persistent Chroma indexing for structured records. **Accept:** index create/reopen works on Python 3.14 ARM64 CPU; manifest records model/revision and runtime dependency versions. **Depends on:** T001.
- [x] **T003.2** Add independently callable BM25 indexing/search over table/column identifiers and safe domain descriptions. **Accept:** lexical mode ranks exact identifiers and phrases and has isolated tests. **Depends on:** T001.
- [x] **T003.3** Add independent dense and hybrid modes with RRF fusion behind a common retrieval interface. **Accept:** dense, BM25, and RRF behavior are independently tested and return structured records with exact metadata. **Depends on:** T003.1, T003.2, T002.
- [x] **T003.4** Persist source hashes/identities for DDL, relationship YAML, observations, record format, and encoder; detect stale source/model state and rebuild deterministically. **Accept:** changes invalidate the index and repeated builds from identical inputs produce matching manifest/record identity. **Depends on:** T003.1–T003.3.

## T004 — Optional Cohere reranking [x]

**Requirements:** R001.4, R003.4, R004.4, A009
**Plan:** P002.5, P003.4
**Files:** optional reranker module/configuration, `pyproject.toml`/lock if needed, tests, benchmark, journal
**Depends on:** T003

- [x] **T004.1** Add explicit opt-in Cohere Rerank v5 Fast over hybrid candidates; keep core retrieval independent of Cohere credentials/service. **Accept:** default modes issue no Cohere request and rerank mode reports service failure/latency separately. **Depends on:** T003.3.
- [x] **T004.2** Evaluate quality and latency separately; retain reranking in supported configuration only when measured quality gain justifies added latency and external dependency. Pace Cohere trial requests to its observed 10 requests/minute limit; if evaluation uses a sample, document its selection and size. **Accept:** report per-mode results and the evidence-based retain/defer decision. **Depends on:** T005.

## T005 — Retrieval labels and benchmarks [x]

**Requirements:** R001.5, R004.1–R004.5, A006–A010
**Plan:** P003.1–P003.4
**Files:** `data/evaluation/azraq-evaluation.jsonl`, benchmark and label scripts, tests, journal
**Depends on:** T003

- [x] **T005.1** Derive gold table, column, and validated relationship labels from all 120 reference SQL queries and relationship metadata. **Accept:** every query has reproducible labels; references involving ineligible relationships are surfaced for review and are not labeled eligible. **Depends on:** T002.
- [x] **T005.2** Run dense, BM25, and hybrid modes on the fixed query set and preserve ranked-result inspection data, Recall@K, MRR, category breakdowns, and average/P50/P95 retrieval latency. **Accept:** results are reproducible from recorded model/index/query identities and cover exact identifiers, semantic questions, and multi-table joins. **Depends on:** T005.1, T003.
- [x] **T005.3** Implement and run a model-neutral SQL generator benchmark against retrieved-schema and full-schema prompt strategies. **Depends on:** T005.1, T005.2.
  - [x] **T005.3.1** Implement a provider-neutral generation interface, configurable OpenAI Responses adapter, prompt construction, SQL safety validation, read-only execution, token accounting, and latency reporting. **Accept:** regression tests cover adapter output, prompt exclusion, writes, sensitive columns/functions, and result limits. **Depends on:** none.
  - [x] **T005.3.2** Run all 120 queries through both strategies with a caller-configured `OPENAI_MODEL` and the fixed database snapshot. **Accept:** report SQL execution accuracy, prompt-token use, and end-to-end latency, with query-category failures. The run used the caller-configured `.env` settings. **Depends on:** T005.3.1.
- [x] **T005.4** Run optional rerank evaluation and record results for T004.2. **Accept:** quality delta, added latency, external-service dependency, and retain/defer decision are explicit; document the 10-query sample and observed 10 calls/minute trial limit. **Depends on:** T004.1, T005.2.

## T006 — Compatibility, regression, and documentation [x]

**Requirements:** R001–R004, A001–A010
**Plan:** P004.1–P004.3
**Files:** `tests/`, scripts/modules added by T001–T005, `docs/002-schema-rag.md`, tutorial on completion
**Depends on:** T001–T005

- [x] **T006.1** Add and run unit/integration checks for schema safety, relationship eligibility/predicates, each retrieval mode, stale-index rebuilds, and label derivation. **Accept:** prescribed `uv` commands pass on Python 3.14 ARM64; commands/results are recorded. **Depends on:** T001–T005.
- [x] **T006.2** Document setup, index build/query, modes, source/model manifest, evaluation method/results, limitations, and failure categories in the durable journal. **Accept:** all commands and metrics have recorded evidence; no unverified success claims. **Depends on:** T005.
- [x] **T006.3** Create or append the user tutorial at feature completion. **Accept:** tutorial follows repository naming and append-only convention. **Depends on:** T006.2.

## T007 — Failure-focused retrieval and reranked SQL optimization [x]

**Requirements:** R001.5, R004.1–R004.5, A006–A010
**Plan:** P003.2–P003.4
**Files:** frozen `data/evaluation/azraq-sql-prompt-results.json` and `data/evaluation/azraq-retrieval-results.json`; failure-cohort artifacts; benchmark scripts/tests; new experiment result artifacts; `docs/002-schema-rag.md`
**Depends on:** T005–T006

- [x] **T007.1** Freeze the original 120-query baseline before experiments. **Requirements:** R004.1, R004.3; **Plan:** P003.1, P003.3. **Files:** the two existing result artifacts and `docs/002-schema-rag.md`. **Accept:** preserve the committed SQL result SHA256 `ee7beb0a1229fe8fad1985d1f37591054eb0feac082b7e2c2f7c72dffb6e09e1` and retrieval result SHA256 `f4eaa6a81b951380c38f8c42eae29ccd25bdd0ea3fbb631d9692ca3a37cfe776`; record query-set SHA256 `1cbe40d2d027a28d32fd39e91807e6427c6fad10d8a338a488b60bc7703dc87a`, index-manifest SHA256 `e3e9c32aa1b62321e7dc3664061945e37bc3ffcad04b1fd1b33bad64586ce92b`, snapshot `ba058d581b04d1d75f63ac0a4705d98ea0d8ea54dcf577ee90b58222d082dddc`, model `gpt-6-luna`, reasoning effort `low`, and baseline `candidate_k=20` / `top_k=5`. Keep these result artifacts unchanged and write follow-up runs to new paths. **Depends on:** T005.3.2.
- [x] **T007.2** Extract the retrieved-schema SQL failures from the frozen baseline into a deterministic query/label cohort. **Requirements:** R004.1; **Plan:** P003.1. **Files:** new `scripts/extract_azraq_sql_failures.py`, `data/evaluation/azraq-retrieval-failure-labels.jsonl`, and tests. **Accept:** include exactly the 53 failed IDs from the original retrieved-schema run, retain their categories, expected results, and relevant labels, and test that no passing baseline query enters the cohort. **Depends on:** T007.1.
- [x] **T007.3** Run Phase 1 SQL experiments on the frozen failure cohort with Cohere `rerank-v5.0-fast` enabled and `top_k=5`: baseline `candidate_k=20`, then `candidate_k=30`, `40`, and `53` (the full current index). Generate SQL with the configured Luna model at `low` reasoning effort and execute against the fixed snapshot. **Requirements:** R001.5, R004.2–R004.5; **Plan:** P003.2–P003.4. **Files:** `scripts/benchmark_azraq_failure_sql.py`, `src/triage_sql/prompt_benchmark.py`, tests, and new Phase 1 result artifacts. **Accept:** use identical query IDs, index/model revision, snapshot, generator settings, and labels; report SQL execution accuracy, mean input tokens, end-to-end latency, effective candidate count, Recall@5, MRR, per-query rankings, Cohere latency, and category breakdown. Confirm the current index record count before running; if it differs from 53, cap the largest candidate pool at the actual count and record it. Pace Cohere calls to the observed free-tier cap of 10 requests/minute (at least 6.5 seconds between requests); preserve each configuration in a separate result artifact. **Depends on:** T007.2.
- [x] **T007.6** Document the frozen baseline, deterministic failure cohort, completed Phase 1 candidate-pool results, incidental partial exploratory evidence, and the user-directed scope narrowing. **Requirements:** R001.5, R004.1–R004.5, A006–A010; **Plan:** P003.1–P003.4. **Files:** `docs/002-schema-rag.md` and saved experiment artifacts. **Accept:** record hashes/configuration identities, distinguish complete results from partial runs, preserve original baselines, and state that no additional full-set revalidation ran. **Depends on:** T007.1–T007.3.
