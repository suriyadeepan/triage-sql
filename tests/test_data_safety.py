import unittest

from triage_sql.data_safety import prompt_columns, sanitize_row


class DataSafetyTests(unittest.TestCase):
    def test_users_password_is_omitted_from_prompt_columns(self):
        self.assertEqual(
            prompt_columns("users", ["id", "username", "password", "role_id"]),
            ["id", "username", "role_id"],
        )

    def test_users_password_is_replaced_before_loading(self):
        header = ["id", "username", "password"]
        source = ["9", "synthetic-user", "must-not-escape"]
        sanitized = sanitize_row("users", header, source)

        self.assertEqual(sanitized, ["9", "synthetic-user", ""])
        self.assertNotIn("must-not-escape", sanitized)
        self.assertEqual(source[-1], "must-not-escape")

    def test_other_tables_are_preserved(self):
        self.assertEqual(prompt_columns("clients", ["id", "name"]), ["id", "name"])
        self.assertEqual(sanitize_row("clients", ["id", "name"], ["1", "Example"]), ["1", "Example"])

    def test_row_width_must_match_header(self):
        with self.assertRaises(ValueError):
            sanitize_row("users", ["id", "password"], ["1"])


if __name__ == "__main__":
    unittest.main()
