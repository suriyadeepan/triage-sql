import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from triage_sql.prompt_benchmark import build_prompt, validate_generated_sql
from triage_sql.sql_generation import OpenAIResponsesGenerator


class FakeResponses:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            output_text="SELECT count(*) FROM loans",
            usage=SimpleNamespace(
                input_tokens=21,
                output_tokens=13,
                input_tokens_details=SimpleNamespace(cached_tokens=5),
                output_tokens_details=SimpleNamespace(reasoning_tokens=7),
            ),
        )


class FakeClient:
    def __init__(self):
        self.responses = FakeResponses()


class PromptBenchmarkTests(unittest.TestCase):
    def test_prompt_is_structured_and_only_uses_supplied_safe_context(self):
        prompt = build_prompt("Count active loans", [{"kind": "table", "table": "loans", "columns": [{"name": "status"}]}])
        self.assertIn('"table": "loans"', prompt)
        self.assertIn("Count active loans", prompt)
        self.assertNotIn("password", prompt.casefold())

    def test_openai_adapter_uses_configured_model_and_returns_usage(self):
        client = FakeClient()
        with patch("triage_sql.sql_generation.load_dotenv"), patch.dict(
            "os.environ", {"OPENAI_REASONING_EFFORT": "low"}
        ):
            adapter = OpenAIResponsesGenerator("configured-test-model", client)
        generated = adapter.generate("schema and question")
        self.assertEqual(generated.model, "configured-test-model")
        self.assertEqual(generated.input_tokens, 21)
        self.assertEqual(generated.output_tokens, 13)
        self.assertEqual(generated.reasoning_tokens, 7)
        self.assertEqual(generated.cached_input_tokens, 5)
        self.assertEqual(generated.text, "SELECT count(*) FROM loans")
        self.assertEqual(client.responses.kwargs["model"], "configured-test-model")
        self.assertEqual(client.responses.kwargs["reasoning"], {"effort": "low"})

    def test_openai_adapter_preserves_existing_sdk_retry_defaults(self):
        factory = Mock()
        with patch("triage_sql.sql_generation.load_dotenv"), patch.dict(
            "os.environ", {"OPENAI_MODEL": "gpt-6-luna", "OPENAI_REASONING_EFFORT": "high"}
        ), patch.dict("sys.modules", {"openai": SimpleNamespace(OpenAI=factory)}):
            OpenAIResponsesGenerator()
        factory.assert_called_once_with()

    def test_generated_sql_must_be_single_read_only_safe_select(self):
        self.assertEqual(validate_generated_sql("```sql\nSELECT count(*) FROM loans;\n```"), "SELECT count(*) FROM loans")
        self.assertEqual(
            validate_generated_sql("SELECT count(*) FROM loans", {"loans"}),
            "SELECT count(*) FROM loans",
        )
        for sql in (
            "DELETE FROM loans",
            "SELECT 1; SELECT 2",
            "SELECT password FROM users",
            "SELECT pg_read_file('/etc/passwd') FROM loans",
            "SELECT * FROM pg_catalog.pg_class",
        ):
            with self.subTest(sql=sql), self.assertRaises(ValueError):
                validate_generated_sql(sql, {"loans", "users"})

    def test_openai_adapter_requires_explicit_model(self):
        with patch("triage_sql.sql_generation.load_dotenv"), patch.dict("os.environ", {"OPENAI_MODEL": ""}):
            with self.assertRaisesRegex(ValueError, "OPENAI_MODEL"):
                OpenAIResponsesGenerator("")

    def test_openai_adapter_loads_dotenv_without_overriding_environment(self):
        with patch("triage_sql.sql_generation.find_dotenv", return_value="test.env") as find, patch(
            "triage_sql.sql_generation.load_dotenv"
        ) as load:
            OpenAIResponsesGenerator("configured-test-model", FakeClient())
        find.assert_called_once_with(usecwd=True)
        load.assert_called_once_with("test.env", override=False)


if __name__ == "__main__":
    unittest.main()
