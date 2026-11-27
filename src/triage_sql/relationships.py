"""Validated-only relationship loading and SQL JOIN clause generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from psycopg import sql


@dataclass(frozen=True)
class Endpoint:
    table: str
    column: str


@dataclass(frozen=True)
class Relationship:
    id: str
    source: Endpoint
    target: Endpoint | None
    cardinality: str
    confidence: float
    status: str
    evidence: tuple[str, ...]
    target_filter: tuple[str, str] | None
    metadata: dict
    candidate: bool = False


def load_relationships(path: Path) -> list[Relationship]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("relationship metadata must be a YAML mapping")
    result: list[Relationship] = []
    for section, candidate in (("relationships", False), ("unresolved_candidates", True)):
        entries = document.get(section, [])
        if not isinstance(entries, list):
            raise ValueError(f"{section} must be a list")
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
                raise ValueError(f"invalid relationship entry in {section}")
            source_data = entry.get("from")
            if not isinstance(source_data, dict):
                raise ValueError(f"{entry['id']}: missing source endpoint")
            source = Endpoint(str(source_data["table"]), str(source_data["column"]))
            target_data = entry.get("to")
            target = None
            if isinstance(target_data, dict):
                target = Endpoint(str(target_data["table"]), str(target_data["column"]))
            elif not candidate:
                raise ValueError(f"{entry['id']}: missing target endpoint")
            filter_data = entry.get("target_filter")
            target_filter = None
            if filter_data is not None:
                if not isinstance(filter_data, dict) or "equals" not in filter_data:
                    raise ValueError(f"{entry['id']}: malformed target filter")
                target_filter = (str(filter_data["column"]), str(filter_data["equals"]))
            result.append(Relationship(
                id=entry["id"],
                source=source,
                target=target,
                cardinality=str(entry.get("cardinality", "unknown")),
                confidence=float(entry.get("confidence", 0)),
                status=str(entry.get("status", "inferred")),
                evidence=tuple(entry.get("evidence", [])),
                target_filter=target_filter,
                metadata=dict(entry),
                candidate=candidate,
            ))
    return result


def validated_relationships(relationships: list[Relationship]) -> list[Relationship]:
    return [
        relationship
        for relationship in relationships
        if not relationship.candidate and relationship.status == "validated" and relationship.target is not None
    ]


def relationship_join_clause(
    relationship: Relationship,
    source_alias: str | None = None,
    target_alias: str | None = None,
) -> sql.Composed:
    """Build a JOIN clause only for a reviewed validated relationship."""
    if relationship not in validated_relationships([relationship]):
        raise ValueError(f"relationship {relationship.id} is not validated for JOIN generation")
    assert relationship.target is not None
    source_alias = source_alias or relationship.source.table
    target_alias = target_alias or relationship.target.table
    clause = sql.SQL("JOIN {} AS {} ON {}.{} = {}.{}").format(
        sql.Identifier(relationship.target.table),
        sql.Identifier(target_alias),
        sql.Identifier(source_alias),
        sql.Identifier(relationship.source.column),
        sql.Identifier(target_alias),
        sql.Identifier(relationship.target.column),
    )
    if relationship.target_filter:
        column, expected = relationship.target_filter
        clause += sql.SQL(" AND {}.{} = {}").format(
            sql.Identifier(target_alias), sql.Identifier(column), sql.Literal(expected)
        )
    return clause
