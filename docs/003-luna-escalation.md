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
