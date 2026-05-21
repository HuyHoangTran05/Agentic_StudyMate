"""
Agentic StudyMate — Citation Verifier

Step 7 of the agentic pipeline: post-processes the generated answer
to verify that all citations map to actual content.

This is a deterministic step — no LLM call needed.
Parses [filename, page N] citations, cross-references with the
provided chunks, and removes ungrounded citations.
"""

import re
from dataclasses import dataclass, field

from app.models.schemas import Citation
from app.core.reranker import RerankResult


@dataclass
class VerifiedAnswer:
    """The final verified answer with cleaned citations."""
    answer: str
    citations: list[Citation] = field(default_factory=list)
    removed_count: int = 0  # how many citations were removed


# Regex to match [filename, page N] or [filename] citations
CITATION_PATTERN = re.compile(
    r'\[([^\[\]]+?)(?:,\s*page\s*(\d+))?\]'
)


def _normalize_filename(name: str) -> str:
    """Normalize a filename for matching (lowercase, strip whitespace)."""
    return name.strip().lower()


def verify_citations(
    answer: str,
    chunks: list[RerankResult],
) -> VerifiedAnswer:
    """
    Verify all citations in the answer against actual chunk content.

    Args:
        answer: The raw generated answer with [filename, page N] citations
        chunks: The chunks that were provided as context

    Returns:
        VerifiedAnswer with cleaned answer and verified citation list
    """
    if not answer or not chunks:
        return VerifiedAnswer(answer=answer)

    # Build lookup: normalized_filename → set of page numbers
    # Also build chunk lookup for citation objects
    file_pages: dict[str, set[int | None]] = {}
    chunk_lookup: dict[str, RerankResult] = {}  # "filename|page" → chunk

    for chunk in chunks:
        fname = _normalize_filename(
            getattr(chunk, "_file_name", "") or ""
        )
        if not fname:
            continue

        page = chunk.page_number

        if fname not in file_pages:
            file_pages[fname] = set()
        file_pages[fname].add(page)

        # Store chunk for building Citation objects
        key = f"{fname}|{page}"
        if key not in chunk_lookup:
            chunk_lookup[key] = chunk

    # Find all citations in the answer
    verified_citations: list[Citation] = []
    removed_count = 0
    cleaned_answer = answer

    # Track unique citations to avoid duplicates
    seen_citations: set[str] = set()

    for match in CITATION_PATTERN.finditer(answer):
        full_match = match.group(0)
        cited_name = match.group(1).strip()
        cited_page_str = match.group(2)
        cited_page = int(cited_page_str) if cited_page_str else None

        normalized_name = _normalize_filename(cited_name)

        # Check if this citation matches any chunk
        is_verified = False

        # Exact match: filename + page
        if normalized_name in file_pages:
            if cited_page is None:
                # Citation without page — accept if the file exists
                is_verified = True
            elif cited_page in file_pages[normalized_name]:
                is_verified = True
            elif None in file_pages[normalized_name]:
                # Chunks without page numbers — accept the citation
                is_verified = True

        # Also try partial filename matching (LLM might truncate extension)
        if not is_verified:
            for known_fname in file_pages:
                if (
                    normalized_name in known_fname
                    or known_fname in normalized_name
                    or known_fname.rsplit(".", 1)[0] == normalized_name.rsplit(".", 1)[0]
                ):
                    is_verified = True
                    normalized_name = known_fname  # Use the actual filename
                    break

        if is_verified:
            # Build citation key to deduplicate
            cite_key = f"{normalized_name}|{cited_page}"
            if cite_key not in seen_citations:
                seen_citations.add(cite_key)

                # Find the best matching chunk
                lookup_key = f"{normalized_name}|{cited_page}"
                chunk_ref = chunk_lookup.get(lookup_key)

                # Fallback: find any chunk from this file
                if not chunk_ref:
                    for key, ch in chunk_lookup.items():
                        if key.startswith(f"{normalized_name}|"):
                            chunk_ref = ch
                            break

                if chunk_ref:
                    # Create a short snippet for the citation
                    snippet = chunk_ref.content[:150].strip()
                    if len(chunk_ref.content) > 150:
                        snippet += "..."

                    verified_citations.append(Citation(
                        file_name=cited_name,
                        page_number=cited_page,
                        chunk_id=chunk_ref.chunk_id,
                        section_title=chunk_ref.section_title,
                        snippet=snippet,
                    ))
        else:
            # Unverified citation — remove from answer
            cleaned_answer = cleaned_answer.replace(full_match, "", 1)
            removed_count += 1

    # Clean up any double spaces or awkward whitespace from removals
    cleaned_answer = re.sub(r'  +', ' ', cleaned_answer)
    cleaned_answer = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_answer)

    return VerifiedAnswer(
        answer=cleaned_answer.strip(),
        citations=verified_citations,
        removed_count=removed_count,
    )
