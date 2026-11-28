"""Guards and Luna-low comparators for the frozen FS-03 input set."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


FROZEN_SHA256 = {
    "sql_baseline": "ee7beb0a1229fe8fad1985d1f37591054eb0feac082b7e2c2f7c72dffb6e09e1",
    "retrieval_baseline": "f4eaa6a81b951380c38f8c42eae29ccd25bdd0ea3fbb631d9692ca3a37cfe776",
    "cohort": "150579fb833e209c6b66f1c7d4eca579116b5d6644514b4e8cce6c69f855f764",
    "query_set": "1cbe40d2d027a28d32fd39e91807e6427c6fad10d8a338a488b60bc7703dc87a",
    "index_manifest": "e3e9c32aa1b62321e7dc3664061945e37bc3ffcad04b1fd1b33bad64586ce92b",
}
FROZEN_SNAPSHOT_ID = "ba058d581b04d1d75f63ac0a4705d98ea0d8ea54dcf577ee90b58222d082dddc"
FROZEN_MODEL = "gpt-6-luna"
FROZEN_REASONING_EFFORT = "low"
COHORT_SIZE = 53
BASELINE_QUERY_COUNT = 120


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _verified_hash(path: Path, expected: str, label: str) -> str:
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(f"frozen {label} SHA256 mismatch: expected {expected}, found {actual}")
    return actual


def verify_frozen_inputs(root: Path) -> dict[str, Any]:
    """Fail closed unless all FS-03 baseline identities and cohort members match."""
    evaluation_dir = root / "data/evaluation"
    paths = {
        "sql_baseline": evaluation_dir / "azraq-sql-prompt-results.json",
        "retrieval_baseline": evaluation_dir / "azraq-retrieval-results.json",
        "cohort": evaluation_dir / "azraq-retrieval-failure-labels.jsonl",
        "query_set": evaluation_dir / "azraq-evaluation.jsonl",
        "index_manifest": root / "data/index/azraq-schema/manifest.json",
    }
    identities = {
        name: _verified_hash(path, FROZEN_SHA256[name], name.replace("_", " "))
        for name, path in paths.items()
    }

    baseline = json.loads(paths["sql_baseline"].read_text(encoding="utf-8"))
    cohort = _jsonl(paths["cohort"])
    queries = _jsonl(paths["query_set"])
    manifest = json.loads(paths["index_manifest"].read_text(encoding="utf-8"))
    snapshot_path = root / "data/manifest/azraq-postgres.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))

    if len(cohort) != COHORT_SIZE or len({item["id"] for item in cohort}) != COHORT_SIZE:
        raise ValueError(f"frozen failure cohort must contain {COHORT_SIZE} unique queries")
    if len(queries) != BASELINE_QUERY_COUNT or len({item["id"] for item in queries}) != BASELINE_QUERY_COUNT:
        raise ValueError(f"frozen baseline query set must contain {BASELINE_QUERY_COUNT} unique queries")
    if len(baseline["retrieved_schema"]["queries"]) != BASELINE_QUERY_COUNT:
        raise ValueError("SQL baseline must contain all 120 retrieved-schema results")
    if len(baseline["full_schema"]["queries"]) != BASELINE_QUERY_COUNT:
        raise ValueError("SQL baseline must contain all 120 full-schema results")
    if baseline.get("dataset_snapshot_id") != FROZEN_SNAPSHOT_ID or snapshot.get("dataset_snapshot_id") != FROZEN_SNAPSHOT_ID:
        raise ValueError("SQL baseline or database manifest is not bound to the frozen snapshot")
    if baseline.get("generator_model") != FROZEN_MODEL or baseline.get("generator_reasoning_effort") != FROZEN_REASONING_EFFORT:
        raise ValueError("SQL baseline model/effort differs from the frozen Luna-low comparison")
    if baseline.get("top_k") != 5:
        raise ValueError("SQL baseline top_k differs from the frozen value 5")
    if manifest.get("record_count") != 53 or manifest.get("table_count") != 26 or manifest.get("relationship_count") != 27:
        raise ValueError("schema index manifest must contain 26 tables and 27 validated relationships")
    if manifest.get("sources", {}).get("dataset_snapshot_id") != FROZEN_SNAPSHOT_ID:
        raise ValueError("schema index manifest is not bound to the frozen snapshot")
    if snapshot.get("table_count") != 26:
        raise ValueError("database manifest must represent all 26 tables")

    expected_ids = [item["id"] for item in cohort]
    baseline_rows = baseline["retrieved_schema"]["queries"]
    failed_rows = [item for item in baseline_rows if not item.get("execution_accuracy")]
    failure_ids = [item["id"] for item in failed_rows]
    if failure_ids != expected_ids:
        raise ValueError("failure cohort IDs/order do not match the Luna-low retrieved-schema failures")
    summary_ids = [item["id"] for item in baseline["retrieved_schema"].get("failures", [])]
    if summary_ids != expected_ids:
        raise ValueError("baseline failure summary does not match per-query failures and frozen cohort")

    identities["snapshot_id"] = FROZEN_SNAPSHOT_ID
    identities["cohort_ids"] = expected_ids
    return identities


def pair_luna_low_baseline(cohort: list[dict], sql_results: dict) -> dict[str, dict[str, Any]]:
    """Pair every frozen query with its existing retrieved and full-schema outcomes."""
    cohort_ids = [item["id"] for item in cohort]
    if len(cohort_ids) != COHORT_SIZE or len(set(cohort_ids)) != COHORT_SIZE:
        raise ValueError(f"comparison requires {COHORT_SIZE} unique frozen cohort queries")

    paired: dict[str, dict[str, Any]] = {}
    for condition in ("retrieved_schema", "full_schema"):
        rows = sql_results.get(condition, {}).get("queries", [])
        by_id = {row["id"]: row for row in rows}
        if len(by_id) != len(rows):
            raise ValueError(f"{condition} baseline contains duplicate query IDs")
        missing = set(cohort_ids) - by_id.keys()
        if missing:
            raise ValueError(f"{condition} baseline misses frozen cohort IDs: {sorted(missing)}")
        for query_id in cohort_ids:
            paired.setdefault(query_id, {})[condition] = by_id[query_id]

    retrieved_successes = sum(row["retrieved_schema"]["execution_accuracy"] for row in paired.values())
    full_successes = sum(row["full_schema"]["execution_accuracy"] for row in paired.values())
    if (retrieved_successes, full_successes) != (0, 19):
        raise ValueError(
            "frozen Luna-low cohort comparison must be 0/53 retrieved and 19/53 full-schema successes"
        )
    return paired
