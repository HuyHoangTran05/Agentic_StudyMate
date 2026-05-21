"""
Agentic StudyMate — Unified LLM Client

Abstracts Gemini / OpenAI / Anthropic behind one async interface.
Supports both structured (JSON) responses and streaming text.

Fallback chain: Gemini → OpenAI → Anthropic.
If the primary provider fails, automatically tries the next.
"""

import json
import asyncio
from typing import AsyncGenerator

from app.config import get_settings


class LLMClient:
    """
    Unified LLM client with multi-provider fallback.

    Usage:
        client = get_llm_client()
        result = await client.call_llm("What is X?", system_prompt="...")
        async for chunk in client.stream_llm("Explain Y", system_prompt="..."):
            print(chunk, end="")
    """

    def __init__(self):
        self._settings = get_settings()
        self._gemini_client = None
        self._openai_client = None
        self._anthropic_client = None

    # ─── Provider Initialization (Lazy) ───────────────────────────────────

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
        """Return available providers in priority order."""
        providers = []
        if self._settings.GEMINI_API_KEY:
            providers.append("gemini")
        if self._settings.OPENAI_API_KEY:
            providers.append("openai")
        if self._settings.ANTHROPIC_API_KEY:
            providers.append("anthropic")
        return providers

    # ─── Gemini ───────────────────────────────────────────────────────────

    async def _call_gemini(
        self, prompt: str, system_prompt: str, json_mode: bool = False
    ) -> str:
        """Call Gemini API (sync SDK wrapped in thread)."""
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

        response = await asyncio.to_thread(
            client.models.generate_content,
            model=self._settings.GEMINI_MODEL,
            contents=prompt,
            config=config,
        )
        return response.text

    async def _stream_gemini(
        self, prompt: str, system_prompt: str
    ) -> AsyncGenerator[str, None]:
        """Stream from Gemini API."""
        client = self._get_gemini_client()
        if client is None:
            raise RuntimeError("Gemini client not available")

        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.3,
        )

        # Gemini's stream is sync — run in thread and yield via queue
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        def _stream_sync():
            response = client.models.generate_content_stream(
                model=self._settings.GEMINI_MODEL,
                contents=prompt,
                config=config,
            )
            for chunk in response:
                if chunk.text:
                    queue.put_nowait(chunk.text)
            queue.put_nowait(None)  # sentinel

        task = asyncio.get_event_loop().run_in_executor(None, _stream_sync)

        while True:
            try:
                text = await asyncio.wait_for(queue.get(), timeout=60.0)
            except asyncio.TimeoutError:
                break
            if text is None:
                break
            yield text

        await task  # ensure thread completes

    # ─── OpenAI ───────────────────────────────────────────────────────────

    async def _call_openai(
        self, prompt: str, system_prompt: str, json_mode: bool = False
    ) -> str:
        """Call OpenAI API."""
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

        response = await client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    async def _stream_openai(
        self, prompt: str, system_prompt: str
    ) -> AsyncGenerator[str, None]:
        """Stream from OpenAI API."""
        client = self._get_openai_client()
        if client is None:
            raise RuntimeError("OpenAI client not available")

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

    # ─── Anthropic ────────────────────────────────────────────────────────

    async def _call_anthropic(
        self, prompt: str, system_prompt: str, json_mode: bool = False
    ) -> str:
        """Call Anthropic API."""
        client = self._get_anthropic_client()
        if client is None:
            raise RuntimeError("Anthropic client not available")

        # For JSON mode, append instruction to system prompt
        effective_system = system_prompt
        if json_mode:
            effective_system += "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown fences, no extra text."

        response = await client.messages.create(
            model=self._settings.ANTHROPIC_MODEL,
            max_tokens=4096,
            system=effective_system,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return response.content[0].text

    async def _stream_anthropic(
        self, prompt: str, system_prompt: str
    ) -> AsyncGenerator[str, None]:
        """Stream from Anthropic API."""
        client = self._get_anthropic_client()
        if client is None:
            raise RuntimeError("Anthropic client not available")

        async with client.messages.stream(
            model=self._settings.ANTHROPIC_MODEL,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    # ─── Public API ───────────────────────────────────────────────────────

    async def call_llm(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        json_mode: bool = False,
    ) -> str:
        """
        Call LLM with automatic provider fallback.

        Args:
            prompt: User prompt
            system_prompt: System instruction
            json_mode: If True, request JSON-formatted output

        Returns:
            LLM response text

        Raises:
            RuntimeError: If no LLM provider is available or all fail
        """
        providers = self._get_provider_order()
        if not providers:
            raise RuntimeError(
                "No LLM API key configured. Set GEMINI_API_KEY, OPENAI_API_KEY, "
                "or ANTHROPIC_API_KEY in your .env file."
            )

        call_map = {
            "gemini": self._call_gemini,
            "openai": self._call_openai,
            "anthropic": self._call_anthropic,
        }

        last_error = None
        for provider in providers:
            try:
                result = await call_map[provider](prompt, system_prompt, json_mode)
                return result
            except Exception as e:
                print(f"⚠ LLM call failed with {provider}: {e}")
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

    async def stream_llm(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
    ) -> AsyncGenerator[str, None]:
        """
        Stream LLM response with automatic provider fallback.

        Args:
            prompt: User prompt
            system_prompt: System instruction

        Yields:
            Text chunks as they arrive
        """
        providers = self._get_provider_order()
        if not providers:
            raise RuntimeError(
                "No LLM API key configured. Set GEMINI_API_KEY, OPENAI_API_KEY, "
                "or ANTHROPIC_API_KEY in your .env file."
            )

        stream_map = {
            "gemini": self._stream_gemini,
            "openai": self._stream_openai,
            "anthropic": self._stream_anthropic,
        }

        last_error = None
        for provider in providers:
            try:
                async for chunk in stream_map[provider](prompt, system_prompt):
                    yield chunk
                return  # Success — stream completed
            except Exception as e:
                print(f"⚠ LLM stream failed with {provider}: {e}")
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
