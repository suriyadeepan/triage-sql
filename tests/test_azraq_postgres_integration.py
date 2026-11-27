import csv
import hashlib
import os
import tempfile
import unittest
from pathlib import Path

import psycopg

from scripts.azraq_init import copy_table


TEST_DSN = os.environ.get("AZRAQ_TEST_DSN")


@unittest.skipUnless(TEST_DSN, "set AZRAQ_TEST_DSN to run PostgreSQL integration checks")
class PostgreSQLCopyIntegrationTests(unittest.TestCase):
    def test_users_password_is_null_after_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "users.csv"
            with source.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["id", "username", "password"])
                writer.writerow(["17", "synthetic-user", "SENSITIVE_FIXTURE_VALUE"])

            with psycopg.connect(TEST_DSN) as conn:
                with conn.transaction():
                    conn.execute("CREATE TEMP TABLE users (id BIGINT, username TEXT, password TEXT)")
                    with conn.cursor() as cursor:
                        copy_table(
                            cursor,
                            "users",
                            ["id", "username", "password"],
                            source,
                            1,
                            hashlib.sha256(source.read_bytes()).hexdigest(),
                        )
                    row = conn.execute("SELECT id, username, password IS NULL FROM users").fetchone()
                    self.assertEqual(row, (17, "synthetic-user", True))

    def test_raw_copy_preserves_csv_quoting(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "clients.csv"
            with source.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["id", "name"])
                writer.writerow(["18", "Synthetic, Group"])
            content = source.read_bytes()

            with psycopg.connect(TEST_DSN) as conn:
                with conn.transaction():
                    conn.execute("CREATE TEMP TABLE clients (id BIGINT, name TEXT)")
                    with conn.cursor() as cursor:
                        copy_table(
                            cursor,
                            "clients",
                            ["id", "name"],
                            source,
                            1,
                            hashlib.sha256(content).hexdigest(),
                        )
                    row = conn.execute("SELECT id, name FROM clients").fetchone()
                    self.assertEqual(row, (18, "Synthetic, Group"))


if __name__ == "__main__":
    unittest.main()
