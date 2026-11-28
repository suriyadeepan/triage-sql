# FS-03 — Failure-Triggered Luna-High SQL Generation Experiment

**Purpose:** Evaluate whether Luna-high improves SQL execution accuracy on queries Luna-low failed, without using stronger reasoning on routine queries.

## Requirements

### R001 — Frozen experiment scope

- **R001.1** Reuse only the frozen 53-query retrieved-schema failure cohort at `data/evaluation/azraq-retrieval-failure-labels.jsonl`.
- **R001.2** Preserve the original 120-query baseline artifacts and hashes; do not regenerate or overwrite them.
- **R001.3** Run Luna-high only on the frozen failures, never on successful baseline queries.
- **R001.4** Fix retrieved-schema retrieval to hybrid RRF with Cohere reranking, `candidate_k=20`, and `top_k=5`, using the existing benchmark configuration.
- **R001.5** Run exactly two schema-context conditions: (a) retrieved schema with the fixed configuration; (b) full schema containing all 26 tables and validated relationships.
- **R001.6** Do not vary candidate/top-k, retrieval mode, or reranking configuration.

### R002 — Controlled model execution

- **R002.1** Reuse the existing model-neutral SQL-generation adapter.
- **R002.2** Configure `OPENAI_MODEL` explicitly for Luna-high and set the required high reasoning effort.
- **R002.3** Keep prompts, SQL validation, database snapshot, execution limits, and generation settings identical between conditions except for schema context and reasoning effort.
- **R002.4** Route all generated SQL through the existing read-only validation and execution pipeline.
- **R002.5** Do not use Luna-high for SQL correction or follow-up generation. API request retries are permitted only as bounded by R003.2; malformed model output must not trigger a new generation.

### R003 — Call and cost controls

- **R003.1** Make at most one initial generation request for each of the 53 frozen failures in each of two conditions (106 initial requests total), with at most 50 additional retry requests across the experiment.
- **R003.2** Retry only transient API request errors, at most two retries for any initial request and at most 50 retries overall. Count every retry attempt toward the 50-retry cap. Do not retry malformed model output or non-transient API errors; record them and stop the run on malformed output, a non-transient/exhausted API error, or when the global retry cap is reached.
- **R003.3** Do not repeat the experiment without explicit user approval.
- **R003.4** Record model identifier, reasoning effort, input/output/reasoning tokens where available, latency, and estimated cost per query and condition.
- **R003.5** Checkpoint results incrementally so interrupted runs do not repeat completed calls.

### R004 — Evaluation and evidence

- **R004.1** Compare the existing Luna-low baseline on the 53-query cohort with Luna-high retrieved-schema and Luna-high full-schema conditions.
- **R004.2** Measure SQL execution accuracy and improvement over Luna-low, first-pass SQL validity and execution success, and result correctness against expected outputs.
- **R004.3** Measure input/output/reasoning tokens, latency, estimated cost, and cost per additional successful query.
- **R004.4** Report failures by query category and error type.
- **R004.5** Preserve per-query outputs, execution results, errors, and configuration metadata in separate experiment artifacts without modifying the baseline or cohort.
- **R004.6** Report whether each Luna-high condition improves execution accuracy enough to justify its additional cost; recommend failure-triggered Luna-high escalation only if the cost per additional success is acceptable.

### R005 — Excluded scope

- **R005.1** Do not run an all-120-query Luna-high benchmark, tune candidate/top-k values, implement automatic model routing, add SQL correction, or deploy to production.

## Acceptance criteria

- **A001** Only the 53 frozen baseline failures are evaluated.
- **A002** Retrieved-schema retrieval uses exactly candidate-k 20 and top-k 5.
- **A003** Full-schema context includes all 26 tables and validated relationships.
- **A004** At most 106 initial Luna-high generation requests and 50 retry requests occur (156 API attempts maximum); each initial request has at most two retries, retries apply only to transient API errors, and malformed output is never regenerated.
- **A005** Comparisons use the existing Luna-low failure baseline and retain distinct per-condition artifacts.
- **A006** The report includes accuracy change, cost per additional successful query, and a separate cost justification for retrieved and full schema; any recommendation is limited to failure-triggered escalation.

## Planning gaps

- The user chose to report the measured cost/accuracy tradeoff and leave cost acceptability open; do not invent a numeric threshold or unconditional recommendation.
- The baseline recorded input tokens and latency but not output/reasoning tokens or historical cost. Compare only measurements available in the original artifact and label unavailable baseline measures explicitly.
- The existing OpenAI adapter currently relies on SDK retry defaults and records only input tokens. FS-03 implementation must replace hidden SDK retries with explicit bounded retry accounting and usage capture without changing existing baseline artifacts.
