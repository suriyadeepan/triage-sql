"""Run Phase 1 Luna SQL experiments for each failure-cohort candidate pool."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from triage_sql.prompt_benchmark import run_prompt_benchmark
from triage_sql.rerank import CohereReranker
from triage_sql.retrieval import DEFAULT_MODEL, SchemaRetriever, SentenceTransformerEncoder
from triage_sql.sql_generation import OpenAIResponsesGenerator
from scripts.azraq_init import DEFAULT_DSN


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATES = (20, 30, 40, 53)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-k", type=int, nargs="+", default=list(DEFAULT_CANDIDATES))
    parser.add_argument("--queries", type=Path, default=ROOT / "data/evaluation/azraq-retrieval-failure-labels.jsonl")
    parser.add_argument("--index-dir", type=Path, default=ROOT / "data/index/azraq-schema")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/evaluation/experiments/failure-sql-phase1")
    parser.add_argument("--model", default=None, help="defaults to OPENAI_MODEL")
    parser.add_argument("--delay-seconds", type=float, default=6.5)
    args = parser.parse_args()
    generator = OpenAIResponsesGenerator(args.model)
    if generator.model != "gpt-6-luna" or generator.reasoning_effort != "low":
        raise ValueError("T007 experiments require OPENAI_MODEL=gpt-6-luna and OPENAI_REASONING_EFFORT=low")
    cohort = [json.loads(line) for line in args.queries.read_text(encoding="utf-8").splitlines() if line]
    if len(cohort) != 53:
        raise ValueError(f"expected the frozen 53-query failure cohort, found {len(cohort)}")
    snapshot_path = ROOT / "data/manifest/azraq-postgres.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if snapshot["dataset_snapshot_id"] != "ba058d581b04d1d75f63ac0a4705d98ea0d8ea54dcf577ee90b58222d082dddc":
        raise ValueError("database manifest is not the frozen FS-02 baseline snapshot")
    retriever = SchemaRetriever(
        ROOT / "data/raw/azraq-schema.sql", ROOT / "data/raw/azraq-relationships.yaml",
        ROOT / "data/raw/azraq.md", args.index_dir,
        SentenceTransformerEncoder(DEFAULT_MODEL, device="cpu"), snapshot_path,
    )
    if retriever.is_stale():
        retriever.build()
    manifest = json.loads(retriever.manifest_path.read_text(encoding="utf-8"))
    if manifest["record_count"] != 53:
        raise ValueError(f"expected current index size 53, found {manifest['record_count']}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for candidate_k in args.candidate_k:
        if candidate_k not in (20, 30, 40, 53):
            raise ValueError(f"unexpected Phase 1 candidate_k: {candidate_k}")
        output_path = args.output_dir / f"candidate-k-{candidate_k}-top-k-5.json"
        result = run_prompt_benchmark(
            args.queries, retriever, generator, os.environ.get("DATABASE_URL", DEFAULT_DSN),
            snapshot_path, output_path, top_k=5, candidate_k=candidate_k,
            reranker=CohereReranker(), rerank_delay_seconds=args.delay_seconds,
            include_full_schema=False,
        )
        result.update({
            "experiment": "phase1-candidate-pool-luna-sql",
            "candidate_k_requested": candidate_k,
            "candidate_k_effective": min(candidate_k, manifest["record_count"]),
            "source_evaluation_query_set_sha256": hashlib.sha256((ROOT / "data/evaluation/azraq-evaluation.jsonl").read_bytes()).hexdigest(),
            "cohort_sha256": hashlib.sha256(args.queries.read_bytes()).hexdigest(),
            "baseline_sql_results_sha256": hashlib.sha256((ROOT / "data/evaluation/azraq-sql-prompt-results.json").read_bytes()).hexdigest(),
            "baseline_retrieval_results_sha256": hashlib.sha256((ROOT / "data/evaluation/azraq-retrieval-results.json").read_bytes()).hexdigest(),
            "index_record_count": manifest["record_count"],
        })
        output_path.write_text(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        summary = result["retrieved_schema"]
        print(json.dumps({
            "candidate_k": candidate_k,
            "sql_execution_accuracy": summary["sql_execution_accuracy"],
            "mean_input_tokens": summary["prompt_tokens"]["average"],
            "mean_end_to_end_latency_ms": summary["end_to_end_latency_ms"]["average"],
            "recall_at_5": result["retrieval_metrics"]["recall_at_5"],
            "mrr": result["retrieval_metrics"]["mrr"],
            "cohere_latency_ms": summary["cohere_latency_ms"],
            "output": str(output_path),
        }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
