#!/usr/bin/env python3
"""Initialize one immutable PostgreSQL schema from the versioned Azraq manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
from pathlib import Path

import psycopg
from psycopg import sql

from scripts.azraq_manifest import DEFAULT_DATA_DIR, DEFAULT_RELATIONSHIPS, DEFAULT_SCHEMA, parse_schema, sha256_file, snapshot_identity
from triage_sql.data_safety import sanitize_row


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "data/manifest/azraq-snapshot.json"
DEFAULT_DATABASE_MANIFEST = ROOT / "data/manifest/azraq-postgres.json"
DEFAULT_DSN = "postgresql://azraq:azraq_local_only@127.0.0.1:55432/azraq"
EXPECTED_POSTGRES_VERSION = "18.7"
BATCH_ROWS = 10_000


def schema_name(snapshot_id: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", snapshot_id):
        raise ValueError("manifest contains an invalid snapshot ID")
    return f"azraq_{snapshot_id[:16]}"


def validate_manifest(
    manifest: dict,
    data_dir: Path,
    schema_path: Path,
    relationships_path: Path,
) -> tuple[dict[str, list[dict[str, str]]], str]:
    schema = parse_schema(schema_path)
    if set(schema) != set(manifest.get("tables", {})):
        raise ValueError("manifest table set does not match the DDL")
    if sha256_file(schema_path) != manifest.get("schema", {}).get("sha256"):
        raise ValueError("DDL checksum does not match the manifest")
    if sha256_file(relationships_path) != manifest.get("relationships", {}).get("sha256"):
        raise ValueError("relationship metadata checksum does not match the manifest")

    table_records = {}
    for table, record in sorted(manifest["tables"].items()):
        path = data_dir / f"{table}.csv"
        if not path.is_file() or sha256_file(path) != record.get("sha256"):
            raise ValueError(f"source checksum mismatch for table {table}")
        table_records[table] = record
    snapshot_id = snapshot_identity(manifest["schema"]["sha256"], table_records)
    if snapshot_id != manifest.get("dataset_snapshot_id"):
        raise ValueError("snapshot identity does not match the manifest")

    ddl = schema_path.read_text(encoding="utf-8")
    ddl_without_comments = re.sub(r"(?m)^\s*--.*$", "", ddl)
    if re.search(r"\b(PRIMARY\s+KEY|FOREIGN\s+KEY|REFERENCES)\b", ddl_without_comments, re.I):
        raise ValueError("source DDL must not declare PK/FK constraints")
    for table, columns in schema.items():
        record = manifest["tables"][table]
        expected = [column["name"] for column in columns]
        if record.get("columns") != expected or record.get("ddl_columns") != columns:
            raise ValueError(f"manifest columns do not match the DDL for {table}")
    return schema, snapshot_id


def ddl_statements(schema_path: Path) -> list[str]:
    statements = []
    ddl = re.sub(r"(?m)^\s*--.*$", "", schema_path.read_text(encoding="utf-8"))
    for statement in ddl.split(";"):
        if re.search(r"\bCREATE\s+TABLE\b", statement, re.I):
            statements.append(statement.strip())
    return statements


def copy_table(
    cursor,
    table: str,
    columns: list[str],
    csv_path: Path,
    expected_rows: int,
    expected_sha256: str,
) -> None:
    sensitive = table.casefold() == "users"
    header_option = "" if sensitive else ", HEADER TRUE"
    copy_sql = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT CSV, NULL ''" + header_option + ")").format(
        sql.Identifier(table), sql.SQL(", ").join(sql.Identifier(column) for column in columns)
    )
    digest = hashlib.sha256()
    with cursor.copy(copy_sql) as copy:
        if not sensitive:
            with csv_path.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
                    copy.write(chunk)
        else:
            buffer = io.StringIO(newline="")
            writer = csv.writer(buffer, lineterminator="\n")
            rows = 0
            with csv_path.open("r", newline="", encoding="utf-8-sig") as source:
                reader = csv.reader(source)
                header = next(reader, [])
                if header != columns:
                    raise ValueError(f"CSV header mismatch for table {table}")
                for rows, row in enumerate(reader, start=1):
                    if len(row) != len(header):
                        raise ValueError(f"CSV row width mismatch for table {table} at data row {rows}")
                    writer.writerow(sanitize_row(table, header, row))
                    if rows % BATCH_ROWS == 0:
                        copy.write(buffer.getvalue())
                        buffer.seek(0)
                        buffer.truncate(0)
            if buffer.tell():
                copy.write(buffer.getvalue())
    if sensitive and rows != expected_rows:
        raise ValueError(f"CSV row count mismatch for table {table}: expected {expected_rows}, found {rows}")
    actual_hash = sha256_file(csv_path) if sensitive else digest.hexdigest()
    if actual_hash != expected_sha256:
        raise ValueError(f"source checksum changed during import for table {table}")


def existing_schema_counts(conn, name: str, table_names: set[str]) -> dict[str, int] | None:
    schema_exists = conn.execute(
        "SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = %s)", (name,)
    ).fetchone()[0]
    if not schema_exists:
        return None
    rows = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = %s AND table_type = 'BASE TABLE'",
        (name,),
    ).fetchall()
    existing_tables = {row[0] for row in rows}
    if existing_tables != table_names:
        raise ValueError("snapshot schema already exists but its table set is incomplete or different")
    counts: dict[str, int] = {}
    for table in sorted(table_names):
        query = sql.SQL("SELECT count(*) FROM {}.{}").format(sql.Identifier(name), sql.Identifier(table))
        counts[table] = conn.execute(query).fetchone()[0]
    return counts


def initialize(dsn: str, manifest_path: Path, data_dir: Path, schema_path: Path, relationships_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    schema, snapshot_id = validate_manifest(manifest, data_dir, schema_path, relationships_path)
    target_schema = schema_name(snapshot_id)
    table_names = set(schema)

    with psycopg.connect(dsn, autocommit=True) as conn:
        server_version = conn.execute("SHOW server_version").fetchone()[0]
        server_version = server_version.split()[0]
        if server_version != EXPECTED_POSTGRES_VERSION:
            raise ValueError(f"PostgreSQL {EXPECTED_POSTGRES_VERSION} is required; server version differs")
        existing = existing_schema_counts(conn, target_schema, table_names)
        expected_counts = {table: manifest["tables"][table]["row_count"] for table in table_names}
        if existing is not None:
            if existing != expected_counts:
                raise ValueError("snapshot schema exists but row counts do not match the manifest")
            return {
                "dataset_snapshot_id": snapshot_id,
                "schema": target_schema,
                "postgres_version": server_version,
                "table_count": len(table_names),
                "row_counts": existing,
                "already_initialized": True,
            }

        with conn.transaction():
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(target_schema)))
            conn.execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(target_schema)))
            for statement in ddl_statements(schema_path):
                conn.execute(statement)
            with conn.cursor() as cursor:
                for table in sorted(table_names):
                    print(f"Loading table {table}.", flush=True)
                    columns = [column["name"] for column in schema[table]]
                    copy_table(
                        cursor,
                        table,
                        columns,
                        data_dir / f"{table}.csv",
                        manifest["tables"][table]["row_count"],
                        manifest["tables"][table]["sha256"],
                    )
            actual = existing_schema_counts(conn, target_schema, table_names)
            if actual != expected_counts:
                raise ValueError("loaded row counts do not match the source manifest")

    return {
        "dataset_snapshot_id": snapshot_id,
        "schema": target_schema,
        "postgres_version": server_version,
        "table_count": len(table_names),
        "row_counts": expected_counts,
        "already_initialized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=os.environ.get("DATABASE_URL", DEFAULT_DSN))
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--relationships", type=Path, default=DEFAULT_RELATIONSHIPS)
    parser.add_argument("--database-manifest", type=Path, default=DEFAULT_DATABASE_MANIFEST)
    args = parser.parse_args(argv)

    try:
        result = initialize(args.dsn, args.manifest, args.data_dir, args.schema, args.relationships)
        args.database_manifest.parent.mkdir(parents=True, exist_ok=True)
        args.database_manifest.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            f"PostgreSQL {result['postgres_version']}: schema {result['schema']} has "
            f"{result['table_count']} tables and {sum(result['row_counts'].values())} rows"
        )
        print(f"Database snapshot manifest: {args.database_manifest}")
        return 0
    except Exception as exc:
        # Driver errors may include a COPY context containing source row values.
        print(f"ERROR: initialization failed ({type(exc).__name__}); details suppressed to protect source values", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
