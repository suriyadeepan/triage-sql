#!/usr/bin/env python3
"""Verify the pinned Python/PostgreSQL runtime and one read-only snapshot query."""

import argparse
import json
import os
import platform
from pathlib import Path

import psycopg
from psycopg import sql

from scripts.azraq_init import schema_name

DEFAULT_DSN = "postgresql://azraq:azraq_local_only@127.0.0.1:55432/azraq"


def verify_runtime(dsn: str, manifest_path: Path) -> dict:
    python_version = platform.python_version()
    if not python_version.startswith("3.14."):
        raise RuntimeError(f"Python 3.14 is required; found {python_version}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    snapshot = manifest["dataset_snapshot_id"]
    schema = schema_name(snapshot)
    with psycopg.connect(dsn) as conn:
        server_version = conn.execute("SHOW server_version").fetchone()[0].split()[0]
        if server_version != "18.7":
            raise RuntimeError(f"PostgreSQL 18.7 is required; found {server_version}")
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(schema)))
            table_count = conn.execute(
                "SELECT count(*) FROM information_schema.tables WHERE table_schema = %s AND table_type = 'BASE TABLE'",
                (schema,),
            ).fetchone()[0]
            client_count = conn.execute("SELECT count(*) FROM clients").fetchone()[0]
            password_rows = conn.execute("SELECT count(*) FROM users WHERE password IS NOT NULL").fetchone()[0]
            read_only = conn.execute("SHOW transaction_read_only").fetchone()[0] == "on"
    if table_count != 26 or client_count != manifest["row_counts"]["clients"] or password_rows != 0 or not read_only:
        raise RuntimeError("live runtime smoke assertions failed")
    return {"python_version": python_version, "postgres_version": server_version, "dataset_snapshot_id": snapshot,
            "table_count": table_count, "client_rows": client_count, "non_null_password_rows": password_rows,
            "read_only_query": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=os.environ.get("DATABASE_URL", DEFAULT_DSN))
    parser.add_argument("--manifest", type=Path, default=Path("data/manifest/azraq-postgres.json"))
    args = parser.parse_args()
    print(json.dumps(verify_runtime(args.dsn, args.manifest), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
