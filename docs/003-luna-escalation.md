# FS-03 — Failure-Triggered Luna-High SQL Generation Experiment Journal

This journal records implementation history, evidence, and decisions. Task status remains canonical in [the TODO](003-luna-escalation-todo.md).

## Frozen comparison inputs

The approved experiment is limited to the failure cohort at `data/evaluation/azraq-retrieval-failure-labels.jsonl` and compares both Luna-high schema conditions with the corresponding Luna-low baseline results. The fixed identities are:

- SQL baseline: `ee7beb0a1229fe8fad1985d1f37591054eb0feac082b7e2c2f7c72dffb6e09e1`
- Retrieval baseline: `f4eaa6a81b951380c38f8c42eae29ccd25bdd0ea3fbb631d9692ca3a37cfe776`
- Failure cohort: `150579fb833e209c6b66f1c7d4eca579116b5d6644514b4e8cce6c69f855f764`
- 120-query evaluation set: `1cbe40d2d027a28d32fd39e91807e6427c6fad10d8a338a488b60bc7703dc87a`
- Index manifest: `e3e9c32aa1b62321e7dc3664061945e37bc3ffcad04b1fd1b33bad64586ce92b`
- Database snapshot: `ba058d581b04d1d75f63ac0a4705d98ea0d8ea54dcf577ee90b58222d082dddc`

The Luna-low baseline uses `gpt-6-luna` at low reasoning effort. Of the same 53 cohort IDs, the retrieved-schema baseline succeeded on 0 and the full-schema baseline succeeded on 19.

## Implementation record

### T001 — Frozen input guards and paired baseline

- Added `triage_sql.experiment_inputs` to verify the frozen SQL/retrieval/cohort/evaluation/index hashes, 53 cohort members and their failure order, 120-row baseline conditions, model/effort, top-k, index table/relationship counts, and snapshot identity before a future run.
- Added a pairing helper that joins each cohort ID to both original SQL baseline conditions and fails unless the known Luna-low comparison remains 0/53 retrieved and 19/53 full-schema successes.
- Verification: `uv run pytest -q tests/test_experiment_inputs.py` — 4 passed. All frozen hashes listed above matched at implementation time.
- No Luna-high or Cohere service calls were made. Original baseline and cohort files were read only.

### T002 — Usage capture and bounded retry primitives

- Extended the generation response with output, reasoning, and cached-input token counts when supplied by the Responses API. The FS-03 CLI alone creates an OpenAI client with SDK-managed retries disabled; other adapter callers retain the prior SDK default.
- Added a high-effort/model guard, a serializable retry budget (two retries per request, 50 overall), and a classifier limited to OpenAI connection/timeouts and HTTP 408/409/429/5xx errors. SQL/output validation failures are not retryable.
- Added cost calculation from a captured rate card. Cached input is priced separately when usage and a cached rate are available; reasoning is included once within output tokens. Cost is unavailable when input or output usage is missing.
- Verification: `uv run pytest -q tests/test_prompt_benchmark.py tests/test_api_retry.py tests/test_costing.py` — 19 passed, 14 subtests passed. An initial retry-classifier test fixture used an invalid direct exception allocation; replacing it with actual SDK exception instances fixed the fixture. Chroma emitted one existing deprecation warning.
- No Luna-high or Cohere service calls were made.

### T003 — Fixed, checkpointed two-condition runner

