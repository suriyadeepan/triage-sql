# FS-03 — Failure-Triggered Luna-High SQL Generation Experiment Plan

## Scope and approach

Implement [FS-03 requirements](003-luna-escalation-requirements.md) as a one-time, checkpointed experiment over the frozen 53 retrieved-schema Luna-low failures. The existing baseline identifies model `gpt-6-luna` with effort `low`; interpret Luna-high as that same model with `OPENAI_REASONING_EFFORT=high`. Use the existing model-neutral generator, retrieval/index, prompt, SQL validator, read-only PostgreSQL execution, expected-results comparison, and fixed snapshot. No Luna-high call is made before the experiment receives explicit run approval.

Run exactly two conditions, each over the same ordered 53 IDs:

1. Retrieved schema: hybrid RRF, Cohere rerank v5 Fast, `candidate_k=20`, `top_k=5`.
2. Full schema: all 26 table records and all validated relationship records (the existing manifest/journal reports 27 validated edges).

Both conditions use high effort and otherwise identical prompt construction, timeout/row limits, database snapshot, and SQL safety/execution settings. Retrieval happens only for condition 1. Do not add alternate retrieval settings, all-120 calls, SQL correction, or follow-up generation. The user authorized up to two retries per initial generation request for transient API errors, capped at 50 retries across the experiment.

The baseline artifact has 53 retrieved-schema failures among 120; on those same IDs, its full-schema condition passed 19. Compute each high-effort delta against the matching low-effort baseline condition, so retrieved-schema and full-schema improvement use the correct denominator. Report token/cost metrics for Luna-high and the corresponding Luna-low accuracy; clearly mark historical output/reasoning tokens and baseline costs unavailable where absent.

The user directed that the report quantify the cost/accuracy tradeoff and leave acceptability to the reader. Do not introduce a numeric acceptance threshold or claim an unconditional cost justification. State the additional successful-query count and cost per additional success for each condition when the delta is positive; otherwise report no accuracy gain and leave that ratio undefined. Any recommendation must remain conditional on the user's cost judgment and limited to failure-triggered escalation.

## Plan

### P001 — Freeze inputs and bind the comparison

- **P001.1** Verify the cohort has exactly the baseline's 53 failed IDs and record its SHA256 `150579fb833e209c6b66f1c7d4eca579116b5d6644514b4e8cce6c69f855f764`. **Requirements:** R001.1–R001.3, A001.
- **P001.2** Pin and recheck original SQL baseline SHA256 `ee7beb0a1229fe8fad1985d1f37591054eb0feac082b7e2c2f7c72dffb6e09e1`, retrieval baseline SHA256 `f4eaa6a81b951380c38f8c42eae29ccd25bdd0ea3fbb631d9692ca3a37cfe776`, query-set SHA256 `1cbe40d2d027a28d32fd39e91807e6427c6fad10d8a338a488b60bc7703dc87a`, index manifest SHA256 `e3e9c32aa1b62321e7dc3664061945e37bc3ffcad04b1fd1b33bad64586ce92b`, and snapshot ID `ba058d581b04d1d75f63ac0a4705d98ea0d8ea54dcf577ee90b58222d082dddc`. Reject the run if any frozen identity or baseline cohort membership differs. **Requirements:** R001.2, R004.1, R004.5, A005.
- **P001.3** Define separate per-condition Luna-low comparators by joining the 53 cohort IDs to the original 120-query results; preserve the retrieved/full baseline outcomes (0/53 and 19/53 successes respectively). **Requirements:** R004.1–R004.3, A005–A006.

### P002 — Add a bounded, resumable experiment runner

