import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import openai

from triage_sql.costing import RerankRateCard, TokenRateCard
from triage_sql.failure_experiment import (
    CONDITIONS,
    AmbiguousAttemptError,
    ExperimentStopped,
    FailureTriggeredExperiment,
)
from triage_sql.sql_generation import Generation
from scripts.benchmark_azraq_luna_high import _build_experiment_generator


ROOT = Path(__file__).resolve().parents[1]
RECORDS = json.loads((ROOT / "data/index/azraq-schema/records.json").read_text())


class FakeGenerator:
    model = "gpt-6-luna"
    reasoning_effort = "high"

    def __init__(self, outputs=None):
        self.outputs = list(outputs or [])
        self.calls = 0

    def generate(self, prompt):
        self.calls += 1
        if self.outputs:
            value = self.outputs.pop(0)
            if isinstance(value, BaseException):
                raise value
            return value
        return Generation(
            "SELECT count(*) FROM clients", 20, 1.0, self.model,
            output_tokens=7, reasoning_tokens=3, cached_input_tokens=2,
        )


class FailOncePerPromptGenerator(FakeGenerator):
    def __init__(self):
        super().__init__()
        self.seen_prompts = set()

    def generate(self, prompt):
        self.calls += 1
        if prompt not in self.seen_prompts:
            self.seen_prompts.add(prompt)
            request = httpx.Request("POST", "https://api.openai.test/v1/responses")
            raise openai.APIConnectionError(request=request)
        return Generation(
            "SELECT count(*) FROM clients", 20, 1.0, self.model,
            output_tokens=7, reasoning_tokens=3, cached_input_tokens=2,
        )


class FakeRetriever:
    records_path = ROOT / "data/index/azraq-schema/records.json"

    def __init__(self):
        self.calls = []

    def ensure_fresh(self):
        return None

    def search(self, question, mode, *, top_k, candidate_k):
        self.calls.append({"mode": mode, "top_k": top_k, "candidate_k": candidate_k})
        return RECORDS[:candidate_k]


class FakeReranker:
    last_usage = {"billed_input_tokens": 500, "billed_output_tokens": None, "search_units": 1.0}

    def __init__(self):
        self.calls = []

    def rerank(self, question, records, top_k):
        self.calls.append({"top_k": top_k, "candidate_count": len(records)})
        return records[:top_k]


class FakeConnection:
    def __enter__(self):
        return object()

    def __exit__(self, *_):
        return False


def make_experiment(output_dir, *, generator=None, retriever=None, reranker=None, resume=False,
                   continue_after_stop=False, rerank_min_interval_seconds=0.0):
    return FailureTriggeredExperiment(
        root=ROOT,
        generator=generator or FakeGenerator(),
        retriever=retriever or FakeRetriever(),
        reranker=reranker or FakeReranker(),
        dsn="postgresql://unused",
        output_dir=output_dir,
        rate_card=TokenRateCard(
            model="gpt-6-luna", input_usd_per_million=0.10,
            cached_input_usd_per_million=0.01, output_usd_per_million=0.50,
            source_url="https://developers.openai.com/api/docs/pricing", checked_at="2026-11-28",
        ),
        rerank_rate_card=RerankRateCard(
            model="rerank-v5.0-fast", input_usd_per_million=0.02,
            source_url="https://cohere.com/blog/rerank-5", checked_at="2026-11-28", account_tier="trial",
        ),
        approved_run=True,
        resume=resume,
        continue_after_stop=continue_after_stop,
        rerank_min_interval_seconds=rerank_min_interval_seconds,
    )


class FailureTriggeredExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp.name) / "experiment"
        self.connection_patch = patch("triage_sql.failure_experiment.psycopg.connect", return_value=FakeConnection())
        self.execution_patch = patch(
            "triage_sql.failure_experiment._execute_read_only", return_value=([], 2.0)
        )
        self.connection_patch.start()
        self.execution_patch.start()

    def tearDown(self):
        self.connection_patch.stop()
        self.execution_patch.stop()
        self.temp.cleanup()

    def test_run_uses_only_the_two_fixed_conditions_and_53_ids(self):
        generator, retriever, reranker = FakeGenerator(), FakeRetriever(), FakeReranker()
        state = make_experiment(
            self.output_dir, generator=generator, retriever=retriever, reranker=reranker
        ).run()

        self.assertEqual(state["status"], "completed")
        self.assertEqual(generator.calls, 106)
        self.assertEqual(len(retriever.calls), 53)
        self.assertEqual(len(reranker.calls), 53)
        self.assertTrue(all(call == {"mode": "hybrid", "top_k": 20, "candidate_k": 20} for call in retriever.calls))
        self.assertTrue(all(call == {"top_k": 5, "candidate_count": 20} for call in reranker.calls))
        for condition in CONDITIONS:
            artifact = json.loads((self.output_dir / {
                "retrieved_schema": "retrieved-schema.json", "full_schema": "full-schema.json"
            }[condition]).read_text())
            self.assertEqual(len(artifact["queries"]), 53)
            self.assertTrue(all(row["status"] == "completed" for row in artifact["queries"]))
            self.assertEqual(artifact["metadata"]["generator_model"], "gpt-6-luna")
            self.assertEqual(artifact["metadata"]["reasoning_effort"], "high")
        retrieved = json.loads((self.output_dir / "retrieved-schema.json").read_text())
        full = json.loads((self.output_dir / "full-schema.json").read_text())
        self.assertEqual(retrieved["queries"][0]["context_record_count"], 5)
        self.assertEqual(full["queries"][0]["context_record_count"], 53)
        self.assertEqual(retrieved["queries"][0]["estimated_cohere_cost_usd"], 0.0)

    def test_unapproved_run_is_rejected_before_generation(self):
        generator = FakeGenerator()
        with self.assertRaisesRegex(PermissionError, "explicit --approve-run"):
            FailureTriggeredExperiment(
                root=ROOT,
                generator=generator,
                retriever=FakeRetriever(),
                reranker=FakeReranker(),
                dsn="postgresql://unused",
                output_dir=self.output_dir,
                rate_card=TokenRateCard(
                    "gpt-6-luna", 0.1, 0.5, "https://example.test", "2026-11-28"
                ),
                rerank_rate_card=RerankRateCard(
                    "rerank-v5.0-fast", 0.02, "https://example.test", "2026-11-28", "trial"
                ),
            )
        self.assertEqual(generator.calls, 0)

    def test_experiment_generator_disables_sdk_retries_explicitly(self):
        with patch.dict("os.environ", {"OPENAI_MODEL": "gpt-6-luna", "OPENAI_REASONING_EFFORT": "high"}), patch(
            "scripts.benchmark_azraq_luna_high.openai.OpenAI"
        ) as factory:
            generator = _build_experiment_generator()
        factory.assert_called_once_with(max_retries=0)
        self.assertEqual(generator.model, "gpt-6-luna")

    def test_cohere_requests_are_spaced_for_trial_quota(self):
        experiment = make_experiment(self.output_dir, rerank_min_interval_seconds=6.5)
        first, second = experiment.cohort[:2]
        first_row = experiment.state["conditions"]["retrieved_schema"][first["id"]]
        second_row = experiment.state["conditions"]["retrieved_schema"][second["id"]]
        with patch("triage_sql.failure_experiment.time.sleep") as sleep:
            experiment._get_context("retrieved_schema", first["id"], first_row, first)
            experiment._get_context("retrieved_schema", second["id"], second_row, second)
        sleep.assert_called_once()
        self.assertGreater(sleep.call_args.args[0], 0)
        self.assertLessEqual(sleep.call_args.args[0], 6.5)

    def test_malformed_sql_is_checkpointed_and_stops_without_a_new_generation(self):
        generator = FakeGenerator([Generation("not SQL", 5, 1.0, "gpt-6-luna", output_tokens=2)])
        experiment = make_experiment(self.output_dir, generator=generator)
        with self.assertRaisesRegex(ExperimentStopped, "malformed Luna-high SQL"):
            experiment.run()
        self.assertEqual(generator.calls, 1)
        checkpoint = json.loads((self.output_dir / "checkpoint.json").read_text())
        self.assertEqual(checkpoint["status"], "stopped")
        self.assertEqual(checkpoint["stop_reason"]["type"], "malformed_model_output")
        row = checkpoint["conditions"]["retrieved_schema"]["eval-011"]
        self.assertEqual(row["status"], "malformed_output")
        self.assertEqual(row["raw_output"], "not SQL")

    def test_two_transient_retries_are_allowed_then_the_run_stops(self):
        request = httpx.Request("POST", "https://api.openai.test/v1/responses")
        first = openai.APIConnectionError(request=request)
        second = openai.APITimeoutError(request=request)
        third = openai.APIStatusError(
            "server error", response=httpx.Response(503, request=request), body=None
        )
        generator = FakeGenerator([first, second, third])
        experiment = make_experiment(self.output_dir, generator=generator)
        with self.assertRaisesRegex(ExperimentStopped, "OpenAI request failed"):
            experiment.run()
        self.assertEqual(generator.calls, 3)
        checkpoint = json.loads((self.output_dir / "checkpoint.json").read_text())
        self.assertEqual(checkpoint["retry_budget"]["total_used"], 2)
        attempts = checkpoint["conditions"]["retrieved_schema"]["eval-011"]["attempts"]
        self.assertEqual([item["request_kind"] for item in attempts], ["initial", "retry", "retry"])

    def test_global_retry_cap_stops_before_any_fifty_first_retry(self):
        generator = FailOncePerPromptGenerator()
        experiment = make_experiment(self.output_dir, generator=generator)
        with self.assertRaisesRegex(ExperimentStopped, "global retry cap"):
            experiment.run()
        checkpoint = json.loads((self.output_dir / "checkpoint.json").read_text())
        self.assertEqual(generator.calls, 100)
        self.assertEqual(checkpoint["initial_requests_used"], 50)
        self.assertEqual(checkpoint["retry_budget"]["total_used"], 50)

    def test_resume_after_response_checkpoint_does_not_repeat_generation(self):
        generator = FakeGenerator()
        experiment = make_experiment(self.output_dir, generator=generator)
        with patch(
            "triage_sql.failure_experiment.validate_generated_sql", side_effect=KeyboardInterrupt
        ):
            with self.assertRaises(KeyboardInterrupt):
                experiment.run()
        self.assertEqual(generator.calls, 1)

        resumed = make_experiment(self.output_dir, generator=generator, resume=True).run()
        self.assertEqual(resumed["status"], "completed")
        self.assertEqual(generator.calls, 106)
        first = resumed["conditions"]["retrieved_schema"]["eval-011"]
        self.assertEqual(len(first["attempts"]), 1)

    def test_explicit_continuation_skips_malformed_and_completed_calls(self):
        experiment = make_experiment(self.output_dir)
        malformed_id = experiment.cohort[1]["id"]
        pending_id = experiment.cohort[-1]["id"]
        for condition in CONDITIONS:
            for query_id, row in experiment.state["conditions"][condition].items():
                if condition == "retrieved_schema" and query_id == malformed_id:
                    row.update({
                        "status": "malformed_output", "raw_output": "",
                        "validation_error": "generated SQL must contain exactly one SELECT query",
                        "error_type": "SQLValidationError",
                        "attempts": [{"request_kind": "initial", "status": "succeeded"}],
                    })
                elif condition == "full_schema" and query_id == malformed_id:
                    row.update({
                        "status": "malformed_output", "raw_output": "SELECT broken",
                        "validation_error": "generated SQL could not be parsed",
                        "error_type": "SQLValidationError",
                        "attempts": [{"request_kind": "initial", "status": "succeeded"}],
                    })
                elif condition == "full_schema" and query_id == pending_id:
                    row["status"] = "not_started"
                else:
                    row["status"] = "completed"
                    row["sql_valid"] = True
                    row["execution_success"] = True
                    row["result_correct"] = True
                    row["attempts"] = [{"request_kind": "initial", "status": "succeeded"}]
        experiment.state["initial_requests_used"] = 105
        experiment.state["status"] = "stopped"
        experiment.state["continuations"] = [{
            "approved": True, "malformed_condition": "retrieved_schema",
            "malformed_query_skipped": malformed_id,
        }]
        experiment.state["stop_reason"] = {
            "type": "malformed_model_output", "condition": "full_schema",
            "query_id": malformed_id, "at": "2026-11-28T00:00:00+00:00"
        }
        experiment._save()

        with self.assertRaisesRegex(ValueError, "explicitly approved malformed-output continuation"):
            make_experiment(self.output_dir, resume=True)

        generator = FakeGenerator()
        resumed = make_experiment(
            self.output_dir, generator=generator, resume=True, continue_after_stop=True
        ).run()
        self.assertEqual(generator.calls, 1)
        self.assertEqual(resumed["initial_requests_used"], 106)
        self.assertEqual(resumed["status"], "completed")
        self.assertEqual(resumed["conditions"]["retrieved_schema"][malformed_id]["status"], "malformed_output")
        self.assertEqual(resumed["conditions"]["full_schema"][malformed_id]["status"], "malformed_output")
        self.assertEqual(resumed["conditions"]["full_schema"][pending_id]["status"], "completed")
        self.assertEqual(resumed["continuations"][-1]["malformed_query_skipped"], malformed_id)

    def test_ambiguous_in_flight_request_is_never_repeated(self):
        generator = FakeGenerator()
        experiment = make_experiment(self.output_dir, generator=generator)
        with patch.object(experiment, "_save", wraps=experiment._save) as save:
            # Simulate the crash immediately after an initial request is checkpointed as started.
            original_generate = generator.generate
            def interrupt(prompt):
                raise KeyboardInterrupt
            generator.generate = interrupt
            with self.assertRaises(KeyboardInterrupt):
                experiment.run()
        self.assertGreater(save.call_count, 0)
        resumed = make_experiment(self.output_dir, generator=generator, resume=True)
        with self.assertRaises(AmbiguousAttemptError):
            resumed.run()
        self.assertEqual(generator.calls, 0)


if __name__ == "__main__":
    unittest.main()
