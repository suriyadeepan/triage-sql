import csv
import tempfile
import unittest
from pathlib import Path

from scripts.validate_azraq_relationships import (
    Endpoint,
    parse_relationships,
    referenced_values,
)


class RelationshipMetadataTests(unittest.TestCase):
    def test_parse_declared_target_filter(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yaml_path = Path(temp_dir) / "relationships.yaml"
            yaml_path.write_text(
                """relationships:
  - id: groups_members.group_id__clients.id
    from: {table: groups_members, column: group_id}
    to: {table: clients, column: id}
    target_filter: {column: type, equals: Group}
    cardinality: many_to_one
    status: validated
    evidence: [full_referential_coverage_check]
unresolved_candidates: []
""",
                encoding="utf-8",
            )

            [relationship] = parse_relationships(yaml_path)

        self.assertEqual(relationship.source, Endpoint("groups_members", "group_id"))
        self.assertEqual(relationship.targets, (Endpoint("clients", "id"),))
        self.assertEqual(relationship.target_filter, ("type", "Group"))
        self.assertEqual(relationship.status, "validated")


class TargetLookupTests(unittest.TestCase):
    def write_clients(self, path):
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["id", "type"])
            writer.writerows([["1", "Individual"], ["2", "Group"], ["2", "Group"], ["", "Group"]])

    def test_target_filter_scopes_ids_and_counts_nulls_and_duplicates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            clients = Path(temp_dir) / "clients.csv"
            self.write_clients(clients)

            group_ids, nulls, duplicates = referenced_values(clients, "id", ("type", "Group"))
            all_ids, all_nulls, all_duplicates = referenced_values(clients, "id")

        self.assertEqual(group_ids, {"2"})
        self.assertEqual(nulls, 1)
        self.assertEqual(duplicates, 1)
        self.assertEqual(all_ids, {"1", "2"})
        self.assertEqual(all_nulls, 1)
        self.assertEqual(all_duplicates, 1)


if __name__ == "__main__":
    unittest.main()
