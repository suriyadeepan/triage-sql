"""Create table, column, and validated-edge labels for Azraq retrieval evaluation."""

from __future__ import annotations

import argparse
from pathlib import Path

from triage_sql.retrieval_eval import write_labels


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation", type=Path, default=ROOT / "data/evaluation/azraq-evaluation.jsonl")
    parser.add_argument("--schema", type=Path, default=ROOT / "data/raw/azraq-schema.sql")
    parser.add_argument("--relationships", type=Path, default=ROOT / "data/raw/azraq-relationships.yaml")
    parser.add_argument("--output", type=Path, default=ROOT / "data/evaluation/azraq-retrieval-labels.jsonl")
    args = parser.parse_args()
    count = write_labels(args.evaluation, args.schema, args.relationships, args.output)
    print(f"Wrote labels for {count} evaluation queries to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
