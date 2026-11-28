# FS-02 — Lightweight Hybrid Schema RAG Plan

## Scope and approach

Implement [FS-02 requirements](002-schema-rag-requirements.md) as a local structured retrieval component in `src/triage_sql/`. Reuse the retrieval patterns in [nse-rag](https://github.com/suriyadeepan/nse-rag) (Chroma, BM25, RRF, ranked retrieval evaluation), while using SentenceTransformers as explicitly required for dense embeddings. The reference repository currently documents an OpenAI embedding backend, so its document ingestion and embedding implementation are not copied.

Parse the DDL and external YAML into stable table/column and relationship records. Use descriptions from `azraq.md` only where safe and useful; do not index sample rows, credentials, or `users.password`. Keep joins strictly behind the existing validated relationship policy and preserve endpoint direction, cardinality, subtype filters, provenance, and status. Persist indexes with hashes/identities for all source artifacts, encoder model/revision, and record format; rebuild deterministically when any indexed source identity differs.

Expose independently configurable dense, BM25, hybrid RRF, and optional hybrid-rerank modes. Derive gold table, column, and validated relationship labels from each reference SQL query. Evaluate ranked retrieval and latency on all 120 queries, then compare schema-retrieval prompting with full-schema injection using the same SQL execution harness and report token use and latency. Keep Cohere opt-in; report rerank results separately and retain only if measured quality gains justify its latency and external dependency.

## Plan

### P001 — Define safe structured schema records

- **P001.1** Parse the authoritative 26-table DDL, relationship YAML, and relevant source observations into typed, deterministic table/column and relationship records. **Requirements:** R002.1–R002.3; R002.9.
- **P001.2** Enforce password/credential/value exclusions at record construction and prompt serialization. **Requirements:** R002.4; A001.
- **P001.3** Reuse the validated-only relationship policy; include exact join orientation, cardinality, subtype predicate, provenance, and status in eligible relationship context. **Requirements:** R002.5–R002.7; A002–A003.

### P002 — Implement versioned indexes and modes

- **P002.1** Add SentenceTransformer embeddings with Chroma storage for structured records; record configurable model identity and revision. **Requirements:** R001.1; R003.1.
- **P002.2** Add BM25 indexing/search with exact identifiers and domain descriptions retained in searchable fields. **Requirements:** R001.2; R003.2.
- **P002.3** Implement RRF over independently produced dense and BM25 rankings and expose all modes through a common configurable retrieval interface. **Requirements:** R001.3; R003.3–R003.5; A004.
- **P002.4** Record DDL, relationship YAML, observations, encoder, and record-format identities; detect staleness and build equivalent indexes deterministically. **Requirements:** R002.8; A005.
- **P002.5** Add optional Cohere Rerank v5 Fast on hybrid candidates, disabled by default and requiring explicit mode selection. **Requirements:** R001.4; R003.4; R004.4.

### P003 — Evaluate retrieval and prompt baselines

- **P003.1** Derive per-query relevant table, column, and validated relationship IDs from the fixed 120 reference SQL statements and relationship metadata. **Requirements:** R001.5; R004.1; A006.
- **P003.2** Report per-mode ranked results, Recall@K, MRR, average/P50/P95 latency, and category breakdowns for exact identifiers, semantic questions, and multi-table joins. **Requirements:** R001.5; R004.2; R004.5; A007; A010.
- **P003.3** Compare retrieved context against full-schema injection on the same query set for SQL execution accuracy, prompt-token usage, and end-to-end latency. **Requirements:** R004.3; A008.
- **P003.4** Evaluate reranking separately and report quality change, added latency, and external-service dependency; retain it only if evidence meets the stated trade-off. **Requirements:** R004.4; A009.

### P004 — Regression coverage and evidence

- **P004.1** Add regression coverage for all-table parsing, sensitive-field/value exclusion, exact identifiers, join direction, subtype predicates, and refusal to surface unvalidated/candidate edges.
- **P004.2** Test dense, lexical, and fusion behavior independently; test stale-index detection and deterministic rebuild identity.
- **P004.3** Record benchmark commands, environment, model/index identities, metrics, ranked-result artifacts, failures, and limitations in the feature journal.

### Approved follow-up experiment scope

The user narrowed T007 to Phase 1 only: compare candidate pools at `top_k=5` on the frozen SQL failure cohort, generate with `gpt-6-luna` / `low`, and execute against the fixed snapshot. Phase 2 top-k optimization and the conditional new all-120 rerun were removed from this follow-up at the user's direction. The original 120-query full-schema and retrieved-schema baselines required by R004.3/P003.3 remain recorded under T005; no additional full-set run is planned here. Three Phase 2 outputs had completed before the stop request and are retained as explicitly partial exploratory evidence in the journal, not as a completed phase or configuration recommendation.

## Affected files and dependencies

- Existing inputs: `data/raw/azraq-schema.sql`, `data/raw/azraq-relationships.yaml`, `data/raw/azraq.md`; evaluation input `data/evaluation/azraq-evaluation.jsonl`.
- Existing integration point: `src/triage_sql/relationships.py` and its relationship tests.
- Expected additions: structured schema record/parser module(s), index/retriever module(s), retrieval CLI or script, benchmark/label derivation script(s), unit/integration tests, and feature documentation.
- Dependency changes likely include `sentence-transformers`, `chromadb`, and a BM25 implementation; Cohere dependency should be optional or isolated to rerank use. Resolve exact versions with `uv` during implementation.
- Index output is generated local state and must not replace or modify raw schema/evaluation inputs.

## Architecture compatibility matrix

| Area | Status | Evidence and action |
|---|---|---|
| Python runtime | VERIFIED | Project requires Python `>=3.14` and uses `uv`; user confirms Python 3.14 is the target. Preserve the project runtime and lockfile workflow. |
| Host CPU/OS | VERIFIED | User confirms the target PC is ARM64. Validate native wheels and inference execution for selected dependencies on ARM64. |
| Existing DB/schema components | VERIFIED | Relationship loader is Python/PyYAML/psycopg and supplies validated-only JOIN clauses; DDL and YAML are local inputs. |
| SentenceTransformers/PyTorch on Python 3.14 ARM64 | VERIFIED | `uv` resolved SentenceTransformers 6.3.0/PyTorch 2.15.0; imports and CPU model inference succeeded on Python 3.14.10 ARM64. MPS is available on the current Mac ARM host. |
| Chroma persistence on target runtime | VERIFIED | Chroma 1.5.9 persistent create/query/rebuild tests pass on Python 3.14.10 ARM64. |
| BM25 library/runtime | VERIFIED | `rank-bm25` 0.2.2 is locked and retrieval tests pass on Python 3.14.10 ARM64. |
| Cohere service | VERIFIED as optional external integration | Reference `nse-rag` uses Cohere Rerank v5 Fast and an API key. A trial key reported a 10-request/minute cap. Keep opt-in; benchmark dependency/network latency and never require credentials for core modes. |
| Deployment/CI target | UNKNOWN | No target was established in FS-01 planning. Keep local CLI/library operation reproducible; add compatibility checks to configured CI if present. |

## Risks and mitigations

- **Native runtime and installation size:** SentenceTransformers/PyTorch add substantial dependencies and model downloads. Python 3.14 ARM64 CPU inference works in the current environment; record model revision, keep reranking optional, and document required model download/cache space.
- **Prompt benchmark provider:** Keep the SQL generator model-neutral. Execution accuracy, prompt-token use, and end-to-end latency remain pending until the caller configures a provider; never substitute reference SQL for generated SQL.
- **Provider configuration:** Optional OpenAI and Cohere adapters load the project `.env` with `python-dotenv` while preserving process environment overrides. The SQL adapter passes `OPENAI_REASONING_EFFORT` when configured; model and effort remain caller-selected and model-dependent.
- **Untrusted joins:** relationship records are not database constraints. Reuse validated-only filtering and assert candidate/needs-review edges are excluded at retrieval serialization boundaries.
- **Sensitive metadata leakage:** schema descriptions include sample observations. Build explicit allowlisted fields and test that password names, credential-like fields, and row values cannot enter records or prompts.
- **Stale or irreproducible index:** hash source files and record model/revision, library versions, record format, and deterministic build settings in a manifest; rebuild on mismatch.
- **Evaluation label bias:** reference SQL can mention unsupported or nonvalidated joins. Derive only eligible relationship labels from validated metadata and separately surface unresolved reference joins for review rather than granting them relevance.
- **Benchmark comparability:** run retrieval and full-schema baselines on the identical 120 queries, database snapshot, model, and SQL evaluation harness; separate cold build costs from query latency.
- **Reranker service variance:** keep Cohere outside default modes and report per-query service latency and availability separately.
- **Cohere trial throughput:** a live request showed the configured trial key is limited to 10 requests per minute. Pace requests and record this constraint; use a stratified sample when full-corpus reranking would exceed the available run window or quota.

## Acceptance criteria and validation

Satisfy [A001–A010](002-schema-rag-requirements.md). Validate all 26 parsed tables; sensitive-field/value exclusion; exact record identifiers and join predicates; no unvalidated JOIN candidates; separate mode correctness; source/model manifest staleness and reproducible rebuild; and labeled 120-query comparisons. Report Recall@K, MRR, ranked lists, average/P50/P95 retrieval latency, SQL execution accuracy, prompt-token use, and end-to-end latency for retrieval and full-schema prompt baselines. Keep reranker measurements separate. Use `uv` for Python environment commands and record verification evidence in `docs/002-schema-rag.md` during implementation.
