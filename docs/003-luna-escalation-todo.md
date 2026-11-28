# FS-03 — Failure-Triggered Luna-High SQL Generation TODO

Tasks are the canonical status source. Lineage: requirement → plan → task → implementation/tests.

## T001 — Freeze comparison inputs and baseline pairing [x]

**Requirements:** R001.1–R001.3, R001.6, R004.1, R004.5, R005.1, A001, A005
**Plan:** P001.1–P001.3
**Files:** baseline/cohort readers and comparison helpers, tests, `docs/003-luna-escalation.md`
**Depends on:** none

- [x] **T001.1** Add pre-run checks for the cohort, baseline artifacts, query set, index manifest, and snapshot identities. **Accept:** verify exactly the frozen 53 retrieved-schema failure IDs; verify the recorded hashes/snapshot; fail before generation on any mismatch; never write to baseline/cohort paths. **Depends on:** none.
- [x] **T001.2** Join cohort IDs to both existing Luna-low conditions. **Accept:** preserve exact expected outputs and statuses; establish 0/53 retrieved-schema and 19/53 full-schema successes; never run Luna-high on other IDs. **Depends on:** T001.1.

## T002 — Extend the generation adapter with bounded usage and retry accounting [ ]

**Requirements:** R002.1–R002.3, R002.5, R003.1–R003.4, A004
**Plan:** P002.1, P002.3, P002.5
**Files:** `src/triage_sql/sql_generation.py`, adapter tests, experiment configuration in `scripts/`
**Depends on:** none

- [ ] **T002.1** Configure the experiment explicitly for `gpt-6-luna` and high reasoning effort while preserving model-neutral adapter behavior. **Accept:** verify effective model/effort before any request and leave existing baseline files/configuration untouched. **Depends on:** none.
- [ ] **T002.2** Capture input, output, cached-input, and reasoning token usage where returned, plus model ID, effort, and request latency; calculate per-request cost from recorded rate-card/tier data without double-counting reasoning tokens. **Accept:** missing usage remains explicitly unavailable; rate card source/date and per-token rates are recorded. **Depends on:** T002.1.
- [ ] **T002.3** Replace opaque SDK retry behavior in the experiment path with explicit bounded retries for transient API errors only. **Accept:** maximum two retries per initial request and 50 total; every request/retry is counted; malformed outputs and non-transient errors are recorded and stop without another generation. **Depends on:** T002.1.

## T003 — Implement the fixed two-condition checkpointed runner [ ]

**Requirements:** R001.4–R001.6, R002.2–R002.4, R003.1–R003.3, R003.5, R004.2, R004.5, R005.1, A001–A005
**Plan:** P002.1–P002.4, P004.2
**Files:** new experiment runner under `scripts/`, `src/triage_sql/prompt_benchmark.py` if needed, `data/evaluation/experiments/failure-sql-luna-high/`, integration tests
**Depends on:** T001, T002

- [ ] **T003.1** Enforce only the retrieved condition (hybrid RRF, Cohere rerank v5 Fast, candidate-k 20/top-k 5) and the full-schema condition (all 26 tables and validated edges). **Accept:** reject all other retrieval modes/parameters; verify the full context contains 26 tables and exactly the validated relationship set. **Depends on:** T001.1, T002.1.
- [ ] **T003.2** Run one initial generation request per cohort ID and condition through the existing prompt, validator, read-only executor, and expected-results comparator. **Accept:** only the frozen 53 IDs are eligible; both conditions use identical settings except schema context; no SQL correction/follow-up generation occurs. **Depends on:** T003.1.
- [ ] **T003.3** Persist call state before every request/retry and checkpoint each response before validation/execution. **Accept:** separate condition artifacts record raw output, validated SQL, execution rows/status, error type, usage, latency, retry count, and configuration; resume never repeats a completed or ambiguous request. **Depends on:** T003.2.
- [ ] **T003.4** Enforce initial/retry budgets and stop rules in the runner. **Accept:** at most 106 initial requests, two retries per initial request, and 50 retries total; stop on malformed output, non-transient/exhausted API errors, or exhausted global retry budget. **Depends on:** T003.3.
- [ ] **T003.5** Make real generation opt-in behind an explicit run-approval switch. **Accept:** normal/help/smoke invocations make no Luna-high requests; runner refuses to generate unless the operator explicitly acknowledges the approved one-time experiment. **Depends on:** T003.1–T003.4.

## T004 — Report comparative accuracy, failures, and cost [ ]

**Requirements:** R004.1–R004.6, A005–A006
**Plan:** P003.1–P003.3
**Files:** evaluation/report helpers, condition result artifacts, `docs/003-luna-escalation.md`, tests
**Depends on:** T001, T003

- [ ] **T004.1** Calculate per-condition first-pass SQL validity, execution success, expected-result correctness, category/error breakdown, and accuracy delta against the matching Luna-low condition. **Accept:** report both retrieved and full-schema counts and rates on the same 53 IDs. **Depends on:** T001.2, T003.2.
- [ ] **T004.2** Calculate token use, latency, estimated cost, and cost per net additional successful query separately for both conditions. **Accept:** when the net additional success count is nonpositive, report no gain and leave cost-per-additional-success undefined; distinguish unavailable Luna-low cost/output/reasoning data. **Depends on:** T002.2, T003.3, T004.1.
- [ ] **T004.3** State that cost acceptability is left to the reader and limit any recommendation to conditional failure-triggered escalation. **Accept:** no invented dollar threshold or unconditional recommendation. **Depends on:** T004.1, T004.2.

## T005 — Regression verification, convergence, and journal evidence [ ]

**Requirements:** R001–R005, A001–A006
**Plan:** P004.1–P004.3
**Files:** `tests/`, `docs/003-luna-escalation.md`, `docs/003-luna-escalation-todo.md`, `.current`
**Depends on:** T001–T004

- [ ] **T005.1** Add mocked tests for input/hash guards, fixed settings, exact contexts, call/retry ceilings, transient retry policy, malformed-output stop behavior, checkpoint/resume, token/cost calculation, and comparison metrics. **Accept:** regression tests prove the runner makes no external model calls during test execution. **Depends on:** T001–T004.
- [ ] **T005.2** Exercise schema construction and read-only execution against the fixed snapshot without invoking Luna-high. **Accept:** execution remains behind the existing safety pipeline and saved expected results compare correctly. **Depends on:** T003.1–T003.2.
- [ ] **T005.3** Record implementation, commands/results, frozen identities, compatibility, limitations, and experiment approval gate in the durable journal; run convergence review and resolve gaps. **Accept:** preserve baselines/cohort, distinguish mock/integration verification from real-world model run, and leave the real experiment gated for explicit approval. **Depends on:** T005.1–T005.2.
- [ ] **T005.4** Create the feature-completion tutorial under `docs/tutorial-003-luna-escalation.md`. **Accept:** append-only user-facing instructions explain the fixed experiment, artifacts, interpretation, limitations, and separate real-run approval gate; do not imply the real experiment ran unless it did. **Depends on:** T005.3.
