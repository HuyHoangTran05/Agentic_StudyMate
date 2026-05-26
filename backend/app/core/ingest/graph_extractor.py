"""
Knowledge graph triplet extraction for ingestion.

For each text chunk, ask the configured LLM to extract entity relationship
triplets, then persist them to Neo4j with the source chunk ID.
"""

import asyncio
import json
from typing import Any

from app.config import get_settings
from app.core.agent.llm_client import get_llm_client
from app.core.db.neo4j_client import get_neo4j_client
from app.core.ingest.chunker import TextChunk


KNOWLEDGE_GRAPH_SYSTEM_PROMPT = """
Extract entities and relationships from this text. Output ONLY a strict JSON array of objects with "source", "relation", and "target" keys. Example: [{"source": "Apache Spark", "relation": "MANAGES", "target": "Worker Node"}]
""".strip()


def _sanitize_json_array(raw: str | None) -> str:
    """
    Strip Markdown/code-fence noise and return the raw JSON array text.

    Handles responses like:
        ```json
        [{"source": "...", "relation": "...", "target": "..."}]
        ```

    If surrounding prose slips through, prefer the first complete [...] block.
    """
    if not raw:
        return ""

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    if cleaned.lower().startswith("json"):
        cleaned = cleaned[4:].strip()
    cleaned = cleaned.strip("`").strip()

    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start != -1 and end != -1 and end >= start:
        return cleaned[start:end + 1].strip()

    return cleaned


def _normalize_triplets(raw: str) -> list[dict[str, str]]:
    """Parse and validate the strict triplet array format."""
    sanitized = _sanitize_json_array(raw)
    try:
        parsed: Any = json.loads(sanitized)
    except Exception as exc:
        print(
            "[GraphRAG][WARN] Failed to parse LLM triplet JSON. "
            f"Error: {exc}. Raw output: {raw!r}"
        )
        return []

    if not isinstance(parsed, list):
        print(
            "[GraphRAG][WARN] LLM triplet response was not a JSON array. "
            f"Raw output: {raw!r}"
        )
        return []

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


async def ingest_triplets_for_chunks(
    chunk_sources: list[tuple[TextChunk, str]],
) -> None:
    """
    Extract graph triplets for all chunks and write them to Neo4j.

    Failures are logged per chunk and do not interrupt document ingestion.
    """
    if not chunk_sources:
        return

    settings = get_settings()
    if not settings.get_available_llm():
        print("[GraphRAG] Skipping triplet extraction: no LLM API key configured")
        return

    neo4j_available = bool(
        settings.NEO4J_URI and settings.NEO4J_USER and settings.NEO4J_PASSWORD
    )
    if not neo4j_available:
        print("[GraphRAG] Neo4j not configured; triplets will be extracted and logged only")

    print(f"  -> Extracting knowledge graph triplets for {len(chunk_sources)} chunks...")

    for index, (chunk, chunk_id) in enumerate(chunk_sources):
        try:
            triplets = await extract_triplets_for_chunk(chunk)
            if neo4j_available:
                neo4j_client = get_neo4j_client()
                written = await neo4j_client.ingest_triplets(triplets, chunk_id)
                print(f"[GraphRAG] chunk={chunk.chunk_index} neo4j_relationships={written}")
        except Exception as exc:
            print(f"[GraphRAG] chunk={chunk.chunk_index} ingestion failed: {exc}")

        if index < len(chunk_sources) - 1:
            await asyncio.sleep(1.5)

    print("  -> Knowledge graph ingestion finished")
