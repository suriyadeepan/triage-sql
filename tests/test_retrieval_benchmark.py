import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from triage_sql.retrieval_benchmark import evaluate_rerank, evaluate_retrieval, stratified_rerank_sample


class RetrievalBenchmarkTests(unittest.TestCase):
    def test_rerank_sample_is_deterministic_and_spans_query_tags(self):
        queries = [
            {"id": "exact", "question": "loans by status", "relevant_tables": ["loans"], "relevant_columns": [], "category": "aggregation"},
            {"id": "semantic", "question": "how are these agreements doing", "relevant_tables": ["loans"], "relevant_columns": [], "category": "filter"},
            {"id": "multi", "question": "clients by city", "relevant_tables": ["clients", "cities"], "relevant_columns": [], "category": "multi_table"},
            {"id": "other", "question": "other", "relevant_tables": ["roles"], "relevant_columns": [], "category": "filter"},
        ]
        selected = stratified_rerank_sample(queries, 3)
        self.assertEqual([item["id"] for item in selected], ["exact", "semantic", "multi"])

    def test_metrics_ranked_inspection_and_category_breakdowns(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "manifest.json"
            manifest_path.write_text(json.dumps({"sources": {"dataset_snapshot_id": "snapshot"}}), encoding="utf-8")
            table = {
                "id": "table:loans", "kind": "table", "table": "loans",
                "columns": [{"name": "id", "type": "BIGINT"}],
            }
            edge = {
                "id": "loans.client_id__clients.id", "kind": "relationship",
            }
            class FakeRetriever:
                def __init__(self):
                    self.manifest_path = manifest_path

                def search(self, query, mode, top_k, candidate_k):
                    return [table, edge]

            rows = [{
                "id": "eval-test", "question": "Count loans", "category": "join",
                "relevant_tables": ["loans"], "relevant_columns": ["loans.id"],
                "relevant_relationships": ["loans.client_id__clients.id"],
                "unresolved_relationships": [],
            }]
            result = evaluate_retrieval(FakeRetriever(), rows, top_k=2, candidate_k=2, repeats=1)
            dense = result["modes"]["dense"]
            self.assertEqual(dense["query_count"], 1)
            self.assertEqual(dense["recall_at_k"], 1.0)
            self.assertEqual(dense["mrr"], 1.0)
            self.assertEqual(dense["latency_ms"]["samples"], 1)
            self.assertEqual(dense["by_source_category"]["join"]["query_count"], 1)
            self.assertEqual(dense["by_failure_category"]["exact_identifier"]["query_count"], 1)
            self.assertEqual(dense["failures"], [])

    def test_rerank_metrics_are_separate_and_measure_hybrid_plus_service(self):
        table = {"id": "table:loans", "kind": "table", "table": "loans", "columns": []}
        class FakeRetriever:
            def search(self, query, mode, top_k, candidate_k):
                self.last_mode = mode
                return [table]

        class FakeReranker:
            def rerank(self, query, candidates, top_k):
                return candidates[:top_k]

        queries = [{
            "id": "eval-test", "question": "count these records", "category": "filter",
            "relevant_tables": ["loans"], "relevant_columns": [], "relevant_relationships": [],
        }]
        metrics = evaluate_rerank(FakeRetriever(), queries, FakeReranker(), top_k=1, candidate_k=1)
        self.assertEqual(metrics["recall_at_k"], 1.0)
        self.assertTrue(metrics["latency_ms"]["includes_hybrid_retrieval"])
        self.assertEqual(metrics["latency_ms"]["external_service"], "Cohere Rerank v5 Fast")
        self.assertEqual(metrics["latency_ms"]["service_failures"], 0)
        self.assertEqual(metrics["latency_ms"]["cohere_service_latency_ms"]["samples"], 1)


if __name__ == "__main__":
    unittest.main()
