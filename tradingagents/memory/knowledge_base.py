"""
§8.3 Knowledge base — seed markdown files under memory/kb/.

Ingests static quantum domain knowledge into the vector store for RAG.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

from .vector_store import VectorStore

log = logging.getLogger(__name__)

KB_DIR = Path(__file__).parent / "kb"


def ingest_kb(store: VectorStore) -> int:
    """Ingest all .md files from memory/kb/ into the vector store.

    Returns count of files ingested.
    """
    if not KB_DIR.exists():
        log.warning("KB directory %s does not exist", KB_DIR)
        return 0

    count = 0
    for md_file in sorted(KB_DIR.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        doc_id = f"kb_{hashlib.md5(md_file.name.encode()).hexdigest()}"
        metadata = {
            "source": "knowledge_base",
            "doc_type": "kb",
            "published_at": "2024-01-01T00:00:00Z",  # static KB, always retrievable
            "filename": md_file.name,
        }
        store.ingest(doc_id, text, metadata)
        count += 1
        log.info("Ingested KB: %s (%d chars)", md_file.name, len(text))

    return count
