"""Build and query the local Azraq schema retrieval index."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from triage_sql.rerank import CohereReranker
from triage_sql.retrieval import DEFAULT_MODEL, SchemaRetriever, SentenceTransformerEncoder


ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "query"))
    parser.add_argument("query", nargs="?", help="natural-language schema query (query command)")
    parser.add_argument("--mode", choices=("dense", "bm25", "hybrid", "hybrid-rerank"), default="hybrid")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--candidate-k", type=int, default=20)
    parser.add_argument("--index-dir", type=Path, default=ROOT / "data/index/azraq-schema")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--revision", help="Hugging Face model revision; resolved revision is recorded")
    parser.add_argument("--device", help="PyTorch device, such as cpu or mps")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "query" and not args.query:
        raise SystemExit("query command requires a question")
    encoder = SentenceTransformerEncoder(args.model, args.revision, args.device)
    retriever = SchemaRetriever(
        ROOT / "data/raw/azraq-schema.sql",
        ROOT / "data/raw/azraq-relationships.yaml",
        ROOT / "data/raw/azraq.md",
        args.index_dir,
        encoder,
        ROOT / "data/manifest/azraq-postgres.json",
    )
    if args.command == "build":
        print(json.dumps(retriever.build(), indent=2, sort_keys=True))
        return 0
    reranker = CohereReranker() if args.mode == "hybrid-rerank" else None
    records = retriever.search(args.query, args.mode, args.top_k, args.candidate_k, reranker)
    print(json.dumps(records, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
