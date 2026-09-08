"""
Document orchestration service.
Manages the high-level flow of document ingestion.
"""

import logging
import hashlib
import shutil
from pathlib import Path
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


class DocumentService:
    """Handles file management for uploaded documents."""

    def __init__(self):
        settings = get_settings()
        self.upload_dir = Path(settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = settings.max_upload_size_mb * 1024 * 1024

    def save_upload(self, filename: str, content: bytes) -> Path:
        """
        Save uploaded file to the upload directory.
        Returns the path to the saved file.
        """
        if len(content) > self.max_size_bytes:
            raise ValueError(
                f"File too large: {len(content)} bytes "
                f"(max {self.max_size_bytes} bytes)"
            )

        # Sanitize filename
        safe_name = Path(filename).name  # Remove path components
        if not safe_name.lower().endswith(".pdf"):
            raise ValueError("Only PDF files are accepted")

        dest = self.upload_dir / safe_name

        # Handle name collision by appending counter
        counter = 1
        while dest.exists():
            stem = Path(safe_name).stem
            dest = self.upload_dir / f"{stem}_{counter}.pdf"
            counter += 1

        dest.write_bytes(content)
        logger.info("Saved upload: %s (%d bytes)", dest.name, len(content))
        return dest

    @staticmethod
    def compute_content_hash(content: bytes) -> str:
        """Compute SHA-256 hash of raw file content."""
        return hashlib.sha256(content).hexdigest()
