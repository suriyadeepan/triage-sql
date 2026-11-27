import unittest

from triage_sql.examples import EXAMPLES, _partition, leakage_findings


class ExampleDatasetTests(unittest.TestCase):
    def test_all_declared_edges_are_validated_catalog_edges(self):
        import yaml
        from pathlib import Path

        doc = yaml.safe_load(Path("data/raw/azraq-relationships.yaml").read_text())
        eligible = {r["id"] for r in doc["relationships"] if r["status"] == "validated"}
        self.assertTrue(all(set(edges) <= eligible for *_, edges in EXAMPLES))
        self.assertEqual(len({_partition(i) for i in range(len(EXAMPLES))}), 3)

    def test_leakage_checker_detects_question_sql_result_and_pattern(self):
        train = [{"question": "count clients", "sql": "SELECT count(*)", "expected_result": [[1]], "pattern_id": "a"}]
        heldout = [{"question": "count clients", "sql": "SELECT count(*)", "expected_result": [[1]], "pattern_id": "a"}]
        findings = leakage_findings({"train": train, "heldout": heldout})
        self.assertEqual({finding["kind"] for finding in findings}, {"question", "sql", "result", "pattern"})


if __name__ == "__main__":
    unittest.main()
