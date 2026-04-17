"""
P2-T15 test: vector store sim_date filter prevents look-ahead bias.

Ingest 3 docs with known dates, query at a middle date, assert only
docs with published_at <= sim_date are returned.
"""

from __future__ import annotations

import shutil
import tempfile
from datetime import datetime

import pytest

from tradingagents.memory.vector_store import VectorStore


@pytest.fixture
def store():
    tmpdir = tempfile.mkdtemp()
    vs = VectorStore(persist_dir=tmpdir)
    # Ingest 3 docs with known dates
    vs.ingest("doc_jan", "IonQ announces 32 qubit processor",
              {"source": "test", "published_at": "2024-01-15T00:00:00Z", "doc_type": "news"})
    vs.ingest("doc_jun", "Google Willow below-threshold error correction",
              {"source": "test", "published_at": "2024-06-15T00:00:00Z", "doc_type": "news"})
    vs.ingest("doc_dec", "IBM roadmap update for 2025",
              {"source": "test", "published_at": "2024-12-01T00:00:00Z", "doc_type": "news"})
    yield vs
    shutil.rmtree(tmpdir, ignore_errors=True)


class TestSimDateFilter:

    def test_no_sim_date_returns_all(self, store: VectorStore):
        results = store.retrieve("quantum processor", n=10, sim_date=None)
        assert len(results) == 3

    def test_sim_date_june_returns_only_jan_and_jun(self, store: VectorStore):
        sim = datetime(2024, 6, 15)
        results = store.retrieve("quantum processor", n=10, sim_date=sim)
        ids = {r["id"] for r in results}
        assert "doc_jan" in ids
        assert "doc_jun" in ids
        assert "doc_dec" not in ids, "Look-ahead! doc_dec (Dec 2024) returned at sim_date June"

    def test_sim_date_january_returns_only_jan(self, store: VectorStore):
        sim = datetime(2024, 1, 31)
        results = store.retrieve("quantum processor", n=10, sim_date=sim)
        ids = {r["id"] for r in results}
        assert "doc_jan" in ids
        assert "doc_jun" not in ids
        assert "doc_dec" not in ids

    def test_sim_date_before_all_returns_empty(self, store: VectorStore):
        sim = datetime(2023, 1, 1)
        results = store.retrieve("quantum processor", n=10, sim_date=sim)
        assert len(results) == 0


class TestBasicOps:

    def test_count(self, store: VectorStore):
        assert store.count == 3

    def test_retrieve_returns_metadata(self, store: VectorStore):
        results = store.retrieve("IonQ", n=1)
        assert len(results) >= 1
        assert "metadata" in results[0]
        assert results[0]["metadata"]["source"] == "test"
