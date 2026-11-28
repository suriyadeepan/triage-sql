"""Checkpointed, failure-only Luna-high SQL generation experiment."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg

from triage_sql.api_retry import (
    MAX_RETRIES_PER_EXPERIMENT,
    MAX_RETRIES_PER_REQUEST,
    RetryBudget,
    is_transient_openai_error,
    require_luna_high_configuration,
)
from triage_sql.costing import (
    RerankRateCard,
    TokenRateCard,
    estimate_rerank_cost_usd,
    estimate_token_cost_usd,
)
from triage_sql.experiment_inputs import pair_luna_low_baseline, verify_frozen_inputs
from triage_sql.prompt_benchmark import _execute_read_only, build_prompt, validate_generated_sql
from triage_sql.retrieval import SchemaRetriever
from triage_sql.rerank import COHERE_RERANK_MODEL, CohereReranker
from triage_sql.sql_generation import Generation, SQLGenerator


CONDITIONS = ("retrieved_schema", "full_schema")
OUTPUT_DIR = Path("data/evaluation/experiments/failure-sql-luna-high")
CHECKPOINT_NAME = "checkpoint.json"
ARTIFACT_NAMES = {
    "retrieved_schema": "retrieved-schema.json",
    "full_schema": "full-schema.json",
}
STATEMENT_TIMEOUT_MS = 15000
MAX_RESULT_ROWS = 1000
MAX_OUTPUT_TOKENS = 512


class ExperimentStopped(RuntimeError):
    """Raised when a configured stop rule prevents further requests."""


class AmbiguousAttemptError(ExperimentStopped):
    """Raised when a checkpoint cannot establish whether a request completed."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as output:
            temp_name = output.name
            json.dump(data, output, sort_keys=True, indent=2, ensure_ascii=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def _error_metadata(error: BaseException) -> dict:
    status = getattr(error, "status_code", None)
    message = str(error).replace("\n", " ")[:1000]
    return {"type": type(error).__name__, "status_code": status, "message": message}


def _usage(generation: Generation) -> dict:
    return {
        "input_tokens": generation.input_tokens,
        "output_tokens": generation.output_tokens,
        "reasoning_tokens": generation.reasoning_tokens,
        "cached_input_tokens": generation.cached_input_tokens,
    }


class FailureTriggeredExperiment:
    """Runs only the frozen 53 IDs, under the two approved schema conditions."""

    def __init__(
        self,
        *,
        root: Path,
        generator: SQLGenerator,
        retriever: SchemaRetriever,
        reranker: CohereReranker,
        dsn: str,
        output_dir: Path = OUTPUT_DIR,
        rate_card: TokenRateCard,
        rerank_rate_card: RerankRateCard,
        approved_run: bool = False,
        resume: bool = False,
    ):
        if not approved_run:
            raise PermissionError("real Luna-high generation requires explicit --approve-run acknowledgement")
        require_luna_high_configuration(generator)
        if rate_card.model != generator.model:
            raise ValueError("OpenAI rate card model must match the configured generator")
        if rerank_rate_card.model != COHERE_RERANK_MODEL:
            raise ValueError("Cohere rate card model must match the configured reranker")
        self.root = root
        self.generator = generator
        self.retriever = retriever
        self.reranker = reranker
        self.dsn = dsn
        self.output_dir = output_dir
        self.rate_card = rate_card
        self.rerank_rate_card = rerank_rate_card
        self.resume = resume
        self.checkpoint_path = output_dir / CHECKPOINT_NAME
        self.artifact_paths = {
            condition: output_dir / ARTIFACT_NAMES[condition] for condition in CONDITIONS
        }

        # These are read-only identities and independent of output/checkpoint state.
        self.identities = verify_frozen_inputs(root)
        evaluation_dir = root / "data/evaluation"
        self.cohort = [
            json.loads(line)
            for line in (evaluation_dir / "azraq-retrieval-failure-labels.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.baseline = json.loads(
            (evaluation_dir / "azraq-sql-prompt-results.json").read_text(encoding="utf-8")
        )
        self.baseline_pairs = pair_luna_low_baseline(self.cohort, self.baseline)
        self.snapshot = json.loads((root / "data/manifest/azraq-postgres.json").read_text(encoding="utf-8"))

        self.retriever.ensure_fresh()
        self.records = json.loads(self.retriever.records_path.read_text(encoding="utf-8"))
        tables = [record for record in self.records if record.get("kind") == "table"]
        relationships = [record for record in self.records if record.get("kind") == "relationship"]
        if len(tables) != 26 or len(relationships) != 27 or len(self.records) != 53:
            raise ValueError("FS-03 schema context must contain all 26 tables and 27 validated relationships")
        if any(record.get("status") != "validated" for record in relationships):
            raise ValueError("full schema context may contain only validated relationships")
        self.allowed_tables = {record["table"] for record in tables}
        self.full_context_hash = _canonical_hash(self.records)
        self.metadata = self._build_metadata()
        self.state = self._load_or_initialize()

    def _build_metadata(self) -> dict:
        return {
            "experiment": "FS-03 failure-triggered Luna-high SQL generation",
            "cohort_count": len(self.cohort),
            "cohort_ids": [row["id"] for row in self.cohort],
            "cohort_sha256": self.identities["cohort"],
            "sql_baseline_sha256": self.identities["sql_baseline"],
            "retrieval_baseline_sha256": self.identities["retrieval_baseline"],
            "query_set_sha256": self.identities["query_set"],
            "index_manifest_sha256": self.identities["index_manifest"],
            "dataset_snapshot_id": self.identities["snapshot_id"],
            "generator_model": self.generator.model,
            "reasoning_effort": getattr(self.generator, "reasoning_effort", None),
            "prompt_format": "Schema context (JSON), question, SQL",
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "statement_timeout_ms": STATEMENT_TIMEOUT_MS,
            "maximum_result_rows": MAX_RESULT_ROWS,
            "conditions": {
                "retrieved_schema": {
                    "retrieval_mode": "hybrid-rrf",
                    "reranker": COHERE_RERANK_MODEL,
                    "candidate_k": 20,
                    "top_k": 5,
                },
                "full_schema": {
                    "table_count": 26,
                    "validated_relationship_count": 27,
                    "record_count": 53,
                    "context_sha256": self.full_context_hash,
                },
            },
            "retry_policy": {
                "per_initial_request_max_retries": MAX_RETRIES_PER_REQUEST,
                "global_max_retries": MAX_RETRIES_PER_EXPERIMENT,
                "retryable_errors": "OpenAI connection/timeouts; HTTP 408, 409, 429, and 5xx",
                "malformed_output_retry": False,
            },
            "rate_card": {
                "model": self.rate_card.model,
                "input_usd_per_million": self.rate_card.input_usd_per_million,
                "cached_input_usd_per_million": self.rate_card.cached_input_usd_per_million,
                "output_usd_per_million": self.rate_card.output_usd_per_million,
                "pricing_tier": self.rate_card.pricing_tier,
                "source_url": self.rate_card.source_url,
                "checked_at": self.rate_card.checked_at,
            },
            "rerank_rate_card": {
                "model": self.rerank_rate_card.model,
                "input_usd_per_million": self.rerank_rate_card.input_usd_per_million,
                "account_tier": self.rerank_rate_card.account_tier,
                "source_url": self.rerank_rate_card.source_url,
                "checked_at": self.rerank_rate_card.checked_at,
            },
        }

    def _new_state(self) -> dict:
        return {
            "version": 1,
            "status": "ready",
            "created_at": _now(),
            "updated_at": _now(),
            "metadata": self.metadata,
            "initial_requests_used": 0,
            "retry_budget": RetryBudget().to_dict(),
            "stop_reason": None,
            "conditions": {
                condition: {
                    item["id"]: {
                        "status": "not_started",
                        "attempts": [],
                        "question": item["question"],
                        "category": item.get("category"),
                        "expected_result": item.get("expected_result"),
                        "retrieval_labels": {
                            key: item.get(key, []) for key in (
                                "relevant_tables", "relevant_columns", "relevant_relationships", "unresolved_relationships"
                            )
                        },
                        "luna_low_baseline": self.baseline_pairs[item["id"]][condition],
                    }
                    for item in self.cohort
                }
                for condition in CONDITIONS
            },
        }

    def _load_or_initialize(self) -> dict:
        if self.resume:
            if not self.checkpoint_path.exists():
                raise FileNotFoundError("--resume requires an existing FS-03 checkpoint")
            state = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
            if state.get("metadata") != self.metadata:
                raise ValueError("checkpoint configuration or frozen identities differ from this invocation")
            if state.get("status") == "completed":
                raise ValueError("this one-time experiment is already complete; refusing to repeat it")
            if state.get("status") == "stopped" and state.get("stop_reason") not in {"interrupted_before_request"}:
                raise ValueError("stopped experiment requires a new explicit approval; refusing implicit continuation")
            budget = RetryBudget.from_dict(state["retry_budget"])
            if (budget.per_request_limit, budget.total_limit) != (
                MAX_RETRIES_PER_REQUEST, MAX_RETRIES_PER_EXPERIMENT
            ):
                raise ValueError("checkpoint retry limits differ from the approved FS-03 limits")
            if state.get("initial_requests_used", -1) < 0 or state["initial_requests_used"] > 106:
                raise ValueError("checkpoint initial-request count exceeds the approved 106-request limit")
            expected_ids = set(self.metadata["cohort_ids"])
            for condition in CONDITIONS:
                rows = state.get("conditions", {}).get(condition, {})
                if set(rows) != expected_ids:
                    raise ValueError(f"checkpoint {condition} IDs differ from the frozen cohort")
            recorded_initials = sum(
                attempt.get("request_kind") == "initial"
                for condition in CONDITIONS
                for row in state["conditions"][condition].values()
                for attempt in row.get("attempts", [])
            )
            if recorded_initials != state["initial_requests_used"]:
                raise ValueError("checkpoint initial-request count does not match its recorded attempts")
            return state
        if self.output_dir.exists() and any(self.output_dir.iterdir()):
            raise FileExistsError("experiment output directory is non-empty; use --resume with its checkpoint")
        return self._new_state()

    def _save(self) -> None:
        self.state["updated_at"] = _now()
        _atomic_json(self.checkpoint_path, self.state)
        for condition, path in self.artifact_paths.items():
            artifact = {
                "metadata": self.metadata,
                "condition": condition,
                "experiment_status": self.state["status"],
                "stop_reason": self.state["stop_reason"],
                "initial_requests_used": self.state["initial_requests_used"],
                "retry_budget": self.state["retry_budget"],
                "queries": [
                    {"id": query_id, **row}
                    for query_id, row in self.state["conditions"][condition].items()
                ],
            }
            _atomic_json(path, artifact)

    def _set_stopped(self, reason: str, query_id: str | None = None) -> None:
        self.state["status"] = "stopped"
        self.state["stop_reason"] = {"type": reason, "query_id": query_id, "at": _now()}
        self._save()

    def _get_context(self, condition: str, query_id: str, row: dict, item: dict) -> list[dict]:
        if row.get("context_status") == "ready":
            if condition == "full_schema":
                return self.records
            return row["retrieved_records"]
        if row.get("context_status") == "started":
            self._set_stopped("ambiguous_rerank_attempt_after_interruption", query_id)
            raise AmbiguousAttemptError("checkpoint contains an ambiguous Cohere rerank request")
        if condition == "full_schema":
            context = self.records
            row["context_status"] = "ready"
            row["context_record_count"] = len(context)
            row["context_sha256"] = self.full_context_hash
            row["retrieval_latency_ms"] = 0.0
            row["cohere_latency_ms"] = 0.0
            row["estimated_cohere_cost_usd"] = 0.0
            self._save()
            return context

        row["context_status"] = "started"
        row["context_started_at"] = _now()
        self._save()
        try:
            started = time.perf_counter()
            candidates = self.retriever.search(item["question"], "hybrid", top_k=20, candidate_k=20)
            retrieval_latency_ms = (time.perf_counter() - started) * 1000
            rerank_started = time.perf_counter()
            retrieved = self.reranker.rerank(item["question"], candidates, top_k=5)
            rerank_latency_ms = (time.perf_counter() - rerank_started) * 1000
        except Exception as error:
            row["context_status"] = "error"
            row["context_error"] = _error_metadata(error)
            self._set_stopped("rerank_or_retrieval_error", query_id)
            raise ExperimentStopped("retrieved schema context failed; run stopped") from error
        if len(retrieved) != 5:
            row["context_status"] = "error"
            row["context_error"] = {"type": "ConfigurationError", "message": "reranker must return exactly five records"}
            self._set_stopped("retrieved_context_count_mismatch", query_id)
            raise ExperimentStopped("retrieved context did not contain exactly five records")
        row["context_status"] = "ready"
        row["retrieval_latency_ms"] = retrieval_latency_ms
        row["cohere_latency_ms"] = rerank_latency_ms
        row["cohere_usage"] = getattr(self.reranker, "last_usage", None)
        billed_input_tokens = (row["cohere_usage"] or {}).get("billed_input_tokens")
        row["estimated_cohere_cost_usd"] = estimate_rerank_cost_usd(
            self.rerank_rate_card, billed_input_tokens
        )
        row["context_record_count"] = len(retrieved)
        row["context_sha256"] = _canonical_hash(retrieved)
        row["retrieved_records"] = retrieved
        self._save()
        return retrieved

    def _finish_sql(self, condition: str, query_id: str, row: dict, item: dict, conn) -> None:
        if row["status"] == "response_received":
            try:
                sql_text = validate_generated_sql(row["raw_output"], self.allowed_tables)
            except ValueError as error:
                row["sql_valid"] = False
                row["status"] = "malformed_output"
                row["validation_error"] = str(error)
                row["error_type"] = "SQLValidationError"
                self._save()
                self._set_stopped("malformed_model_output", query_id)
                raise ExperimentStopped(f"malformed Luna-high SQL for {query_id}; run stopped") from error
            row["sql_valid"] = True
            row["sql"] = sql_text
            row["status"] = "sql_validated"
            self._save()

        if row["status"] != "sql_validated":
            return
        try:
            rows, elapsed = _execute_read_only(
                conn, self.snapshot["schema"], row["sql"], STATEMENT_TIMEOUT_MS
            )
        except (psycopg.Error, ValueError) as error:
            row["execution_success"] = False
            row["result_correct"] = False
            row["execution_status"] = type(error).__name__
            row["execution_error"] = str(error).replace("\n", " ")[:1000]
            row["execution_latency_ms"] = 0.0
        else:
            row["execution_rows"] = rows
            row["execution_latency_ms"] = elapsed
            row["execution_success"] = True
            row["result_correct"] = rows == item.get("expected_result")
            row["execution_status"] = "passed" if row["result_correct"] else "result_mismatch"
        row["execution_accuracy"] = bool(row["result_correct"])
        row["status"] = "completed"
        row["completed_at"] = _now()
        self._save()

    def _attempt_generation(self, condition: str, query_id: str, row: dict, prompt: str) -> None:
        key = f"{condition}:{query_id}"
        budget = RetryBudget.from_dict(self.state["retry_budget"])
        attempts = row["attempts"]
        has_initial = any(attempt["request_kind"] == "initial" for attempt in attempts)
        if not has_initial:
            if self.state["initial_requests_used"] >= 106:
                self._set_stopped("initial_request_cap_reached", query_id)
                raise ExperimentStopped("initial generation request cap reached")
            if budget.total_used >= budget.total_limit:
                self._set_stopped("global_retry_cap_reached", query_id)
                raise ExperimentStopped("global retry cap reached before all initial requests started")

        while True:
            is_initial = not has_initial
            preclaimed_retry = bool(row.get("retry_preclaimed"))
            if not is_initial and budget.total_used >= budget.total_limit and not preclaimed_retry:
                row["status"] = "api_error"
                self._set_stopped("global_retry_cap_reached", query_id)
                raise ExperimentStopped("global retry cap reached")
            if is_initial:
                self.state["initial_requests_used"] += 1
            attempt = {
                "attempt_number": len(attempts) + 1,
                "request_kind": "initial" if is_initial else "retry",
                "status": "started",
                "started_at": _now(),
            }
            attempts.append(attempt)
            row["retry_preclaimed"] = False
            row["status"] = "initial_in_progress" if is_initial else "retry_in_progress"
            self.state["retry_budget"] = budget.to_dict()
            self._save()
            started = time.perf_counter()
            try:
                generation = self.generator.generate(prompt)
            except Exception as error:
                attempt["latency_ms"] = (time.perf_counter() - started) * 1000
                attempt["status"] = "error"
                attempt["error"] = _error_metadata(error)
                row["last_api_error"] = attempt["error"]
                if is_transient_openai_error(error) and budget.can_retry(key):
                    budget.claim_retry(key)
                    self.state["retry_budget"] = budget.to_dict()
                    row["retry_preclaimed"] = True
                    row["status"] = "retry_pending"
                    self._save()
                    has_initial = True
                    continue
                row["status"] = "api_error"
                self._save()
                self._set_stopped(
                    "non_transient_or_exhausted_api_error",
                    query_id,
                )
                raise ExperimentStopped(f"OpenAI request failed for {query_id}; run stopped") from error

            attempt["status"] = "response_received"
            attempt["latency_ms"] = generation.latency_ms
            attempt["usage"] = _usage(generation)
            attempt["estimated_cost_usd"] = estimate_token_cost_usd(
                self.rate_card,
                generation.input_tokens,
                generation.output_tokens,
                generation.cached_input_tokens,
            )
            attempt["model"] = generation.model
            attempt["reasoning_effort"] = getattr(self.generator, "reasoning_effort", None)
            row["raw_output"] = generation.text
            row["model"] = generation.model
            row["reasoning_effort"] = getattr(self.generator, "reasoning_effort", None)
            row["usage"] = _usage(generation)
            known_attempt_costs = [
                item["estimated_cost_usd"] for item in attempts if item.get("estimated_cost_usd") is not None
            ]
            row["estimated_generation_cost_usd"] = sum(known_attempt_costs)
            row["generation_cost_estimate_complete"] = all(
                item.get("estimated_cost_usd") is not None for item in attempts
            )
            row["unpriced_request_attempts"] = sum(
                item.get("status") == "error" or item.get("estimated_cost_usd") is None
                for item in attempts
            )
            cohere_cost = row.get("estimated_cohere_cost_usd")
            known_total_costs = [
                cost for cost in (row["estimated_generation_cost_usd"], cohere_cost)
                if cost is not None
            ]
            row["estimated_total_cost_usd"] = sum(known_total_costs)
            row["total_cost_estimate_complete"] = (
                row["generation_cost_estimate_complete"] and cohere_cost is not None
            )
            row["generation_latency_ms"] = sum(
                item.get("latency_ms", 0.0) for item in attempts
            )
            attempt["status"] = "succeeded"
            row["status"] = "response_received"
            row["response_received_at"] = _now()
            self._save()
            return

    def _recover_ambiguous_attempts(self) -> None:
        for condition in CONDITIONS:
            for query_id, row in self.state["conditions"][condition].items():
                if row.get("status") in {"initial_in_progress", "retry_in_progress"}:
                    attempt = row["attempts"][-1]
                    attempt["status"] = "ambiguous_after_interruption"
                    row["status"] = "ambiguous_attempt"
                    self._set_stopped("ambiguous_generation_attempt", query_id)
                    raise AmbiguousAttemptError(
                        f"checkpoint has ambiguous {condition} request for {query_id}; it will not be repeated"
                    )

    def run(self) -> dict:
        self._recover_ambiguous_attempts()
        self.state["status"] = "running"
        self.state["stop_reason"] = None
        self._save()
        with psycopg.connect(self.dsn) as conn:
            for condition in CONDITIONS:
                for item in self.cohort:
                    query_id = item["id"]
                    row = self.state["conditions"][condition][query_id]
                    if row["status"] == "completed":
                        continue
                    if row["status"] in {"malformed_output", "api_error", "ambiguous_attempt"}:
                        self._set_stopped("terminal_query_failure", query_id)
                        raise ExperimentStopped(f"terminal failure checkpointed for {query_id}")
                    context = self._get_context(condition, query_id, row, item)
                    if row["status"] == "not_started" or row["status"] == "retry_pending":
                        prompt = build_prompt(item["question"], context)
                        row["prompt_sha256"] = hashlib.sha256(prompt.encode()).hexdigest()
                        self._attempt_generation(condition, query_id, row, prompt)
                    self._finish_sql(condition, query_id, row, item, conn)
                if self.state["status"] == "stopped":
                    break
        if self.state["status"] != "stopped":
            all_complete = all(
                row["status"] == "completed"
                for condition in CONDITIONS
                for row in self.state["conditions"][condition].values()
            )
            self.state["status"] = "completed" if all_complete else "stopped"
            if not all_complete:
                self.state["stop_reason"] = {"type": "incomplete_checkpoint", "at": _now()}
        self._save()
        return self.state


def check_experiment_readiness(root: Path) -> dict:
    """Read-only preflight; does not initialize clients or issue service requests."""
    identities = verify_frozen_inputs(root)
    baseline = json.loads((root / "data/evaluation/azraq-sql-prompt-results.json").read_text())
    cohort = [
        json.loads(line)
        for line in (root / "data/evaluation/azraq-retrieval-failure-labels.jsonl").read_text().splitlines()
        if line.strip()
    ]
    paired = pair_luna_low_baseline(cohort, baseline)
    return {
        "ready": True,
        "cohort_count": len(cohort),
        "baseline_successes": {
            condition: sum(pair[condition]["execution_accuracy"] for pair in paired.values())
            for condition in CONDITIONS
        },
        "initial_request_cap": 106,
        "retry_cap": MAX_RETRIES_PER_EXPERIMENT,
        "maximum_api_attempts": 106 + MAX_RETRIES_PER_EXPERIMENT,
        "identities": identities,
    }
