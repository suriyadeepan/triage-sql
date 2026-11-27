import csv
import tempfile
import unittest
from pathlib import Path

from scripts.azraq_init import ddl_statements, schema_name, validate_manifest
from scripts.azraq_manifest import build_manifest


class AzraqInitializerTests(unittest.TestCase):
    def test_snapshot_schema_name_is_stable_and_validated(self):
        snapshot = "a" * 64
        self.assertEqual(schema_name(snapshot), "azraq_aaaaaaaaaaaaaaaa")
        with self.assertRaises(ValueError):
            schema_name("not-a-hash")

    def test_manifest_and_ddl_validate_without_reading_source_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "azraq"
            data.mkdir()
            with (data / "clients.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["id", "type"])
                writer.writerow(["1", "Individual"])
            schema = root / "schema.sql"
            schema.write_text("CREATE TABLE clients (\n id BIGINT,\n type TEXT\n);\n", encoding="utf-8")
            relationships = root / "relationships.yaml"
            relationships.write_text("relationships: []\n", encoding="utf-8")

            manifest = build_manifest(data, schema, relationships)
            parsed, snapshot = validate_manifest(manifest, data, schema, relationships)
            statements = ddl_statements(schema)

        self.assertEqual(set(parsed), {"clients"})
        self.assertEqual(snapshot, manifest["dataset_snapshot_id"])
        self.assertEqual(len(statements), 1)

    def test_source_ddl_constraints_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "azraq"
            data.mkdir()
            (data / "clients.csv").write_text("id\n1\n", encoding="utf-8")
            schema = root / "schema.sql"
            schema.write_text("CREATE TABLE clients (\n id BIGINT PRIMARY KEY\n);\n", encoding="utf-8")
            relationships = root / "relationships.yaml"
            relationships.write_text("relationships: []\n", encoding="utf-8")
            manifest = build_manifest(data, schema, relationships)

            with self.assertRaisesRegex(ValueError, "must not declare PK/FK"):
                validate_manifest(manifest, data, schema, relationships)


if __name__ == "__main__":
    unittest.main()
