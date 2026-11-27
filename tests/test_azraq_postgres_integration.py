import csv
import hashlib
import os
import tempfile
import unittest
from pathlib import Path

import psycopg

from scripts.azraq_init import copy_table
from scripts.validate_azraq_relationships_pg import validate_one
from triage_sql.relationships import Endpoint, Relationship, relationship_join_clause
from triage_sql.evaluation import generate, validate_items
from triage_sql.examples import generate_examples, leakage_findings


TEST_DSN = os.environ.get("AZRAQ_TEST_DSN")


@unittest.skipUnless(TEST_DSN, "set AZRAQ_TEST_DSN to run PostgreSQL integration checks")
class PostgreSQLCopyIntegrationTests(unittest.TestCase):
    def test_fixed_snapshot_evaluation_executes_every_item(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "evaluation.jsonl"
            count = generate(TEST_DSN, root / "data/manifest/azraq-postgres.json", output)
            items = [__import__("json").loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            snapshot = __import__("json").loads((root / "data/manifest/azraq-postgres.json").read_text())["dataset_snapshot_id"]
            validate_items(items, snapshot)
            self.assertEqual(count, 120)
            self.assertTrue(all(item["execution"]["status"] == "passed" for item in items))
            self.assertTrue(any(item["category"] == "subtype_join" for item in items))

    def test_generated_examples_are_read_only_validated_and_split_by_pattern(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            count = generate_examples(
                TEST_DSN,
                root / "data/manifest/azraq-postgres.json",
                root / "data/raw/azraq-relationships.yaml",
                output,
            )
            self.assertEqual(count, 48)
            for kind in ("text_to_sql", "sql_correction"):
                partitions = {}
                for split in ("train", "validation", "heldout"):
                    path = output / kind / f"{split}.jsonl"
                    partitions[split] = [__import__("json").loads(line) for line in path.read_text().splitlines()]
                    self.assertTrue(all(row["validation"]["parse"] == "passed" and row["validation"]["execution"] == "passed" for row in partitions[split]))
                    self.assertTrue(all(row["provenance"]["dataset_snapshot_id"] for row in partitions[split]))
                self.assertEqual(leakage_findings(partitions), [])

    def test_users_password_is_null_after_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "users.csv"
            with source.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["id", "username", "password"])
                writer.writerow(["17", "synthetic-user", "SENSITIVE_FIXTURE_VALUE"])

            with psycopg.connect(TEST_DSN) as conn:
                with conn.transaction():
                    conn.execute("CREATE TEMP TABLE users (id BIGINT, username TEXT, password TEXT)")
                    with conn.cursor() as cursor:
                        copy_table(
                            cursor,
                            "users",
                            ["id", "username", "password"],
                            source,
                            1,
                            hashlib.sha256(source.read_bytes()).hexdigest(),
                        )
                    row = conn.execute("SELECT id, username, password IS NULL FROM users").fetchone()
                    self.assertEqual(row, (17, "synthetic-user", True))

    def test_raw_copy_preserves_csv_quoting(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "clients.csv"
            with source.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["id", "name"])
                writer.writerow(["18", "Synthetic, Group"])
            content = source.read_bytes()

            with psycopg.connect(TEST_DSN) as conn:
                with conn.transaction():
                    conn.execute("CREATE TEMP TABLE clients (id BIGINT, name TEXT)")
                    with conn.cursor() as cursor:
                        copy_table(
                            cursor,
                            "clients",
                            ["id", "name"],
                            source,
                            1,
                            hashlib.sha256(content).hexdigest(),
                        )
                    row = conn.execute("SELECT id, name FROM clients").fetchone()
                    self.assertEqual(row, (18, "Synthetic, Group"))

    def test_generated_join_applies_target_subtype_filter(self):
        with psycopg.connect(TEST_DSN) as conn:
            expected = {
                "collaterals.owner_id__clients.id": ("owner_id", None),
                "groups_members.group_id__clients.id": ("group_id", "Group"),
                "groups_members.member_id__clients.id": ("member_id", "Individual"),
                "nsg_meetings.group_id__clients.id": ("group_id", "NSG"),
            }
            for relationship_id, (source_column, subtype) in expected.items():
                relationship = Relationship(
                    id=relationship_id,
                    source=Endpoint(relationship_id.split(".")[0], source_column),
                    target=Endpoint("clients", "id"),
                    cardinality="many_to_one",
                    confidence=1.0,
                    status="validated",
                    evidence=("full_postgresql_validation", "semantic_review"),
                    target_filter=("type", subtype) if subtype else None,
                    metadata={"semantic_review": "Reviewed"},
                )
                source_alias = "src"
                rendered = relationship_join_clause(relationship, source_alias, "client").as_string(conn)
                base = f'JOIN "clients" AS "client" ON "src"."{source_column}" = "client"."id"'
                suffix = f" AND \"client\".\"type\" = '{subtype}'" if subtype else ""
                self.assertEqual(rendered, base + suffix)

    def test_relationship_report_counts_nulls_orphans_duplicates_and_subtypes(self):
        relationship = Relationship(
            id="source_fixture.client_id__target_fixture.id",
            source=Endpoint("source_fixture", "client_id"),
            target=Endpoint("target_fixture", "id"),
            cardinality="many_to_one",
            confidence=1.0,
            status="validated",
            evidence=("full_postgresql_validation", "semantic_review"),
            target_filter=("type", "Group"),
            metadata={"semantic_review": "Reviewed"},
        )
        with psycopg.connect(TEST_DSN) as conn:
            with conn.transaction():
                conn.execute("CREATE TEMP TABLE source_fixture (client_id BIGINT)")
                conn.execute("INSERT INTO source_fixture VALUES (1), (1), (2), (NULL), (3)")
                conn.execute("CREATE TEMP TABLE target_fixture (id BIGINT, type TEXT)")
                conn.execute("INSERT INTO target_fixture VALUES (1, 'Group'), (1, 'Group'), (2, 'Individual')")
                report = validate_one(conn, relationship, "pg_temp")

        self.assertEqual(report["coverage"], "full")
        self.assertEqual(report["source_rows"], 5)
        self.assertEqual(report["source_null_count"], 1)
        self.assertEqual(report["matched_source_rows"], 2)
        self.assertEqual(report["orphan_source_rows"], 1)
        self.assertEqual(report["subtype_mismatch_count"], 1)
        self.assertEqual(report["target_null_count"], 0)
        self.assertEqual(report["target_duplicate_keys"], 1)
        self.assertEqual(report["filtered_target_duplicate_keys"], 1)
        self.assertTrue(report["join_eligible"])


if __name__ == "__main__":
    unittest.main()
