"""Safe structured context records for tables and validated relationships."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from triage_sql.relationships import Relationship, load_relationships, validated_relationships
from triage_sql.schema import TableRecord


@dataclass(frozen=True)
class RelationshipRecord:
    id: str
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    cardinality: str
    status: str
    confidence: float
    evidence: tuple[str, ...]
    target_filter: tuple[str, str] | None
    provenance: dict

    @property
    def searchable_text(self) -> str:
        details = " ".join(
            str(value) for key, value in self.provenance.items()
            if key in {"rationale", "semantic_review"} and value
        )
        return " ".join((
            self.id, self.source_table, self.source_column, self.target_table,
            self.target_column, self.cardinality, self.join_predicate,
            " ".join(self.evidence), self.status, details,
        ))

    @property
    def join_predicate(self) -> str:
        predicate = f"{self.source_table}.{self.source_column} = {self.target_table}.{self.target_column}"
        if self.target_filter:
            column, expected = self.target_filter
            escaped = expected.replace("'", "''")
            predicate += f" AND {self.target_table}.{column} = '{escaped}'"
        return predicate

    def to_dict(self) -> dict:
        return {
            "kind": "relationship",
            "id": self.id,
            "from": {"table": self.source_table, "column": self.source_column},
            "to": {"table": self.target_table, "column": self.target_column},
            "cardinality": self.cardinality,
            "join_predicate": self.join_predicate,
            "target_filter": (
                {"column": self.target_filter[0], "equals": self.target_filter[1]}
                if self.target_filter else None
            ),
            "status": self.status,
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            "provenance": self.provenance,
            "searchable_text": self.searchable_text,
        }


def _relationship_record(relationship: Relationship) -> RelationshipRecord:
    if relationship.target is None:
        raise ValueError(f"relationship {relationship.id} has no target")
    return RelationshipRecord(
        id=relationship.id,
        source_table=relationship.source.table,
        source_column=relationship.source.column,
        target_table=relationship.target.table,
        target_column=relationship.target.column,
        cardinality=relationship.cardinality,
        status=relationship.status,
        confidence=relationship.confidence,
        evidence=relationship.evidence,
        target_filter=relationship.target_filter,
        provenance=relationship.metadata,
    )


def relationship_records(path: Path) -> tuple[RelationshipRecord, ...]:
    """Load only declared, reviewed validated edges; unresolved candidates are excluded."""
    relationships = load_relationships(path)
    return tuple(_relationship_record(item) for item in validated_relationships(relationships))


def context_records(
    tables: tuple[TableRecord, ...], relationships: tuple[RelationshipRecord, ...]
) -> tuple[dict, ...]:
    """Serialize table and relationship metadata for index/prompt use."""
    result = [
        {
            "kind": "table",
            "id": f"table:{table.name}",
            "table": table.name,
            "description": table.description,
            "columns": [{"name": col.name, "type": col.data_type} for col in table.columns],
            "searchable_text": table.searchable_text,
        }
        for table in tables
    ]
    result.extend(record.to_dict() for record in relationships)
    return tuple(result)
