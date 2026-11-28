import unittest
from pathlib import Path

from triage_sql.schema import load_schema, parse_schema


ROOT = Path(__file__).resolve().parents[1]


class SchemaRecordTests(unittest.TestCase):
    def test_azraq_schema_loads_all_tables_and_types_without_sample_values(self):
        records = load_schema(ROOT / "data/raw/azraq-schema.sql", ROOT / "data/raw/azraq.md")
        by_name = {record.name: record for record in records}

        self.assertEqual(len(records), 26)
        self.assertEqual(set(by_name), {
            "branches", "cities", "client_locations", "clients", "collateral_products", "collaterals",
            "currencies", "delinquency_tracking", "districts", "economic_activities", "exchange_rates",
            "funding_lines", "groups_members", "loan_products", "loan_tranches", "loan_writeoffs", "loans",
            "manual_schedule_adjustments", "nsg_meetings", "regions", "repayments", "roles",
            "savings_accounts", "savings_products", "savings_transactions", "users",
        })
        self.assertEqual(by_name["clients"].columns[0].name, "id")
        self.assertEqual(by_name["clients"].columns[0].data_type, "BIGINT")
        self.assertEqual(by_name["collaterals"].columns[2].name, "owner_id")
        self.assertNotIn("Anthony Johnson", " ".join(record.searchable_text for record in records))
        self.assertNotIn("password", " ".join(record.searchable_text for record in records).casefold())

    def test_password_columns_are_removed_and_observation_rows_are_not_read(self):
        ddl = "CREATE TABLE users (\n id BIGINT,\n password TEXT\n);"
        records = parse_schema(ddl)
        self.assertEqual([column.name for column in records[0].columns], ["id"])

    def test_credential_like_columns_are_excluded(self):
        ddl = "CREATE TABLE users (\n id BIGINT,\n api_key TEXT,\n access_token TEXT,\n credential_secret TEXT\n);"
        records = parse_schema(ddl)
        self.assertEqual([column.name for column in records[0].columns], ["id"])

    def test_malformed_column_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unsupported column"):
            parse_schema("CREATE TABLE broken (\n id BIGINT REFERENCES users(id)\n);")


if __name__ == "__main__":
    unittest.main()
