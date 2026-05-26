"""
Knowledge graph triplet extraction for ingestion.

This is the first GraphRAG hook: for each text chunk, ask the configured LLM
to extract entity relationship triplets and log the JSON result. The output is
not persisted yet; Neo4j or another graph store can consume this later.
"""

import asyncio
import json
from typing import Any

from app.config import get_settings
from app.core.agent.llm_client import get_llm_client
from app.core.ingest.chunker import TextChunk


KNOWLEDGE_GRAPH_SYSTEM_PROMPT = """
You extract factual knowledge graph relationships from study material.

Return ONLY a valid JSON array. Do not include markdown fences, prose, or a
wrapper object. Each array item must be an object with exactly these keys:
"source", "relation", "target".

Rules:
- "source" and "target" must be concise entity names from the text.
- "relation" must be a concise lower_snake_case relationship type.
- Extract only relationships supported by the provided text.
- If no relationships are present, return [].

Required format:
[{"source": "Entity1", "relation": "relationship_type", "target": "Entity2"}]
""".strip()


def _strip_markdown_fence(raw: str) -> str:
    """Remove accidental JSON markdown fences from an LLM response."""
    cleaned = raw.strip()
    if not cleaned.startswith("```"):
        return cleaned

    lines = cleaned.splitlines()
    if lines:
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _normalize_triplets(raw: str) -> list[dict[str, str]]:
    """Parse and validate the strict triplet array format."""
    parsed: Any = json.loads(_strip_markdown_fence(raw))
    if not isinstance(parsed, list):
        raise ValueError("Knowledge graph extraction must return a JSON array")

    triplets: list[dict[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue

        source = item.get("source")
        relation = item.get("relation")
        target = item.get("target")

        if not all(isinstance(value, str) for value in (source, relation, target)):
            continue

        source = source.strip()
        relation = relation.strip()
        target = target.strip()
        if not source or not relation or not target:
            continue

        triplets.append({
            "source": source,
            "relation": relation,
            "target": target,
        })

    return triplets


async def extract_triplets_for_chunk(chunk: TextChunk) -> list[dict[str, str]]:
    """
    Extract and log graph triplets for one chunk.

    json_mode is intentionally not used here because some providers only
    support JSON object response formats, while GraphRAG triplets are requested
    as a top-level JSON array.
    """
    client = get_llm_client()
    prompt = f"""
Extract knowledge graph triplets from this text chunk.

Chunk index: {chunk.chunk_index}
Page number: {chunk.page_number}
Section title: {chunk.section_title or "N/A"}

Text:
{chunk.content}
""".strip()

    raw = await client.call_llm(
        prompt=prompt,
        system_prompt=KNOWLEDGE_GRAPH_SYSTEM_PROMPT,
        json_mode=False,
    )
    triplets = _normalize_triplets(raw)

    print(
        f"[GraphRAG] chunk={chunk.chunk_index} triplets="
        f"{json.dumps(triplets, ensure_ascii=False)}"
    )
    return triplets


async def log_triplets_for_chunks(chunks: list[TextChunk]) -> None:
    """
    Extract graph triplets for all chunks and log the JSON arrays.

    Failures are logged per chunk and do not interrupt document ingestion.
    """
    if not chunks:
        return

    settings = get_settings()
    if not settings.get_available_llm():
        print("[GraphRAG] Skipping triplet extraction: no LLM API key configured")
        return

    print(f"  -> Extracting knowledge graph triplets for {len(chunks)} chunks...")

    async def _extract_with_logging(chunk: TextChunk) -> None:
        try:
            await extract_triplets_for_chunk(chunk)
        except Exception as exc:
            print(f"[GraphRAG] chunk={chunk.chunk_index} extraction failed: {exc}")

    await asyncio.gather(*(_extract_with_logging(chunk) for chunk in chunks))
    print("  -> Knowledge graph triplet extraction finished")
