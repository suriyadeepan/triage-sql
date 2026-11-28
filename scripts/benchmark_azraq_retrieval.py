"""Evaluate dense, BM25, and hybrid schema retrieval on fixed Azraq labels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from triage_sql.retrieval import DEFAULT_MODEL, SchemaRetriever, SentenceTransformerEncoder
from triage_sql.retrieval_benchmark import _metrics, evaluate_rerank, run_benchmark, stratified_rerank_sample
from triage_sql.rerank import CohereReranker


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path, default=ROOT / "data/evaluation/azraq-retrieval-labels.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "data/evaluation/azraq-retrieval-results.json")
    parser.add_argument("--index-dir", type=Path, default=ROOT / "data/index/azraq-schema")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--revision")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--candidate-k", type=int, default=20)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--rerank", action="store_true", help="also run the opt-in Cohere rerank evaluation")
    parser.add_argument("--rerank-delay-seconds", type=float, default=6.5)
    parser.add_argument("--rerank-limit", type=int, default=10,
                        help="stratified query count for the rate-limited Cohere trial key; use 120 for full evaluation")
    args = parser.parse_args()

    encoder = SentenceTransformerEncoder(args.model, args.revision, args.device)
    retriever = SchemaRetriever(
        ROOT / "data/raw/azraq-schema.sql",
        ROOT / "data/raw/azraq-relationships.yaml",
        ROOT / "data/raw/azraq.md",
        args.index_dir,
        encoder,
        ROOT / "data/manifest/azraq-postgres.json",
    )
    if retriever.is_stale():
        retriever.build()
    result = run_benchmark(args.labels, retriever, args.output, args.top_k, args.candidate_k, args.repeats)
    if args.rerank:
        labels = [json.loads(line) for line in args.labels.read_text(encoding="utf-8").splitlines()]
        sample = stratified_rerank_sample(labels, min(args.rerank_limit, len(labels)))
        result["modes"]["hybrid-rerank"] = evaluate_rerank(
            retriever, sample, CohereReranker(), args.top_k, args.candidate_k, args.rerank_delay_seconds
        )
        result["modes"]["hybrid-rerank"]["sample_selection"] = {
            "method": "deterministic spread across exact identifier, semantic, and multi-table tags, then source order",
            "requested_count": args.rerank_limit,
            "query_ids": [item["id"] for item in sample],
        }
        baseline_by_id = {
            row["id"]: row for row in result["modes"]["hybrid"]["ranked_results"]
        }
        sample_baseline = [baseline_by_id[item["id"]] for item in sample]
        baseline_metrics = _metrics(sample_baseline)
        result["modes"]["hybrid-rerank"]["hybrid_baseline_same_sample"] = {
            "query_count": len(sample_baseline),
            "recall_at_k": baseline_metrics["overall_recall_at_k"],
            "mrr": baseline_metrics["overall_mrr"],
        }
        args.output.write_text(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({mode: {key: value for key, value in metrics.items() if key not in {"failures", "ranked_results"}}
                      for mode, metrics in result["modes"].items()}, indent=2, sort_keys=True))
    print(f"Ranked results and failures: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
