"""
Agentic StudyMate — Unified LLM Client (4-Provider Failover Router)

Abstracts Groq / Gemini / OpenAI / Anthropic behind one async interface.
Supports both structured (JSON) responses and streaming text.

Failover chain (strict cascade):
    Groq (Primary)  →  Gemini  →  OpenAI  →  Anthropic

If a provider throws any exception (429, timeout, network error),
the router logs a warning and immediately tries the next provider.

Rate-limiting features:
  • Concurrency semaphore — caps simultaneous API calls
  • Exponential backoff — retries on 429/rate-limit errors per provider
  • Retry-delay parsing — extracts server-suggested wait from error messages
  • Standardized output — all providers return plain string text
"""

import json
import re
import asyncio
from typing import Any, AsyncGenerator

from app.config import get_settings


# ─── Rate-limit Helpers ──────────────────────────────────────────────────────

def _is_rate_limit_error(error: Exception) -> bool:
    """Check if an exception is a rate-limit (429) error."""
    err_str = str(error)
    return (
        "429" in err_str
        or "RESOURCE_EXHAUSTED" in err_str
        or "rate limit" in err_str.lower()
        or "quota" in err_str.lower()
        or "too many requests" in err_str.lower()
    )


def _parse_retry_delay(error: Exception) -> float | None:
    """
    Extract the server-suggested retry delay from the error message.

    Gemini errors include a `retryDelay` field like `'retryDelay': '51s'`
    or `'retryDelay': '41.709722063s'`. We parse that to seconds.
    Groq errors include `retry-after` headers or similar patterns.
    """
    err_str = str(error)

    # Match patterns like: retryDelay': '51s' or retryDelay': '41.709s'
    match = re.search(r"retryDelay['\"]?\s*:\s*['\"]?([\d.]+)s", err_str)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass

    # Match "Please retry in Xs" pattern
    match = re.search(r"retry in ([\d.]+)s", err_str)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass

    # Match "try again in Xs" pattern (Groq)
    match = re.search(r"try again in ([\d.]+)", err_str)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass

    return None


class LLMClient:
    """
    Unified LLM client with 4-provider cascading failover, concurrency
    limiting, and exponential backoff on rate-limit errors.

    Failover chain: Groq → Gemini → OpenAI → Anthropic

    The rest of the system doesn't know or care which provider actually
    answered — all methods return standardized plain text strings.

    Usage:
        client = get_llm_client()
        result = await client.call_llm("What is X?", system_prompt="...")
        async for chunk in client.stream_llm("Explain Y", system_prompt="..."):
            print(chunk, end="")
    """

    def __init__(self):
        self._settings = get_settings()
        self._groq_client = None
        self._gemini_client = None
        self._openai_client = None
        self._anthropic_client = None

        # Concurrency semaphore — limits simultaneous LLM API calls
        self._semaphore = asyncio.Semaphore(self._settings.LLM_MAX_CONCURRENT)

    # ─── Provider Initialization (Lazy) ───────────────────────────────────

    def _get_groq_client(self):
        """Lazy-init Groq async client."""
        if self._groq_client is None and self._settings.GROQ_API_KEY:
            from groq import AsyncGroq
            self._groq_client = AsyncGroq(
                api_key=self._settings.GROQ_API_KEY
            )
        return self._groq_client

    def _get_gemini_client(self):
        """Lazy-init Google GenAI client."""
        if self._gemini_client is None and self._settings.GEMINI_API_KEY:
            from google import genai
            self._gemini_client = genai.Client(
                api_key=self._settings.GEMINI_API_KEY
            )
        return self._gemini_client

    def _get_openai_client(self):
        """Lazy-init OpenAI client."""
        if self._openai_client is None and self._settings.OPENAI_API_KEY:
            from openai import AsyncOpenAI
            self._openai_client = AsyncOpenAI(
                api_key=self._settings.OPENAI_API_KEY
            )
        return self._openai_client

    def _get_anthropic_client(self):
        """Lazy-init Anthropic client."""
        if self._anthropic_client is None and self._settings.ANTHROPIC_API_KEY:
            import anthropic
            self._anthropic_client = anthropic.AsyncAnthropic(
                api_key=self._settings.ANTHROPIC_API_KEY
            )
        return self._anthropic_client

    # ─── Provider Order ───────────────────────────────────────────────────

    def _get_provider_order(self) -> list[str]:
        """Return available providers in strict priority order."""
        providers = []
        if self._settings.GROQ_API_KEY:
            providers.append("groq")
        if self._settings.GEMINI_API_KEY:
            providers.append("gemini")
        if self._settings.OPENAI_API_KEY:
            providers.append("openai")
        if self._settings.ANTHROPIC_API_KEY:
            providers.append("anthropic")
        return providers

    # ─── Retry Logic ──────────────────────────────────────────────────────

    async def _retry_with_backoff(self, coro_factory, provider: str):
        """
        Execute an async callable with exponential backoff on rate-limit errors.

        Args:
            coro_factory: A zero-arg callable that returns a new coroutine each call
            provider: Provider name for logging

        Returns:
            The result of the coroutine

        Raises:
            The last exception if all retries fail, or immediately if not rate-limited
        """
        max_retries = self._settings.LLM_MAX_RETRIES
        base_delay = self._settings.LLM_RETRY_BASE_DELAY
        max_delay = self._settings.LLM_RETRY_MAX_DELAY

        for attempt in range(max_retries + 1):
            try:
                return await coro_factory()
            except Exception as e:
                if not _is_rate_limit_error(e):
                    raise  # Not a rate limit — fail immediately

                if attempt >= max_retries:
                    raise  # Out of retries

                # Calculate delay: use server-suggested delay if available,
                # otherwise use exponential backoff
                server_delay = _parse_retry_delay(e)
                if server_delay is not None:
                    # Use the server's suggestion but cap it
                    delay = min(server_delay + 1.0, max_delay)
                else:
                    # Exponential backoff: 2s, 4s, 8s, ...
                    delay = min(base_delay * (2 ** attempt), max_delay)

                print(
                    f"[RETRY] Rate limited by {provider} (attempt {attempt + 1}/{max_retries}). "
                    f"Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)

    async def _retry_stream_with_backoff(self, stream_factory, provider: str):
        """
        Retry a streaming call with exponential backoff on rate-limit errors.
        Returns an async generator that yields text chunks.
        """
        max_retries = self._settings.LLM_MAX_RETRIES
        base_delay = self._settings.LLM_RETRY_BASE_DELAY
        max_delay = self._settings.LLM_RETRY_MAX_DELAY

        for attempt in range(max_retries + 1):
            try:
                async for chunk in stream_factory():
                    yield chunk
                return  # Stream completed successfully
            except Exception as e:
                if not _is_rate_limit_error(e) or attempt >= max_retries:
                    raise

                server_delay = _parse_retry_delay(e)
                delay = (
                    min(server_delay + 1.0, max_delay)
                    if server_delay is not None
                    else min(base_delay * (2 ** attempt), max_delay)
                )

                print(
                    f"[RETRY] Stream rate limited by {provider} (attempt {attempt + 1}/{max_retries}). "
                    f"Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)

    # ═══════════════════════════════════════════════════════════════════════
    # PROVIDER 1: GROQ (Primary — fastest inference, generous free tier)
    # ═══════════════════════════════════════════════════════════════════════

    async def _call_groq(
        self, prompt: str, system_prompt: str, json_mode: bool = False
    ) -> str:
        """Call Groq API with semaphore + retry."""
        client = self._get_groq_client()
        if client is None:
            raise RuntimeError("Groq client not available")

        kwargs: dict = {
            "model": self._settings.TEXT_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 2048,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        async def _do_call():
            async with self._semaphore:
                response = await client.chat.completions.create(**kwargs)
                return response.choices[0].message.content

        return await self._retry_with_backoff(_do_call, "groq")

    async def _call_groq_multimodal(
        self,
        prompt: str,
        image_url: str,
        system_prompt: str,
        json_mode: bool = False,
    ) -> str:
        """
        Call Groq's OpenAI-compatible multimodal chat endpoint.

        image_url may be an HTTP(S) URL or a data URL such as
        data:image/jpeg;base64,... .
        """
        client = self._get_groq_client()
        if client is None:
            raise RuntimeError("Groq client not available")

        user_content: list[dict[str, Any]] = [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {
                    "url": image_url,
                },
            },
        ]
        kwargs: dict[str, Any] = {
            "model": self._settings.VISION_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.2,
            "max_tokens": 4096,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        async def _do_call():
            async with self._semaphore:
                response = await client.chat.completions.create(**kwargs)
                return response.choices[0].message.content

        return await self._retry_with_backoff(_do_call, "groq")

    async def _stream_groq(
        self, prompt: str, system_prompt: str
    ) -> AsyncGenerator[str, None]:
        """Stream from Groq API with semaphore + retry."""
        client = self._get_groq_client()
        if client is None:
            raise RuntimeError("Groq client not available")

        async def _do_stream():
            stream = await client.chat.completions.create(
                model=self._settings.TEXT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=2048,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content

        async with self._semaphore:
            async for text in self._retry_stream_with_backoff(_do_stream, "groq"):
                yield text

    # ═══════════════════════════════════════════════════════════════════════
    # PROVIDER 2: GEMINI (Fallback 1)
    # ═══════════════════════════════════════════════════════════════════════

    async def _call_gemini(
        self, prompt: str, system_prompt: str, json_mode: bool = False
    ) -> str:
        """Call Gemini API with semaphore + retry."""
        client = self._get_gemini_client()
        if client is None:
            raise RuntimeError("Gemini client not available")

        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.3,
        )
        if json_mode:
            config.response_mime_type = "application/json"

        async def _do_call():
            async with self._semaphore:
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=self._settings.GEMINI_MODEL,
                    contents=prompt,
                    config=config,
                )
                return response.text

        return await self._retry_with_backoff(_do_call, "gemini")

    async def _stream_gemini(
        self, prompt: str, system_prompt: str
    ) -> AsyncGenerator[str, None]:
        """Stream from Gemini API with semaphore + retry on initial connection."""
        client = self._get_gemini_client()
        if client is None:
            raise RuntimeError("Gemini client not available")

        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.3,
        )

        # Acquire semaphore for the duration of the stream
        async with self._semaphore:
            max_retries = self._settings.LLM_MAX_RETRIES
            base_delay = self._settings.LLM_RETRY_BASE_DELAY
            max_delay = self._settings.LLM_RETRY_MAX_DELAY

            for attempt in range(max_retries + 1):
                try:
                    queue: asyncio.Queue[str | None | Exception] = asyncio.Queue()

                    def _stream_sync():
                        try:
                            response = client.models.generate_content_stream(
                                model=self._settings.GEMINI_MODEL,
                                contents=prompt,
                                config=config,
                            )
                            for chunk in response:
                                if chunk.text:
                                    queue.put_nowait(chunk.text)
                            queue.put_nowait(None)  # sentinel
                        except Exception as e:
                            queue.put_nowait(e)  # pass error to async side

                    task = asyncio.get_event_loop().run_in_executor(None, _stream_sync)

                    # Read the first item to check for immediate errors
                    first = await asyncio.wait_for(queue.get(), timeout=120.0)

                    if isinstance(first, Exception):
                        raise first
                    if first is None:
                        await task
                        return
                    yield first

                    # Stream remaining chunks
                    while True:
                        try:
                            text = await asyncio.wait_for(queue.get(), timeout=120.0)
                        except asyncio.TimeoutError:
                            break
                        if text is None:
                            break
                        if isinstance(text, Exception):
                            raise text
                        yield text

                    await task
                    return  # Stream completed successfully

                except Exception as e:
                    if not _is_rate_limit_error(e) or attempt >= max_retries:
                        raise

                    server_delay = _parse_retry_delay(e)
                    delay = (
                        min(server_delay + 1.0, max_delay)
                        if server_delay is not None
                        else min(base_delay * (2 ** attempt), max_delay)
                    )

                    print(
                        f"[RETRY] Stream rate limited by gemini (attempt {attempt + 1}/{max_retries}). "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)

    # ═══════════════════════════════════════════════════════════════════════
    # PROVIDER 3: OPENAI (Fallback 2)
    # ═══════════════════════════════════════════════════════════════════════

    async def _call_openai(
        self, prompt: str, system_prompt: str, json_mode: bool = False
    ) -> str:
        """Call OpenAI API with semaphore + retry."""
        client = self._get_openai_client()
        if client is None:
            raise RuntimeError("OpenAI client not available")

        kwargs = {
            "model": self._settings.OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        async def _do_call():
            async with self._semaphore:
                response = await client.chat.completions.create(**kwargs)
                return response.choices[0].message.content

        return await self._retry_with_backoff(_do_call, "openai")

    async def _stream_openai(
        self, prompt: str, system_prompt: str
    ) -> AsyncGenerator[str, None]:
        """Stream from OpenAI API with semaphore + retry."""
        client = self._get_openai_client()
        if client is None:
            raise RuntimeError("OpenAI client not available")

        async def _do_stream():
            stream = await client.chat.completions.create(
                model=self._settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content

        async with self._semaphore:
            async for text in self._retry_stream_with_backoff(_do_stream, "openai"):
                yield text

    # ═══════════════════════════════════════════════════════════════════════
    # PROVIDER 4: ANTHROPIC (Fallback 3 — last resort)
    # ═══════════════════════════════════════════════════════════════════════

    async def _call_anthropic(
        self, prompt: str, system_prompt: str, json_mode: bool = False
    ) -> str:
        """Call Anthropic API with semaphore + retry."""
        client = self._get_anthropic_client()
        if client is None:
            raise RuntimeError("Anthropic client not available")

        # For JSON mode, append instruction to system prompt
        effective_system = system_prompt
        if json_mode:
            effective_system += "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown fences, no extra text."

        async def _do_call():
            async with self._semaphore:
                response = await client.messages.create(
                    model=self._settings.ANTHROPIC_MODEL,
                    max_tokens=4096,
                    system=effective_system,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                )
                return response.content[0].text

        return await self._retry_with_backoff(_do_call, "anthropic")

    async def _stream_anthropic(
        self, prompt: str, system_prompt: str
    ) -> AsyncGenerator[str, None]:
        """Stream from Anthropic API with semaphore + retry."""
        client = self._get_anthropic_client()
        if client is None:
            raise RuntimeError("Anthropic client not available")

        async with self._semaphore:
            max_retries = self._settings.LLM_MAX_RETRIES
            base_delay = self._settings.LLM_RETRY_BASE_DELAY
            max_delay = self._settings.LLM_RETRY_MAX_DELAY

            for attempt in range(max_retries + 1):
                try:
                    async with client.messages.stream(
                        model=self._settings.ANTHROPIC_MODEL,
                        max_tokens=4096,
                        system=system_prompt,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                    ) as stream:
                        async for text in stream.text_stream:
                            yield text
                    return

                except Exception as e:
                    if not _is_rate_limit_error(e) or attempt >= max_retries:
                        raise

                    server_delay = _parse_retry_delay(e)
                    delay = (
                        min(server_delay + 1.0, max_delay)
                        if server_delay is not None
                        else min(base_delay * (2 ** attempt), max_delay)
                    )

                    print(
                        f"[RETRY] Stream rate limited by anthropic (attempt {attempt + 1}/{max_retries}). "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)

    # ═══════════════════════════════════════════════════════════════════════
    # PUBLIC API — Standardized Output (plain string, provider-agnostic)
    # ═══════════════════════════════════════════════════════════════════════

    async def call_llm(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        json_mode: bool = False,
    ) -> str:
        """
        Call LLM with automatic cascading failover.

        Tries each provider in order: Groq → Gemini → OpenAI → Anthropic.
        If a provider fails (429, timeout, any error), logs a warning and
        immediately attempts the next one.

        Args:
            prompt: User prompt
            system_prompt: System instruction
            json_mode: If True, request JSON-formatted output

        Returns:
            LLM response text (standardized plain string)

        Raises:
            RuntimeError: If no LLM provider is available or all fail
        """
        providers = self._get_provider_order()
        if not providers:
            raise RuntimeError(
                "No LLM API key configured. Set GROQ_API_KEY, GEMINI_API_KEY, "
                "OPENAI_API_KEY, or ANTHROPIC_API_KEY in your .env file."
            )

        call_map = {
            "groq": self._call_groq,
            "gemini": self._call_gemini,
            "openai": self._call_openai,
            "anthropic": self._call_anthropic,
        }

        last_error = None
        for i, provider in enumerate(providers):
            try:
                result = await call_map[provider](prompt, system_prompt, json_mode)
                return result
            except Exception as e:
                next_provider = providers[i + 1] if i + 1 < len(providers) else None
                if next_provider:
                    print(
                        f"[WARN] {provider.capitalize()} failed, switching to "
                        f"{next_provider.capitalize()}... (Error: {type(e).__name__})"
                    )
                else:
                    print(f"[WARN] {provider.capitalize()} failed (last provider): {e}")
                last_error = e
                continue

        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")

    async def call_llm_json(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant. Respond in JSON.",
    ) -> dict:
        """
        Call LLM and parse the response as JSON.

        Args:
            prompt: User prompt
            system_prompt: System instruction (should mention JSON output)

        Returns:
            Parsed JSON dict
        """
        raw = await self.call_llm(prompt, system_prompt, json_mode=True)

        # Clean potential markdown fences
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last lines (fences)
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)

        return json.loads(cleaned)

    async def call_multimodal(
        self,
        prompt: str,
        image_url: str,
        system_prompt: str = "You are a helpful multimodal assistant.",
        json_mode: bool = False,
    ) -> str:
        """
        Call the unified Groq Scout model with text plus one image.

        The request follows the OpenAI/Groq multimodal message format:
        user.content is an array of text and image_url parts.
        """
        if not self._settings.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is required for multimodal calls")

        return await self._call_groq_multimodal(
            prompt=prompt,
            image_url=image_url,
            system_prompt=system_prompt,
            json_mode=json_mode,
        )

    async def stream_llm(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
    ) -> AsyncGenerator[str, None]:
        """
        Stream LLM response with automatic cascading failover.

        Tries each provider in order: Groq → Gemini → OpenAI → Anthropic.

        Args:
            prompt: User prompt
            system_prompt: System instruction

        Yields:
            Text chunks as they arrive (standardized plain strings)
        """
        providers = self._get_provider_order()
        if not providers:
            raise RuntimeError(
                "No LLM API key configured. Set GROQ_API_KEY, GEMINI_API_KEY, "
                "OPENAI_API_KEY, or ANTHROPIC_API_KEY in your .env file."
            )

        stream_map = {
            "groq": self._stream_groq,
            "gemini": self._stream_gemini,
            "openai": self._stream_openai,
            "anthropic": self._stream_anthropic,
        }

        last_error = None
        for i, provider in enumerate(providers):
            try:
                async for chunk in stream_map[provider](prompt, system_prompt):
                    yield chunk
                return  # Success — stream completed
            except Exception as e:
                next_provider = providers[i + 1] if i + 1 < len(providers) else None
                if next_provider:
                    print(
                        f"[WARN] {provider.capitalize()} stream failed, switching to "
                        f"{next_provider.capitalize()}... (Error: {type(e).__name__})"
                    )
                else:
                    print(f"[WARN] {provider.capitalize()} stream failed (last provider): {e}")
                last_error = e
                continue

        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")


# ─── Singleton ────────────────────────────────────────────────────────────────

_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Get or create the singleton LLM client."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
