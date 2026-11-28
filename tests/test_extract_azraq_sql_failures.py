import unittest

from scripts.extract_azraq_sql_failures import extract_failures


class ExtractFailuresTests(unittest.TestCase):
    def test_uses_only_execution_failures_and_preserves_label_order(self):
        baseline = {"retrieved_schema": {
            "queries": [
                {"id": "q1", "execution_accuracy": True},
                {"id": "q2", "execution_accuracy": False},
            ],
            "failures": [{"id": "q2"}],
        }}
        labels = [{"id": "q1", "relevant_tables": ["a"]}, {"id": "q2", "relevant_tables": ["b"]}]
        self.assertEqual(extract_failures(baseline, labels), [labels[1]])

    def test_rejects_mismatched_failure_summary(self):
        baseline = {"retrieved_schema": {
            "queries": [{"id": "q1", "execution_accuracy": False}], "failures": [],
        }}
        with self.assertRaises(ValueError):
            extract_failures(baseline, [{"id": "q1"}])


if __name__ == "__main__":
    unittest.main()
