import unittest
from pathlib import Path

from triage_sql.schema_context import context_records, relationship_records
from triage_sql.schema import load_schema


ROOT = Path(__file__).resolve().parents[1]


class SchemaContextTests(unittest.TestCase):
    def test_only_validated_declared_edges_are_join_candidates(self):
        records = relationship_records(ROOT / "data/raw/azraq-relationships.yaml")
        self.assertEqual(len(records), 27)
        ids = {record.id for record in records}
        self.assertNotIn("loans.officer_id__users.id", ids)
        self.assertFalse(any("candidate" in record.id for record in records))
        self.assertTrue(all(record.status == "validated" for record in records))

    def test_direction_cardinality_subtype_predicates_and_provenance_are_preserved(self):
        records = {r.id: r for r in relationship_records(ROOT / "data/raw/azraq-relationships.yaml")}
        group = records["groups_members.group_id__clients.id"]
        member = records["groups_members.member_id__clients.id"]
        nsg = records["nsg_meetings.group_id__clients.id"]
        collateral = records["collaterals.owner_id__clients.id"]

        self.assertEqual(group.join_predicate, "groups_members.group_id = clients.id AND clients.type = 'Group'")
        self.assertEqual(member.join_predicate, "groups_members.member_id = clients.id AND clients.type = 'Individual'")
        self.assertEqual(nsg.join_predicate, "nsg_meetings.group_id = clients.id AND clients.type = 'NSG'")
        self.assertEqual(collateral.join_predicate, "collaterals.owner_id = clients.id")
        self.assertEqual(group.cardinality, "many_to_one")
        self.assertIn("full_postgresql_validation", group.evidence)
        self.assertTrue(group.provenance["semantic_review"])

    def test_context_keeps_table_records_structured_and_password_free(self):
        tables = load_schema(ROOT / "data/raw/azraq-schema.sql", ROOT / "data/raw/azraq.md")
        relations = relationship_records(ROOT / "data/raw/azraq-relationships.yaml")
        records = context_records(tables, relations)
        table_records = [record for record in records if record["kind"] == "table"]
        text = repr(records).casefold()
        self.assertEqual(len(table_records), 26)
        self.assertNotIn("password", text)
        self.assertNotIn("anthony johnson", text)


if __name__ == "__main__":
    unittest.main()
