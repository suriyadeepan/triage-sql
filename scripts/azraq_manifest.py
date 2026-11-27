#!/usr/bin/env python3
"""Inventory the Azraq source without printing or persisting row values."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / "data/raw/azraq"
DEFAULT_SCHEMA = ROOT / "data/raw/azraq-schema.sql"
DEFAULT_RELATIONSHIPS = ROOT / "data/raw/azraq-relationships.yaml"
DEFAULT_OUTPUT = ROOT / "data/manifest/azraq-snapshot.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_schema(path: Path) -> dict[str, list[dict[str, str]]]:
    """Return DDL tables and inferred column names/types without SQL execution."""
    schema: dict[str, list[dict[str, str]]] = {}
    ddl = path.read_text(encoding="utf-8")
    for match in re.finditer(r"CREATE\s+TABLE\s+(\w+)\s*\((.*?)\);", ddl, re.I | re.S):
        table, body = match.groups()
        columns: list[dict[str, str]] = []
        for line in body.splitlines():
            line = line.strip().rstrip(",")
            if not line or line.startswith("--"):
                continue
            parts = line.split()
            if len(parts) < 2:
                raise ValueError(f"malformed DDL column declaration in table {table}")
            columns.append({"name": parts[0].strip('"'), "type": parts[1].upper()})
        if table in schema:
            raise ValueError(f"duplicate DDL table: {table}")
        schema[table] = columns
    if not schema:
        raise ValueError("no CREATE TABLE declarations found")
    return schema


def inspect_csv(path: Path) -> tuple[list[str], int, int, list[int]]:
    """Return header, data record count, byte count, and malformed record numbers."""
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.reader(stream)
        header = next(reader, [])
        if not header:
            raise ValueError(f"CSV has no header: {path.name}")
        count = 0
        malformed: list[int] = []
        for record_number, row in enumerate(reader, start=2):
            count += 1
            if len(row) != len(header):
                malformed.append(record_number)
    return header, count, path.stat().st_size, malformed


def build_manifest(data_dir: Path, schema_path: Path, relationships_path: Path) -> dict:
    schema = parse_schema(schema_path)
    csv_paths = sorted(data_dir.glob("*.csv"))
    csv_tables = {path.stem for path in csv_paths}
    ddl_tables = set(schema)
    missing_csv = sorted(ddl_tables - csv_tables)
    extra_csv = sorted(csv_tables - ddl_tables)
    tables: dict[str, dict] = {}
    errors: list[str] = []

    for path in csv_paths:
        table = path.stem
        header, rows, size_bytes, malformed = inspect_csv(path)
        expected_columns = [column["name"] for column in schema.get(table, [])]
        tables[table] = {
            "path": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.name,
            "sha256": sha256_file(path),
            "size_bytes": size_bytes,
            "row_count": rows,
            "columns": header,
            "ddl_columns": schema.get(table, []),
            "missing_columns": sorted(set(expected_columns) - set(header)),
            "extra_columns": sorted(set(header) - set(expected_columns)),
            "malformed_record_count": len(malformed),
        }
        if malformed:
            errors.append(f"{table}: {len(malformed)} record(s) have the wrong number of columns")

    schema_hash = sha256_file(schema_path)
    relationships_hash = sha256_file(relationships_path)
    identity = hashlib.sha256()
    identity.update(schema_hash.encode("ascii"))
    identity.update(relationships_hash.encode("ascii"))
    for table, record in sorted(tables.items()):
        identity.update(table.encode("utf-8"))
        identity.update(record["sha256"].encode("ascii"))

    return {
        "manifest_version": 1,
        "dataset": "azraq",
        "dataset_snapshot_id": identity.hexdigest(),
        "anonymization_provenance": "User-confirmed anonymized; not independently audited by this tool.",
        "schema": {"path": schema_path.name, "sha256": schema_hash},
        "relationships": {"path": relationships_path.name, "sha256": relationships_hash},
        "ddl_table_count": len(schema),
        "csv_table_count": len(csv_tables),
        "missing_csv_tables": missing_csv,
        "extra_csv_tables": extra_csv,
        "tables": tables,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--relationships", type=Path, default=DEFAULT_RELATIONSHIPS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    try:
        manifest = build_manifest(args.data_dir, args.schema, args.relationships)
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        print(f"ERROR: inventory failed: {exc}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    total_rows = sum(table["row_count"] for table in manifest["tables"].values())
    print(
        f"Wrote {args.output}: {len(manifest['tables'])} CSV tables, "
        f"{total_rows} data rows; snapshot {manifest['dataset_snapshot_id']}"
    )
    if manifest["missing_csv_tables"] or manifest["extra_csv_tables"]:
        print("ERROR: CSV table set differs from DDL table set", file=sys.stderr)
        return 1
    if any(table["missing_columns"] or table["extra_columns"] for table in manifest["tables"].values()):
        print("ERROR: CSV headers differ from DDL columns", file=sys.stderr)
        return 1
    if manifest["errors"]:
        print("ERROR: malformed CSV records detected", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
