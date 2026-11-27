# Agentic Text-to-SQL POC — Feature Specifications

**Type:** Engineering POC with lightweight MLOps/deployment  
**Objective:** Extend the Azraq Text-to-SQL + RAG pipeline into a tiered agentic system demonstrating PEFT/QLoRA, AWQ/GPTQ, vLLM, adaptive routing, MLflow, CI/CD, and automated deployment.  
**Scope:** Reuse existing Text-to-SQL and `nse-rag` components. Prioritize working, measurable implementations; exclude Kubernetes, distributed serving, multi-LoRA, and extensive security hardening.

## FS-01 — Azraq Data, Schema & Evaluation

**Purpose:** Reproducible banking data and leakage-safe SQL training/evaluation.

**Requirements**
- Treat `data/raw/` as the source-data location. Use its Azraq CSVs plus:
  - `data/raw/azraq-schema.sql` — 26-table DDL and inferred column types.
  - `data/raw/azraq-relationships.yaml` — external relationship metadata, evidence, confidence, subtype filters, and validation policy.
  - `data/raw/azraq.md` — source observations, if present.
- Preserve source table/column names and inferred types; do not invent generic `accounts`/`transactions` tables. The 26 tables are: `branches`, `cities`, `client_locations`, `clients`, `collateral_products`, `collaterals`, `currencies`, `delinquency_tracking`, `districts`, `economic_activities`, `exchange_rates`, `funding_lines`, `groups_members`, `loan_products`, `loan_tranches`, `loan_writeoffs`, `loans`, `manual_schedule_adjustments`, `nsg_meetings`, `regions`, `repayments`, `roles`, `savings_accounts`, `savings_products`, `savings_transactions`, `users`.
- DDL declares no PK/FK constraints. Keep inferred relationships in YAML; never treat them as database-enforced constraints. Preserve endpoints, cardinality, status, confidence, evidence/provenance, and subtype filters. Do not use `needs_review` or merely `inferred` edges for JOIN generation; require reviewed `validated` status.
- Preserve the four profiled `clients.type` ranges as evidence only: Individual 1–2,800,000; Group 2,800,001–3,200,000; NSG 3,200,001–3,400,000; Corporate 3,400,001–4,000,000. Preserve subtype-aware links: `collaterals.owner_id` → `clients.id` (any type); `groups_members.group_id` → `clients.id` (`type='Group'`); `groups_members.member_id` → `clients.id` (`type='Individual'`); `nsg_meetings.group_id` → `clients.id` (`type='NSG'`). Keep all other YAML relationships and evidence.
- Do not overstate integrity: YAML records 1,000-row randomized samples per source for these four links (seed `20261127`, zero null/nonmatch in each sample), plus manual full-file subtype counts; full null/orphan validation is explicitly `not_performed`. Promote relationships only after checking target-key uniqueness, nulls, orphans, subtype mismatches, and semantics.
- Use synthetic/anonymized data only. Exclude secrets, especially `users.password`, from prompts, indexes, and generated examples; use safe placeholders only if needed for loading.
- Initialize reproducibly from versioned DDL, raw data/import scripts, and relationship metadata. Record dataset/schema versions, row counts, and sampling/subsetting.
- Create ~100–200 NL evaluation queries with reference SQL and expected results, covering filters, joins (including subtype-aware), aggregations, dates, and supported multi-table questions. Label unsupported/ambiguous questions; do not fabricate SQL.
- Generate separate synthetic Text-to-SQL and SQL-correction examples from the actual schema/validated relationships. Parse and execute generated SQL. Keep train/validation/held-out sets separate; split by query/template pattern where practical and prevent held-out question, SQL, or result leakage.

**Acceptance criteria**
- Reproducible database initialization; all 26 tables/columns represented or exclusions documented.
- Relationship metadata remains separate from DDL; only `validated` edges reach JOIN generation. Subtype predicates are correct.
- Validation reports target uniqueness, null, matched, orphan, and (where applicable) subtype-mismatch counts; no full-integrity claim without full coverage.
- Every evaluation item has reference SQL and execution outcome on a fixed DB snapshot, or an explicit unsupported/ambiguous label.
- Training/correction examples are independently validated; automated checks detect held-out leakage.

## FS-02 — Hybrid Schema RAG (`nse-rag` reuse)

**Purpose:** Retrieve schema context for SQL generation.

