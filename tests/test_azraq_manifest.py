import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.azraq_manifest import build_manifest


class AzraqManifestTests(unittest.TestCase):
    def test_manifest_tracks_schema_rows_and_hashes_without_source_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "azraq"
            data.mkdir()
            (data / "clients.csv").write_text(
                "id,type,password\n1,Individual,DO_NOT_EMIT\n", encoding="utf-8"
            )
            schema = root / "schema.sql"
            schema.write_text(
                "CREATE TABLE clients (\n id BIGINT,\n type TEXT,\n password TEXT\n);\n",
                encoding="utf-8",
            )
            relationships = root / "relationships.yaml"
            relationships.write_text("relationships: []\n", encoding="utf-8")

            manifest = build_manifest(data, schema, relationships)
            rendered = json.dumps(manifest)

        self.assertEqual(manifest["ddl_table_count"], 1)
        self.assertEqual(manifest["csv_table_count"], 1)
        self.assertEqual(manifest["tables"]["clients"]["row_count"], 1)
        self.assertEqual(manifest["tables"]["clients"]["missing_columns"], [])
        self.assertEqual(manifest["tables"]["clients"]["extra_columns"], [])
        self.assertNotIn("DO_NOT_EMIT", rendered)

    def test_manifest_reports_header_and_record_width_mismatches(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "azraq"
            data.mkdir()
            (data / "clients.csv").write_text(
                "id,type,extra\n1,Individual,extra,overflow\n", encoding="utf-8"
            )
            schema = root / "schema.sql"
            schema.write_text("CREATE TABLE clients (\n id BIGINT,\n type TEXT,\n);\n", encoding="utf-8")
            relationships = root / "relationships.yaml"
            relationships.write_text("relationships: []\n", encoding="utf-8")

            manifest = build_manifest(data, schema, relationships)

        table = manifest["tables"]["clients"]
        self.assertEqual(table["extra_columns"], ["extra"])
        self.assertEqual(table["malformed_record_count"], 1)
        self.assertEqual(manifest["errors"], ["clients: 1 record(s) have the wrong number of columns"])

    def test_relationship_metadata_version_does_not_change_database_snapshot_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data = root / "azraq"
            data.mkdir()
            (data / "clients.csv").write_text("id\n1\n", encoding="utf-8")
            schema = root / "schema.sql"
            schema.write_text("CREATE TABLE clients (\n id BIGINT\n);\n", encoding="utf-8")
            relationships = root / "relationships.yaml"
            relationships.write_text("relationships: []\n", encoding="utf-8")

            first = build_manifest(data, schema, relationships)
            relationships.write_text("relationships: []\n# reviewed\n", encoding="utf-8")
            second = build_manifest(data, schema, relationships)

        self.assertEqual(first["dataset_snapshot_id"], second["dataset_snapshot_id"])
        self.assertNotEqual(first["relationships"]["sha256"], second["relationships"]["sha256"])


if __name__ == "__main__":
    unittest.main()
