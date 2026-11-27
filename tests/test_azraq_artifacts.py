import json
import re
import unittest
from pathlib import Path

import yaml

from scripts.azraq_manifest import parse_schema
from triage_sql.examples import leakage_findings

ROOT = Path(__file__).resolve().parents[1]


class AzraqVersionedArtifactTests(unittest.TestCase):
    def test_manifest_covers_all_26_ddl_tables_and_columns_without_constraints(self):
        schema_path = ROOT / "data/raw/azraq-schema.sql"
        schema = parse_schema(schema_path)
        manifest = json.loads((ROOT / "data/manifest/azraq-snapshot.json").read_text())
        self.assertEqual(len(schema), 26)
        self.assertEqual(set(schema), set(manifest["tables"]))
        for table, columns in schema.items():
            self.assertEqual([column["name"] for column in columns], manifest["tables"][table]["columns"])
        ddl = re.sub(r"(?m)^\s*--.*$", "", schema_path.read_text())
        self.assertIsNone(re.search(r"\b(PRIMARY\s+KEY|FOREIGN\s+KEY|REFERENCES)\b", ddl, re.I))

    def test_evaluation_and_training_artifacts_are_snapshot_bound_and_safe(self):
        snapshot = json.loads((ROOT / "data/manifest/azraq-postgres.json").read_text())["dataset_snapshot_id"]
        evaluation = [json.loads(line) for line in (ROOT / "data/evaluation/azraq-evaluation.jsonl").read_text().splitlines()]
        self.assertGreaterEqual(len(evaluation), 100)
        self.assertLessEqual(len(evaluation), 200)
        for item in evaluation:
            self.assertEqual(item["dataset_snapshot_id"], snapshot)
            self.assertEqual(item["status"], "supported")
            self.assertEqual(item["execution"]["status"], "passed")

        document = yaml.safe_load((ROOT / "data/raw/azraq-relationships.yaml").read_text())
        eligible = {edge["id"] for edge in document["relationships"] if edge["status"] == "validated"}
        all_content = []
        for corpus in ("text_to_sql", "sql_correction"):
            partitions = {}
            for split in ("train", "validation", "heldout"):
                items = [json.loads(line) for line in (ROOT / "data/examples/azraq" / corpus / f"{split}.jsonl").read_text().splitlines()]
                partitions[split] = items
                for item in items:
                    self.assertEqual(item["split"], split)
                    self.assertEqual(item["validation"]["execution"], "passed")
                    self.assertEqual(item["provenance"]["dataset_snapshot_id"], snapshot)
                    self.assertTrue(set(item["provenance"]["validated_relationships"]) <= eligible)
                all_content.extend(json.dumps(item) for item in items)
            self.assertEqual(leakage_findings(partitions), [])
        self.assertNotRegex("\n".join(all_content + [json.dumps(item) for item in evaluation]), r"\bpassword\b")


if __name__ == "__main__":
    unittest.main()
