"""Compare retrieved-schema and full-schema SQL generation on Azraq."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from triage_sql.prompt_benchmark import run_prompt_benchmark
from triage_sql.retrieval import DEFAULT_MODEL, SchemaRetriever, SentenceTransformerEncoder
from triage_sql.sql_generation import OpenAIResponsesGenerator
from scripts.azraq_init import DEFAULT_DSN


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=None, help="OpenAI model; defaults to OPENAI_MODEL")
    parser.add_argument("--index-dir", type=Path, default=ROOT / "data/index/azraq-schema")
    parser.add_argument("--output", type=Path, default=ROOT / "data/evaluation/azraq-sql-prompt-results.json")
    parser.add_argument("--top-k", type=int, default=5)
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
        ROOT / "data/evaluation/azraq-evaluation.jsonl", retriever, generator, dsn,
        ROOT / "data/manifest/azraq-postgres.json", args.output, args.top_k,
        args.timeout_ms, args.limit,
    )
    for strategy in ("retrieved_schema", "full_schema"):
        summary = result[strategy]
        print(strategy, "accuracy", summary["sql_execution_accuracy"],
              "mean prompt tokens", summary["prompt_tokens"]["average"],
              "mean end-to-end ms", summary["end_to_end_latency_ms"]["average"])
    print(f"Detailed SQL benchmark: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
