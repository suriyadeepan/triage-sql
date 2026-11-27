"""Derive retrieval relevance labels from the fixed Azraq reference SQL."""

from __future__ import annotations

import json
from pathlib import Path

from sqlglot import exp, parse_one

from triage_sql.relationships import load_relationships, validated_relationships
from triage_sql.schema import load_schema


def derive_labels(reference_sql: str, schema_columns: dict[str, set[str]], relationships: list) -> dict:
    try:
        query = parse_one(reference_sql, read="postgres")
    except Exception as exc:
        raise ValueError(f"cannot parse reference SQL: {exc}") from exc
    if not isinstance(query, exp.Query):
        raise ValueError("reference SQL must be a query")

    table_nodes = list(query.find_all(exp.Table))
    alias_to_table = {node.alias_or_name.casefold(): node.name.casefold() for node in table_nodes}
    relevant_tables = sorted(set(alias_to_table.values()))
    relevant_columns: set[str] = set()
    unresolved_columns: set[str] = set()

    def resolve_column(column: exp.Column) -> tuple[str, str] | None:
        column_name = column.name.casefold()
        if column_name == "*":
            return None
        if column.table:
            table = alias_to_table.get(column.table.casefold())
            if table is None:
                return None
            return table, column_name
        matches = [table for table in relevant_tables if column_name in schema_columns.get(table, set())]
        if len(matches) == 1:
            return matches[0], column_name
        unresolved_columns.add(column_name)
        return None

    for column in query.find_all(exp.Column):
        resolved = resolve_column(column)
        if resolved is not None:
            relevant_columns.add(f"{resolved[0]}.{resolved[1]}")

    validated = validated_relationships(relationships)
    validated_pairs: dict[frozenset, list] = {}
    for relationship in validated:
        assert relationship.target is not None
        pair = frozenset(((relationship.source.table.casefold(), relationship.source.column.casefold()),
                          (relationship.target.table.casefold(), relationship.target.column.casefold())))
        validated_pairs.setdefault(pair, []).append(relationship)

    relevant_relationships: set[str] = set()
    unresolved_relationships: set[str] = set()
    for join in query.find_all(exp.Join):
        on = join.args.get("on")
        if on is None:
            continue
        for equality in on.find_all(exp.EQ):
            if not isinstance(equality.this, exp.Column) or not isinstance(equality.expression, exp.Column):
                continue
            left, right = resolve_column(equality.this), resolve_column(equality.expression)
            if left is None or right is None:
                continue
            pair = frozenset((left, right))
            candidates = validated_pairs.get(pair, [])
            if not candidates:
                continue
            eligible = []
            for relationship in candidates:
                if relationship.target_filter is None:
                    eligible.append(relationship)
                    continue
                filter_column, expected = relationship.target_filter
                found = False
                for filter_eq in on.find_all(exp.EQ):
                    if not isinstance(filter_eq.this, exp.Column) or not isinstance(filter_eq.expression, exp.Literal):
                        continue
                    filter_endpoint = resolve_column(filter_eq.this)
                    if (
                        filter_endpoint == (relationship.target.table.casefold(), filter_column.casefold())
                        and str(filter_eq.expression.this).casefold() == expected.casefold()
                    ):
                        found = True
                        break
                if found:
                    eligible.append(relationship)
            if eligible:
                relevant_relationships.update(item.id for item in eligible)
            else:
                unresolved_relationships.update(item.id for item in candidates)

    # Flag endpoint pairs present in JOIN SQL but not among validated edges.
    for join in query.find_all(exp.Join):
        on = join.args.get("on")
        if on is None:
            continue
        for equality in on.find_all(exp.EQ):
            if not isinstance(equality.this, exp.Column) or not isinstance(equality.expression, exp.Column):
                continue
            left, right = resolve_column(equality.this), resolve_column(equality.expression)
            if left is None or right is None:
                continue
            pair = frozenset((left, right))
            if pair in validated_pairs:
                continue
            for relationship in relationships:
                if relationship.target is None:
                    continue
                relation_pair = frozenset(((relationship.source.table.casefold(), relationship.source.column.casefold()),
                                           (relationship.target.table.casefold(), relationship.target.column.casefold())))
                if pair == relation_pair:
                    unresolved_relationships.add(relationship.id)

    return {
        "relevant_tables": relevant_tables,
        "relevant_columns": sorted(relevant_columns),
        "relevant_relationships": sorted(relevant_relationships),
        "unresolved_columns": sorted(unresolved_columns),
        "unresolved_relationships": sorted(unresolved_relationships),
    }


def label_evaluation_set(evaluation_path: Path, ddl_path: Path, relationships_path: Path) -> list[dict]:
    columns = {table.name.casefold(): {column.name.casefold() for column in table.columns}
               for table in load_schema(ddl_path)}
    relationships = load_relationships(relationships_path)
    eligible = validated_relationships(relationships)
    results = []
    for line in evaluation_path.read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        if item.get("status") != "supported" or not item.get("reference_sql"):
            item["relevant_tables"] = []
            item["relevant_columns"] = []
            item["relevant_relationships"] = []
            item["unresolved_columns"] = []
            item["unresolved_relationships"] = []
        else:
            labels = derive_labels(item["reference_sql"], columns, relationships)
            item.update(labels)
        results.append(item)
    return results


def write_labels(evaluation_path: Path, ddl_path: Path, relationships_path: Path, output_path: Path) -> int:
    results = label_evaluation_set(evaluation_path, ddl_path, relationships_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(json.dumps(item, sort_keys=True, ensure_ascii=False) + "\n" for item in results), encoding="utf-8")
    return len(results)
