"""
Agentic StudyMate — BM25 Keyword Search Store

Provides traditional keyword-based search using the BM25 (Okapi) algorithm.
Complements vector search by catching exact keyword matches that semantic
search might miss (e.g., acronyms, specific terms, formulas).

Design:
- Maintains an in-memory BM25 index built from DB chunks
- Supports incremental add/remove by document
- Tokenizes using simple whitespace + punctuation splitting
- Returns ranked chunk IDs with scores
"""

import re
import asyncio
from dataclasses import dataclass, field
from rank_bm25 import BM25Okapi

from app.config import get_settings


@dataclass
class BM25Result:
    """A single BM25 search result."""
    chunk_id: str
    document_id: str
    content: str
    page_number: int | None
    section_title: str | None
    chunk_index: int
    score: float
    source: str = "bm25"


def _tokenize(text: str) -> list[str]:
    """
    Simple tokenizer for BM25.
    
    Lowercases, removes punctuation, splits on whitespace.
    Keeps numbers and basic alphanumeric tokens.
    """
    text = text.lower()
    # Replace non-alphanumeric chars (except spaces) with spaces
    text = re.sub(r"[^\w\s]", " ", text)
    # Split and filter empty tokens
    tokens = [t for t in text.split() if len(t) > 1]
    return tokens


class BM25Store:
    """
    In-memory BM25 index for keyword search.
    
    The index is rebuilt from the database on startup,
    and updated incrementally when documents are added/removed.
    """

    def __init__(self):
        self._corpus: list[list[str]] = []       # Tokenized documents
        self._chunk_data: list[dict] = []         # Chunk metadata
        self._bm25: BM25Okapi | None = None
        self._initialized = False

    async def initialize_from_db(self):
        """
        Build the BM25 index from all chunks in the database.
        Called once at startup.
        """
        from app.db.session import async_session_factory
        from app.models.db_models import Chunk, Document
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload

        async with async_session_factory() as db:
            result = await db.execute(
                select(Chunk).options(joinedload(Chunk.document))
            )
            chunks = result.scalars().all()

        if not chunks:
            self._initialized = True
            print("✓ BM25 index initialized (empty — no chunks yet)")
            return

        self._corpus = []
        self._chunk_data = []

        for chunk in chunks:
            tokens = _tokenize(chunk.content)
            self._corpus.append(tokens)
            self._chunk_data.append({
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "content": chunk.content,
                "page_number": chunk.page_number,
                "section_title": chunk.section_title,
                "chunk_index": chunk.chunk_index,
            })

        self._bm25 = BM25Okapi(self._corpus)
        self._initialized = True
        print(f"✓ BM25 index initialized with {len(self._corpus)} chunks")

    def add_chunks(self, chunks: list[dict]):
        """
        Add new chunks to the BM25 index (called after document ingestion).
        
        Args:
            chunks: List of dicts with keys: chunk_id, document_id, content,
                     page_number, section_title, chunk_index
        """
        for chunk in chunks:
            tokens = _tokenize(chunk["content"])
            self._corpus.append(tokens)
            self._chunk_data.append(chunk)

        # Rebuild BM25 index (fast for small-medium corpora)
        if self._corpus:
            self._bm25 = BM25Okapi(self._corpus)

    def remove_document(self, document_id: str):
        """
        Remove all chunks belonging to a document from the index.
        
        Args:
            document_id: The document to remove
        """
        # Find indices to remove
        indices_to_remove = set()
        for i, data in enumerate(self._chunk_data):
            if data["document_id"] == document_id:
                indices_to_remove.add(i)

        if not indices_to_remove:
            return

        # Rebuild without removed indices
        self._corpus = [c for i, c in enumerate(self._corpus) if i not in indices_to_remove]
        self._chunk_data = [d for i, d in enumerate(self._chunk_data) if i not in indices_to_remove]

        # Rebuild BM25
        if self._corpus:
            self._bm25 = BM25Okapi(self._corpus)
        else:
            self._bm25 = None

    async def search(
        self,
        query: str,
        document_ids: list[str] | None = None,
        top_k: int = 20,
    ) -> list[BM25Result]:
        """
        Search chunks using BM25 keyword matching.
        
        Args:
            query: The search query string
            document_ids: Optional filter to specific documents
            top_k: Number of results to return
            
        Returns:
            List of BM25Result objects, sorted by score descending
        """
        if not self._bm25 or not self._corpus:
            return []

        def _search():
            query_tokens = _tokenize(query)
            if not query_tokens:
                return []

            scores = self._bm25.get_scores(query_tokens)

            # Pair scores with chunk data
            scored_results = []
            for i, score in enumerate(scores):
                if score <= 0:
                    continue

                data = self._chunk_data[i]

                # Apply document filter if specified
                if document_ids and data["document_id"] not in document_ids:
                    continue

                scored_results.append(BM25Result(
                    chunk_id=data["chunk_id"],
                    document_id=data["document_id"],
                    content=data["content"],
                    page_number=data["page_number"],
                    section_title=data["section_title"],
                    chunk_index=data["chunk_index"],
                    score=float(score),
                ))

            # Sort by score descending and take top_k
            scored_results.sort(key=lambda x: x.score, reverse=True)
            return scored_results[:top_k]

        return await asyncio.to_thread(_search)


# Singleton
_bm25_store: BM25Store | None = None


def get_bm25_store() -> BM25Store:
    """Get or create the singleton BM25 store instance."""
    global _bm25_store
    if _bm25_store is None:
        _bm25_store = BM25Store()
    return _bm25_store