**Requirements**
- Reuse/adapt `nse-rag` retrieval, ranking, and metadata tools. Index table/column names, descriptions, and relationship metadata.
- Dense retrieval: SentenceTransformers + Chroma. Keyword retrieval: BM25. Fuse with RRF; optionally rerank with Cohere Rerank v5 Fast.
- Return relevant tables, columns, descriptions, and eligible relationships for prompts.

**Acceptance criteria:** NL queries retrieve usable schema context; dense, BM25, and fused retrieval are independently exercisable; retrieved context reaches SQL-generation prompts.

## FS-03 — Text-to-SQL Proposal Generator

**Purpose:** Turn user intent into a lightweight execution plan.

**Requirements:** Identify the data task; use Luna as master orchestrator; plan schema retrieval → SQL generation → validation → execution → result analysis. Do not build a separate complex planning agent.

**Acceptance criteria:** Each NL request yields an actionable plan identifying SQL generation and downstream steps.

## FS-04 — Tiered LLM Stack & Adaptive Routing

**Purpose:** Use the least expensive suitable model with a stronger fallback.

| Tier | Model | Responsibility |
|---|---|---|
| Master/orchestrator | Luna (low) | Intent, planning, model selection, tool orchestration, synthesis |
| Reasoning | DeepSeek V4.1 Flash | Complex SQL/schema reasoning and difficult correction |
| Local specialist | Fine-tuned 1.5B–3B model | Routine SQL generation and simple correction |

**Requirements**
- Luna coordinates; it does not generate every SQL query.
- Route routine work locally; complex SQL/schema work to DeepSeek. Escalate local failures/low confidence.
- Use simple rules and confidence/failure signals, not elaborate routing.
- Log model, routing reason, tokens, latency, and estimated cost per query; Luna synthesizes the response.

**Acceptance criteria:** Requests route to either model; low-confidence/failed local attempts escalate; routing and usage are inspectable.

## FS-05 — PEFT/QLoRA Fine-Tuning

**Purpose:** Demonstrate domain fine-tuning and adapter management.

**Requirements:** Select a code-capable 1.5B–3B base model; prepare schema-grounded banking Text-to-SQL and synthetic correction examples; fine-tune with Transformers, PEFT, bitsandbytes, and TRL using QLoRA; save/reload one LoRA adapter; compare base vs. adapter on held-out queries; provide reproducible configs/scripts.

**Acceptance criteria:** Training produces a loadable inference adapter; held-out comparison is recorded.

## FS-06 — AWQ/GPTQ Quantization

**Purpose:** Measure inference-memory/quality trade-offs.

**Requirements**
- Produce AWQ and GPTQ variants of the fine-tuned model where supported.
- Verify base/adapter/merged-checkpoint, quantizer, and vLLM compatibility.
- Compare original and quantized variants on identical workloads; measure SQL execution accuracy, VRAM, latency, and throughput.
- Document degradation and efficiency trade-offs; treat both as experiments, not guaranteed support.

**Acceptance criteria:** At least one quantized variant is served/evaluated; compatibility blockers are documented; results compare with unquantized baseline.

## FS-07 — vLLM Serving

**Purpose:** Serve the local model through optimized inference.

**Requirements:** Serve the fine-tuned model via vLLM and OpenAI-compatible API; integrate as local specialist; enable automatic prefix caching; compare baseline inference vs. vLLM and test quantized variants where supported; measure P50/P95 latency, throughput, tokens/sec, and GPU memory.

**Acceptance criteria:** Pipeline calls the vLLM endpoint; baseline comparison is recorded; prefix caching can be enabled and measured.

## FS-08 — SQL Generation, Validation & Execution

**Purpose:** Generate executable, safe SQL.

**Requirements:** Generate with the routed model and retrieved schema; validate syntax with SQLGlot and tables/columns against schema; execute via SQLAlchemy against the POC database using read-only analytical queries.

**Acceptance criteria:** NL requests produce SQL; syntax/schema errors are caught before or during execution; valid SQL returns results.

## FS-09 — SQL Error Correction

**Purpose:** Repair generation/execution failures using database feedback.

**Requirements:** Capture parse/schema/execution errors; isolate enough context to repair; send failed SQL, relevant schema, and error to the selected model; use local model for simple fixes and DeepSeek for difficult ones; bound retries and log attempts/outcomes.

**Acceptance criteria:** Failed SQL can be repaired; corrected SQL is revalidated before execution; repair success/retry counts are measurable.

## FS-10 — Data Analysis & Visualization

**Purpose:** Summarize query results and optionally visualize them.

