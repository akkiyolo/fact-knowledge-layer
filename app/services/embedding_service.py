"""
Embedding Service abstraction.
Provides a generic interface with a local Sentence Transformers implementation.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingService(ABC):
    """Abstract embedding service interface."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts. Returns list of vectors."""
        ...

    @abstractmethod
    def embed_single(self, text: str) -> list[float]:
        """Embed a single text. Returns a vector."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension."""
        ...


class LocalEmbeddingService(EmbeddingService):
    """Local Sentence Transformers embedding service."""

    def __init__(self):
        settings = get_settings()
        self.model_name = settings.embedding_model
        self._dimension = settings.embedding_dimension
        self._model = None

    def _load_model(self):
        """Lazy-load the embedding model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info("Loading embedding model: %s", self.model_name)
                self._model = SentenceTransformer(self.model_name)
                # Verify dimension
                test_emb = self._model.encode(["test"])
                actual_dim = len(test_emb[0])
                if actual_dim != self._dimension:
                    logger.warning(
                        "Configured EMBEDDING_DIMENSION=%d but model produces %d. "
                        "Using actual dimension.",
                        self._dimension,
                        actual_dim,
                    )
                    self._dimension = actual_dim
                logger.info(
                    "Embedding model loaded: %s (dim=%d)",
                    self.model_name,
                    self._dimension,
                )
            except ImportError:
                raise RuntimeError(
                    "sentence-transformers is required for local embeddings. "
                    "Install with: pip install sentence-transformers"
                )
            except Exception as e:
                raise RuntimeError(
                    f"Failed to load embedding model '{self.model_name}': {e}"
                )

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts."""
        if not texts:
            return []
        self._load_model()
        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()

    def embed_single(self, text: str) -> list[float]:
        """Embed a single text string."""
        results = self.embed([text])
        return results[0] if results else []

    @property
    def dimension(self) -> int:
        return self._dimension


# ── Singleton ────────────────────────────────────────────────

_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get the configured embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        settings = get_settings()
        if settings.embedding_provider == "local":
            _embedding_service = LocalEmbeddingService()
        else:
            raise ValueError(
                f"Unsupported embedding provider: {settings.embedding_provider}. "
                f"Currently supported: 'local'"
            )
    return _embedding_service
