"""Application configuration using pydantic-settings.

All configuration is read from environment variables or a .env file.
Never use os.environ.get() directly in service or router code —
always import `settings` from this module.
"""
import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Required fields (no default — must be set in environment or .env):
        OPENAI_API_KEY: OpenAI API key for GPT-4o and embeddings.
        DATABASE_URL: Async-compatible PostgreSQL URL.

    Optional fields (have sensible defaults for development):
        CHROMA_PERSIST_DIR: Directory for ChromaDB persistence.
        OPENAI_MODEL: GPT model to use for analysis.
        EMBEDDING_MODEL: OpenAI embedding model for RAG.
        RAG_TOP_K: Number of RAG results per retrieval query.
        OPENAI_TIMEOUT_SECONDS: Timeout for per-stock OpenAI calls.
        ENVIRONMENT: Runtime environment (development / production).
        CORS_ORIGINS: Comma-separated list of allowed CORS origins.
        LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR).
    """

    # Required — no defaults
    OPENAI_API_KEY: str
    DATABASE_URL: str

    # Optional with defaults
    CHROMA_PERSIST_DIR: str = "./rag_data"
    OPENAI_MODEL: str = "gpt-4o"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    RAG_TOP_K: int = 3
    OPENAI_TIMEOUT_SECONDS: int = 30
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: str = "http://localhost:3000"
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Allow extra fields to avoid errors when .env has additional vars
        extra="ignore",
    )


# Module-level singleton — import this everywhere
# Guards against missing .env in test environments by checking for env vars.
# The test suite overrides via direct instantiation with kwargs.
try:
    settings = Settings()
except Exception as _settings_exc:
    if os.environ.get("TESTING") != "1":
        raise RuntimeError(
            "Failed to load application settings. "
            "Ensure OPENAI_API_KEY and DATABASE_URL are set in your environment or .env file. "
            f"Original error: {_settings_exc}"
        ) from _settings_exc
    # In test environments (TESTING=1), allow settings=None so modules can import
    # without a real .env file. Tests that need specific settings create their own
    # Settings instances directly.
    settings = None  # type: ignore[assignment]
