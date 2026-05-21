"""
Agentic StudyMate — Hybrid Retrieval with Reciprocal Rank Fusion (RRF)

Merges results from two retrieval systems:
1. Vector search (Qdrant) — semantic similarity
2. BM25 search — keyword matching

Uses Reciprocal Rank Fusion (RRF) to combine ranked lists.
RRF is simple, robust, and requires no training:

    RRF_score(d) = Σ  1 / (k + rank_i(d))

where k=60 (standard constant) and rank_i is the rank in each system.

This ensures documents that appear in both lists get boosted,
while documents strong in only one modality still surface.
"""

from dataclasses import dataclass, field

from app.core.ingest.embedder import get_embedder
from app.core.retrieval.vector_store import get_vector_store
from app.core.retrieval.bm25_store import get_bm25_store
from app.config import get_settings


@dataclass
class RetrievalResult:
    """A single unified retrieval result after fusion."""
    chunk_id: str
    document_id: str
    content: str
    page_number: int | None = None
    section_title: str | None = None
    chunk_index: int = 0
    rrf_score: float = 0.0
    vector_score: float | None = None
    bm25_score: float | None = None
    sources: list[str] = field(default_factory=list)  # ["vector", "bm25"]


def rrf_merge(
    bm25_results: list[dict],
    vector_results: list[dict],
    k: int = 60,
) -> list[RetrievalResult]:
    """
    Merge BM25 and vector search results using Reciprocal Rank Fusion.
    
    Args:
        bm25_results: Ranked results from BM25 (list of dicts with chunk_id)
        vector_results: Ranked results from Qdrant (list of dicts with chunk_id)
        k: RRF constant (default 60, standard value)
        
    Returns:
        Merged and deduplicated results sorted by RRF score
    """
    # Track scores and data by chunk_id
    scores: dict[str, float] = {}
    data: dict[str, dict] = {}
    sources: dict[str, list[str]] = {}
    original_scores: dict[str, dict] = {}

    # Process BM25 results
    for rank, result in enumerate(bm25_results):
        chunk_id = result.chunk_id if hasattr(result, "chunk_id") else result["chunk_id"]
        rrf_contribution = 1.0 / (k + rank + 1)
        scores[chunk_id] = scores.get(chunk_id, 0) + rrf_contribution

        if chunk_id not in data:
            data[chunk_id] = {
                "chunk_id": chunk_id,
                "document_id": result.document_id if hasattr(result, "document_id") else result["document_id"],
                "content": result.content if hasattr(result, "content") else result["content"],
                "page_number": result.page_number if hasattr(result, "page_number") else result.get("page_number"),
                "section_title": result.section_title if hasattr(result, "section_title") else result.get("section_title"),
                "chunk_index": result.chunk_index if hasattr(result, "chunk_index") else result.get("chunk_index", 0),
            }
            sources[chunk_id] = []
            original_scores[chunk_id] = {}

        sources[chunk_id].append("bm25")
        bm25_score = result.score if hasattr(result, "score") else result.get("score", 0)
        original_scores[chunk_id]["bm25"] = bm25_score

    # Process vector results
    for rank, result in enumerate(vector_results):
        chunk_id = result["chunk_id"] if isinstance(result, dict) else result.chunk_id
        rrf_contribution = 1.0 / (k + rank + 1)
        scores[chunk_id] = scores.get(chunk_id, 0) + rrf_contribution

        if chunk_id not in data:
            r = result if isinstance(result, dict) else result.__dict__
            data[chunk_id] = {
                "chunk_id": chunk_id,
                "document_id": r.get("document_id", ""),
                "content": r.get("content", ""),
                "page_number": r.get("page_number"),
                "section_title": r.get("section_title"),
                "chunk_index": r.get("chunk_index", 0),
            }
            sources[chunk_id] = []
            original_scores[chunk_id] = {}

        sources[chunk_id].append("vector")
        vector_score = result.get("score", 0) if isinstance(result, dict) else getattr(result, "score", 0)
        original_scores[chunk_id]["vector"] = vector_score

    # Build merged results
    merged = []
    for chunk_id in scores:
        d = data[chunk_id]
        orig = original_scores.get(chunk_id, {})
        merged.append(RetrievalResult(
            chunk_id=d["chunk_id"],
            document_id=d["document_id"],
            content=d["content"],
            page_number=d["page_number"],
            section_title=d["section_title"],
            chunk_index=d["chunk_index"],
            rrf_score=scores[chunk_id],
            vector_score=orig.get("vector"),
            bm25_score=orig.get("bm25"),
            sources=sources[chunk_id],
        ))

    # Sort by RRF score descending
    merged.sort(key=lambda x: x.rrf_score, reverse=True)
    return merged


class HybridRetriever:
    """
    Hybrid retrieval combining vector search and BM25.
    
    Pipeline:
    1. Embed the query using sentence-transformers
    2. Run vector search in Qdrant (semantic)
    3. Run BM25 search (keyword)
    4. Merge results using RRF
    5. Return top-K unified results
    """

    def __init__(self):
        self._embedder = get_embedder()
        self._vector_store = get_vector_store()
        self._bm25_store = get_bm25_store()

    async def search(
        self,
        query: str,
        document_ids: list[str] | None = None,
        top_k: int | None = None,
    ) -> list[RetrievalResult]:
        """
        Perform hybrid search: vector + BM25, merged with RRF.
        
        Args:
            query: The search query
            document_ids: Optional filter to specific documents
            top_k: Number of final results (default from settings)
            
        Returns:
            Merged results sorted by RRF score
        """
        settings = get_settings()
        if top_k is None:
            top_k = settings.RETRIEVAL_TOP_K

        # Run both searches in parallel
        vector_results = []
        bm25_results = []

        # Vector search (may fail if Qdrant is not running)
        try:
            query_vector = await self._embedder.embed_query(query)
            vector_results = await self._vector_store.search(
                query_vector=query_vector,
                document_ids=document_ids,
                top_k=top_k,
            )
        except Exception as e:
            print(f"⚠ Vector search failed (Qdrant may be offline): {e}")

        # BM25 search
        try:
            bm25_results = await self._bm25_store.search(
                query=query,
                document_ids=document_ids,
                top_k=top_k,
            )
        except Exception as e:
            print(f"⚠ BM25 search failed: {e}")

        # If both failed, return empty
        if not vector_results and not bm25_results:
            return []

        # Merge with RRF
        merged = rrf_merge(bm25_results, vector_results)

        # Return top_k
        return merged[:top_k]


# Singleton
_hybrid_retriever: HybridRetriever | None = None


def get_hybrid_retriever() -> HybridRetriever:
    """Get or create the singleton hybrid retriever."""
    global _hybrid_retriever
    if _hybrid_retriever is None:
        _hybrid_retriever = HybridRetriever()
    return _hybrid_retriever
