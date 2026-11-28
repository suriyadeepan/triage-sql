import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace

from triage_sql.retrieval import SchemaRetriever, StaleIndexError, reciprocal_rank_fusion
from triage_sql.rerank import COHERE_RERANK_MODEL, CohereReranker


ROOT = Path(__file__).resolve().parents[1]


class FakeEncoder:
    model_name = "test/hash-encoder"
    revision = "1"

    def encode(self, texts):
        vectors = []
        for text in texts:
            raw = hashlib.sha256(text.encode()).digest()
            vectors.append([float(byte) / 255 for byte in raw[:16]])
        return vectors


class FakeCohereClient:
    def __init__(self):
        self.request = None

    def rerank(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(
            results=[SimpleNamespace(index=1), SimpleNamespace(index=0)],
            meta=SimpleNamespace(
                billed_units=SimpleNamespace(input_tokens=500, output_tokens=None, search_units=1.0)
            ),
        )


class RetrievalIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.ddl = self.root / "schema.sql"
        self.rels = self.root / "relationships.yaml"
        self.notes = self.root / "notes.md"
        self.snapshot = self.root / "snapshot.json"
        self.ddl.write_bytes((ROOT / "data/raw/azraq-schema.sql").read_bytes())
        self.rels.write_bytes((ROOT / "data/raw/azraq-relationships.yaml").read_bytes())
        self.notes.write_bytes((ROOT / "data/raw/azraq.md").read_bytes())
        self.snapshot.write_text(json.dumps({"dataset_snapshot_id": "snapshot-test"}), encoding="utf-8")
        self.retriever = SchemaRetriever(
            self.ddl, self.rels, self.notes, self.root / "index", FakeEncoder(), self.snapshot
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_build_persists_manifest_and_independent_modes(self):
        manifest = self.retriever.build()
        self.assertEqual(manifest["table_count"], 26)
        self.assertEqual(manifest["relationship_count"], 27)
        self.assertFalse(self.retriever.is_stale())

        dense = self.retriever.search("groups_members group client type", mode="dense", top_k=3)
        lexical = self.retriever.search("groups_members.group_id clients.id", mode="bm25", top_k=3)
        hybrid = self.retriever.search("groups_members.group_id clients.id", mode="hybrid", top_k=3)
        self.assertEqual(len(dense), 3)
        self.assertEqual(lexical[0]["id"], "groups_members.group_id__clients.id")
        self.assertEqual(len(hybrid), 3)
        self.assertTrue(all("kind" in item for item in hybrid))

    def test_rrf_rewards_consensus_rank_and_is_stable(self):
        rankings = [["a", "b", "c"], ["a", "b", "d"]]
        self.assertEqual(reciprocal_rank_fusion(rankings, 3), ["a", "b", "c"])
        self.assertEqual(reciprocal_rank_fusion(rankings, 3), reciprocal_rank_fusion(rankings, 3))

    def test_stale_sources_are_detected_and_rebuild_is_repeatable(self):
        first = self.retriever.build()
        second = self.retriever.build()
        self.assertEqual(first, second)
        self.rels.write_text(self.rels.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        self.assertTrue(self.retriever.is_stale())
        with self.assertRaises(StaleIndexError):
            self.retriever.search("loans", mode="bm25")

    def test_manifest_records_all_source_and_encoder_identities(self):
        self.retriever.build()
        manifest = json.loads(self.retriever.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(set(manifest["sources"]), {
            "schema_sha256", "relationships_sha256", "observations_sha256",
            "dataset_snapshot_id", "snapshot_manifest_sha256", "record_format_version",
            "encoder", "runtime", "libraries",
        })
        self.assertEqual(manifest["sources"]["dataset_snapshot_id"], "snapshot-test")
        self.assertEqual(manifest["sources"]["encoder"], {"model": "test/hash-encoder", "revision": "1"})

    def test_reranking_is_opt_in_and_orders_existing_records(self):
        self.retriever.build()
        with self.assertRaisesRegex(ValueError, "requires explicit"):
            self.retriever.search("loans", mode="hybrid-rerank", top_k=2)
        records = self.retriever.search("loans", mode="hybrid", top_k=2, candidate_k=4)
        client = FakeCohereClient()
        reranker = CohereReranker(client=client)
        ranked = reranker.rerank("loans", records, 2)
        self.assertEqual(ranked, [records[1], records[0]])
        self.assertEqual(client.request["model"], COHERE_RERANK_MODEL)
        self.assertEqual(client.request["top_n"], 2)
        self.assertEqual(reranker.last_usage, {
            "billed_input_tokens": 500,
            "billed_output_tokens": None,
            "search_units": 1.0,
        })

    def test_cohere_adapter_loads_dotenv_without_overriding_environment(self):
        with patch("triage_sql.rerank.find_dotenv", return_value="test.env") as find, patch(
            "triage_sql.rerank.load_dotenv"
        ) as load:
            CohereReranker(client=object())
        find.assert_called_once_with(usecwd=True)
        load.assert_called_once_with("test.env", override=False)


if __name__ == "__main__":
    unittest.main()
