"""
Dynamic attribute canonicalization service.
No fixed vocabulary — discovers canonical forms from the data.
"""

import logging
from typing import Optional

import numpy as np

from app.services.embedding_service import get_embedding_service
from app.config import get_settings

logger = logging.getLogger(__name__)


class AttributeService:
    """
    Dynamically canonicalizes attribute names using embedding similarity.

    For every raw attribute:
    1. Embed it.
    2. Compare to existing canonical attributes.
    3. If similarity exceeds threshold, merge to the existing canonical form.
    4. Otherwise, create a new canonical attribute.

    No predefined attribute list. No domain-specific logic.
    """

    def __init__(self):
        self._canonical_cache: dict[str, list[float]] = {}
        self._threshold = get_settings().attribute_similarity_threshold

    def canonicalize(self, raw_attribute: str) -> str:
        """
        Canonicalize a raw attribute string.
        Returns the canonical form (may be the raw attribute itself if new).
        """
        if not raw_attribute or not raw_attribute.strip():
            return raw_attribute

        raw_clean = raw_attribute.strip().lower()

        # Exact match shortcut
        for canonical in self._canonical_cache:
            if canonical.lower() == raw_clean:
                return canonical

        # Embed the raw attribute
        embedding_service = get_embedding_service()
        raw_embedding = embedding_service.embed_single(raw_attribute)

        if not raw_embedding:
            return raw_attribute

        # Compare against all known canonical attributes
        best_match: Optional[str] = None
        best_similarity: float = 0.0

        for canonical, canon_emb in self._canonical_cache.items():
            sim = self._cosine_similarity(raw_embedding, canon_emb)
            if sim > best_similarity:
                best_similarity = sim
                best_match = canonical

        if best_match and best_similarity >= self._threshold:
            logger.debug(
                "Canonicalized '%s' → '%s' (sim=%.3f)",
                raw_attribute,
                best_match,
                best_similarity,
            )
            return best_match

        # New canonical attribute
        canonical_form = raw_attribute.strip()
        self._canonical_cache[canonical_form] = raw_embedding
        logger.debug("New canonical attribute: '%s'", canonical_form)
        return canonical_form

    def load_existing_attributes(self, attributes: list[str]):
        """
        Pre-load existing canonical attributes from the database.
        Embeds them for future comparisons.
        """
        if not attributes:
            return

        embedding_service = get_embedding_service()
        embeddings = embedding_service.embed(attributes)

        for attr, emb in zip(attributes, embeddings):
            self._canonical_cache[attr] = emb

        logger.info("Loaded %d existing canonical attributes", len(attributes))

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        a_arr = np.array(a)
        b_arr = np.array(b)
        norm_a = np.linalg.norm(a_arr)
        norm_b = np.linalg.norm(b_arr)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a_arr, b_arr) / (norm_a * norm_b))

    @property
    def known_attributes(self) -> list[str]:
        """Return all currently known canonical attributes."""
        return list(self._canonical_cache.keys())
