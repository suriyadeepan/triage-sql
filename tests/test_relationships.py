import unittest
from pathlib import Path

import yaml

from scripts.validate_azraq_relationships_pg import render_human_report
from triage_sql.relationships import (
    Endpoint,
    Relationship,
    load_relationships,
    relationship_join_clause,
    validated_relationships,
)


ROOT = Path(__file__).resolve().parents[1]
RELATIONSHIPS = ROOT / "data/raw/azraq-relationships.yaml"


class RelationshipMetadataTests(unittest.TestCase):
    def test_human_report_includes_exact_coverage_counts_and_eligibility(self):
        report = {
            "dataset_snapshot_id": "snapshot-test",
            "postgres_version": "18.7",
            "relationship_metadata_sha256": "hash-test",
            "coverage": "full",
            "relationships": [{
                "id": "groups_members.group_id__clients.id",
                "coverage": "full",
                "source_rows": 3,
                "source_null_count": 0,
                "matched_source_rows": 3,
                "orphan_source_rows": 0,
                "subtype_mismatch_count": 0,
                "target_rows": 2,
                "target_null_count": 0,
                "target_duplicate_keys": 0,
                "filtered_target_duplicate_keys": 0,
                "status": "validated",
                "join_eligible": True,
            }],
        }
        rendered = render_human_report(report)
        self.assertIn("**full**", rendered)
        self.assertIn("| `groups_members.group_id__clients.id` | full | 3 | 0 | 3 | 0 | 0 | 2 | 0 | 0 | 0 | validated | yes |", rendered)

    def test_all_metadata_and_subtype_filters_are_preserved(self):
        relationships = load_relationships(RELATIONSHIPS)
        by_id = {relationship.id: relationship for relationship in relationships}
        document = yaml.safe_load(RELATIONSHIPS.read_text(encoding="utf-8"))

        self.assertIn("collaterals.owner_id__clients.id", by_id)
        self.assertIsNone(by_id["collaterals.owner_id__clients.id"].target_filter)
        self.assertEqual(by_id["groups_members.group_id__clients.id"].target_filter, ("type", "Group"))
        self.assertEqual(by_id["groups_members.member_id__clients.id"].target_filter, ("type", "Individual"))
        self.assertEqual(by_id["nsg_meetings.group_id__clients.id"].target_filter, ("type", "NSG"))
        self.assertEqual(by_id["users.branch_id__branches.id"].cardinality, "many_to_one")
        self.assertGreaterEqual(by_id["users.branch_id__branches.id"].confidence, 0.9)
        self.assertIn("evidence", by_id["users.branch_id__branches.id"].metadata)
        self.assertEqual(
            document["profiling_evidence"]["client_type_counts_and_id_ranges"]["Individual"],
            {"id_min": 1, "id_max": 2800000, "rows": 2800000},
        )
        self.assertEqual(
            document["profiling_evidence"]["client_type_counts_and_id_ranges"]["Group"],
            {"id_min": 2800001, "id_max": 3200000, "rows": 400000},
        )
        self.assertEqual(
            document["profiling_evidence"]["client_type_counts_and_id_ranges"]["NSG"],
            {"id_min": 3200001, "id_max": 3400000, "rows": 200000},
        )
        self.assertEqual(
            document["profiling_evidence"]["client_type_counts_and_id_ranges"]["Corporate"],
            {"id_min": 3400001, "id_max": 4000000, "rows": 600000},
        )
        sampled = document["profiling_evidence"]["randomized_validation"]
        self.assertEqual(sampled["seed"], 20261127)
        self.assertEqual(sampled["sample_size_per_source_table"], 1000)
        self.assertFalse(sampled["full_source_coverage"])
        self.assertEqual(sampled["results"]["collaterals.owner_id"], {"sampled": 1000, "nulls": 0, "nonmatching": 0})
        self.assertEqual(document["profiling_evidence"]["full_validation"]["initial_status"], "not_performed")

    def test_unreviewed_edges_never_reach_join_generation(self):
        relationships = load_relationships(RELATIONSHIPS)
        eligible = validated_relationships(relationships)
        self.assertEqual(len(eligible), 27)
        eligible_ids = {item.id for item in eligible}
        self.assertNotIn("loans.officer_id__users.id", eligible_ids)
        self.assertNotIn("savings_accounts.officer_id__users.id", eligible_ids)
        for status in ("inferred", "needs_review", "rejected"):
            unreviewed = Relationship(
                id=f"unreviewed-{status}",
                source=Endpoint("source", "id"),
                target=Endpoint("target", "id"),
                cardinality="many_to_one",
                confidence=0.5,
                status=status,
                evidence=(),
                target_filter=None,
                metadata={},
            )
            self.assertNotIn(unreviewed, validated_relationships([unreviewed]))
            with self.assertRaisesRegex(ValueError, "is not validated"):
                relationship_join_clause(unreviewed)

    def test_only_validated_declared_edges_are_eligible(self):
        validated = Relationship(
            id="groups_members.group_id__clients.id",
            source=Endpoint("groups_members", "group_id"),
            target=Endpoint("clients", "id"),
            cardinality="many_to_one",
            confidence=1.0,
            status="validated",
            evidence=("full_postgresql_validation", "semantic_review"),
            target_filter=("type", "Group"),
            metadata={"semantic_review": "Reviewed"},
        )
        candidate = Relationship(
            id="candidate",
            source=Endpoint("source", "id"),
            target=Endpoint("target", "id"),
            cardinality="unknown",
            confidence=0,
            status="validated",
            evidence=(),
            target_filter=None,
            metadata={},
            candidate=True,
        )
        self.assertEqual(validated_relationships([validated, candidate]), [validated])


if __name__ == "__main__":
    unittest.main()
