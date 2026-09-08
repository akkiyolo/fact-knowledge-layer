"""
Node: create_chunks
Page-aware, token-based chunking with overlap.
"""

import logging
import uuid

import tiktoken

from app.pipeline.state import PipelineState, ChunkData
from app.config import get_settings

logger = logging.getLogger(__name__)


def create_chunks(state: PipelineState) -> PipelineState:
    """Create page-aware chunks from extracted PDF content."""
    errors = state.get("errors", [])

    if state.get("is_duplicate"):
        return state

    pages = state.get("pages", [])
    if not pages:
        errors.append({"stage": "chunk", "error": "No pages to chunk"})
        return {**state, "errors": errors, "status": "failed"}

    settings = get_settings()
    max_tokens = settings.max_chunk_tokens
    overlap_tokens = settings.chunk_overlap_tokens

    try:
        tokenizer = tiktoken.get_encoding("cl100k_base")
    except Exception:
        tokenizer = None

    chunks = []

    for page_data in pages:
        page_num = page_data["page_number"]
        page_text = page_data["text"]
        page_char_start = page_data["char_start"]

        if not page_text.strip():
            continue

        # Split page text into chunks respecting token limits
        page_chunks = _split_text_into_chunks(
            page_text, max_tokens, overlap_tokens, tokenizer
        )

        for chunk_text, local_start, local_end in page_chunks:
            chunk = ChunkData(
                chunk_id=str(uuid.uuid4()),
                page_number=page_num,
                char_start=page_char_start + local_start,
                char_end=page_char_start + local_end,
                text=chunk_text,
                metadata={"page_number": page_num},
            )
            chunks.append(chunk)

    # DEMO FAST PATH: limit chunks for quick demonstration without hitting rate limits
    if len(chunks) > 2:
        mid = len(chunks) // 2
        # Pick 2 chunks from the middle to avoid Table of Contents and ensure we get real facts
        chunks = chunks[mid:mid+2]

    logger.info("Created %d chunks from %d pages", len(chunks), len(pages))

    return {
        **state,
        "chunks": chunks,
        "status": "chunked",
        "errors": errors,
    }


def _split_text_into_chunks(
    text: str,
    max_tokens: int,
    overlap_tokens: int,
    tokenizer=None,
) -> list[tuple[str, int, int]]:
    """
    Split text into chunks of max_tokens with overlap.
    Returns list of (chunk_text, char_start, char_end).
    """
    if not text.strip():
        return []

    # If text fits in one chunk, return as-is
    token_count = _count_tokens(text, tokenizer)
    if token_count <= max_tokens:
        return [(text, 0, len(text))]

    # Split by sentences/paragraphs for natural boundaries
    sentences = _split_into_sentences(text)

    chunks = []
    current_sentences = []
    current_tokens = 0
    current_char_start = 0

    for sent_text, sent_start, sent_end in sentences:
        sent_tokens = _count_tokens(sent_text, tokenizer)

        if current_tokens + sent_tokens > max_tokens and current_sentences:
            # Flush current chunk
            chunk_text = "".join(s[0] for s in current_sentences)
            chunk_start = current_sentences[0][1]
            chunk_end = current_sentences[-1][2]
            chunks.append((chunk_text, chunk_start, chunk_end))

            # Overlap: keep last few sentences
            overlap_sents = []
            overlap_count = 0
            for s in reversed(current_sentences):
                s_tokens = _count_tokens(s[0], tokenizer)
                if overlap_count + s_tokens > overlap_tokens:
                    break
                overlap_sents.insert(0, s)
                overlap_count += s_tokens

            current_sentences = overlap_sents
            current_tokens = overlap_count

        current_sentences.append((sent_text, sent_start, sent_end))
        current_tokens += sent_tokens

    # Final chunk
    if current_sentences:
        chunk_text = "".join(s[0] for s in current_sentences)
        chunk_start = current_sentences[0][1]
        chunk_end = current_sentences[-1][2]
        chunks.append((chunk_text, chunk_start, chunk_end))

    return chunks


def _split_into_sentences(text: str) -> list[tuple[str, int, int]]:
    """Split text into sentence-like segments with positions."""
    segments = []
    current_start = 0

    # Split on newlines and sentence boundaries
    lines = text.split("\n")
    pos = 0
    for line in lines:
        if line.strip():
            segments.append((line + "\n", pos, pos + len(line) + 1))
        pos += len(line) + 1

    if not segments:
        segments = [(text, 0, len(text))]

    return segments


def _count_tokens(text: str, tokenizer=None) -> int:
    """Count tokens in text."""
    if tokenizer:
        return len(tokenizer.encode(text))
    # Rough estimate: ~4 chars per token
    return len(text) // 4
