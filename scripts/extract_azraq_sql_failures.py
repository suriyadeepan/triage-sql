"""Freeze the retrieved-schema SQL failure cohort with its retrieval labels."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def extract_failures(sql_results: dict, labeled_queries: list[dict]) -> list[dict]:
    """Return failed retrieved-schema query labels in source evaluation order."""
    result_queries = sql_results["retrieved_schema"]["queries"]
    failures = {row["id"] for row in result_queries if not row["execution_accuracy"]}
    if len(failures) != len(sql_results["retrieved_schema"]["failures"]):
        raise ValueError("baseline failure list does not match per-query execution results")
    labeled_by_id = {row["id"]: row for row in labeled_queries}
    if len(labeled_by_id) != len(labeled_queries) or not failures <= labeled_by_id.keys():
        raise ValueError("baseline failures do not map uniquely to retrieval labels")
    if len(result_queries) != len(labeled_queries):
        raise ValueError("SQL baseline and labeled query set have different sizes")
    return [labeled_by_id[row["id"]] for row in labeled_queries if row["id"] in failures]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sql-results", type=Path, default=ROOT / "data/evaluation/azraq-sql-prompt-results.json")
    parser.add_argument("--labels", type=Path, default=ROOT / "data/evaluation/azraq-retrieval-labels.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "data/evaluation/azraq-retrieval-failure-labels.jsonl")
    args = parser.parse_args()
    sql_bytes = args.sql_results.read_bytes()
    rows = [json.loads(line) for line in args.labels.read_text(encoding="utf-8").splitlines() if line]
    cohort = extract_failures(json.loads(sql_bytes), rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in cohort), encoding="utf-8")
    print(json.dumps({
        "query_count": len(cohort),
        "query_ids": [row["id"] for row in cohort],
        "baseline_sql_sha256": hashlib.sha256(sql_bytes).hexdigest(),
        "cohort_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "output": str(args.output),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
