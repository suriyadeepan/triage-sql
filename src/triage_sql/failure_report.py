"""Comparative metrics for completed FS-03 experiment artifacts."""

from __future__ import annotations

from collections import Counter
from typing import Any

from triage_sql.failure_experiment import CONDITIONS


def _rate(count: int, total: int) -> float | None:
    return count / total if total else None


def _sum_known(rows: list[dict], key: str) -> tuple[int | None, int]:
    values = [row[key] for row in rows if isinstance(row.get(key), (int, float))]
    return (sum(values), len(values)) if values else (None, 0)


def build_failure_report(cohort: list[dict], baseline_pairs: dict[str, dict], artifacts: dict[str, dict]) -> dict:
    """Compare both high-effort conditions with their paired Luna-low rows."""
    ids = [item["id"] for item in cohort]
    if len(ids) != 53 or len(set(ids)) != 53 or set(baseline_pairs) != set(ids):
        raise ValueError("FS-03 report requires the exact 53 unique frozen cohort IDs")
    if set(artifacts) != set(CONDITIONS):
        raise ValueError("FS-03 report requires exactly retrieved_schema and full_schema artifacts")

    output = {"cohort_count": 53, "cost_acceptability": "left to the reader; no threshold was specified", "conditions": {}}
    categories = {item["id"]: item.get("category") or "unknown" for item in cohort}
    for condition in CONDITIONS:
        artifact = artifacts[condition]
        if artifact.get("experiment_status") != "completed":
            raise ValueError(f"{condition} artifact is not from a completed experiment")
        metadata = artifact.get("metadata", {})
        if metadata.get("generator_model") != "gpt-6-luna" or metadata.get("reasoning_effort") != "high":
            raise ValueError(f"{condition} artifact does not match the approved Luna-high configuration")
        rows = {row["id"]: row for row in artifact.get("queries", [])}
        if set(rows) != set(ids):
            raise ValueError(f"{condition} artifact must contain exactly the 53 cohort IDs")
        high_rows = [rows[query_id] for query_id in ids]
        if any(row.get("status") not in {"completed", "malformed_output"} for row in high_rows):
            raise ValueError(f"{condition} artifact contains an unfinished query")
        low_rows = [baseline_pairs[query_id][condition] for query_id in ids]
        low_correct = sum(bool(row.get("execution_accuracy")) for row in low_rows)
        high_valid = sum(bool(row.get("sql_valid")) for row in high_rows)
        high_executed = sum(bool(row.get("execution_success")) for row in high_rows)
        high_correct = sum(bool(row.get("result_correct")) for row in high_rows)
        delta = high_correct - low_correct
        generation_cost, priced_generation_queries = _sum_known(high_rows, "estimated_generation_cost_usd")
        cohere_cost, priced_cohere_queries = _sum_known(high_rows, "estimated_cohere_cost_usd")
        total_cost, priced_total_queries = _sum_known(high_rows, "estimated_total_cost_usd")
        generation_latency, generation_latency_queries = _sum_known(high_rows, "generation_latency_ms")
        execution_latency, execution_latency_queries = _sum_known(high_rows, "execution_latency_ms")
        retrieval_latency, retrieval_latency_queries = _sum_known(high_rows, "retrieval_latency_ms")
        rerank_latency, rerank_latency_queries = _sum_known(high_rows, "cohere_latency_ms")
        category_metrics = {}
        for category in sorted(set(categories.values())):
            selected = [row for row in high_rows if categories[row["id"]] == category]
            category_metrics[category] = {
                "queries": len(selected),
                "sql_valid": sum(bool(row.get("sql_valid")) for row in selected),
                "execution_success": sum(bool(row.get("execution_success")) for row in selected),
                "result_correct": sum(bool(row.get("result_correct")) for row in selected),
                "failures": sum(not bool(row.get("result_correct")) for row in selected),
            }
        errors = Counter(
            str(row.get("error_type") or row.get("execution_status") or row.get("status") or "unknown")
            for row in high_rows if not row.get("result_correct")
        )
        input_values = [row["usage"]["input_tokens"] for row in high_rows
                        if isinstance(row.get("usage", {}).get("input_tokens"), (int, float))]
        output_values = [row["usage"]["output_tokens"] for row in high_rows
                         if isinstance(row.get("usage", {}).get("output_tokens"), (int, float))]
        reasoning_values = [row["usage"]["reasoning_tokens"] for row in high_rows
                            if isinstance(row.get("usage", {}).get("reasoning_tokens"), (int, float))]
        all_metrics_present = priced_total_queries == 53 and all(
            row.get("total_cost_estimate_complete") is True for row in high_rows
        )
        reported_total_cost = total_cost if all_metrics_present else None
        output["conditions"][condition] = {
            "baseline": {"correct": low_correct, "total": 53, "accuracy": _rate(low_correct, 53),
                         "cost": "unavailable", "output_tokens": "unavailable", "reasoning_tokens": "unavailable"},
            "luna_high": {
                "sql_valid": {"count": high_valid, "total": 53, "rate": _rate(high_valid, 53)},
                "execution_success": {"count": high_executed, "total": 53, "rate": _rate(high_executed, 53)},
                "result_correct": {"count": high_correct, "total": 53, "accuracy": _rate(high_correct, 53)},
                "improvement": {"additional_correct_queries": delta, "percentage_points": 100 * (high_correct - low_correct) / 53},
                "tokens": {"input": sum(input_values) if input_values else None,
                           "input_queries_with_usage": len(input_values),
                           "output": sum(output_values) if output_values else None,
                           "output_queries_with_usage": len(output_values),
                           "reasoning": sum(reasoning_values) if reasoning_values else None,
                           "reasoning_queries_with_usage": len(reasoning_values)},
                "latency_ms": {"generation_sum": generation_latency, "generation_queries": generation_latency_queries,
                               "execution_sum": execution_latency, "execution_queries": execution_latency_queries,
                               "retrieval_sum": retrieval_latency, "retrieval_queries": retrieval_latency_queries,
                               "cohere_rerank_sum": rerank_latency, "rerank_queries": rerank_latency_queries},
                "estimated_cost_usd": {"generation": generation_cost, "generation_queries_priced": priced_generation_queries,
                                       "cohere_rerank": cohere_cost, "rerank_queries_priced": priced_cohere_queries,
                                       "total": reported_total_cost,
                                       "queries_fully_priced": sum(row.get("total_cost_estimate_complete") is True for row in high_rows),
                                       "complete": all_metrics_present},
                "cost_per_additional_success_usd": (reported_total_cost / delta if delta > 0 and all_metrics_present else None),
                "category_breakdown": category_metrics,
                "failures_by_error_type": dict(sorted(errors.items())),
            },
        }
    output["recommendation"] = (
        "Consider Luna-high only as failure-triggered escalation if the reader judges its measured cost per additional successful query acceptable."
    )
    return output