- **P002.1** Reuse the existing model-neutral generation and benchmark components; require explicit `OPENAI_MODEL=gpt-6-luna` and `OPENAI_REASONING_EFFORT=high`, and assert the effective values before any generation. **Requirements:** R002.1–R002.3.
- **P002.2** Constrain condition and retrieval settings in the runner to the two approved contexts only. Verify full context has 26 tables plus validated relationships and retrieved context comes from hybrid RRF with Cohere at candidate-k 20/top-k 5. **Requirements:** R001.4–R001.6, R002.3, A002–A003.
- **P002.3** Disable hidden SDK retries and implement explicit retry accounting. Make at most one initial generation request per `(condition, query_id)`, permit at most two retry requests for transient API errors from that request, and cap retries at 50 globally (106 initial + 50 retry = 156 maximum API attempts). Do not retry malformed model output or non-transient API errors; stop on those failures, exhausted per-request retries, or the global cap. **Requirements:** R002.5, R003.1–R003.2, A004.
- **P002.4** Checkpoint state before every initial/retry request and immediately persist returned responses before validation/execution. Record attempt type, retry count, and error status. On resume, skip completed requests and never duplicate a started/ambiguous attempt; continue only eligible transient-error retries and not-yet-started initial requests within the remaining global budget. Persist validated SQL, read-only execution output/status, errors, usage, latency, and config metadata separately for each condition. **Requirements:** R003.5, R004.2–R004.5, A004–A005.
- **P002.5** Capture input/output/reasoning token counts when present, latency, and the rate-card identity/effective token rates used for estimated cost. Count reasoning tokens as a subset of output tokens when calculating cost; do not double-count them. Use the pricing tier and rate card effective at run time and preserve its source/date in result metadata. **Requirements:** R003.4, R004.3.

### P003 — Evaluate both conditions against the frozen baseline

- **P003.1** Compare per-query first-pass SQL validity, execution status, and result correctness against expected rows, by condition and query category/error type. No correction or second generation is permitted. **Requirements:** R002.4–R002.5, R004.2, R004.4.
- **P003.2** Report Luna-low and Luna-high successes/53, percentage-point and count deltas, token use, latency, estimated cost, and cost per net additional successful query separately for retrieved and full schema. **Requirements:** R004.1–R004.3, R004.6.
- **P003.3** Explain that cost acceptability has no preset threshold and remains a user judgment; make any failure-triggered escalation recommendation conditional on that judgment. **Requirements:** R004.6.

### P004 — Verify safeguards and record evidence

- **P004.1** Add unit coverage for fixed configuration guards, exact cohort/hash checks, 106-initial/50-retry caps, two-retries-per-request maximum, transient-error-only retry policy, no malformed-output regeneration, stop conditions, checkpoint resume without repeating completed/ambiguous attempts, output capture, and metric calculations. Use mocked generation to avoid unapproved API use. **Requirements:** R001–R004, A001–A006.
- **P004.2** Add an integration/smoke path that validates both contexts and exercises SQL validation/execution against the fixed snapshot without making Luna-high requests; keep real model execution as a separately gated verification. **Requirements:** R001.5, R002.3–R002.4, R004.2.
- **P004.3** Record commands, exact environment/configuration, hashes, rate-card evidence, per-condition artifacts, failures, and limitations in the FS-03 journal. Do not modify or regenerate the baseline/cohort. **Requirements:** R001.2, R003.3–R003.5, R004.5.

## Affected files and dependencies

- Inputs to verify read-only: `data/evaluation/azraq-retrieval-failure-labels.jsonl`, `data/evaluation/azraq-sql-prompt-results.json`, `data/evaluation/azraq-retrieval-results.json`, `data/evaluation/azraq-evaluation.jsonl`, the schema index/manifest, and `data/manifest/azraq-postgres.json`.
- Expected implementation: experiment runner under `scripts/`, experiment-specific additions to `src/triage_sql/sql_generation.py` and/or `src/triage_sql/prompt_benchmark.py`, regression tests under `tests/`, and separate output files under `data/evaluation/experiments/failure-sql-luna-high/` (one retrieved, one full-schema, with checkpoint metadata).
- Documentation: `docs/003-luna-escalation-requirements.md`, this plan, canonical TODO `docs/003-luna-escalation-todo.md`, journal `docs/003-luna-escalation.md`, and local `.current`.
- Reuse current OpenAI optional dependency and Cohere rerank extra; avoid unrelated dependency changes. Disable SDK-managed retries and implement experiment-scoped bounded retries so every request is checkpointed and charged against the 50-retry ceiling.

