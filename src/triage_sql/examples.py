"""Build, execute, and leakage-check synthetic Azraq SQL examples."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import psycopg
from psycopg import sql
import yaml

from scripts.azraq_init import schema_name


ROOT = Path(__file__).resolve().parents[2]
DB_MANIFEST = ROOT / "data/manifest/azraq-postgres.json"
RELATIONSHIPS = ROOT / "data/raw/azraq-relationships.yaml"
OUTPUT_DIR = ROOT / "data/examples/azraq"

# (pattern, NL request, corrected SQL, incorrect SQL, required validated edges)
EXAMPLES = [
    ("client-type-count", "Count clients grouped by client type.", "SELECT type, count(*) FROM clients GROUP BY type ORDER BY type", "SELECT type, count(*) FROM client GROUP BY type ORDER BY type", ()),
    ("active-loans", "Count loans with Active status.", "SELECT count(*) FROM loans WHERE status = 'Active'", "SELECT count(*) FROM loans WHERE status = Active", ()),
    ("loan-principal-by-status", "Show average principal amount for each loan status.", "SELECT status, round(avg(principal_amount), 2) FROM loans GROUP BY status ORDER BY status", "SELECT status, round(avg(principal_amount), 2) FROM loans GROUP BY loan_status ORDER BY status", ()),
    ("loan-disbursement-years", "Count loans by disbursement year.", "SELECT date_part('year', disbursed_date)::int, count(*) FROM loans GROUP BY 1 ORDER BY 1", "SELECT date_part('year', disbursed_date)::int, count(*) FROM loans GROUP BY 1 ORDER BY disbursed_date", ()),
    ("products-with-funding-lines", "List loan product names and their funding line names.", "SELECT p.name, f.name FROM loan_products p JOIN funding_lines f ON p.funding_line_id = f.id ORDER BY p.name", "SELECT p.name, f.name FROM loan_products p JOIN funding_lines f ON p.funding_line_id = f.id ORDER BY p.name", ("loan_products.funding_line_id__funding_lines.id",)),
    ("group-memberships", "Count membership rows for Group clients.", "SELECT count(*) FROM groups_members gm JOIN clients g ON gm.group_id = g.id AND g.type = 'Group'", "SELECT count(*) FROM groups_members gm JOIN clients g ON gm.group_id = g.id", ("groups_members.group_id__clients.id",)),
    ("individual-members", "Count individual clients listed as group members.", "SELECT count(*) FROM groups_members gm JOIN clients m ON gm.member_id = m.id AND m.type = 'Individual'", "SELECT count(*) FROM groups_members gm JOIN clients m ON gm.member_id = m.id AND m.type = 'Group'", ("groups_members.member_id__clients.id",)),
    ("collateral-owners", "Count collateral records with a matching client owner.", "SELECT count(*) FROM collaterals x JOIN clients c ON x.owner_id = c.id", "SELECT count(*) FROM collaterals x JOIN clients c ON x.owner_id = c.id AND c.type = 'Individual'", ("collaterals.owner_id__clients.id",)),
    ("nsg-meetings", "Count meetings linked to NSG clients.", "SELECT count(*) FROM nsg_meetings n JOIN clients c ON n.group_id = c.id AND c.type = 'NSG'", "SELECT count(*) FROM nsg_meetings n JOIN clients c ON n.group_id = c.id", ("nsg_meetings.group_id__clients.id",)),
    ("clients-by-branch", "Count clients at each branch.", "SELECT b.name, count(*) FROM clients c JOIN branches b ON c.branch_id = b.id GROUP BY b.name ORDER BY b.name", "SELECT b.name, count(*) FROM clients c JOIN branches b ON c.branch_id = b.id GROUP BY b.id ORDER BY b.name", ("clients.branch_id__branches.id",)),
    ("savings-status", "Count savings accounts by status.", "SELECT status, count(*) FROM savings_accounts GROUP BY status ORDER BY status", "SELECT status, count(*) FROM savings_accounts GROUP BY status ORDER BY status", ()),
    ("transactions-by-type", "Count savings transactions by transaction type.", "SELECT transaction_type, count(*) FROM savings_transactions GROUP BY transaction_type ORDER BY transaction_type", "SELECT transaction_type, count(*) FROM savings_transactions GROUP BY transaction_type ORDER BY type", ()),
    ("repayment-year-totals", "Sum principal paid by repayment year.", "SELECT date_part('year', payment_date)::int, round(sum(principal_paid), 2) FROM repayments GROUP BY 1 ORDER BY 1", "SELECT date_part('year', payment_date)::int, round(sum(principal_paid), 2) FROM repayments GROUP BY 1 ORDER BY 1", ()),
    ("late-loan-events", "Count delinquency events with more than 30 late days.", "SELECT count(*) FROM delinquency_tracking WHERE late_days > 30", "SELECT count(*) FROM delinquency_tracking WHERE late_days > '30 days'", ()),
    ("collateral-products", "Count collateral records by collateral product.", "SELECT p.name, count(*) FROM collaterals x JOIN collateral_products p ON x.product_id = p.id GROUP BY p.name ORDER BY p.name", "SELECT p.name, count(*) FROM collaterals x JOIN collateral_products p ON x.product_id = p.id GROUP BY p.name ORDER BY p.name", ("collaterals.product_id__collateral_products.id",)),
    ("clients-by-district", "Count clients by district through their city.", "SELECT d.name, count(*) FROM clients c JOIN cities ci ON c.city_id = ci.id JOIN districts d ON ci.district_id = d.id GROUP BY d.name ORDER BY d.name", "SELECT d.name, count(*) FROM clients c JOIN cities ci ON c.city_id = ci.id JOIN districts d ON ci.district_id = d.id GROUP BY d.name ORDER BY d.name", ("clients.city_id__cities.id", "cities.district_id__districts.id")),
    ("loans-by-product", "Count loans by loan product name.", "SELECT p.name, count(*) FROM loans l JOIN loan_products p ON l.product_id = p.id GROUP BY p.name ORDER BY p.name", "SELECT p.name, count(*) FROM loans l JOIN loan_products p ON l.product_id = p.id GROUP BY p.name ORDER BY p.name", ("loans.product_id__loan_products.id",)),
    ("savings-product-frequency", "Count savings products by transaction frequency.", "SELECT frequency, count(*) FROM savings_products GROUP BY frequency ORDER BY frequency", "SELECT frequency, count(*) FROM savings_products GROUP BY frequency ORDER BY frequency", ()),
    ("registration-by-year", "Count clients registered in each year.", "SELECT date_part('year', registration_date)::int, count(*) FROM clients GROUP BY 1 ORDER BY 1", "SELECT date_part('year', registration_date)::int, count(*) FROM clients GROUP BY 1 ORDER BY 1", ()),
    ("loan-repayments", "Count repayment records per loan.", "SELECT loan_id, count(*) FROM repayments GROUP BY loan_id ORDER BY loan_id LIMIT 10", "SELECT loan_id, count(*) FROM repayments GROUP BY loan_id ORDER BY loan_id LIMIT 10", ()),
    ("average-savings-balance", "Show average savings balance by account status.", "SELECT status, round(avg(balance), 2) FROM savings_accounts GROUP BY status ORDER BY status", "SELECT status, round(avg(balance), 2) FROM savings_accounts GROUP BY status ORDER BY status", ()),
    ("client-activity", "Count clients by economic activity.", "SELECT e.name, count(*) FROM clients c JOIN economic_activities e ON c.economic_activity_id = e.id GROUP BY e.name ORDER BY e.name", "SELECT e.name, count(*) FROM clients c JOIN economic_activities e ON c.economic_activity_id = e.id GROUP BY e.name ORDER BY e.name", ("clients.economic_activity_id__economic_activities.id",)),
    ("loan-funding-lines", "Count loans by funding line.", "SELECT f.name, count(*) FROM loans l JOIN funding_lines f ON l.funding_line_id = f.id GROUP BY f.name ORDER BY f.name", "SELECT f.name, count(*) FROM loans l JOIN funding_lines f ON l.funding_line_id = f.id GROUP BY f.name ORDER BY f.name", ("loans.funding_line_id__funding_lines.id",)),
    ("loan-tranche-dates", "Show the earliest and latest tranche dates.", "SELECT min(tranche_date), max(tranche_date) FROM loan_tranches", "SELECT min(tranche_date), max(tranche_date) FROM loan_tranches", ()),
]


def _json_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def canonical_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).casefold()
    return hashlib.sha256(raw.encode()).hexdigest()


def leakage_findings(partitions: dict[str, list[dict]]) -> list[dict[str, str]]:
    """Find exact question, SQL, result, or pattern reuse crossing held-out splits."""
    seen: dict[tuple[str, str], tuple[str, str]] = {}
    findings = []
    for split, records in partitions.items():
        for item in records:
            keys = {
                "question": re.sub(r"\W+", " ", item["question"].casefold()).strip(),
                "sql": re.sub(r"\s+", " ", item["sql"].casefold()).strip(),
                "result": canonical_hash(item["expected_result"]),
                "pattern": item["pattern_id"],
            }
            for kind, value in keys.items():
                previous = seen.get((kind, value))
                if previous and previous[0] != split and "heldout" in {previous[0], split}:
                    findings.append({"kind": kind, "heldout_split": split if split == "heldout" else previous[0], "pattern_id": item["pattern_id"]})
                else:
                    seen[(kind, value)] = (split, item["pattern_id"])
    return findings


def _partition(index: int) -> str:
    return "train" if index % 5 < 3 else "validation" if index % 5 == 3 else "heldout"


def generate_examples(dsn: str, manifest_path: Path = DB_MANIFEST, relationship_path: Path = RELATIONSHIPS, output_dir: Path = OUTPUT_DIR) -> int:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    snapshot = manifest["dataset_snapshot_id"]
    schema = schema_name(snapshot)
    relationship_doc = yaml.safe_load(relationship_path.read_text(encoding="utf-8"))
    eligible = {r["id"] for r in relationship_doc.get("relationships", []) if r.get("status") == "validated"}
    if any(not set(edges) <= eligible for _, _, _, _, edges in EXAMPLES):
        raise ValueError("example uses a relationship that is not validated")

    collections = {"text_to_sql": {s: [] for s in ("train", "validation", "heldout")}, "sql_correction": {s: [] for s in ("train", "validation", "heldout")}}
    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(schema)))
            for index, (pattern_id, question, correct_sql, incorrect_sql, edges) in enumerate(EXAMPLES):
                split = _partition(index)
                if not correct_sql.lstrip().upper().startswith("SELECT") or ";" in correct_sql or re.search(r"\bpassword\b", correct_sql, re.I):
                    raise ValueError(f"unsafe SQL in pattern {pattern_id}")
                cursor = conn.execute(correct_sql)
                result = [[_json_value(value) for value in row] for row in cursor.fetchall()]
                if incorrect_sql == correct_sql:
                    incorrect_sql = f"SELECT * FROM {pattern_id}_missing_table"
                conn.execute("SAVEPOINT bad_example")
                try:
                    bad_result = [[_json_value(value) for value in row] for row in conn.execute(incorrect_sql).fetchall()]
                    bad_outcome = {"status": "executed_needs_correction", "result_differs": bad_result != result}
                except psycopg.Error as exc:
                    bad_outcome = {"status": "rejected", "sqlstate": exc.sqlstate}
                    conn.execute("ROLLBACK TO SAVEPOINT bad_example")
                finally:
                    conn.execute("RELEASE SAVEPOINT bad_example")
                provenance = {"dataset_snapshot_id": snapshot, "source_schema": "data/raw/azraq-schema.sql", "validated_relationships": list(edges)}
                common = {"pattern_id": pattern_id, "split": split, "sql": correct_sql, "expected_result": result, "validation": {"parse": "passed", "execution": "passed", "read_only": True}, "provenance": provenance}
                collections["text_to_sql"][split].append({"id": f"t2sql-{pattern_id}", "question": question, **common})
                correction = {"id": f"correction-{pattern_id}", "question": f"Correct this SQL for the request: {question}", "incorrect_sql": incorrect_sql, "incorrect_sql_validation": bad_outcome, **common}
                collections["sql_correction"][split].append(correction)

    for kind, partitions in collections.items():
        findings = leakage_findings(partitions)
        if findings:
            raise ValueError(f"held-out leakage detected in {kind}: {findings[:3]}")
        for split, records in partitions.items():
            path = output_dir / kind / f"{split}.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("".join(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")
    return len(EXAMPLES) * 2
