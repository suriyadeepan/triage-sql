"""Compare retrieved-schema and full-schema SQL generation on Azraq queries."""

from __future__ import annotations

import hashlib
import json
import re
import statistics
import time
from pathlib import Path

import psycopg
from psycopg import sql
from sqlglot import exp, parse

from triage_sql.evaluation import _json_value
from triage_sql.retrieval import SchemaRetriever
from triage_sql.rerank import CohereReranker
from triage_sql.sql_generation import SQLGenerator


def build_prompt(question: str, context_records: list[dict]) -> str:
    context = json.dumps(context_records, sort_keys=True, ensure_ascii=False)
    return f"Schema context (JSON):\n{context}\n\nQuestion: {question}\nSQL:"


def validate_generated_sql(text: str, allowed_tables: set[str] | None = None) -> str:
    sql_text = text.strip()
    sql_text = re.sub(r"\A```(?:sql)?\s*|\s*```\Z", "", sql_text, flags=re.IGNORECASE).strip()
    try:
        statements = parse(sql_text, read="postgres")
    except Exception as exc:
        raise ValueError("generated SQL could not be parsed") from exc
    if len(statements) != 1 or not isinstance(statements[0], exp.Query):
        raise ValueError("generated SQL must contain exactly one SELECT query")
    query = statements[0]
    forbidden = (exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create, exp.Drop, exp.Alter, exp.Command)
    if any(query.find(kind) is not None for kind in forbidden):
        raise ValueError("generated SQL contains a write or command operation")
    if any(column.name.casefold() in {"password", "passwd", "credential", "secret", "api_key"}
           for column in query.find_all(exp.Column)):
        raise ValueError("generated SQL references a sensitive column")
    if allowed_tables is not None:
        known_tables = {name.casefold() for name in allowed_tables}
        cte_names = {cte.alias_or_name.casefold() for cte in query.find_all(exp.CTE)}
        query_tables = {table.name.casefold() for table in query.find_all(exp.Table)}
        if not query_tables or not query_tables <= (known_tables | cte_names):
            raise ValueError("generated SQL references a table outside the Azraq schema")
    safe_anonymous_functions = {
        "coalesce", "nullif", "date_trunc", "concat", "lower", "upper", "substring", "trim",
        "abs", "round", "greatest", "least", "extract", "to_char", "string_agg",
    }
    for function in query.find_all(exp.Anonymous):
        if function.name.casefold() not in safe_anonymous_functions:
            raise ValueError("generated SQL uses a function outside the benchmark allowlist")
    return sql_text.rstrip(";")


def _execute_read_only(conn, schema_name: str, generated_sql: str, timeout_ms: int) -> tuple[list[list], float]:
    start = time.perf_counter()
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        conn.execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(schema_name)))
        conn.execute(sql.SQL("SET LOCAL statement_timeout TO {} ").format(sql.Literal(f"{timeout_ms}ms")))
        cursor = conn.execute(generated_sql)
        rows = cursor.fetchmany(1001)
    elapsed = (time.perf_counter() - start) * 1000
    if len(rows) > 1000:
        raise ValueError("generated query returned more than 1000 rows")
    return [[_json_value(value) for value in row] for row in rows], elapsed


def _percentiles(values: list[float]) -> dict:
    ordered = sorted(values)
    index = lambda fraction: ordered[max(0, min(len(ordered) - 1, int((len(ordered) - 1) * fraction + 0.999999)))]
    return {
        "average": statistics.mean(values),
        "p50": index(0.50),
        "p95": index(0.95),
        "samples": len(values),
    }


