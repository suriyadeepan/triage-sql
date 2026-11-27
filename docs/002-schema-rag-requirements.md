# FS-02 — Lightweight Hybrid Schema RAG Requirements

**Purpose:** Retrieve query-relevant Azraq schema context and validated JOIN relationships for Text-to-SQL generation.

**Reference implementation:** [suriyadeepan/nse-rag](https://github.com/suriyadeepan/nse-rag)

## Requirements

### R001 — Reuse retrieval techniques

- **R001.1** Reuse SentenceTransformer embeddings and Chroma vector search for dense retrieval.
- **R001.2** Reuse BM25 indexing and search for exact table/column identifiers, banking terminology, and phrases.
- **R001.3** Reuse Reciprocal Rank Fusion (RRF) to combine dense and BM25 rankings.
- **R001.4** Retain Cohere Rerank v5 Fast as an optional experiment; defer enabling unless evaluation demonstrates sufficient benefit.
- **R001.5** Adapt the existing retrieval benchmark approach: query labels, ranked-result inspection, Recall@K, MRR, and per-mode latency measurements.

### R002 — Structured Azraq schema records

- **R002.1** Replace PDF downloading, ZIP extraction, PyMuPDF parsing, LlamaIndex chunking, and circular-document metadata with structured schema metadata.
- **R002.2** Build records from `data/raw/azraq-schema.sql` (26 tables, columns, and data types), `data/raw/azraq-relationships.yaml` (endpoints, cardinality, subtype predicates, status, confidence, and provenance), and relevant observations from `data/raw/azraq.md`.
- **R002.3** Represent tables and relationships as structured retrieval records rather than arbitrary text chunks. Preserve exact identifiers and metadata.
- **R002.4** Exclude `users.password`, credentials, and sensitive values from indexing and prompts.
- **R002.5** Treat relationship metadata as external to DDL. Only reviewed `validated` edges are eligible JOIN candidates; exclude `needs_review` and candidate edges.
- **R002.6** Preserve relationship direction, cardinality, and subtype predicates:
  - Group, individual-member, and NSG joins require their corresponding `clients.type` filters.
  - `collaterals.owner_id` accepts any client type.
- **R002.7** Return relevant tables, columns, types, descriptions, and eligible relationships, including exact JOIN predicates and relationship provenance/status.
- **R002.8** Record schema, relationship metadata, and snapshot identities; detect stale indexes and support deterministic rebuilds.
- **R002.9** Do not reuse document-specific circular citations, PDF page references, or claim-validation logic.

### R003 — Retrieval modes

- **R003.1** Provide dense retrieval with SentenceTransformers and Chroma.
- **R003.2** Provide lexical retrieval with BM25.
- **R003.3** Provide hybrid retrieval with dense, BM25, and RRF.
- **R003.4** Provide optional hybrid plus Cohere reranking.
- **R003.5** Keep modes independently configurable and testable.

### R004 — Evaluation and comparison

- **R004.1** Evaluate against the fixed 120-query Azraq dataset. Derive relevant table, column, and relationship labels from reference SQL and validated relationship metadata.
- **R004.2** Compare Recall@K and MRR across retrieval modes; report retrieval latency (average, P50, P95).
- **R004.3** Benchmark against full-schema prompt injection for SQL execution accuracy, prompt-token usage, and latency.
- **R004.4** Evaluate reranking separately; retain it only if its quality improvement justifies added latency and external-service dependency.
- **R004.5** Document retrieval failures by query category, especially exact identifiers, semantic questions, and multi-table joins.

## Acceptance criteria

- **A001** All 26 tables are represented; sensitive fields and values are excluded.
- **A002** Retrieved context preserves exact identifiers, relationship direction, and subtype predicates.
- **A003** Unvalidated relationships never appear as JOIN candidates.
- **A004** Dense, BM25, and RRF modes are independently testable.
- **A005** Index source versions are recorded; stale indexes are detected and reproducibly rebuilt.
- **A006** Retrieval is evaluated on the fixed 120-query dataset with derived table, column, and relationship labels.
- **A007** Recall@K, MRR, average/P50/P95 retrieval latency, and ranked results are compared across modes.
- **A008** Full-schema prompt injection is benchmarked for SQL execution accuracy, prompt-token usage, and latency.
- **A009** Reranking is evaluated separately and retained only when quality gains justify latency and external-service costs.
- **A010** Failures are documented by query category, including exact identifiers, semantic questions, and multi-table joins.

## Planning assumptions and gaps

- The repository contains `data/evaluation/azraq-evaluation.jsonl` with 120 entries and a validated-only relationship API in `src/triage_sql/relationships.py`; the plan adapts these existing artifacts.
- The requested SentenceTransformer dense encoder differs from the current `nse-rag` README's OpenAI embedding backend. The reference provides retrieval patterns (Chroma, BM25, RRF, benchmark structure); FS-02 uses the explicitly required SentenceTransformers encoder.
- The exact SentenceTransformer model is not prescribed. The implementation makes the model configurable and records its immutable identity/revision; the default is `sentence-transformers/all-MiniLM-L6-v2`.
- The model-neutral prompt benchmark needs a caller-configured SQL generator before SQL execution accuracy, prompt-token use, and end-to-end latency can be measured. No provider/model has been selected for this feature.
- The retrieved context is schema metadata only. No dataset row values or credentials are indexed or returned.
