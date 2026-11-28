## FS-03 — Failure-Triggered Luna-High SQL Generation Experiment

**Purpose:** Evaluate whether Luna-high improves SQL execution accuracy on queries that Luna-low failed, without paying for stronger reasoning on routine queries.

**Requirements**

### Experiment scope
- Reuse the frozen 53-query retrieved-schema failure cohort:
  `data/evaluation/azraq-retrieval-failure-labels.jsonl`.
- Preserve the original 120-query baseline artifacts and their hashes. Do not regenerate or overwrite them.
- Run Luna-high only on the frozen failure cohort. Never run it on successful baseline queries.
- Fix the retrieval configuration:
  - `candidate_k=20`
  - `top_k=5`
  - Hybrid RRF retrieval with Cohere reranking, using the existing benchmark configuration.
- Run exactly two schema-context conditions:
  1. **Retrieved schema:** Hybrid retrieval, candidate-k 20, top-k 5.
  2. **Full schema:** All 26 tables and validated relationships.
- Do not experiment with other candidate-k/top-k combinations, retrieval modes, or reranking configurations in this feature.

### Model execution
- Use the existing model-neutral SQL-generation adapter.
- Configure `OPENAI_MODEL` explicitly for Luna-high and set the required high reasoning effort.
- Keep prompts, SQL validation, database snapshot, execution limits, and generation settings identical between the two conditions, except for schema context and reasoning effort.
- Execute all generated SQL through the existing read-only validation/execution pipeline.
- Do not invoke Luna-high for retries, correction, or follow-up generation in this experiment.

### Cost controls
- Limit Luna-high calls to the 53 frozen failure cases per schema condition: maximum **106 generation calls**.
- No automatic retries for API errors or malformed responses. Record failures and stop rather than silently increasing usage.
- Do not run the experiment again unless explicitly approved.
- Record model identifier, reasoning effort, input/output/reasoning tokens where available, latency, and estimated cost per query and condition.
- Checkpoint results incrementally so interrupted runs do not repeat completed calls.

### Evaluation
Compare:
1. Existing Luna-low baseline on the 53-query cohort.
2. Luna-high with retrieved schema (`candidate_k=20`, `top_k=5`).
3. Luna-high with full schema.

Measure:
- SQL execution accuracy and improvement over Luna-low.
- First-pass SQL validity and execution success.
- Result correctness against expected outputs.
- Input/output/reasoning tokens, latency, and estimated cost.
- Cost per additional successful query.
- Failures by query category and error type.

Preserve per-query outputs, execution results, errors, and configuration metadata in separate experiment artifacts. Do not modify the original baseline or failure cohort.

### Acceptance criteria
- Only the 53 frozen baseline failures are evaluated.
- Retrieved-schema configuration uses exactly candidate-k 20 and top-k 5.
- Full-schema condition includes all 26 tables and validated relationships.
- No more than 106 Luna-high generation calls are made.
- No automatic retries or additional model calls occur.
- Results are directly comparable with the existing Luna-low failure baseline.
- Report whether Luna-high improves execution accuracy enough to justify its additional cost, separately for retrieved and full schema.
- Recommend Luna-high only for failure-triggered escalation if its cost per additional successful query is acceptable.

**Out of scope:** All-120-query Luna-high benchmark, candidate/top-k tuning, automatic model routing, SQL correction, and production deployment.
