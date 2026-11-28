import unittest

try:
    import httpx
    import openai
except ImportError:
    httpx = None
    openai = None

from triage_sql.api_retry import RetryBudget, is_transient_openai_error, require_luna_high_configuration


class RetryBudgetTests(unittest.TestCase):
    def test_enforces_two_retries_per_request(self):
        budget = RetryBudget()
        key = "retrieved_schema:eval-011"
        self.assertEqual(budget.claim_retry(key), 1)
        self.assertEqual(budget.claim_retry(key), 2)
        self.assertFalse(budget.can_retry(key))
        with self.assertRaisesRegex(RuntimeError, "exhausted"):
            budget.claim_retry(key)

    def test_enforces_fifty_retries_across_requests(self):
        budget = RetryBudget(per_request_limit=2, total_limit=50)
        for index in range(25):
            key = f"condition:query-{index}"
            budget.claim_retry(key)
            budget.claim_retry(key)
        self.assertEqual(budget.total_used, 50)
        self.assertFalse(budget.can_retry("condition:query-25"))

    def test_round_trip_preserves_global_and_per_request_counts(self):
        budget = RetryBudget()
        budget.claim_retry("full_schema:eval-011")
        restored = RetryBudget.from_dict(budget.to_dict())
        self.assertEqual(restored.to_dict(), budget.to_dict())

    def test_rejects_inconsistent_persisted_counts(self):
        with self.assertRaisesRegex(ValueError, "sum"):
            RetryBudget(total_used=1, used_by_request={})

    def test_global_cap_must_be_at_least_the_saved_retry_count(self):
        with self.assertRaisesRegex(ValueError, "global retry limit"):
            RetryBudget(total_limit=0, total_used=1, used_by_request={"q": 1})


class LunaHighConfigurationTests(unittest.TestCase):
    def test_requires_explicit_high_model_and_effort(self):
        require_luna_high_configuration(
            type("Generator", (), {"model": "gpt-6-luna", "reasoning_effort": "high"})()
        )
        with self.assertRaisesRegex(ValueError, "OPENAI_MODEL"):
            require_luna_high_configuration(
                type("Generator", (), {"model": "another-model", "reasoning_effort": "high"})()
            )
        with self.assertRaisesRegex(ValueError, "REASONING_EFFORT"):
            require_luna_high_configuration(
                type("Generator", (), {"model": "gpt-6-luna", "reasoning_effort": "low"})()
            )


@unittest.skipIf(openai is None, "OpenAI SDK is an optional benchmark dependency")
class TransientOpenAIErrorTests(unittest.TestCase):
    def test_connection_and_timeout_errors_are_transient(self):
        request = httpx.Request("GET", "https://api.openai.test")
        connection_error = openai.APIConnectionError(request=request)
        timeout_error = openai.APITimeoutError(request=request)
        self.assertTrue(is_transient_openai_error(connection_error))
        self.assertTrue(is_transient_openai_error(timeout_error))

    def test_only_selected_api_statuses_are_transient(self):
        for status in (408, 409, 429, 500, 503):
            with self.subTest(status=status):
                response = httpx.Response(status, request=httpx.Request("GET", "https://api.openai.test"))
                error = openai.APIStatusError("server response", response=response, body=None)
                self.assertTrue(is_transient_openai_error(error))
        for status in (400, 401, 403, 404):
            with self.subTest(status=status):
                response = httpx.Response(status, request=httpx.Request("GET", "https://api.openai.test"))
                error = openai.APIStatusError("client response", response=response, body=None)
                self.assertFalse(is_transient_openai_error(error))

    def test_generic_and_malformed_output_errors_are_not_transient(self):
        self.assertFalse(is_transient_openai_error(ValueError("malformed SQL")))
        self.assertFalse(is_transient_openai_error(RuntimeError("unexpected failure")))


if __name__ == "__main__":
    unittest.main()
