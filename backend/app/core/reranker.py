"""
Agentic StudyMate — Cross-Encoder Reranker

Second-stage reranker using cross-encoder/ms-marco-MiniLM-L-6-v2.

Why rerank?
- First-stage retrieval (vector + BM25) optimizes for recall (find everything relevant)
- Reranking optimizes for precision (keep only the best matches)
- Cross-encoders score query-document pairs jointly, giving much higher accuracy
  than bi-encoders, but are too slow for full-corpus search

Pipeline position:
    Query → Hybrid Retrieval (top 20) → Reranker (top 5) → LLM

Design:
- Model loaded lazily on first use
- Inference runs in a thread (CPU-only, via asyncio.to_thread)
- Batch scoring for efficiency
"""

import asyncio
from dataclasses import dataclass
from app.config import get_settings
from app.core.retrieval.hybrid import RetrievalResult


@dataclass
class RerankResult:
    """A reranked retrieval result with the cross-encoder score."""
    chunk_id: str
    document_id: str
    content: str
    page_number: int | None = None
    section_title: str | None = None
    chunk_index: int = 0
    rerank_score: float = 0.0
    rrf_score: float = 0.0
    sources: list[str] | None = None


class Reranker:
    """
    Cross-encoder reranker (CPU-only).
    
    Uses cross-encoder/ms-marco-MiniLM-L-6-v2 which was trained on
    MS MARCO passage ranking — well-suited for document QA.
    
    Lazily loads the model on first use to keep startup fast.
    """

    def __init__(self):
        self._model = None
        self._settings = get_settings()

    def _load_model(self):
        """Load the cross-encoder model (lazy initialization)."""
        if self._model is None:
            from sentence_transformers import CrossEncoder
            print(f"⏳ Loading reranker model: {self._settings.RERANKER_MODEL}")
            self._model = CrossEncoder(
                self._settings.RERANKER_MODEL,
                device="cpu",
            )
            print(f"✓ Reranker model loaded")

    def _score_sync(self, query: str, documents: list[str]) -> list[float]:
        """Synchronous scoring — runs in thread."""
        self._load_model()
        pairs = [(query, doc) for doc in documents]
        scores = self._model.predict(pairs, batch_size=32, show_progress_bar=False)
        return [float(s) for s in scores]

    async def rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
        top_n: int | None = None,
    ) -> list[RerankResult]:
        """
        Rerank retrieval candidates using the cross-encoder.
        
        Args:
            query: The original user query
            candidates: Results from hybrid retrieval
            top_n: Number of top results to keep (default from settings)
            
        Returns:
            Reranked results sorted by cross-encoder score, top_n only
        """
        if not candidates:
            return []

        settings = get_settings()
        if top_n is None:
            top_n = settings.RERANK_TOP_N

        # Extract document texts
        documents = [c.content for c in candidates]

        # Score all pairs (query, document)
        scores = await asyncio.to_thread(self._score_sync, query, documents)

        # Build reranked results
        reranked = []
        for candidate, score in zip(candidates, scores):
            reranked.append(RerankResult(
                chunk_id=candidate.chunk_id,
                document_id=candidate.document_id,
                content=candidate.content,
                page_number=candidate.page_number,
                section_title=candidate.section_title,
                chunk_index=candidate.chunk_index,
                rerank_score=score,
                rrf_score=candidate.rrf_score,
                sources=candidate.sources,
            ))

        # Sort by rerank score (highest = most relevant)
        reranked.sort(key=lambda x: x.rerank_score, reverse=True)

        # Return top_n
        return reranked[:top_n]


# Singleton
_reranker: Reranker | None = None


def get_reranker() -> Reranker:
    """Get or create the singleton reranker instance."""
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker
