"""Model-neutral SQL generation interface with an optional OpenAI Responses adapter."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Protocol

from dotenv import find_dotenv, load_dotenv


@dataclass(frozen=True)
class Generation:
    text: str
    input_tokens: int | None
    latency_ms: float
    model: str
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    cached_input_tokens: int | None = None


class SQLGenerator(Protocol):
    model: str

    def generate(self, prompt: str) -> Generation: ...


class OpenAIResponsesGenerator:
    """Uses the Responses API; model must be passed or set as OPENAI_MODEL."""

    def __init__(self, model: str | None = None, client=None):
        load_dotenv(find_dotenv(usecwd=True), override=False)
        self.model = model or os.environ.get("OPENAI_MODEL", "")
        self.reasoning_effort = os.environ.get("OPENAI_REASONING_EFFORT")
        if not self.model:
            raise ValueError("set OPENAI_MODEL or pass a model to run SQL-generation evaluation")
        if client is None:
            import openai

            client = openai.OpenAI()
        self.client = client

    def generate(self, prompt: str) -> Generation:
        start = time.perf_counter()
        request = dict(
            model=self.model,
            instructions=(
                "Generate one read-only PostgreSQL SELECT query for the question. "
                "Use only the supplied schema context. Return SQL only, without Markdown. "
                "Never reference credentials or the users.password column."
            ),
            input=prompt,
            max_output_tokens=512,
        )
        if self.reasoning_effort:
            request["reasoning"] = {"effort": self.reasoning_effort}
        response = self.client.responses.create(**request)
        elapsed = (time.perf_counter() - start) * 1000
        usage = getattr(response, "usage", None)
        input_details = getattr(usage, "input_tokens_details", None)
        output_details = getattr(usage, "output_tokens_details", None)
        return Generation(
            text=str(response.output_text).strip(),
            input_tokens=getattr(usage, "input_tokens", None),
            latency_ms=elapsed,
            model=self.model,
            output_tokens=getattr(usage, "output_tokens", None),
            reasoning_tokens=getattr(output_details, "reasoning_tokens", None),
            cached_input_tokens=getattr(input_details, "cached_tokens", None),
        )
