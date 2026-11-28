import unittest

from triage_sql.costing import (
    RerankRateCard,
    TokenRateCard,
    estimate_rerank_cost_usd,
    estimate_token_cost_usd,
)


class TokenCostingTests(unittest.TestCase):
    def setUp(self):
        self.rate_card = TokenRateCard(
            model="gpt-6-luna",
            input_usd_per_million=0.10,
            output_usd_per_million=0.50,
            cached_input_usd_per_million=0.01,
            source_url="https://example.test/pricing",
            checked_at="2026-11-28",
        )

    def test_cost_counts_cached_and_uncached_input_and_all_output_once(self):
        # Seven reasoning tokens are included in the 13 output tokens, not added again.
        self.assertAlmostEqual(
            estimate_token_cost_usd(self.rate_card, 21, 13, cached_input_tokens=5),
            (16 * 0.10 + 5 * 0.01 + 13 * 0.50) / 1_000_000,
        )

    def test_missing_usage_makes_estimate_unavailable(self):
        self.assertIsNone(estimate_token_cost_usd(self.rate_card, 21, None))

    def test_unknown_cached_usage_uses_standard_input_rate(self):
        self.assertAlmostEqual(
            estimate_token_cost_usd(self.rate_card, 21, 13),
            (21 * 0.10 + 13 * 0.50) / 1_000_000,
        )

    def test_rejects_negative_token_counts_and_rates(self):
        with self.assertRaisesRegex(ValueError, "token counts"):
            estimate_token_cost_usd(self.rate_card, -1, 5)
        with self.assertRaisesRegex(ValueError, "rates"):
            TokenRateCard(
                model="gpt-6-luna", input_usd_per_million=-1, output_usd_per_million=0,
                source_url="source", checked_at="today",
            )

    def test_cohere_trial_cost_is_zero_and_production_uses_billed_input_tokens(self):
        trial = RerankRateCard(
            "rerank-v5.0-fast", 0.02, "https://cohere.com/pricing", "2026-11-28", "trial"
        )
        production = RerankRateCard(
            "rerank-v5.0-fast", 0.02, "https://cohere.com/pricing", "2026-11-28", "production"
        )
        self.assertEqual(estimate_rerank_cost_usd(trial, None), 0.0)
        self.assertAlmostEqual(estimate_rerank_cost_usd(production, 500), 500 * 0.02 / 1_000_000)
        self.assertIsNone(estimate_rerank_cost_usd(production, None))


if __name__ == "__main__":
    unittest.main()
