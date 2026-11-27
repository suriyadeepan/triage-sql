"""Structured, value-free records parsed from the Azraq schema DDL."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_CREATE_TABLE = re.compile(
    r"CREATE\s+TABLE\s+(?P<table>[A-Za-z_][A-Za-z0-9_]*)\s*\((?P<body>.*?)\)\s*;",
    re.IGNORECASE | re.DOTALL,
)
_COLUMN = re.compile(r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s+(?P<type>[A-Za-z][A-Za-z0-9_]*(?:\s*\([^)]*\))?)\s*,?\s*$")
_PASSWORD_NAME = re.compile(r"password|passwd|credential|secret|token|api[_-]?key", re.IGNORECASE)


@dataclass(frozen=True)
class ColumnRecord:
    name: str
    data_type: str


@dataclass(frozen=True)
class TableRecord:
    name: str
    columns: tuple[ColumnRecord, ...]
    description: str

    @property
    def searchable_text(self) -> str:
        columns = " ".join(f"{column.name} {column.data_type}" for column in self.columns)
        return f"table {self.name} {self.description} {columns}".strip()


def _safe_observation_preamble(path: Path | None) -> str:
    """Read only prose before the sample-table section; never read sample rows."""
    if path is None or not path.exists():
        return ""
    preamble_lines = []
    with path.open(encoding="utf-8") as source:
        for line in source:
            if line.strip() == "## Dataset overview":
                break
            preamble_lines.append(line)
    # Keep only short explanatory prose. This excludes Markdown tables and code-like values.
    lines = [line.strip(" #-") for line in preamble_lines]
    safe_lines = []
    for line in lines:
        if not line or not line.startswith("The SQL schema is") or _PASSWORD_NAME.search(line):
            continue
        observation = re.split(r" Relationship notes below", line, maxsplit=1)[0]
        safe_lines.append(observation)
    return " ".join(safe_lines)


def parse_schema(ddl: str, observations: Path | None = None) -> tuple[TableRecord, ...]:
    """Parse table/column identifiers and types without ingesting row values."""
    table_records: list[TableRecord] = []
    safe_description = _safe_observation_preamble(observations)
    seen_tables: set[str] = set()
    for table_match in _CREATE_TABLE.finditer(ddl):
        table_name = table_match.group("table")
        if table_name.casefold() in seen_tables:
            raise ValueError(f"duplicate table in schema: {table_name}")
        seen_tables.add(table_name.casefold())
        columns: list[ColumnRecord] = []
        seen_columns: set[str] = set()
        for line in table_match.group("body").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            match = _COLUMN.fullmatch(stripped)
            if match is None:
                raise ValueError(f"unsupported column declaration in {table_name}")
            name = match.group("name")
            if name.casefold() in seen_columns:
                raise ValueError(f"duplicate column in {table_name}: {name}")
            seen_columns.add(name.casefold())
            if _PASSWORD_NAME.search(name):
                continue
            columns.append(ColumnRecord(name=name, data_type=re.sub(r"\s+", " ", match.group("type")).upper()))
        table_records.append(TableRecord(table_name, tuple(columns), safe_description))
    if not table_records:
        raise ValueError("schema contains no CREATE TABLE declarations")
    return tuple(table_records)


def load_schema(ddl_path: Path, observations_path: Path | None = None) -> tuple[TableRecord, ...]:
    return parse_schema(ddl_path.read_text(encoding="utf-8"), observations_path)
