"""Offline metrics and ranked-result inspection for schema retrieval."""

from __future__ import annotations

import json
import math
import re
import statistics
import time
from collections import defaultdict
from pathlib import Path

from triage_sql.retrieval import SchemaRetriever
from triage_sql.rerank import CohereReranker


MODES = ("dense", "bm25", "hybrid")


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def _query_tags(item: dict) -> list[str]:
    question = item["question"].casefold()
    identifiers = set(item.get("relevant_tables", []))
    identifiers.update(value.split(".", 1)[-1] for value in item.get("relevant_columns", []))
    exact = any(re.search(rf"(?<![a-z0-9_]){re.escape(value)}(?![a-z0-9_])", question) for value in identifiers)
    tags = []
    if exact:
        tags.append("exact_identifier")
    if len(item.get("relevant_tables", [])) > 1:
        tags.append("multi_table")
    if not exact and len(item.get("relevant_tables", [])) <= 1:
        tags.append("semantic")
    return tags


def stratified_rerank_sample(items: list[dict], limit: int) -> list[dict]:
    """Select a deterministic, category-spread sample across exact/semantic/join queries."""
    if limit < 1:
        raise ValueError("sample limit must be positive")
    selected: list[dict] = []
    seen: set[str] = set()
    quotas = {"exact_identifier": limit // 3, "semantic": limit // 3}
    quotas["multi_table"] = limit - sum(quotas.values())
    for tag, quota in quotas.items():
        categories = sorted({item.get("category", "unknown") for item in items if tag in _query_tags(item)})
        while quota:
            progressed = False
            for category in categories:
                candidate = next((item for item in items
                                  if item.get("category", "unknown") == category
                                  and tag in _query_tags(item) and item["id"] not in seen), None)
                if candidate is not None:
                    selected.append(candidate)
                    seen.add(candidate["id"])
                    quota -= 1
                    progressed = True
                    if quota == 0:
                        break
            if not progressed:
                break
    for item in items:
        if len(selected) >= limit:
            break
        if item["id"] not in seen:
            selected.append(item)
            seen.add(item["id"])
    return selected[:limit]


def _relevant_for_record(record: dict, labels: dict) -> dict[str, set[str]]:
    result = {"tables": set(), "columns": set(), "relationships": set()}
    if record["kind"] == "table":
        if record["table"] in labels["relevant_tables"]:
            result["tables"].add(record["table"])
        available = {f"{record['table']}.{column['name']}" for column in record["columns"]}
        result["columns"].update(available & set(labels["relevant_columns"]))
    elif record["kind"] == "relationship" and record["id"] in labels["relevant_relationships"]:
        result["relationships"].add(record["id"])
    return result


def _metrics(rows: list[dict], category: str | None = None, source_category: bool = False) -> dict:
    selected = [
        row for row in rows
        if category is None or (row["category"] == category if source_category else category in row["tags"])
    ]
    result: dict[str, float | int] = {"query_count": len(selected)}
    if not selected:
        return result
    groups = {
        "tables": "relevant_tables",
        "columns": "relevant_columns",
        "relationships": "relevant_relationships",
    }
    for label_type, key in groups.items():
        recalls = []
        reciprocal_ranks = []
        for row in selected:
            gold = set(row["labels"][key])
            retrieved_rank = None
            hits: set[str] = set()
            for rank, record in enumerate(row["ranked_records"], start=1):
                matched = _relevant_for_record(record, row["labels"])[label_type]
                hits.update(matched)
                if retrieved_rank is None and matched:
                    retrieved_rank = rank
            recalls.append(len(hits & gold) / len(gold) if gold else 0.0)
            reciprocal_ranks.append(1.0 / retrieved_rank if retrieved_rank else 0.0)
        result[f"{label_type}_recall_at_k"] = statistics.mean(recalls)
        result[f"{label_type}_mrr"] = statistics.mean(reciprocal_ranks)

    all_recalls = []
    all_rr = []
    for row in selected:
        gold = set(row["labels"]["relevant_tables"])
        gold.update(row["labels"]["relevant_columns"])
        gold.update(row["labels"]["relevant_relationships"])
        seen: set[str] = set()
        first_rank = None
        for rank, record in enumerate(row["ranked_records"], start=1):
            matches = _relevant_for_record(record, row["labels"])
            matched = matches["tables"] | matches["columns"] | matches["relationships"]
            seen.update(matched)
            if first_rank is None and matched:
                first_rank = rank
        all_recalls.append(len(seen & gold) / len(gold) if gold else 0.0)
        all_rr.append(1 / first_rank if first_rank else 0.0)
    result["overall_recall_at_k"] = statistics.mean(all_recalls)
    result["overall_mrr"] = statistics.mean(all_rr)
    result["failure_count"] = sum(value == 0 for value in all_rr)
    return result


def evaluate_retrieval(
    retriever: SchemaRetriever,
    labeled_queries: list[dict],
    top_k: int = 5,
    candidate_k: int = 20,
    repeats: int = 3,
) -> dict:
    if top_k < 1 or candidate_k < top_k or repeats < 1:
        raise ValueError("top_k, candidate_k, and repeats must be positive and candidate_k >= top_k")
    output = {
        "index_manifest": json.loads(retriever.manifest_path.read_text(encoding="utf-8")),
        "query_count": len(labeled_queries),
        "top_k": top_k,
        "candidate_k": candidate_k,
        "repeats": repeats,
        "modes": {},
    }
    for mode in MODES:
        measured: list[float] = []
        query_results = []
        for item in labeled_queries:
            # One warm-up per query/mode, excluded from latency statistics.
            ranked_records = retriever.search(item["question"], mode, top_k, candidate_k)
            durations = []
            for _ in range(repeats):
                start = time.perf_counter()
                ranked_records = retriever.search(item["question"], mode, top_k, candidate_k)
                durations.append((time.perf_counter() - start) * 1000)
            measured.extend(durations)
            query_results.append({
                "id": item["id"],
                "question": item["question"],
                "category": item.get("category"),
                "tags": _query_tags(item),
                "labels": {
                    "relevant_tables": item.get("relevant_tables", []),
                    "relevant_columns": item.get("relevant_columns", []),
                    "relevant_relationships": item.get("relevant_relationships", []),
                    "unresolved_relationships": item.get("unresolved_relationships", []),
                },
                "ranked_ids": [record["id"] for record in ranked_records],
                "ranked_records": ranked_records,
                "latency_ms": durations,
            })
        metrics = _metrics(query_results)
        metrics["recall_at_k"] = metrics.pop("overall_recall_at_k")
        metrics["mrr"] = metrics.pop("overall_mrr")
        metrics["latency_ms"] = {
            "average": statistics.mean(measured),
            "p50": _percentile(measured, 0.50),
            "p95": _percentile(measured, 0.95),
            "samples": len(measured),
        }
        metrics["by_source_category"] = {
            category: _metrics(query_results, category, source_category=True)
            for category in sorted({item.get("category", "unknown") for item in query_results})
        }
        metrics["by_failure_category"] = {
            category: _metrics(query_results, category)
            for category in ("exact_identifier", "semantic", "multi_table")
        }
        misses = []
        for row in query_results:
            retrieved = {record["id"] for record in row["ranked_records"]}
            missing_tables = sorted(set(row["labels"]["relevant_tables"]) - {item.removeprefix("table:") for item in retrieved if item.startswith("table:")})
            returned_columns = {
                f"{record['table']}.{column['name']}"
                for record in row["ranked_records"] if record["kind"] == "table"
                for column in record["columns"]
            }
            missing_columns = sorted(set(row["labels"]["relevant_columns"]) - returned_columns)
            missing_relationships = sorted(set(row["labels"]["relevant_relationships"]) - retrieved)
            if missing_tables or missing_columns or missing_relationships:
                misses.append({
                    "id": row["id"], "category": row["category"], "tags": row["tags"],
                    "missing_tables": missing_tables,
                    "missing_columns": missing_columns,
                    "missing_relationships": missing_relationships,
                    "ranked_ids": row["ranked_ids"],
                })
        metrics["failures"] = misses
        metrics["ranked_results"] = query_results
        output["modes"][mode] = metrics
    return output


def run_benchmark(labels_path: Path, retriever: SchemaRetriever, output_path: Path, top_k: int = 5,
                  candidate_k: int = 20, repeats: int = 3) -> dict:
    labeled = [json.loads(line) for line in labels_path.read_text(encoding="utf-8").splitlines()]
    result = evaluate_retrieval(retriever, labeled, top_k, candidate_k, repeats)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def evaluate_rerank(retriever: SchemaRetriever, labeled_queries: list[dict], reranker: CohereReranker,
                    top_k: int = 5, candidate_k: int = 20, delay_seconds: float = 6.5) -> dict:
    """Measure hybrid retrieval plus one Cohere request per evaluation query."""
    if top_k < 1 or candidate_k < top_k or delay_seconds < 0:
        raise ValueError("candidate_k must be at least top_k and top_k must be positive")
    rows = []
    durations = []
    service_durations = []
    for index, item in enumerate(labeled_queries):
        start = time.perf_counter()
        candidates = retriever.search(item["question"], "hybrid", candidate_k, candidate_k)
        service_start = time.perf_counter()
        service_error = None
        try:
            ranked_records = reranker.rerank(item["question"], candidates, top_k)
        except Exception as exc:
            ranked_records = []
            service_error = type(exc).__name__
        service_ms = (time.perf_counter() - service_start) * 1000
        service_durations.append(service_ms)
        durations.append((time.perf_counter() - start) * 1000)
        rows.append({
            "id": item["id"], "question": item["question"], "category": item.get("category"),
            "tags": _query_tags(item),
            "labels": {key: item.get(key, []) for key in (
                "relevant_tables", "relevant_columns", "relevant_relationships", "unresolved_relationships"
            )},
            "ranked_ids": [record["id"] for record in ranked_records],
            "ranked_records": ranked_records,
            "latency_ms": durations[-1],
            "service_error": service_error,
            "cohere_latency_ms": service_ms,
        })
        if delay_seconds > 0 and index + 1 < len(labeled_queries):
            time.sleep(delay_seconds)
    metrics = _metrics(rows)
    metrics["recall_at_k"] = metrics.pop("overall_recall_at_k")
    metrics["mrr"] = metrics.pop("overall_mrr")
    metrics["latency_ms"] = {
        "average": statistics.mean(durations), "p50": _percentile(durations, 0.50),
        "p95": _percentile(durations, 0.95), "samples": len(durations),
        "includes_hybrid_retrieval": True, "external_service": "Cohere Rerank v5 Fast",
        "service_failures": sum(row["service_error"] is not None for row in rows),
        "cohere_service_latency_ms": {
            "average": statistics.mean(service_durations), "p50": _percentile(service_durations, 0.50),
            "p95": _percentile(service_durations, 0.95), "samples": len(service_durations),
        },
    }
    metrics["by_source_category"] = {
        category: _metrics(rows, category, source_category=True)
        for category in sorted({item.get("category", "unknown") for item in rows})
    }
    metrics["by_failure_category"] = {
        category: _metrics(rows, category) for category in ("exact_identifier", "semantic", "multi_table")
    }
    failures = []
    for row in rows:
        retrieved = {record["id"] for record in row["ranked_records"]}
        returned_columns = {
            f"{record['table']}.{column['name']}"
            for record in row["ranked_records"] if record["kind"] == "table"
            for column in record["columns"]
        }
        missing_tables = sorted(set(row["labels"]["relevant_tables"]) - {
            item.removeprefix("table:") for item in retrieved if item.startswith("table:")
        })
        missing_columns = sorted(set(row["labels"]["relevant_columns"]) - returned_columns)
        missing_relationships = sorted(set(row["labels"]["relevant_relationships"]) - retrieved)
        if missing_tables or missing_columns or missing_relationships:
            failures.append({
                "id": row["id"], "category": row["category"], "tags": row["tags"],
                "missing_tables": missing_tables, "missing_columns": missing_columns,
                "missing_relationships": missing_relationships, "ranked_ids": row["ranked_ids"],
            })
    metrics["failures"] = failures
    metrics["ranked_results"] = rows
    return metrics
