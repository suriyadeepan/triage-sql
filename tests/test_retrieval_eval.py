import json
import unittest
from pathlib import Path

from triage_sql.relationships import load_relationships
from triage_sql.retrieval_eval import derive_labels, label_evaluation_set
from triage_sql.schema import load_schema


ROOT = Path(__file__).resolve().parents[1]


class RetrievalLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = {
            table.name: {column.name for column in table.columns}
            for table in load_schema(ROOT / "data/raw/azraq-schema.sql")
        }
        cls.relationships = load_relationships(ROOT / "data/raw/azraq-relationships.yaml")

    def test_reference_sql_labels_all_120_queries(self):
        items = label_evaluation_set(
            ROOT / "data/evaluation/azraq-evaluation.jsonl",
            ROOT / "data/raw/azraq-schema.sql",
            ROOT / "data/raw/azraq-relationships.yaml",
        )
        self.assertEqual(len(items), 120)
        subtype = items[90]
        self.assertIn("groups_members", subtype["relevant_tables"])
        self.assertIn("groups_members.group_id__clients.id", subtype["relevant_relationships"])
        self.assertEqual(subtype["unresolved_relationships"], [])
        self.assertNotIn("users.password", repr(items).casefold())

    def test_needs_review_join_is_reported_unresolved_not_eligible(self):
        labels = derive_labels(
            "SELECT count(*) FROM loans l JOIN users u ON l.officer_id = u.id",
            self.schema,
            self.relationships,
        )
        self.assertEqual(labels["relevant_relationships"], [])
        self.assertIn("loans.officer_id__users.id", labels["unresolved_relationships"])

    def test_subtype_join_without_required_filter_is_unresolved(self):
        labels = derive_labels(
            "SELECT count(*) FROM groups_members gm JOIN clients c ON gm.group_id = c.id",
            self.schema,
            self.relationships,
        )
        self.assertEqual(labels["relevant_relationships"], [])
        self.assertIn("groups_members.group_id__clients.id", labels["unresolved_relationships"])


if __name__ == "__main__":
    unittest.main()
