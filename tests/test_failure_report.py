import unittest

from triage_sql.failure_experiment import CONDITIONS
from triage_sql.failure_report import build_failure_report


class FailureReportTests(unittest.TestCase):
    def setUp(self):
        self.cohort = [{"id": f"q{i:02}", "category": "join" if i % 2 else "filter"} for i in range(53)]
        self.pairs = {
            item["id"]: {
                condition: {"execution_accuracy": condition == "full_schema" and index < 19}
                for condition in CONDITIONS
            }
            for index, item in enumerate(self.cohort)
        }
        self.artifacts = {}
        for condition in CONDITIONS:
            self.artifacts[condition] = {
                "experiment_status": "completed",
                "metadata": {"generator_model": "gpt-6-luna", "reasoning_effort": "high"},
                "queries": [
                {
                    "id": item["id"], "status": "completed", "sql_valid": True,
                    "execution_success": True, "result_correct": index < (2 if condition == "retrieved_schema" else 20),
                    "execution_status": "passed" if index < (2 if condition == "retrieved_schema" else 20) else "result_mismatch",
                    "usage": {"input_tokens": 10, "output_tokens": 4, "reasoning_tokens": 2},
                    "generation_latency_ms": 100.0, "execution_latency_ms": 5.0,
                    "estimated_generation_cost_usd": 0.01,
                    "estimated_cohere_cost_usd": 0.0 if condition == "retrieved_schema" else 0.0,
                    "estimated_total_cost_usd": 0.01,
                    "total_cost_estimate_complete": True,
                }
                for index, item in enumerate(self.cohort)
                ],
            }

    def test_reports_accuracy_metrics_cost_and_category_errors_per_condition(self):
        report = build_failure_report(self.cohort, self.pairs, self.artifacts)
        retrieved = report["conditions"]["retrieved_schema"]
        full = report["conditions"]["full_schema"]
        self.assertEqual(retrieved["baseline"]["correct"], 0)
        self.assertEqual(retrieved["luna_high"]["result_correct"]["count"], 2)
        self.assertEqual(retrieved["luna_high"]["improvement"]["additional_correct_queries"], 2)
        self.assertAlmostEqual(retrieved["luna_high"]["cost_per_additional_success_usd"], 53 * 0.01 / 2)
        self.assertEqual(retrieved["luna_high"]["latency_ms"]["generation_mean"], 100.0)
        self.assertEqual(full["baseline"]["correct"], 19)
        self.assertEqual(full["luna_high"]["improvement"]["additional_correct_queries"], 1)
        self.assertEqual(full["luna_high"]["tokens"]["input"], 530)
        self.assertIn("result_mismatch", full["luna_high"]["failures_by_error_type"])
        self.assertEqual(full["luna_high"]["category_breakdown"]["filter"]["queries"], 27)
        self.assertIn("left to the reader", report["cost_acceptability"])

    def test_nonpositive_delta_has_no_cost_per_additional_success(self):
        for row in self.artifacts["full_schema"]["queries"]:
            row["result_correct"] = row["id"] in {item["id"] for item in self.cohort[:19]}
        report = build_failure_report(self.cohort, self.pairs, self.artifacts)
        full = report["conditions"]["full_schema"]["luna_high"]
        self.assertEqual(full["improvement"]["additional_correct_queries"], 0)
        self.assertIsNone(full["cost_per_additional_success_usd"])

    def test_malformed_stopped_query_is_counted_as_a_failed_first_pass_result(self):
        row = self.artifacts["retrieved_schema"]["queries"][0]
        row.update({
            "status": "malformed_output", "sql_valid": False,
            "execution_success": False, "result_correct": False,
            "error_type": "SQLValidationError",
        })
        report = build_failure_report(self.cohort, self.pairs, self.artifacts)
        retrieved = report["conditions"]["retrieved_schema"]["luna_high"]
        self.assertEqual(retrieved["sql_valid"]["count"], 52)
        self.assertEqual(retrieved["result_correct"]["total"], 53)
        self.assertEqual(retrieved["failures_by_error_type"]["SQLValidationError"], 1)

    def test_rejects_artifact_with_wrong_ids_or_extra_condition(self):
        self.artifacts["retrieved_schema"]["queries"].pop()
        with self.assertRaisesRegex(ValueError, "exactly the 53"):
            build_failure_report(self.cohort, self.pairs, self.artifacts)


if __name__ == "__main__":
    unittest.main()
