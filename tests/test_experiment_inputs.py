import json
import unittest
from pathlib import Path
from unittest.mock import patch

from triage_sql import experiment_inputs


ROOT = Path(__file__).resolve().parents[1]


class FrozenExperimentInputsTests(unittest.TestCase):
    def test_repository_inputs_match_the_frozen_baseline(self):
        verified = experiment_inputs.verify_frozen_inputs(ROOT)
        self.assertEqual(len(verified["cohort_ids"]), 53)
        self.assertEqual(verified["snapshot_id"], experiment_inputs.FROZEN_SNAPSHOT_ID)
        self.assertEqual(verified["sql_baseline"], experiment_inputs.FROZEN_SHA256["sql_baseline"])

    def test_hash_mismatch_fails_closed(self):
        path = ROOT / "data/evaluation/azraq-sql-prompt-results.json"
        with patch.object(experiment_inputs, "sha256_file", return_value="0" * 64):
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                experiment_inputs._verified_hash(
                    path, experiment_inputs.FROZEN_SHA256["sql_baseline"], "sql baseline"
                )

    def test_pairs_all_53_queries_to_both_luna_low_conditions(self):
        cohort_path = ROOT / "data/evaluation/azraq-retrieval-failure-labels.jsonl"
        baseline_path = ROOT / "data/evaluation/azraq-sql-prompt-results.json"
        cohort = [json.loads(line) for line in cohort_path.read_text().splitlines() if line]
        baseline = json.loads(baseline_path.read_text())
        paired = experiment_inputs.pair_luna_low_baseline(cohort, baseline)
        self.assertEqual(len(paired), 53)
        self.assertEqual(
            sum(row["retrieved_schema"]["execution_accuracy"] for row in paired.values()), 0
        )
        self.assertEqual(
            sum(row["full_schema"]["execution_accuracy"] for row in paired.values()), 19
        )

    def test_comparison_rejects_an_incomplete_cohort(self):
        baseline = {"retrieved_schema": {"queries": []}, "full_schema": {"queries": []}}
        with self.assertRaisesRegex(ValueError, "53 unique"):
            experiment_inputs.pair_luna_low_baseline([{"id": "eval-011"}], baseline)


if __name__ == "__main__":
    unittest.main()
