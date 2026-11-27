#!/usr/bin/env python3
"""Run full-coverage relationship checks against the immutable PostgreSQL snapshot."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg
from psycopg import sql

from scripts.azraq_init import DEFAULT_DSN, DEFAULT_MANIFEST, schema_name
from scripts.azraq_manifest import sha256_file
from triage_sql.relationships import Relationship, load_relationships


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELATIONSHIPS = ROOT / "data/raw/azraq-relationships.yaml"
DEFAULT_OUTPUT = ROOT / "data/manifest/azraq-relationships-validation.json"


def validation_query(relationship: Relationship, schema: str) -> sql.Composed:
    assert relationship.target is not None
    source = sql.Identifier(schema, relationship.source.table)
    target = sql.Identifier(schema, relationship.target.table)
    source_key = sql.Identifier(relationship.source.column)
    target_key = sql.Identifier(relationship.target.column)

    if relationship.target_filter:
        filter_column, filter_value = relationship.target_filter
        filter_expr = sql.SQL("t.{} = {}").format(sql.Identifier(filter_column), sql.Literal(filter_value))
        filtered_null_expr = sql.SQL("t.{} IS NULL AND {}").format(target_key, filter_expr)
        filtered_rows_expr = sql.SQL("count(*) FILTER (WHERE {})").format(filter_expr)
        mismatch_expr = sql.SQL("count(*) FILTER (WHERE s.{} IS NOT NULL AND g.target_count IS NOT NULL AND g.filtered_count = 0)").format(source_key)
        filtered_target_rows_expr = filtered_rows_expr
        filtered_target_nulls_expr = sql.SQL("count(*) FILTER (WHERE {})").format(filtered_null_expr)
    else:
        filter_expr = sql.SQL("TRUE")
        filtered_rows_expr = sql.SQL("count(*)")
        mismatch_expr = sql.SQL("0::bigint")
        filtered_target_rows_expr = sql.SQL("count(*)")
        filtered_target_nulls_expr = sql.SQL("count(*) FILTER (WHERE t.{} IS NULL)").format(target_key)

    return sql.SQL(
        "WITH target_grouped AS ("
        " SELECT t.{target_key} AS target_key, count(*) AS target_count, "
        " count(*) FILTER (WHERE {filter_expr}) AS filtered_count "
        " FROM {target} AS t WHERE t.{target_key} IS NOT NULL GROUP BY t.{target_key}"
        "), target_stats AS ("
        " SELECT count(*) AS target_rows, "
        " count(*) FILTER (WHERE t.{target_key} IS NULL) AS target_null_count, "
        " {filtered_target_rows_expr} AS filtered_target_rows, "
        " {filtered_target_nulls_expr} AS filtered_target_null_count FROM {target} AS t"
        "), target_duplicates AS ("
        " SELECT count(*) FILTER (WHERE target_count > 1) AS duplicate_keys, "
        " coalesce(sum(target_count - 1) FILTER (WHERE target_count > 1), 0) AS duplicate_rows, "
        " count(*) FILTER (WHERE filtered_count > 1) AS filtered_duplicate_keys "
        " FROM target_grouped"
        "), source_stats AS ("
        " SELECT count(*) AS source_rows, "
        " count(*) FILTER (WHERE s.{source_key} IS NULL) AS source_null_count, "
        " count(*) FILTER (WHERE s.{source_key} IS NOT NULL AND g.target_count IS NOT NULL AND g.filtered_count > 0) AS matched_source_rows, "
        " count(*) FILTER (WHERE s.{source_key} IS NOT NULL AND g.target_count IS NULL) AS orphan_source_rows, "
        " {mismatch_expr} AS subtype_mismatch_count "
        " FROM {source} AS s LEFT JOIN target_grouped AS g ON g.target_key = s.{source_key}"
        ") SELECT source_stats.source_rows, source_stats.source_null_count, "
        " source_stats.matched_source_rows, source_stats.orphan_source_rows, "
        " source_stats.subtype_mismatch_count, target_stats.target_rows, "
        " target_stats.target_null_count, target_duplicates.duplicate_keys, "
        " target_duplicates.duplicate_rows, target_stats.filtered_target_rows, "
        " target_stats.filtered_target_null_count, target_duplicates.filtered_duplicate_keys "
        " FROM source_stats CROSS JOIN target_stats CROSS JOIN target_duplicates"
    ).format(
        target_key=target_key,
        filter_expr=filter_expr,
        target=target,
        filtered_target_rows_expr=filtered_target_rows_expr,
        filtered_target_nulls_expr=filtered_target_nulls_expr,
        source_key=source_key,
        source=source,
        mismatch_expr=mismatch_expr,
    )


def validate_one(conn: psycopg.Connection, relationship: Relationship, schema: str) -> dict:
    if relationship.candidate or relationship.target is None:
        return {"id": relationship.id, "coverage": "not_applicable", "join_eligible": False}
    values = conn.execute(validation_query(relationship, schema)).fetchone()
    fields = (
        "source_rows",
        "source_null_count",
        "matched_source_rows",
        "orphan_source_rows",
        "subtype_mismatch_count",
        "target_rows",
        "target_null_count",
        "target_duplicate_keys",
        "target_duplicate_rows",
        "filtered_target_rows",
        "filtered_target_null_count",
        "filtered_target_duplicate_keys",
    )
    result = {field: int(value) for field, value in zip(fields, values)}
    target_unique = result["target_duplicate_keys"] == 0
    filtered_unique = result["filtered_target_duplicate_keys"] == 0
    no_orphans = result["orphan_source_rows"] == 0
    no_subtype_mismatches = result["subtype_mismatch_count"] == 0
    semantic_reviewed = bool(relationship.metadata.get("semantic_review"))
    result.update({
        "id": relationship.id,
        "from": {"table": relationship.source.table, "column": relationship.source.column},
        "to": {"table": relationship.target.table, "column": relationship.target.column},
        "cardinality": relationship.cardinality,
        "confidence": relationship.confidence,
        "status": relationship.status,
        "evidence": list(relationship.evidence),
        "provenance": relationship.metadata.get("provenance"),
        "target_filter": relationship.target_filter,
        "coverage": "full",
        "target_unique": target_unique,
        "filtered_target_unique": filtered_unique,
        "no_orphans": no_orphans,
        "no_subtype_mismatches": no_subtype_mismatches,
        "semantic_reviewed": semantic_reviewed,
        "join_eligible": relationship.status == "validated",
    })
    return result


def build_report(dsn: str, manifest_path: Path, relationships_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    database_manifest_path = manifest_path.with_name("azraq-postgres.json")
    database_manifest = json.loads(database_manifest_path.read_text(encoding="utf-8"))
    if database_manifest["dataset_snapshot_id"] != manifest["dataset_snapshot_id"]:
        raise ValueError("database and source manifests identify different snapshots")
    schema = schema_name(manifest["dataset_snapshot_id"])
    relationships = load_relationships(relationships_path)

    with psycopg.connect(dsn) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        server_version = conn.execute("SHOW server_version").fetchone()[0].split()[0]
        if server_version != database_manifest["postgres_version"]:
            raise ValueError("connected PostgreSQL version differs from the database snapshot manifest")
        results = []
        for relation in relationships:
            print(f"Validating {relation.id}.", flush=True)
            results.append(validate_one(conn, relation, schema))

    return {
        "report_version": 1,
        "dataset_snapshot_id": manifest["dataset_snapshot_id"],
        "relationship_metadata_sha256": sha256_file(relationships_path),
        "schema": schema,
        "postgres_version": server_version,
        "coverage": "full",
        "relationships": results,
    }


def render_human_report(report: dict) -> str:
    lines = [
        "# Azraq relationship validation",
        "",
        f"- Snapshot: `{report['dataset_snapshot_id']}`",
        f"- PostgreSQL: `{report['postgres_version']}`",
        f"- Coverage: **{report['coverage']}** over the loaded source and target tables",
        f"- Relationship metadata SHA-256: `{report['relationship_metadata_sha256']}`",
        "",
        "All counts are exact for this fixed snapshot. Sample evidence recorded in the YAML remains separate.",
        "",
        "| Relationship | Coverage | Source rows | Source nulls | Matched | Orphans | Subtype mismatches | Target rows | Target nulls | Duplicate target keys | Filtered duplicate keys | Status | JOIN eligible |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|",
    ]
    for item in report["relationships"]:
        if item.get("coverage") != "full":
            lines.append(f"| `{item['id']}` | {item['coverage']} | — | — | — | — | — | — | — | — | — | {item.get('status', 'candidate')} | no |")
            continue
        lines.append(
            "| `{id}` | {coverage} | {source_rows} | {source_null_count} | {matched_source_rows} | "
            "{orphan_source_rows} | {subtype_mismatch_count} | {target_rows} | {target_null_count} | "
            "{target_duplicate_keys} | {filtered_target_duplicate_keys} | {status} | {eligible} |".format(
                **item, eligible="yes" if item["join_eligible"] else "no"
            )
        )
    lines.extend(["", "A `validated` status controls JOIN generation; metadata still does not create database constraints.", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=os.environ.get("DATABASE_URL", DEFAULT_DSN))
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--relationships", type=Path, default=DEFAULT_RELATIONSHIPS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        report = build_report(args.dsn, args.manifest, args.relationships)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        args.output.with_suffix(".md").write_text(render_human_report(report), encoding="utf-8")
    except Exception as exc:
        print(f"ERROR: validation failed ({type(exc).__name__}); details suppressed", file=sys.stderr)
        return 1
    failed = sum(
        not (item.get("target_unique") and item.get("filtered_target_unique") and item.get("no_orphans") and item.get("no_subtype_mismatches"))
        for item in report["relationships"]
        if item.get("coverage") == "full"
    )
    eligible = sum(item.get("join_eligible", False) for item in report["relationships"])
    print(
        f"Full validation: {len(report['relationships'])} metadata entries, "
        f"{failed} entry(s) with integrity findings, {eligible} validated JOIN edge(s); "
        f"report {args.output}"
    )
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
