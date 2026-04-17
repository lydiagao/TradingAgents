"""
§8.2 Vector store — ChromaDB + sentence-transformers all-MiniLM-L6-v2.

Key feature: `sim_date` filter on retrieval prevents look-ahead bias in backtests.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import chromadb
from chromadb.config import Settings

log = logging.getLogger(__name__)


def _iso_to_epoch(iso_str: str) -> float:
    """Convert ISO8601 date string to epoch seconds for ChromaDB numeric filtering."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.timestamp()
    except (ValueError, AttributeError):
        return 0.0


# Lazy-loaded embedding function (avoids importing torch at module level)
_embed_fn = None


def _get_embed_fn():
    global _embed_fn
    if _embed_fn is None:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        _embed_fn = SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
    return _embed_fn


class VectorStore:
    """ChromaDB-backed vector store for market intelligence.

    Collection: `market_intel`
    Metadata: source, tickers (comma-separated), published_at (ISO8601), doc_type
    """

    def __init__(self, persist_dir: str = ".chroma_data"):
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name="market_intel",
            embedding_function=_get_embed_fn(),
        )

    @property
    def count(self) -> int:
        return self._collection.count()

    def ingest(
        self,
        doc_id: str,
        text: str,
        metadata: dict[str, Any],
    ) -> None:
        """Add or update a document.

        Required metadata keys: source, published_at (ISO8601 string).
        Optional: tickers (comma-separated), doc_type.

        Note: published_at is stored BOTH as string (published_at) and as
        epoch float (published_epoch) for ChromaDB $lte filtering.
        """
        metadata = dict(metadata)  # copy
        if "published_at" in metadata:
            metadata["published_epoch"] = _iso_to_epoch(metadata["published_at"])
        self._collection.upsert(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata],
        )

    def ingest_batch(
        self,
        ids: list[str],
        texts: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        enriched = []
        for m in metadatas:
            m = dict(m)
            if "published_at" in m:
                m["published_epoch"] = _iso_to_epoch(m["published_at"])
            enriched.append(m)
        self._collection.upsert(ids=ids, documents=texts, metadatas=enriched)

    def retrieve(
        self,
        query: str,
        n: int = 10,
        sim_date: datetime | None = None,
        tickers: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve top-N similar documents.

        Args:
            query: search query text.
            n: max results.
            sim_date: if set, only return docs with published_at <= sim_date.
                      CRITICAL for backtest correctness (§8.2).
            tickers: optional ticker filter.

        Returns:
            List of dicts with 'id', 'document', 'metadata', 'distance'.
        """
        where: dict | None = None
        conditions = []

        if sim_date is not None:
            epoch = sim_date.replace(tzinfo=timezone.utc).timestamp() if sim_date.tzinfo is None else sim_date.timestamp()
            conditions.append({"published_epoch": {"$lte": epoch}})
        if tickers:
            # ChromaDB doesn't support $in on string fields directly;
            # filter by checking if the tickers metadata contains the value.
            # For now, use a single ticker filter if provided.
            if len(tickers) == 1:
                conditions.append({"tickers": {"$eq": tickers[0]}})

        if len(conditions) == 1:
            where = conditions[0]
        elif len(conditions) > 1:
            where = {"$and": conditions}

        results = self._collection.query(
            query_texts=[query],
            n_results=n,
            where=where,
        )

        docs = []
        if results and results.get("ids"):
            for i, doc_id in enumerate(results["ids"][0]):
                docs.append({
                    "id": doc_id,
                    "document": results["documents"][0][i] if results.get("documents") else "",
                    "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                    "distance": results["distances"][0][i] if results.get("distances") else None,
                })
        return docs

    def delete_older_than(self, cutoff: datetime) -> int:
        """Purge docs older than cutoff (180-day retention per §8.2)."""
        epoch = cutoff.replace(tzinfo=timezone.utc).timestamp() if cutoff.tzinfo is None else cutoff.timestamp()
        all_data = self._collection.get(
            where={"published_epoch": {"$lt": epoch}},
        )
        if all_data and all_data["ids"]:
            self._collection.delete(ids=all_data["ids"])
            return len(all_data["ids"])
        return 0
