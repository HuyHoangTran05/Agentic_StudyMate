"""
Agentic StudyMate — Application Settings

Loads configuration from environment variables (.env file).
Supports multi-LLM providers with priority: Groq > Gemini > OpenAI > Anthropic.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # --- Database ---
    DATABASE_URL: str = "sqlite+aiosqlite:///./studymate.db"

    # --- Neo4j Graph Database ---
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""

    # --- LLM API Keys (priority: Groq > Gemini > OpenAI > Anthropic) ---
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # --- Primary Task Models ---
    TEXT_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    VISION_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"

    # --- Provider-Specific Model Names ---
    GROQ_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    GROQ_VISION_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    GEMINI_MODEL: str = "gemini-2.0-flash-lite"
    GEMINI_VISION_MODEL: str = "gemini-2.0-flash-lite"
    OPENAI_MODEL: str = "gpt-4o-mini"
    ANTHROPIC_MODEL: str = "claude-3-haiku-20240307"

    # --- Embedding Model (CPU) ---
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384

    # --- Reranker Model (CPU) ---
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # --- Qdrant ---
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "studymate_chunks"
    VECTOR_SCORE_THRESHOLD: float = 0.75

    # --- Chunking ---
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64

    # --- Retrieval ---
    RETRIEVAL_TOP_K: int = 20
    RERANK_TOP_N: int = 5
    MAX_RETRIES: int = 2

    # --- LLM Rate Limiting ---
    LLM_MAX_CONCURRENT: int = 2       # Max simultaneous LLM API calls
    LLM_MAX_RETRIES: int = 3          # Max retries on 429 errors
    LLM_RETRY_BASE_DELAY: float = 2.0 # Base delay in seconds for exponential backoff
    LLM_RETRY_MAX_DELAY: float = 60.0 # Max delay cap in seconds

    # --- Map-Reduce Batch Processing ---
    BATCH_CHUNK_SIZE: int = 5          # Chunks per LLM call (keep small for Groq free tier)
    BATCH_THROTTLE_DELAY: float = 3.5  # Seconds to wait between batch calls
    REDUCE_COOLDOWN: float = 10.0      # Seconds to wait before the final Reduce call

    # --- Server ---
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    UPLOAD_DIR: str = "uploads"

    model_config = {
        "env_file": ENV_FILE,
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }

    def get_available_llm(self) -> str | None:
        """Return the highest-priority available LLM provider name."""
        if self.GROQ_API_KEY:
            return "groq"
        if self.GEMINI_API_KEY:
            return "gemini"
        if self.OPENAI_API_KEY:
            return "openai"
        if self.ANTHROPIC_API_KEY:
            return "anthropic"
        return None


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — loaded once at startup."""
    return Settings()
