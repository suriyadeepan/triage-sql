## FS-02 — Lightweight Hybrid Schema RAG (`nse-rag` reuse)

**Purpose:** Retrieve query-relevant Azraq schema context and validated JOIN relationships for Text-to-SQL generation.

**Reference implementation:** [github.com/suriyadeepan/nse-rag](https://github.com/suriyadeepan/nse-rag)

**Requirements**

### Reuse from `nse-rag`
- **Dense retrieval:** Reuse SentenceTransformer embeddings and Chroma vector search.
- **Lexical retrieval:** Reuse BM25 indexing and search for exact table/column identifiers, banking terminology, and phrases.
- **Hybrid fusion:** Reuse Reciprocal Rank Fusion (RRF) to combine dense and BM25 rankings.
- **Optional reranking:** Retain the Cohere Rerank v5 Fast integration as an optional experiment; defer enabling it unless evaluation demonstrates sufficient benefit.
- **Evaluation:** Adapt the existing retrieval benchmark approach, query labels, ranked-result inspection, Recall@K, MRR, and per-mode latency measurements.

### Adapt for Azraq
- Replace PDF downloading, ZIP extraction, PyMuPDF parsing, LlamaIndex chunking, and circular-document metadata with structured schema metadata.
- Build searchable records from:
  - `data/raw/azraq-schema.sql` — 26 tables, columns, and data types.
  - `data/raw/azraq-relationships.yaml` — relationship endpoints, cardinality, subtype predicates, status, confidence, and provenance.
  - `data/raw/azraq.md` — relevant source observations.
- Represent tables and relationships as structured retrieval records rather than arbitrary text chunks. Preserve exact identifiers and metadata.
- Exclude `users.password`, credentials, and sensitive values from indexing and prompts.
- Treat relationship metadata as external to DDL. Only reviewed `validated` edges are eligible JOIN candidates; exclude `needs_review` and candidate edges.
- Preserve relationship direction, cardinality, and subtype predicates:
  - Group, individual-member, and NSG joins require their corresponding `clients.type` filters.
  - `collaterals.owner_id` accepts any client type.
- Return relevant tables, columns, types, descriptions, and eligible relationships, including exact JOIN predicates and relationship provenance/status.
- Keep the index version-aware: record schema, relationship metadata, and snapshot identities; detect stale indexes and support deterministic rebuilds.
- Do not reuse document-specific circular citations, PDF page references, or claim-validation logic.

### Retrieval modes
- Dense: SentenceTransformers + Chroma.
- Lexical: BM25.
- Hybrid: Dense + BM25 + RRF.
- Optional: Hybrid + Cohere reranking.

Keep modes independently configurable and testable.

### Acceptance criteria
- All 26 tables are represented; sensitive fields and values are excluded.
- Retrieved context preserves exact identifiers, relationship direction, and subtype predicates.
- Unvalidated relationships never appear as JOIN candidates.
- Dense, BM25, and RRF modes are independently testable.
- Index source versions are recorded; stale indexes are detected and reproducibly rebuilt.
- Evaluate against the fixed 120-query Azraq dataset. Derive relevant table, column, and relationship labels from reference SQL and validated relationship metadata.
- Compare Recall@K and MRR across retrieval modes; report retrieval latency (average, P50, P95).
- Benchmark against full-schema prompt injection for SQL execution accuracy, prompt-token usage, and latency.
- Evaluate reranking separately; retain it only if its quality improvement justifies added latency and external-service dependency.
- Document retrieval failures by query category, especially exact identifiers, semantic questions, and multi-table joins.
