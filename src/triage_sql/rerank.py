"""Optional Cohere reranking for an already fused candidate list."""

from __future__ import annotations

import json
import os
from typing import Protocol

from dotenv import find_dotenv, load_dotenv


COHERE_RERANK_MODEL = "rerank-v5.0-fast"


class RerankClient(Protocol):
    def rerank(self, *, model: str, query: str, documents: list[str], top_n: int): ...


class CohereReranker:
    def __init__(self, api_key: str | None = None, client: RerankClient | None = None):
        load_dotenv(find_dotenv(usecwd=True), override=False)
        if client is None:
            key = api_key or os.environ.get("COHERE_API_KEY")
            if not key:
                raise ValueError("COHERE_API_KEY is required only for hybrid-rerank mode")
            import cohere

            client = cohere.ClientV2(api_key=key)
        self.client = client

    def rerank(self, query: str, records: list[dict], top_k: int) -> list[dict]:
        if not records or top_k < 1:
            return []
        documents = [json.dumps(record, sort_keys=True, ensure_ascii=False) for record in records]
        response = self.client.rerank(
            model=COHERE_RERANK_MODEL,
            query=query,
            documents=documents,
            top_n=min(top_k, len(records)),
        )
        return [records[result.index] for result in response.results]
