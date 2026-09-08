"""
Centralized application configuration.
All settings are read from environment variables.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── Application ──────────────────────────────────────────
    app_name: str = Field(default="Fact Knowledge Layer", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    # ── Database (Render PostgreSQL) ─────────────────────────
    database_url: str = Field(..., alias="DATABASE_URL")

    # ── LLM ──────────────────────────────────────────────────
    llm_provider: str = Field(default="ollama", alias="LLM_PROVIDER")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="qwen3:8b", alias="OLLAMA_MODEL")
    google_api_key: str | None = Field(default=None, alias="GOOGLE_API_KEY")
    google_model: str = Field(default="gemini-2.5-flash", alias="GOOGLE_MODEL")

    # ── Embeddings ───────────────────────────────────────────
    embedding_provider: str = Field(default="local", alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(default="BAAI/bge-small-en-v1.5", alias="EMBEDDING_MODEL")
    embedding_dimension: int = Field(default=384, alias="EMBEDDING_DIMENSION")

    # ── Claim Extraction ─────────────────────────────────────
    claim_confidence_threshold: float = Field(default=0.70, alias="CLAIM_CONFIDENCE_THRESHOLD")
    grounding_confidence_threshold: float = Field(default=0.70, alias="GROUNDING_CONFIDENCE_THRESHOLD")
    max_claims_per_chunk: int = Field(default=30, alias="MAX_CLAIMS_PER_CHUNK")

    # ── Vector Retrieval ─────────────────────────────────────
    candidate_top_k: int = Field(default=10, alias="CANDIDATE_TOP_K")
    candidate_similarity_threshold: float = Field(default=0.70, alias="CANDIDATE_SIMILARITY_THRESHOLD")

    # ── Attribute Canonicalization ────────────────────────────
    attribute_similarity_threshold: float = Field(default=0.85, alias="ATTRIBUTE_SIMILARITY_THRESHOLD")

    # ── PDF Chunking ─────────────────────────────────────────
    max_chunk_tokens: int = Field(default=1200, alias="MAX_CHUNK_TOKENS")
    chunk_overlap_tokens: int = Field(default=150, alias="CHUNK_OVERLAP_TOKENS")

    # ── File Storage ─────────────────────────────────────────
    upload_dir: str = Field(default="data/uploads", alias="UPLOAD_DIR")
    sample_dir: str = Field(default="data/sample", alias="SAMPLE_DIR")
    max_upload_size_mb: int = Field(default=50, alias="MAX_UPLOAD_SIZE_MB")

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v:
            raise ValueError(
                "DATABASE_URL is required. Set it to your Render PostgreSQL external URL."
            )
        # Ensure psycopg driver for SQLAlchemy 2.0+
        if v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v

    @property
    def database_url_safe(self) -> str:
        """Return a masked version of the DB URL for logging."""
        if not self.database_url:
            return "<not set>"
        try:
            # Mask everything between :// and @
            prefix, rest = self.database_url.split("://", 1)
            if "@" in rest:
                _, host_part = rest.rsplit("@", 1)
                return f"{prefix}://***:***@{host_part}"
            return f"{prefix}://***"
        except Exception:
            return "<masked>"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


# Singleton
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get cached application settings."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
