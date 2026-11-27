import unittest

from triage_sql.evaluation import PATTERNS, VARIANTS, validate_items


class EvaluationDataTests(unittest.TestCase):
    def test_catalog_has_100_to_200_items_and_required_coverage(self):
        self.assertGreaterEqual(len(PATTERNS) * len(VARIANTS), 100)
        self.assertLessEqual(len(PATTERNS) * len(VARIANTS), 200)
        categories = {row[0] for row in PATTERNS}
        self.assertTrue({"filter", "date", "aggregation", "join", "subtype_join", "multi_table"} <= categories)

    def test_validator_requires_execution_snapshot_and_no_password_sql(self):
        item = {"id": "eval-001", "dataset_snapshot_id": "a" * 64, "status": "supported", "reference_sql": "SELECT count(*) FROM clients", "execution": {"status": "passed"}}
        items = [{**item, "id": f"eval-{n:03d}"} for n in range(100)]
        validate_items(items, "a" * 64)
        item["reference_sql"] = "SELECT password FROM users"
        items[0] = item
        with self.assertRaises(ValueError):
            validate_items(items, "a" * 64)

    def test_unsupported_items_must_not_carry_sql(self):
        item = {"id": "eval-001", "dataset_snapshot_id": "a" * 64, "status": "unsupported", "reference_sql": None}
        items = [{**item, "id": f"eval-{n:03d}"} for n in range(100)]
        items[0] = {**items[0], "reference_sql": "SELECT 1"}
        with self.assertRaises(ValueError):
            validate_items(items, "a" * 64)


if __name__ == "__main__":
    unittest.main()
