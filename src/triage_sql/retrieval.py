"""Versioned dense, BM25, and RRF retrieval for structured Azraq context."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import re
import sys
from pathlib import Path
from typing import Protocol

import chromadb
from huggingface_hub import snapshot_download, try_to_load_from_cache
from rank_bm25 import BM25Okapi

from triage_sql.schema import load_schema
from triage_sql.schema_context import context_records, relationship_records
from triage_sql.rerank import CohereReranker


FORMAT_VERSION = 2
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
RRF_K = 60
_TOKEN = re.compile(r"[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*")


class Encoder(Protocol):
    model_name: str
    revision: str

    def encode(self, texts: list[str]) -> list[list[float]]: ...


class SentenceTransformerEncoder:
    def __init__(self, model_name: str = DEFAULT_MODEL, revision: str | None = None, device: str | None = None):
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        requested_revision = revision or (DEFAULT_MODEL_REVISION if model_name == DEFAULT_MODEL else None)
        cached_modules = try_to_load_from_cache(model_name, "modules.json", revision=requested_revision or "main")
        if isinstance(cached_modules, str):
            snapshot_path = Path(cached_modules).parent
        else:
            snapshot_path = Path(snapshot_download(model_name, revision=requested_revision))
        self.revision = snapshot_path.name
        self._model = SentenceTransformer(str(snapshot_path), device=device)

    def encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return vectors.tolist()


class StaleIndexError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for token in _TOKEN.findall(text.casefold()):
        tokens.append(token)
        tokens.extend(part for part in token.split("_") if part != token)
    return tokens


def reciprocal_rank_fusion(rankings: list[list[str]], limit: int, k: int = RRF_K) -> list[str]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda item_id: (-scores[item_id], item_id))[:limit]


class SchemaRetriever:
    def __init__(
        self,
        ddl_path: Path,
        relationships_path: Path,
        observations_path: Path,
        index_dir: Path,
        encoder: Encoder | None = None,
        snapshot_manifest_path: Path | None = None,
    ):
        self.ddl_path = ddl_path
        self.relationships_path = relationships_path
        self.observations_path = observations_path
        self.index_dir = index_dir
        self.snapshot_manifest_path = snapshot_manifest_path
        self.manifest_path = index_dir / "manifest.json"
        self.records_path = index_dir / "records.json"
        self.encoder = encoder or SentenceTransformerEncoder()
        self._chroma_client = None
        self._chroma_collection = None
        self._bm25_ids: list[str] | None = None
        self._bm25_index = None

    def _source_manifest(self) -> dict:
        snapshot_identity = None
        snapshot_hash = None
        if self.snapshot_manifest_path is not None and self.snapshot_manifest_path.exists():
            snapshot = json.loads(self.snapshot_manifest_path.read_text(encoding="utf-8"))
            snapshot_identity = snapshot.get("dataset_snapshot_id")
            snapshot_hash = _sha256(self.snapshot_manifest_path)
        return {
            "schema_sha256": _sha256(self.ddl_path),
            "relationships_sha256": _sha256(self.relationships_path),
            "observations_sha256": _sha256(self.observations_path),
            "dataset_snapshot_id": snapshot_identity,
            "snapshot_manifest_sha256": snapshot_hash,
            "record_format_version": FORMAT_VERSION,
            "encoder": {"model": self.encoder.model_name, "revision": self.encoder.revision},
            "runtime": {"python": ".".join(map(str, sys.version_info[:3])), "architecture": platform.machine()},
            "libraries": {
                package: importlib.metadata.version(package)
                for package in ("chromadb", "sentence-transformers", "rank-bm25", "torch")
            },
        }

    def _load_records(self) -> list[dict]:
        tables = load_schema(self.ddl_path, self.observations_path)
        relationships = relationship_records(self.relationships_path)
        return list(context_records(tables, relationships))

    def is_stale(self) -> bool:
        if (
            not self.manifest_path.exists()
            or not self.records_path.exists()
            or not (self.index_dir / "chroma" / "chroma.sqlite3").exists()
        ):
            return True
        try:
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return True
        return manifest.get("sources") != self._source_manifest()

    def build(self) -> dict:
        """Replace the local index deterministically from current source identities."""
        self.index_dir.mkdir(parents=True, exist_ok=True)
        records = self._load_records()
        texts = [record["searchable_text"] for record in records]
        ids = [record["id"] for record in records]
        if len(ids) != len(set(ids)):
            raise ValueError("schema retrieval record IDs must be unique")

        vectors = self.encoder.encode(texts)
        client = chromadb.PersistentClient(path=str(self.index_dir / "chroma"))
        try:
            client.delete_collection("azraq_schema")
        except Exception as exc:
            if "does not exist" not in str(exc).casefold():
                raise
        collection = client.create_collection("azraq_schema", metadata={"hnsw:space": "cosine"})
        collection.add(
            ids=ids,
            documents=texts,
            metadatas=[{"kind": record["kind"]} for record in records],
            embeddings=vectors,
        )
        self._chroma_client = client
        self._chroma_collection = collection
        self._bm25_ids = None
        self._bm25_index = None

        self.records_path.write_text(json.dumps(records, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest = {
            "sources": self._source_manifest(),
            "record_count": len(records),
            "table_count": sum(record["kind"] == "table" for record in records),
            "relationship_count": sum(record["kind"] == "relationship" for record in records),
            "record_ids_sha256": hashlib.sha256("\n".join(ids).encode()).hexdigest(),
        }
        self.manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return manifest

    def ensure_fresh(self) -> None:
        if self.is_stale():
            raise StaleIndexError("Azraq retrieval index is stale; rebuild it from current inputs")

    def _records_by_id(self) -> dict[str, dict]:
        records = json.loads(self.records_path.read_text(encoding="utf-8"))
        return {record["id"]: record for record in records}

    def _dense(self, query: str, top_k: int) -> list[str]:
        if self._chroma_collection is None:
            self._chroma_client = chromadb.PersistentClient(path=str(self.index_dir / "chroma"))
            self._chroma_collection = self._chroma_client.get_collection("azraq_schema")
        result = self._chroma_collection.query(query_embeddings=self.encoder.encode([query]), n_results=top_k)
        return result["ids"][0]

    def _lexical(self, query: str, records: dict[str, dict], top_k: int) -> list[str]:
        if self._bm25_index is None:
            self._bm25_ids = list(records)
            self._bm25_index = BM25Okapi([_tokens(records[item]["searchable_text"]) for item in self._bm25_ids])
        assert self._bm25_ids is not None
        scores = self._bm25_index.get_scores(_tokens(query))
        ranked = sorted(range(len(self._bm25_ids)), key=lambda index: (-float(scores[index]), index))
        return [self._bm25_ids[index] for index in ranked[:top_k]]

    def search(
        self,
        query: str,
        mode: str = "hybrid",
        top_k: int = 5,
        candidate_k: int = 20,
        reranker: CohereReranker | None = None,
    ) -> list[dict]:
        if mode not in {"dense", "bm25", "hybrid", "hybrid-rerank"}:
            raise ValueError("mode must be dense, bm25, hybrid, or hybrid-rerank")
        if top_k < 1 or candidate_k < top_k:
            raise ValueError("candidate_k must be at least top_k and top_k must be positive")
        self.ensure_fresh()
        records = self._records_by_id()
        limit = min(candidate_k, len(records))
        if mode == "dense":
            ranked_ids = self._dense(query, limit)[:top_k]
        elif mode == "bm25":
            ranked_ids = self._lexical(query, records, limit)[:top_k]
        else:
            dense = self._dense(query, limit)
            lexical = self._lexical(query, records, limit)
            ranked_ids = reciprocal_rank_fusion([dense, lexical], limit)
            ranked_records = [records[item_id] for item_id in ranked_ids]
            if mode == "hybrid-rerank":
                if reranker is None:
                    raise ValueError("hybrid-rerank requires explicit CohereReranker configuration")
                return reranker.rerank(query, ranked_records, top_k)
            return ranked_records[:top_k]
        return [records[item_id] for item_id in ranked_ids]


def rebuild_index(retriever: SchemaRetriever) -> dict:
    return retriever.build()
