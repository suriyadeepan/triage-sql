"""Generate and validate the fixed-snapshot Azraq NL evaluation set."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import psycopg
from psycopg import sql

from scripts.azraq_init import schema_name


SNAPSHOT_MANIFEST = Path("data/manifest/azraq-postgres.json")
OUTPUT = Path("data/evaluation/azraq-evaluation.jsonl")
VARIANTS = (
    "How many {subject} are there?",
    "Count the {subject} in the dataset.",
    "What is the total number of {subject}?",
    "Show me the count of {subject}.",
    "Give the number of {subject}.",
)

# Each pattern uses only versioned schema columns and validated relationship links.
PATTERNS = [
    ("filter", "clients", "SELECT count(*) FROM clients WHERE type = 'Individual'", "individual clients"),
    ("filter", "clients", "SELECT count(*) FROM clients WHERE type = 'Group'", "group clients"),
    ("filter", "clients", "SELECT count(*) FROM clients WHERE registration_date >= DATE '2020-01-01'", "clients registered since 2020"),
    ("filter", "loans", "SELECT count(*) FROM loans WHERE status = 'Active'", "active loans"),
    ("filter", "savings_accounts", "SELECT count(*) FROM savings_accounts WHERE status = 'Active'", "active savings accounts"),
    ("date", "loans", "SELECT min(disbursed_date), max(disbursed_date) FROM loans", "loan disbursement date range"),
    ("date", "repayments", "SELECT min(payment_date), max(payment_date) FROM repayments", "repayment date range"),
    ("date", "clients", "SELECT count(*) FROM clients WHERE registration_date >= DATE '2021-01-01' AND registration_date < DATE '2022-01-01'", "clients registered in 2021"),
    ("aggregation", "loans", "SELECT status, count(*) FROM loans GROUP BY status ORDER BY status", "loan counts by status"),
    ("aggregation", "clients", "SELECT type, count(*) FROM clients GROUP BY type ORDER BY type", "client counts by type"),
    ("aggregation", "repayments", "SELECT date_trunc('year', payment_date)::date, count(*) FROM repayments GROUP BY 1 ORDER BY 1", "repayment counts by year"),
    ("aggregation", "savings_accounts", "SELECT status, count(*), round(avg(balance), 2) FROM savings_accounts GROUP BY status ORDER BY status", "savings account counts and average balances by status"),
    ("aggregation", "loan_products", "SELECT interest_method, count(*) FROM loan_products GROUP BY interest_method ORDER BY interest_method", "loan product counts by interest method"),
    ("aggregation", "savings_products", "SELECT frequency, count(*) FROM savings_products GROUP BY frequency ORDER BY frequency", "savings product counts by frequency"),
    ("join", "loans", "SELECT count(*) FROM loans l JOIN clients c ON l.client_id = c.id", "loans linked to clients"),
    ("join", "loans", "SELECT c.type, count(*) FROM loans l JOIN clients c ON l.client_id = c.id GROUP BY c.type ORDER BY c.type", "loan counts by client type"),
    ("join", "clients", "SELECT b.name, count(*) FROM clients c JOIN branches b ON c.branch_id = b.id GROUP BY b.name ORDER BY b.name", "client counts by branch"),
    ("join", "savings_accounts", "SELECT count(*) FROM savings_accounts s JOIN clients c ON s.client_id = c.id", "savings accounts linked to clients"),
    ("subtype_join", "groups_members", "SELECT count(*) FROM groups_members gm JOIN clients g ON gm.group_id = g.id AND g.type = 'Group'", "membership rows linked to Group clients"),
    ("subtype_join", "groups_members", "SELECT count(*) FROM groups_members gm JOIN clients m ON gm.member_id = m.id AND m.type = 'Individual'", "membership rows linked to Individual clients"),
    ("subtype_join", "nsg_meetings", "SELECT count(*) FROM nsg_meetings n JOIN clients c ON n.group_id = c.id AND c.type = 'NSG'", "NSG meetings linked to NSG clients"),
    ("subtype_join", "collaterals", "SELECT count(*) FROM collaterals x JOIN clients c ON x.owner_id = c.id", "collaterals linked to client owners of any type"),
    ("multi_table", "loans", "SELECT p.name, count(*) FROM loans l JOIN loan_products p ON l.product_id = p.id JOIN funding_lines f ON l.funding_line_id = f.id GROUP BY p.name ORDER BY p.name", "loan counts by product with a funding line"),
    ("multi_table", "clients", "SELECT d.name, count(*) FROM clients c JOIN cities ci ON c.city_id = ci.id JOIN districts d ON ci.district_id = d.id GROUP BY d.name ORDER BY d.name", "clients by district through their city"),
]


def _json_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _load_snapshot(path: Path) -> tuple[str, str]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    snapshot = manifest["dataset_snapshot_id"]
    schema = manifest["schema"]
    if not re.fullmatch(r"[0-9a-f]{64}", snapshot) or schema != schema_name(snapshot):
        raise ValueError("invalid fixed database snapshot manifest")
    return snapshot, schema


def generate(dsn: str, manifest_path: Path, output: Path) -> int:
    snapshot, schema = _load_snapshot(manifest_path)
    items = []
    with psycopg.connect(dsn) as conn:
        conn.execute("SET default_transaction_read_only = on")
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(schema)))
            for category, pattern, query, subject in PATTERNS:
                if "password" in query.casefold():
                    raise ValueError("evaluation SQL must not reference credential columns")
                if query.strip().count(";"):
                    raise ValueError("evaluation SQL must contain one statement")
                rows = conn.execute(query).fetchall()
                expected = [[_json_value(v) for v in row] for row in rows]
                for variant_no, phrasing in enumerate(VARIANTS, start=1):
                    item_id = f"eval-{len(items) + 1:03d}"
                    items.append({
                        "id": item_id,
                        "question": phrasing.format(subject=subject),
                        "category": category,
                        "pattern_id": pattern,
                        "status": "supported",
                        "reference_sql": query,
                        "expected_result": expected,
                        "execution": {"status": "passed", "row_count": len(rows)},
                        "dataset_snapshot_id": snapshot,
                        "provenance": "deterministic template over versioned Azraq schema and validated relationship metadata",
                    })
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(item, sort_keys=True, ensure_ascii=False) + "\n" for item in items), encoding="utf-8")
    return len(items)


def validate_items(items: list[dict], snapshot: str) -> None:
    if not 100 <= len(items) <= 200:
        raise ValueError("evaluation set must contain 100 to 200 items")
    ids = set()
    for item in items:
        if item["id"] in ids:
            raise ValueError("duplicate evaluation ID")
        ids.add(item["id"])
        if item.get("dataset_snapshot_id") != snapshot:
            raise ValueError("evaluation item snapshot mismatch")
        if item.get("status") == "supported":
            if not item.get("reference_sql") or item.get("execution", {}).get("status") != "passed":
                raise ValueError("supported item lacks SQL or successful execution")
            if re.search(r"\bpassword\b", item["reference_sql"], re.I):
                raise ValueError("evaluation SQL references a credential column")
        elif item.get("status") not in {"unsupported", "ambiguous"} or item.get("reference_sql") is not None:
            raise ValueError("unhandled evaluation status or fabricated SQL for unsupported item")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
