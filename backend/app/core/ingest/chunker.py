"""
Agentic StudyMate — Text Chunker

Structure-aware recursive text splitting for RAG.

Strategy:
1. Split on headings first (H1, H2, H3) to preserve section boundaries
2. Within each section, use recursive splitting: paragraphs → sentences → words
3. Apply token-based size limits with overlap
4. Attach metadata (page_number, section_title) to each chunk

This ensures chunks are semantically coherent and don't break mid-thought.
"""

from dataclasses import dataclass, field
from app.core.ingest.extractor import ExtractionResult, ExtractedPage
from app.config import get_settings


@dataclass
class TextChunk:
    """A single text chunk ready for embedding."""
    content: str
    chunk_index: int
    page_number: int | None = None
    section_title: str | None = None
    metadata: dict = field(default_factory=dict)


def estimate_tokens(text: str) -> int:
    """
    Rough token estimation: ~4 characters per token for English.
    Good enough for chunking; exact tokenization not needed here.
    """
    return len(text) // 4


def split_text_recursive(
    text: str,
    max_tokens: int,
    overlap_tokens: int,
    separators: list[str] | None = None,
) -> list[str]:
    """
    Recursively split text trying each separator in order.
    
    Separator priority:
    1. Headings (###, ##, #)
    2. Double newlines (paragraph breaks)
    3. Single newlines
    4. Sentences (. ! ?)
    5. Spaces (words)
    
    This mirrors LangChain's RecursiveCharacterTextSplitter logic.
    """
    if separators is None:
        separators = [
            "\n### ",   # H3
            "\n## ",    # H2
            "\n# ",     # H1
            "\n\n",     # Paragraph
            "\n",       # Line
            ". ",       # Sentence
            "! ",       # Sentence
            "? ",       # Sentence
            " ",        # Word
        ]

    # Base case: text fits within limit
    if estimate_tokens(text) <= max_tokens:
        return [text.strip()] if text.strip() else []

    # Try each separator
    for sep in separators:
        if sep in text:
            parts = text.split(sep)
            chunks = []
            current_chunk = ""

            for part in parts:
                # Add separator back (except for the first part)
                candidate = part if not current_chunk else sep + part

                if estimate_tokens(current_chunk + candidate) <= max_tokens:
                    current_chunk += candidate
                else:
                    if current_chunk.strip():
                        chunks.append(current_chunk.strip())
                    current_chunk = part  # Start new chunk without separator

            if current_chunk.strip():
                chunks.append(current_chunk.strip())

            # Apply overlap between chunks
            if overlap_tokens > 0 and len(chunks) > 1:
                chunks = _apply_overlap(chunks, overlap_tokens)

            return chunks

    # Fallback: hard split by character count
    max_chars = max_tokens * 4
    chunks = []
    for i in range(0, len(text), max_chars):
        chunk = text[i:i + max_chars].strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def _apply_overlap(chunks: list[str], overlap_tokens: int) -> list[str]:
    """Add overlap from the end of each chunk to the start of the next."""
    overlap_chars = overlap_tokens * 4
    result = [chunks[0]]

    for i in range(1, len(chunks)):
        prev_chunk = chunks[i - 1]
        overlap_text = prev_chunk[-overlap_chars:] if len(prev_chunk) > overlap_chars else prev_chunk

        # Find a clean break point in the overlap
        for sep in [". ", "\n", " "]:
            idx = overlap_text.find(sep)
            if idx != -1:
                overlap_text = overlap_text[idx + len(sep):]
                break

        result.append(overlap_text + " " + chunks[i])

    return result


def _find_nearest_heading(page: ExtractedPage, chunk_text: str) -> str | None:
    """Find the nearest heading above the chunk in the page content."""
    if not page.headings:
        return None

    # Find which heading is closest above this chunk's position
    chunk_pos = page.content.find(chunk_text[:50])  # Use first 50 chars to locate
    if chunk_pos == -1:
        return page.headings[0] if page.headings else None

    nearest_heading = None
    for heading in page.headings:
        heading_pos = page.content.find(heading)
        if heading_pos != -1 and heading_pos <= chunk_pos:
            nearest_heading = heading

    return nearest_heading or (page.headings[0] if page.headings else None)


def chunk_document(extraction_result: ExtractionResult) -> list[TextChunk]:
    """
    Split an extracted document into chunks for embedding.
    
    Process:
    1. Iterate through pages/sections
    2. Apply recursive splitting within each page
    3. Attach metadata (page number, section title)
    4. Return ordered list of chunks
    
    Args:
        extraction_result: Output from the extractor
        
    Returns:
        List of TextChunk objects ready for embedding
    """
    settings = get_settings()
    max_tokens = settings.CHUNK_SIZE
    overlap_tokens = settings.CHUNK_OVERLAP

    all_chunks: list[TextChunk] = []
    chunk_index = 0

    for page in extraction_result.pages:
        if not page.content.strip():
            continue

        # Split this page's content
        text_segments = split_text_recursive(
            page.content,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
        )

        for segment in text_segments:
            if not segment.strip():
                continue

            # Find the nearest heading for this chunk
            section_title = _find_nearest_heading(page, segment)

            all_chunks.append(TextChunk(
                content=segment,
                chunk_index=chunk_index,
                page_number=page.page_number,
                section_title=section_title,
                metadata={
                    "file_type": extraction_result.metadata.get("file_type", "unknown"),
                },
            ))
            chunk_index += 1

    return all_chunks
