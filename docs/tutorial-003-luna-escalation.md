# FS-03 Luna-high failure escalation experiment

FS-03 measures whether `gpt-6-luna` at high reasoning effort improves SQL results for the frozen set of 53 queries that failed Luna-low with retrieved schema. It evaluates two conditions on the same IDs: hybrid RRF retrieval with Cohere reranking at candidate-k 20/top-k 5, and full schema with all 26 tables and validated relationships.

The experiment compares retrieved-schema results with Luna-low's 0/53 successes and full-schema results with Luna-low's 19/53 successes. It does not include queries Luna-low passed. Prompts, validation, fixed database snapshot, read-only execution, row limits, and generation settings are shared between conditions.

## Preflight

Set the model and reasoning effort explicitly, then inspect readiness. Preflight verifies frozen input hashes and limits without calling OpenAI or Cohere:

```sh
OPENAI_MODEL=gpt-6-luna OPENAI_REASONING_EFFORT=high \
  uv run python -m scripts.benchmark_azraq_luna_high
```

The experiment allows at most 106 initial generation requests and 50 retries overall, with at most two retries per initial request. Only transient API errors can be retried. A malformed SQL response, terminal API error, ambiguous in-flight request, or exhausted retry budget stops the run. Checkpoints preserve each response and completed query so safe work is not repeated after interruption. After a malformed-output stop, continuing requires separate explicit approval; the continuation skips that malformed case and all completed cases, counts prior calls toward the original limits, and stops again on a new malformed response.

## Real model run

The real run requires separate explicit approval for the one-time experiment. Plan approval and preflight do not authorize service calls. Before running, check the current official OpenAI and Cohere pricing for the intended account tiers and enter the effective rates and check date. Do not run this experiment a second time without explicit approval.

After that approval, provide the rate card values and account tier to the opt-in CLI:

```sh
OPENAI_MODEL=gpt-6-luna OPENAI_REASONING_EFFORT=high \
  uv run python -m scripts.benchmark_azraq_luna_high \
  --approve-run \
  --pricing-checked-at YYYY-MM-DD \
  --openai-input-rate INPUT_USD_PER_MILLION \
  --openai-cached-input-rate CACHED_INPUT_USD_PER_MILLION \
  --openai-output-rate OUTPUT_USD_PER_MILLION \
  --cohere-account-tier trial-or-production
```

After a malformed-output stop, resume the same checkpoint only after explicit approval to continue. The malformed query remains recorded as a failure and is not generated again:

```sh
OPENAI_MODEL=gpt-6-luna OPENAI_REASONING_EFFORT=high \
  uv run python -m scripts.benchmark_azraq_luna_high \
  --approve-run --resume --continue-after-stop \
  --pricing-checked-at YYYY-MM-DD \
  --openai-input-rate INPUT_USD_PER_MILLION \
  --openai-cached-input-rate CACHED_INPUT_USD_PER_MILLION \
  --openai-output-rate OUTPUT_USD_PER_MILLION \
  --cohere-account-tier trial-or-production
```

Replace each placeholder with the checked value. On interruption, resume only with separate explicit approval and the existing checkpoint:

```sh
OPENAI_MODEL=gpt-6-luna OPENAI_REASONING_EFFORT=high \
  uv run python -m scripts.benchmark_azraq_luna_high \
  --approve-run --resume \
  --pricing-checked-at YYYY-MM-DD \
  --openai-input-rate INPUT_USD_PER_MILLION \
  --openai-cached-input-rate CACHED_INPUT_USD_PER_MILLION \
  --openai-output-rate OUTPUT_USD_PER_MILLION \
  --cohere-account-tier trial-or-production
```

The output directory is `data/evaluation/experiments/failure-sql-luna-high/`. It contains a checkpoint and separate `retrieved-schema.json` and `full-schema.json` per-query artifacts. The artifacts preserve raw generation output, validated SQL, execution rows/errors, expected-result correctness, token use, latency, rate-card metadata, and estimated cost.

## Report and interpretation

After both conditions finish, create the report:

```sh
uv run python -m scripts.report_azraq_luna_high
```

This writes `comparison-report.json` in the experiment directory. Review each condition separately: result correctness is execution accuracy, while SQL validity and successful execution are reported independently. Cost per additional successful query is shown only for positive net improvement with complete cost data. Historical Luna-low output/reasoning tokens and cost were not captured, so the report marks them unavailable.

There is no preset acceptable price per added successful query. Use the measured per-condition accuracy and cost tradeoff to decide whether failure-triggered escalation is worthwhile. Any recommendation should apply only to the 53-query failure-triggered path.

Implementation verification uses a fake generator, and the fixed-snapshot smoke uses saved reference SQL without a model request. Keep those checks separate from the real experiment results and preserve every stopped attempt in its checkpoint artifacts.