- Added an opt-in runner restricted to the frozen 53 IDs and the two approved contexts. Retrieved context uses hybrid RRF with 20 candidates and Cohere `rerank-v5.0-fast` top 5; full context is the full index of 26 tables and 27 validated relationships.
- The runner persists an in-flight marker before every OpenAI request/retry and persists responses before SQL validation. It checkpoints separate retrieved/full artifacts, records raw output, SQL, read-only results/errors, expected-result correctness, token use, latency, cost metadata and retry state. Resume skips completed work and refuses ambiguous requests.
- SDK retries are disabled only on the experiment client. Explicit retries are limited to transient OpenAI errors, two per initial request and 50 overall. Malformed output and terminal errors stop the run. The CLI requires `--approve-run`; help and preflight do not create a generator or reranker client.
- Verification: `uv run pytest -q tests/test_failure_experiment.py tests/test_costing.py tests/test_retrieval.py tests/test_experiment_inputs.py tests/test_api_retry.py tests/test_prompt_benchmark.py` — 37 passed, 14 subtests passed. The expanded run including report coverage passed 40 tests, 14 subtests. A final adapter compatibility check passed 26 tests, 14 subtests. Full suite: `uv run pytest -q` — 78 passed, 7 PostgreSQL integration tests skipped, 14 subtests passed; one existing Chroma deprecation warning.
- CLI `--help` and read-only preflight passed with `OPENAI_MODEL=gpt-6-luna OPENAI_REASONING_EFFORT=high`. Preflight verified all frozen identities, 53 cohort IDs, baseline successes 0/53 and 19/53, and limits. It reported that no model or reranker requests were made.
- Fixed-snapshot read-only smoke: validated the saved `eval-001` reference SQL using the existing SQL safety validator, executed via `_execute_read_only` against the manifest schema, and matched expected rows (`[[2800000]]`). No generation service was used.
- No real Luna-high or Cohere request was made. The experiment remains separately gated by explicit run approval.

### T004 — Comparative report

- Added report aggregation for per-condition baseline/high accuracy, SQL validity, execution success, expected-result correctness, percentage-point and query-count deltas, token usage, latency, fully priced estimated cost, cost per additional correct query, category counts, and error-type counts.
- The report rejects anything other than the exact 53 cohort IDs and the two conditions. It re-verifies frozen input hashes before reporting. Historical Luna-low output/reasoning tokens and cost are explicitly unavailable. Cost per additional success is null for zero/negative deltas or incomplete cost data; cost acceptability remains with the reader.
- `scripts/report_azraq_luna_high.py` writes `comparison-report.json` only from a completed checkpoint and is not run before the approved model experiment.
- Mocked metric verification: `uv run pytest -q tests/test_failure_report.py` — included in the 40-test passing run above.

### T005 — Regression evidence and completion materials

- Runner tests cover exact conditions and IDs, model/effort gate, explicit SDK retry disabling on the FS-03 client, per-request/global retry caps, malformed-output stop, checkpoint resume, and ambiguous-attempt protection. Report tests cover gains, category/error breakdown, cost completeness, and nonpositive delta handling.
- Automated tests and static fixed-snapshot smoke passed as recorded above. PostgreSQL integration suite was skipped because `AZRAQ_TEST_DSN` was not configured; one independent read-only query through the fixed-snapshot execution pipeline passed.
- No benchmark artifacts were generated because the real model run has not received separate approval. Original baseline and cohort remain read-only.

## Convergence review

Scoped review of T003–T005 traced R001–R005 and A001–A006 through P002–P004 into the runner, report, tests, and tutorial. Fixed-condition and full-schema identities are checked before generation; only frozen cohort IDs enter the run; separate artifacts and checkpoint state enforce retry and resume limits; report comparisons use the corresponding Luna-low condition. Existing adapter retry defaults remain unchanged outside the FS-03 client. Help/preflight, mocked tests, and the fixed-snapshot read-only SQL smoke use no Luna-high calls.

Verification after the final implementation changes: `uv run pytest -q` — 79 passed, 7 environment-gated PostgreSQL integration tests skipped, 14 subtests passed; one existing Chroma deprecation warning. `uv run pytest -q tests/test_failure_report.py tests/test_prompt_benchmark.py` — 9 passed, 5 subtests passed. `git diff --check` passed. CLI help and read-only preflight passed; preflight verified the frozen hashes and returned no service requests. The `eval-001` SQL validation/execution smoke matched the saved expected result on the fixed database snapshot.

No convergence gaps remain in the approved implementation scope. Real Luna-high/Cohere experiment execution remains gated for separate explicit approval and therefore has no outcome or cost evidence yet.