def run_prompt_benchmark(
    queries_path: Path,
    retriever: SchemaRetriever,
    generator: SQLGenerator,
    dsn: str,
    snapshot_manifest_path: Path,
    output_path: Path,
    top_k: int = 5,
    candidate_k: int = 20,
    reranker: CohereReranker | None = None,
    rerank_delay_seconds: float = 6.5,
    timeout_ms: int = 15000,
    limit: int | None = None,
    include_full_schema: bool = True,
) -> dict:
    items = [json.loads(line) for line in queries_path.read_text(encoding="utf-8").splitlines()]
    items = [item for item in items if item.get("status") == "supported"]
    if limit is not None:
        items = items[:limit]
    snapshot = json.loads(snapshot_manifest_path.read_text(encoding="utf-8"))
    all_records = json.loads(retriever.records_path.read_text(encoding="utf-8"))
    allowed_tables = {record["table"] for record in all_records if record["kind"] == "table"}
    if candidate_k < top_k or rerank_delay_seconds < 0:
        raise ValueError("candidate_k must be >= top_k and rerank delay cannot be negative")
    strategies = {"retrieved": []}
    if include_full_schema:
        strategies["full_schema"] = []
    with psycopg.connect(dsn) as conn:
        for item in items:
            start = time.perf_counter()
            retrieved = retriever.search(item["question"], "hybrid", candidate_k if reranker else top_k, candidate_k)
            cohere_latency_ms = 0.0
            if reranker:
                rerank_start = time.perf_counter()
                retrieved = reranker.rerank(item["question"], retrieved, top_k)
                cohere_latency_ms = (time.perf_counter() - rerank_start) * 1000
            retrieval_ms = (time.perf_counter() - start) * 1000
            contexts = {"retrieved": (retrieved, retrieval_ms)}
            if include_full_schema:
                contexts["full_schema"] = (all_records, 0.0)
            for strategy, (records, schema_retrieval_ms) in contexts.items():
                prompt = build_prompt(item["question"], records)
                generation = generator.generate(prompt)
                entry = {
                    "id": item["id"],
                    "category": item.get("category"),
                    "question": item["question"],
                    "sql": None,
                    "execution_accuracy": False,
                    "execution_status": "not_run",
                    "prompt_tokens": generation.input_tokens,
                    "retrieval_latency_ms": schema_retrieval_ms,
                    "cohere_latency_ms": cohere_latency_ms,
                    "retrieval_labels": {
                        key: item.get(key, []) for key in (
                            "relevant_tables", "relevant_columns", "relevant_relationships", "unresolved_relationships"
                        )
                    },
                    "ranked_records": records if strategy == "retrieved" else [],
                    "generation_latency_ms": generation.latency_ms,
                    "execution_latency_ms": 0.0,
                }
                try:
                    generated_sql = validate_generated_sql(generation.text, allowed_tables)
                    entry["sql"] = generated_sql
                    rows, execution_ms = _execute_read_only(conn, snapshot["schema"], generated_sql, timeout_ms)
                    entry["execution_latency_ms"] = execution_ms
                    entry["execution_accuracy"] = rows == item["expected_result"]
                    entry["execution_status"] = "passed" if entry["execution_accuracy"] else "result_mismatch"
                except ValueError as exc:
                    rejection = ("sensitive" in str(exc) or "write" in str(exc)
                                 or "outside" in str(exc) or "allowlist" in str(exc))
                    entry["execution_status"] = "rejected" if rejection else "invalid_sql"
                except psycopg.Error as exc:
                    entry["execution_status"] = type(exc).__name__
                entry["end_to_end_latency_ms"] = (
                    entry["retrieval_latency_ms"] + entry["generation_latency_ms"] + entry["execution_latency_ms"]
                )
                strategies[strategy].append(entry)
            if reranker and item is not items[-1] and rerank_delay_seconds:
                time.sleep(rerank_delay_seconds)

    summary = {}
    for strategy, entries in strategies.items():
        summary[strategy] = {
            "query_count": len(entries),
            "sql_execution_accuracy": sum(entry["execution_accuracy"] for entry in entries) / len(entries) if entries else 0,
            "prompt_tokens": {
                "total": sum(entry["prompt_tokens"] or 0 for entry in entries),
                "average": statistics.mean([entry["prompt_tokens"] or 0 for entry in entries]) if entries else 0,
            },
            "retrieval_latency_ms": _percentiles([entry["retrieval_latency_ms"] for entry in entries]) if entries else {},
            "cohere_latency_ms": _percentiles([entry["cohere_latency_ms"] for entry in entries]) if entries else {},
            "generation_latency_ms": _percentiles([entry["generation_latency_ms"] for entry in entries]) if entries else {},
            "execution_latency_ms": _percentiles([entry["execution_latency_ms"] for entry in entries]) if entries else {},
            "end_to_end_latency_ms": _percentiles([entry["end_to_end_latency_ms"] for entry in entries]) if entries else {},
            "by_category": {},
            "failures": [
                {"id": entry["id"], "category": entry["category"], "status": entry["execution_status"]}
                for entry in entries if not entry["execution_accuracy"]
            ],
            "queries": entries,
        }
        for category in sorted({entry["category"] for entry in entries if entry["category"]}):
            category_entries = [entry for entry in entries if entry["category"] == category]
            summary[strategy]["by_category"][category] = {
                "query_count": len(category_entries),
                "sql_execution_accuracy": sum(entry["execution_accuracy"] for entry in category_entries) / len(category_entries),
            }
    retrieval_metrics = {}
    if "retrieved" in strategies:
        from triage_sql.retrieval_benchmark import _metrics

        retrieval_rows = [{
            "id": row["id"], "category": row["category"],
            "tags": [], "labels": row["retrieval_labels"], "ranked_records": row["ranked_records"],
        } for row in strategies["retrieved"]]
        metrics = _metrics(retrieval_rows)
        recall_at_5 = _metrics([{
            **row, "ranked_records": row["ranked_records"][:5]
        } for row in retrieval_rows])
        retrieval_metrics = {
            "recall_at_5": recall_at_5["overall_recall_at_k"],
            "mrr": metrics["overall_mrr"],
            "query_count": len(retrieval_rows),
        }

    result = {
        "dataset_snapshot_id": snapshot["dataset_snapshot_id"],
        "query_set_sha256": hashlib.sha256(queries_path.read_bytes()).hexdigest(),
        "index_manifest_sha256": hashlib.sha256(retriever.manifest_path.read_bytes()).hexdigest(),
        "generator_model": generator.model,
        "generator_reasoning_effort": getattr(generator, "reasoning_effort", None),
        "top_k": top_k,
        "candidate_k": candidate_k,
        "reranker": "rerank-v5.0-fast" if reranker else None,
        "query_count": len(items),
        "retrieved_schema": summary["retrieved"],
        "retrieval_metrics": retrieval_metrics,
    }
    if "full_schema" in summary:
        result["full_schema"] = summary["full_schema"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result