## Architecture compatibility matrix

| Area | Status | Evidence and action |
|---|---|---|
| Python runtime | VERIFIED | `pyproject.toml` requires Python `>=3.14`; FS-02 recorded verification on Python 3.14.10. Continue with `uv`. |
| CPU/OS | VERIFIED | FS-02 journal records Python 3.14.10 on ARM64; experiment uses the existing CPU retrieval encoder. |
| Schema/context | VERIFIED | Existing schema/context implementation and manifest identify 26 tables and 27 validated relationship records. Assert these identities before run. |
| SQL adapter and safety path | VERIFIED | Existing Responses adapter, prompt builder, SQLGlot validator, read-only PostgreSQL transaction, fixed statement timeout, result cap, and expected-result comparison are implemented. Adapter needs experiment-scoped retry/usage extensions. |
| Frozen benchmark comparison | VERIFIED | Baseline and cohort hashes, model `gpt-6-luna`, low effort, candidate-k 20/top-k 5, and fixed snapshot are recorded in FS-02 journal and artifacts. Recheck immediately before any run. |
| Luna-high service availability, quota, and rate card | UNKNOWN until run | Verify effective model/effort and current official pricing before explicit run approval is used; record rates/tier/date and stop on configuration mismatch. No API calls during planning or mocked verification. |
| Deployment target | UNKNOWN | This is a local benchmark, with no production deployment in scope. |

The official [GPT-6 Luna model reference](https://developers.openai.com/api/docs/models/gpt-6-luna) lists `high` as a supported reasoning effort and supports reasoning-token reporting. Its published Standard text rates currently show $0.10 per million input tokens and $0.50 per million output tokens. The official [API pricing page](https://developers.openai.com/api/docs/pricing) also distinguishes cached input and processing tiers. These values are planning evidence only; capture and use the rate card/tier actually effective at experiment time.

## Risks and mitigations

- **Duplicate billing after interruption:** persist a `started` marker before each request, save the response immediately, and never reissue a started/ambiguous attempt. Resume only not-started cases; failed API attempts remain recorded.
- **Retries exceed the approved budget:** disable hidden SDK retries, checkpoint and count each explicit retry, enforce two retries per initial request and the global 50-retry cap, and test those limits using a fake transport.
- **Condition mismatch:** assert model, effort, prompt settings, timeout, snapshot, cohort IDs, retrieved configuration, and context record counts in the run manifest.
- **Historical cost comparison is incomplete:** the Luna-low artifact has input tokens and latency, not output/reasoning usage or cost. Report those as unavailable and compare accuracy against its exact per-condition results.
- **Unspecified cost tolerance:** quantify price and marginal success counts, but keep acceptability with the user; do not invent a threshold.
- **Variable generation outcomes:** compare on identical fixed query IDs and retain raw per-query outputs, outcomes, and latency rather than inferring significance from aggregate metrics.
- **Cohere service calls:** retrieve/rerank only once per cohort query for the retrieved condition, with existing Cohere configuration. Full-schema context does not invoke the reranker.

## Acceptance and validation

Satisfy [A001–A006](003-luna-escalation-requirements.md). Before a real run, verify the frozen hashes, exact 53 IDs, all 26 tables/validated relationships, explicit model/effort, hidden SDK retries disabled, output paths separate from baselines, 106-initial/50-retry ceilings, and two-retry-per-request maximum. Mocked regression checks cover runner safeguards and checkpoints. Real Luna-high generation is a separately gated experiment requiring explicit approval under R003.3; plan approval alone does not authorize those API calls. Report automated checks, artifact checks, and real-world generation/execution evidence separately.
