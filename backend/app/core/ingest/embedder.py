"""
Agentic StudyMate — Text Embedder

Generates vector embeddings using sentence-transformers (CPU-only).
Uses all-MiniLM-L6-v2 (384-dim) — lightweight and fast on CPU.

Design:
- Model loaded once at module level (singleton)
- All inference runs in a separate thread via asyncio.to_thread
- Batch encoding for efficiency
"""

import asyncio
from dataclasses import dataclass

from app.config import get_settings


@dataclass
class EmbeddingResult:
    """Result of embedding a batch of texts."""
    vectors: list[list[float]]
    dimension: int
    model_name: str


class Embedder:
    """
    Sentence-transformer embedder (CPU-only).
    
    Lazily loads the model on first use to avoid slow imports at startup.
    """

    def __init__(self):
        self._model = None
        self._settings = get_settings()

    def _load_model(self):
        """Load the embedding model (lazy initialization)."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            print(f"⏳ Loading embedding model: {self._settings.EMBEDDING_MODEL}")
            self._model = SentenceTransformer(
                self._settings.EMBEDDING_MODEL,
                device="cpu",
            )
            print(f"✓ Embedding model loaded ({self._model.get_sentence_embedding_dimension()}D)")

    def _encode_sync(self, texts: list[str]) -> list[list[float]]:
        """Synchronous encoding — runs in thread."""
        self._load_model()
        vectors = self._model.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True,  # Cosine similarity works better with normalized vectors
        )
        return vectors.tolist()

    async def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        """
        Embed a batch of texts asynchronously.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            EmbeddingResult with vectors and metadata
        """
        if not texts:
            return EmbeddingResult(vectors=[], dimension=self._settings.EMBEDDING_DIMENSION, model_name=self._settings.EMBEDDING_MODEL)

        vectors = await asyncio.to_thread(self._encode_sync, texts)

        return EmbeddingResult(
            vectors=vectors,
            dimension=len(vectors[0]) if vectors else self._settings.EMBEDDING_DIMENSION,
            model_name=self._settings.EMBEDDING_MODEL,
        )

    async def embed_query(self, query: str) -> list[float]:
        """
        Embed a single query string.
        
        Args:
            query: The search query to embed
            
        Returns:
            Vector embedding as a list of floats
        """
        result = await self.embed_texts([query])
        return result.vectors[0]


# Singleton instance
_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    """Get or create the singleton embedder instance."""
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder
