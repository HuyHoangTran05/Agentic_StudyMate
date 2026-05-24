"""
Agentic StudyMate — Map-Reduce LLM Batch Processor

Solves the TPM (Tokens Per Minute) problem when processing large documents
through LLM APIs like Groq's free tier.

Strategy:
  MAP   -> Split chunks into small batches (e.g., 5 chunks each)
        -> Call LLM on each batch with strict JSON output
        -> Throttle between calls (3.5s default) to avoid 429 rate limits

  REDUCE -> Parse JSON from each batch response
         -> Aggregate all items into a single flat list
         -> Handle JSONDecodeError gracefully (skip bad batches)

Rate-limit safety:
  - Inter-batch throttle delay (BATCH_THROTTLE_DELAY)
  - Pre-reduce cooldown (REDUCE_COOLDOWN) to let TPM bucket refill
  - Trimmed reduce prompts to fit within 8192 context window
  - Partial summaries capped to prevent token overflow

This is provider-agnostic — it uses the unified LLMClient which
handles Groq -> Gemini -> OpenAI -> Anthropic failover internally.
"""

import json
import asyncio
from typing import Any

from app.config import get_settings
from app.core.agent.llm_client import get_llm_client
from app.models.db_models import Chunk


# ─── Constants ────────────────────────────────────────────────────────────────

# Max characters for each partial summary in the reduce prompt.
# Keeps the final reduce prompt under ~4000 tokens (safe for 8192 context).
_MAX_PARTIAL_SUMMARY_CHARS = 300

# Max key facts to include in the reduce prompt.
_MAX_KEY_FACTS_FOR_REDUCE = 15

# Max partial summaries to combine in the reduce step.
# If there are more, we take evenly-spaced ones.
_MAX_PARTIALS_FOR_REDUCE = 10


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _format_chunk_batch(chunks: list[Chunk]) -> str:
    """Format a batch of chunks into a context string for the LLM."""
    passages = []
    for chunk in chunks:
        page_info = f" (page {chunk.page_number})" if chunk.page_number else ""
        section_info = f" - {chunk.section_title}" if chunk.section_title else ""
        passages.append(f"[Passage{page_info}{section_info}]\n{chunk.content}")
    return "\n\n---\n\n".join(passages)


def _split_into_batches(chunks: list[Chunk], batch_size: int) -> list[list[Chunk]]:
    """Split a list of chunks into smaller batches."""
    return [chunks[i:i + batch_size] for i in range(0, len(chunks), batch_size)]


def _safe_parse_json(raw: str) -> dict | None:
    """
    Safely parse a JSON string from LLM output.

    Handles:
    - Raw JSON
    - JSON wrapped in markdown code fences (```json ... ```)
    - Returns None on any parse failure
    """
    cleaned = raw.strip()

    # Strip markdown fences if present
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]  # Remove opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]  # Remove closing fence
        cleaned = "\n".join(lines).strip()

    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[WARN] JSON parse failed for batch response: {e}")
        return None


def _truncate(text: str, max_chars: int) -> str:
    """Truncate text to max_chars, adding ellipsis if truncated."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3] + "..."


def _evenly_sample(items: list, max_count: int) -> list:
    """Take evenly-spaced items from a list if it exceeds max_count."""
    if len(items) <= max_count:
        return items
    step = len(items) / max_count
    return [items[int(i * step)] for i in range(max_count)]


# ─── Map-Reduce Engine ───────────────────────────────────────────────────────


async def map_reduce_llm(
    chunks: list[Chunk],
    system_prompt: str,
    user_prompt_template: str,
    result_key: str,
    file_name: str = "document",
    items_per_batch: int | None = None,
    total_items: int | None = None,
) -> list[dict[str, Any]]:
    """
    Process document chunks through the LLM using a Map-Reduce pattern.

    MAP phase:
      - Split chunks into small batches (default: 5 per batch)
      - Call LLM on each batch with strict JSON mode
      - Throttle between calls to respect rate limits

    REDUCE phase:
      - Parse JSON from each response
      - Extract the array under `result_key`
      - Aggregate into a single flat list

    Args:
        chunks: List of document Chunk ORM objects
        system_prompt: System prompt for the LLM (must demand JSON output)
        user_prompt_template: User prompt with {context}, {file_name}, {num_items} placeholders
        result_key: JSON key containing the result array (e.g., "flashcards", "questions")
        file_name: Document filename for the prompt
        items_per_batch: How many items to request per batch (auto-calculated if None)
        total_items: Total items desired (used to calculate per-batch count)

    Returns:
        Aggregated list of dicts from all batches
    """
    settings = get_settings()
    client = get_llm_client()

    batch_size = settings.BATCH_CHUNK_SIZE
    throttle_delay = settings.BATCH_THROTTLE_DELAY

    # Split chunks into batches
    batches = _split_into_batches(chunks, batch_size)
    num_batches = len(batches)

    # Calculate items per batch
    if items_per_batch is None and total_items is not None:
        # Distribute items evenly across batches, with a minimum of 1
        items_per_batch = max(1, (total_items + num_batches - 1) // num_batches)
    elif items_per_batch is None:
        items_per_batch = 3  # Safe default

    print(
        f"[MAP-REDUCE] Processing {len(chunks)} chunks in {num_batches} batches "
        f"({batch_size} chunks/batch, {items_per_batch} items/batch, "
        f"{throttle_delay}s throttle)"
    )

    # ─── MAP Phase ────────────────────────────────────────────────────────

    aggregated: list[dict[str, Any]] = []

    for i, batch in enumerate(batches):
        batch_num = i + 1
        context = _format_chunk_batch(batch)

        # Build the user prompt from template
        user_prompt = user_prompt_template.format(
            context=context,
            file_name=file_name,
            num_items=items_per_batch,
        )

        print(f"  [Batch {batch_num}/{num_batches}] Calling LLM with {len(batch)} chunks...")

        try:
            result = await client.call_llm_json(
                prompt=user_prompt,
                system_prompt=system_prompt,
            )

            # ─── REDUCE: Extract items from this batch ────────────────
            items = result.get(result_key, [])
            if isinstance(items, list):
                aggregated.extend(items)
                print(f"  [Batch {batch_num}/{num_batches}] Got {len(items)} items")
            else:
                print(f"  [Batch {batch_num}/{num_batches}] Unexpected type for '{result_key}': {type(items)}")

        except json.JSONDecodeError as e:
            print(f"  [Batch {batch_num}/{num_batches}] JSON parse error, skipping: {e}")
        except Exception as e:
            print(f"  [Batch {batch_num}/{num_batches}] LLM call failed, skipping: {e}")

        # Throttle between batches (skip after last batch)
        if batch_num < num_batches:
            print(f"  [Throttle] Waiting {throttle_delay}s before next batch...")
            await asyncio.sleep(throttle_delay)

    print(f"[MAP-REDUCE] Done. Aggregated {len(aggregated)} total items from {num_batches} batches.")
    return aggregated


async def map_reduce_summary(
    chunks: list[Chunk],
    system_prompt: str,
    user_prompt_template: str,
    file_name: str = "document",
) -> dict[str, Any]:
    """
    Map-Reduce specifically for summaries.

    MAP: Generate a partial summary from each batch of chunks.
    REDUCE: Combine all partial summaries into a final summary via one more LLM call.

    Safety features:
      - Pre-reduce cooldown to let TPM bucket refill
      - Partial summaries truncated to fit 8192 context window
      - Key facts capped to prevent token overflow

    Args:
        chunks: List of Chunk ORM objects
        system_prompt: System prompt for partial summaries
        user_prompt_template: Prompt template with {context}, {file_name} placeholders
        file_name: Document filename

    Returns:
        Dict with "summary" (str) and "key_points" (list[str])
    """
    settings = get_settings()
    client = get_llm_client()

    batch_size = settings.BATCH_CHUNK_SIZE
    throttle_delay = settings.BATCH_THROTTLE_DELAY
    reduce_cooldown = settings.REDUCE_COOLDOWN
    batches = _split_into_batches(chunks, batch_size)
    num_batches = len(batches)

    # If the document is small enough for one call, just do it directly
    if num_batches <= 2:
        context = _format_chunk_batch(chunks[:batch_size * 2])
        prompt = user_prompt_template.format(
            context=context,
            file_name=file_name,
            num_items="",  # Not used for summary
        )
        result = await client.call_llm_json(
            prompt=prompt,
            system_prompt=system_prompt,
        )
        return {
            "summary": result.get("summary", ""),
            "key_points": result.get("key_points", []),
        }

    print(
        f"[MAP-REDUCE SUMMARY] Processing {len(chunks)} chunks in {num_batches} batches "
        f"(throttle={throttle_delay}s, reduce_cooldown={reduce_cooldown}s)"
    )

    # ─── MAP: Partial summaries from each batch ───────────────────────────

    PARTIAL_SYSTEM = """\
You are an expert summarizer. Summarize the provided text passages.
Be concise — keep your summary under 200 words.
Extract only the 3-4 most important facts.

Respond ONLY with a JSON object (no markdown, no code fences):
{
  "partial_summary": "concise summary of this section (under 200 words)",
  "key_facts": ["fact 1", "fact 2", "fact 3"]
}\
"""

    partial_summaries: list[str] = []
    all_key_facts: list[str] = []

    for i, batch in enumerate(batches):
        batch_num = i + 1
        context = _format_chunk_batch(batch)

        print(f"  [Batch {batch_num}/{num_batches}] Generating partial summary...")

        try:
            result = await client.call_llm_json(
                prompt=(
                    f"Summarize these passages from '{file_name}'. "
                    f"Be concise (under 200 words):\n\n{context}"
                ),
                system_prompt=PARTIAL_SYSTEM,
            )

            partial = result.get("partial_summary", "")
            facts = result.get("key_facts", [])

            if partial:
                partial_summaries.append(partial)
            if isinstance(facts, list):
                all_key_facts.extend(facts)

            print(f"  [Batch {batch_num}/{num_batches}] Got summary ({len(partial)} chars, {len(facts)} facts)")

        except Exception as e:
            print(f"  [Batch {batch_num}/{num_batches}] Failed, skipping: {e}")

        if batch_num < num_batches:
            print(f"  [Throttle] Waiting {throttle_delay}s...")
            await asyncio.sleep(throttle_delay)

    # ─── REDUCE: Combine partial summaries into final ─────────────────────

    if not partial_summaries:
        return {"summary": "Unable to generate summary.", "key_points": []}

    # ── Pre-reduce cooldown: let Groq's TPM bucket refill ──
    print(
        f"  [COOLDOWN] Waiting {reduce_cooldown}s before Reduce call "
        f"(letting TPM bucket refill)..."
    )
    await asyncio.sleep(reduce_cooldown)

    # ── Trim partials to fit within context window ──
    # Each partial is truncated to _MAX_PARTIAL_SUMMARY_CHARS chars.
    # We also limit the number of partials to _MAX_PARTIALS_FOR_REDUCE.
    sampled_partials = _evenly_sample(partial_summaries, _MAX_PARTIALS_FOR_REDUCE)
    trimmed_partials = [
        _truncate(s, _MAX_PARTIAL_SUMMARY_CHARS)
        for s in sampled_partials
    ]

    print(
        f"  [REDUCE] Combining {len(trimmed_partials)} partial summaries "
        f"(from {len(partial_summaries)} originals)..."
    )

    combined_text = "\n\n".join(
        f"Section {i+1}: {s}" for i, s in enumerate(trimmed_partials)
    )

    # Trim key facts to prevent token overflow
    sampled_facts = _evenly_sample(all_key_facts, _MAX_KEY_FACTS_FOR_REDUCE)
    key_facts_text = "\n".join(f"- {f}" for f in sampled_facts)

    REDUCE_SYSTEM = """\
You are given partial summaries of different sections of a document.
Combine them into ONE well-structured summary. Be concise but comprehensive.
Use markdown formatting (bold, lists) for readability. Do NOT repeat information.
Select the 5-8 most important key points.

Respond ONLY with a JSON object (no markdown fences, no extra text):
{
  "summary": "combined summary with markdown formatting",
  "key_points": ["point 1", "point 2", ...]
}\
"""

    try:
        final = await client.call_llm_json(
            prompt=(
                f"Combine these section summaries of '{file_name}':\n\n"
                f"{combined_text}\n\n"
                f"Key facts:\n{key_facts_text}"
            ),
            system_prompt=REDUCE_SYSTEM,
        )
        print(f"[MAP-REDUCE SUMMARY] Done.")
        return {
            "summary": final.get("summary", ""),
            "key_points": final.get("key_points", []),
        }
    except Exception as e:
        print(f"  [REDUCE] Final combination failed: {e}")
        # Fallback: join the partials directly (no LLM call needed)
        fallback_summary = "\n\n".join(
            f"**Section {i+1}:** {s}" for i, s in enumerate(partial_summaries)
        )
        return {
            "summary": fallback_summary,
            "key_points": all_key_facts[:8],
        }