**Requirements:** Use pandas for basic analysis and concise NL summaries; support optional Plotly charts. Retain Data Analyzer/Plotter concepts; avoid elaborate report generation.

**Acceptance criteria:** Results can be summarized and suitable results visualized; charts never block core SQL flow.

## FS-11 — MLflow Experiment Tracking

**Purpose:** Track training and comparative experiments.

**Requirements:** Log QLoRA parameters, metrics, and artifacts; base-vs-fine-tuned evaluation; AWQ/GPTQ experiments and metrics; model/checkpoint IDs and experiment configuration.

**Acceptance criteria:** Runs are visible/comparable in MLflow, with associated artifacts or references.

## FS-12 — Langfuse Observability

**Purpose:** Inspect multi-model runtime behavior.

**Requirements:** Trace LLM calls/agent execution; capture model, routing decisions, latency, tokens, errors; inspect retrieval, SQL generation, correction, and synthesis. Keep instrumentation lightweight.

**Acceptance criteria:** End-to-end traces distinguish model calls/routing and expose latency/token usage where supported.

## FS-13 — Streamlit Demo

**Purpose:** Demonstrate the complete POC interactively.

**Requirements:** Accept NL banking queries; show selected model/routing, generated SQL/validation, results/correction attempts, concise analysis/optional Plotly charts, and basic latency/token/cost data.

**Acceptance criteria:** Users can inspect the end-to-end workflow without reading logs.

## FS-14 — Docker Packaging & Local Orchestration

**Purpose:** Reproducible development and single-host execution.

**Requirements:** Package app/services with Docker; use Compose for DB, app, and vLLM where hardware permits; externalize configuration/secrets; support local development and single-host deployment.

**Acceptance criteria:** Documented commands start services; app connects to DB/inference; GPU services can target local or cloud compute.

## FS-15 — CI/CD & Automated Deployment

**Purpose:** Demonstrate lightweight software delivery.

**Requirements:** Use GitHub Actions for relevant tests and Docker builds; automate deployment to one configured cloud/GPU host; keep steps reproducible and simple. No Kubernetes/distributed release infrastructure.

**Acceptance criteria:** Repository changes trigger test/build; successful workflow deploys to configured host; setup/configuration is documented.

## FS-16 — Comparative Evaluation & Benchmark

**Purpose:** Substantiate engineering claims with reproducible measurements.

**Workload:** ~100–200 banking queries, separate train/held-out sets, fixed DB state and consistent conditions.

| Experiment | Baseline | Candidate |
|---|---|---|
| Fine-tuning | Base LLM | QLoRA adapter |
| Quantization | Original model | AWQ/GPTQ, where supported |
| Inference | Baseline path | vLLM |
| Prefix caching | Off | On |
| Orchestration | Single model | Tiered adaptive routing |

**Metrics:** SQL execution accuracy; first-pass validity; repair success/mean retries; end-to-end P50/P95 latency; throughput/tokens/sec; GPU memory; estimated cost/successful query; quantization accuracy loss.

**Acceptance criteria:** Held-out, reproducible comparisons with configurations and comparable measurements; report trade-offs and failed/unsupported experiments without claiming unmeasured gains.

## Implementation Order

1. **M1 Baseline:** FS-01, 02, 03, 08, 09.
2. **M2 Fine-tuning:** FS-05, 11.
3. **M3 Serving:** FS-07.
4. **M4 Quantization:** FS-06.
5. **M5 Routing:** FS-04.
6. **M6 Evaluation/observability:** FS-12, 16.
7. **M7 Demo/delivery:** FS-10, 13, 14, 15.

## Definition of Done

- Working Azraq Text-to-SQL pipeline with hybrid schema RAG.
- Luna orchestrates DeepSeek V4.1 Flash and fine-tuned local model via adaptive routing.
- One QLoRA adapter trained, saved, loaded, and evaluated.
- Fine-tuned model served through vLLM/OpenAI-compatible API with prefix caching.
- AWQ/GPTQ evaluated where supported.
- MLflow tracks training/quantization; Langfuse traces runtime.
- Streamlit demonstrates end-to-end flow.
- Docker Compose, GitHub Actions, and single-host automated deployment work.
- Benchmark reports accuracy, latency, throughput, memory, and cost trade-offs.

**Resource constraint:** Use local RTX 3060 Ti (8GB VRAM) for lightweight work; rent cloud GPU compute when training/serving exceeds local capacity.
