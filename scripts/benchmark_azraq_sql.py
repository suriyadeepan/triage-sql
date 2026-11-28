"""Compare retrieved-schema and full-schema SQL generation on Azraq."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from triage_sql.prompt_benchmark import run_prompt_benchmark
from triage_sql.retrieval import DEFAULT_MODEL, SchemaRetriever, SentenceTransformerEncoder
from triage_sql.sql_generation import OpenAIResponsesGenerator
from triage_sql.rerank import CohereReranker
from scripts.azraq_init import DEFAULT_DSN


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=None, help="OpenAI model; defaults to OPENAI_MODEL")
    parser.add_argument("--index-dir", type=Path, default=ROOT / "data/index/azraq-schema")
    parser.add_argument("--output", type=Path, default=ROOT / "data/evaluation/azraq-sql-prompt-results.json")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--candidate-k", type=int, default=20)
    parser.add_argument("--queries", type=Path, default=ROOT / "data/evaluation/azraq-evaluation.jsonl",
                        help="query JSONL; use frozen failure labels for focused experiments")
    parser.add_argument("--rerank", action="store_true", help="apply optional Cohere reranking")
    parser.add_argument("--rerank-delay-seconds", type=float, default=6.5)
    parser.add_argument("--retrieved-only", action="store_true", help="skip full-schema generation strategy")
    parser.add_argument("--timeout-ms", type=int, default=15000)
    parser.add_argument("--limit", type=int, help="small smoke run; omit to process all 120 queries")
    args = parser.parse_args()
    dsn = os.environ.get("DATABASE_URL", DEFAULT_DSN)
    generator = OpenAIResponsesGenerator(args.model)
    encoder = SentenceTransformerEncoder(DEFAULT_MODEL, device="cpu")
    retriever = SchemaRetriever(
        ROOT / "data/raw/azraq-schema.sql",
        ROOT / "data/raw/azraq-relationships.yaml",
        ROOT / "data/raw/azraq.md",
        args.index_dir,
        encoder,
        ROOT / "data/manifest/azraq-postgres.json",
    )
    retriever.ensure_fresh()
    result = run_prompt_benchmark(
        args.queries, retriever, generator, dsn,
        ROOT / "data/manifest/azraq-postgres.json", args.output, args.top_k,
        args.candidate_k, CohereReranker() if args.rerank else None,
        args.rerank_delay_seconds, args.timeout_ms, args.limit,
        not args.retrieved_only,
    )
    for strategy in ("retrieved_schema", "full_schema"):
        if strategy not in result:
            continue
        summary = result[strategy]
        print(strategy, "accuracy", summary["sql_execution_accuracy"],
              "mean prompt tokens", summary["prompt_tokens"]["average"],
              "mean end-to-end ms", summary["end_to_end_latency_ms"]["average"])
    print(f"Detailed SQL benchmark: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
