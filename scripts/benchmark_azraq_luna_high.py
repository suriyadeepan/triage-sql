"""Run the separately approved, frozen 53-query FS-03 Luna-high experiment."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from dotenv import find_dotenv, load_dotenv
import openai

from scripts.azraq_init import DEFAULT_DSN
from triage_sql.api_retry import require_luna_high_configuration
from triage_sql.costing import RerankRateCard, TokenRateCard
from triage_sql.failure_experiment import OUTPUT_DIR, FailureTriggeredExperiment, check_experiment_readiness
from triage_sql.retrieval import DEFAULT_MODEL, SchemaRetriever, SentenceTransformerEncoder
from triage_sql.rerank import COHERE_RERANK_MODEL, CohereReranker
from triage_sql.sql_generation import OpenAIResponsesGenerator


ROOT = Path(__file__).resolve().parents[1]
OPENAI_PRICING_URL = "https://developers.openai.com/api/docs/pricing"
COHERE_PRICING_URL = "https://cohere.com/blog/rerank-5"


def _load_effective_environment() -> None:
    load_dotenv(find_dotenv(usecwd=True), override=False)


def _require_explicit_model_effort() -> None:
    _load_effective_environment()
    require_luna_high_configuration(SimpleNamespace(
        model=os.environ.get("OPENAI_MODEL"),
        reasoning_effort=os.environ.get("OPENAI_REASONING_EFFORT"),
    ))


def _build_experiment_generator() -> OpenAIResponsesGenerator:
    """Build the experiment-only client with SDK retries disabled."""
    return OpenAIResponsesGenerator(client=openai.OpenAI(max_retries=0))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--approve-run", action="store_true",
        help="explicitly acknowledge the one-time experiment and its 106 initial/50 retry request ceilings",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="resume an interrupted checkpoint without repeating completed or ambiguous requests",
    )
    parser.add_argument(
        "--continue-after-stop", action="store_true",
        help="after explicit approval, continue a malformed-output stop while preserving and skipping that query",
    )
    parser.add_argument("--pricing-checked-at", help="date on which both official token rate cards were checked (YYYY-MM-DD)")
    parser.add_argument("--openai-input-rate", type=float, help="USD per million standard OpenAI input tokens")
    parser.add_argument("--openai-cached-input-rate", type=float, help="USD per million cached OpenAI input tokens")
    parser.add_argument("--openai-output-rate", type=float, help="USD per million OpenAI output tokens")
    parser.add_argument("--cohere-account-tier", choices=("trial", "production"), help="Cohere key billing tier")
    parser.add_argument("--cohere-input-rate", type=float, default=0.02,
                        help="USD per million Rerank Fast input tokens; defaults to the published standard rate")
    args = parser.parse_args()

    try:
        readiness = check_experiment_readiness(ROOT)
        _require_explicit_model_effort()
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))

    if not args.approve_run:
        print(json.dumps({
            **readiness,
            "mode": "preflight_only",
            "message": "No model or reranker requests were made. Pass --approve-run only after explicit experiment approval.",
        }, indent=2))
        return 0
    if args.resume is False and (ROOT / OUTPUT_DIR).exists() and any((ROOT / OUTPUT_DIR).iterdir()):
        parser.error("output directory already contains experiment state; use --resume after explicit approval")
    if args.resume and not (ROOT / OUTPUT_DIR / "checkpoint.json").exists():
        parser.error("--resume requires an existing checkpoint")
    if args.continue_after_stop and not args.resume:
        parser.error("--continue-after-stop requires --resume")
    if not args.pricing_checked_at:
        parser.error("--pricing-checked-at is required for an approved experiment run")
    try:
        date.fromisoformat(args.pricing_checked_at)
    except ValueError:
        parser.error("--pricing-checked-at must be an ISO date YYYY-MM-DD")
    if args.openai_input_rate is None or args.openai_cached_input_rate is None or args.openai_output_rate is None:
        parser.error("approved runs require all OpenAI rate-card values")
    if args.cohere_account_tier is None:
        parser.error("approved runs require --cohere-account-tier so reranker cost is estimated correctly")

    try:
        generator = _build_experiment_generator()
        require_luna_high_configuration(generator)
        index_dir = ROOT / "data/index/azraq-schema"
        snapshot_path = ROOT / "data/manifest/azraq-postgres.json"
        retriever = SchemaRetriever(
            ROOT / "data/raw/azraq-schema.sql",
            ROOT / "data/raw/azraq-relationships.yaml",
            ROOT / "data/raw/azraq.md",
            index_dir,
            SentenceTransformerEncoder(DEFAULT_MODEL, device="cpu"),
            snapshot_path,
        )
        experiment = FailureTriggeredExperiment(
            root=ROOT,
            generator=generator,
            retriever=retriever,
            reranker=CohereReranker(),
            dsn=os.environ.get("DATABASE_URL", DEFAULT_DSN),
            output_dir=ROOT / OUTPUT_DIR,
            rate_card=TokenRateCard(
                model=generator.model,
                input_usd_per_million=args.openai_input_rate,
                cached_input_usd_per_million=args.openai_cached_input_rate,
                output_usd_per_million=args.openai_output_rate,
                source_url=OPENAI_PRICING_URL,
                checked_at=args.pricing_checked_at,
            ),
            rerank_rate_card=RerankRateCard(
                model=COHERE_RERANK_MODEL,
                input_usd_per_million=args.cohere_input_rate,
                source_url=COHERE_PRICING_URL,
                checked_at=args.pricing_checked_at,
                account_tier=args.cohere_account_tier,
            ),
            approved_run=True,
            resume=args.resume,
            continue_after_stop=args.continue_after_stop,
        )
        state = experiment.run()
    except Exception as error:
        print(f"FS-03 experiment stopped: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
    print(json.dumps({
        "status": state["status"],
        "stop_reason": state["stop_reason"],
        "initial_requests_used": state["initial_requests_used"],
        "retry_budget": state["retry_budget"],
        "checkpoint": str((ROOT / OUTPUT_DIR / "checkpoint.json").relative_to(ROOT)),
    }, indent=2))
    return 0 if state["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
