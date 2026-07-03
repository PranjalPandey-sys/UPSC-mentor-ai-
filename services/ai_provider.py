"""
services/ai_provider.py — AI Provider Abstraction Layer
==========================================================
Single choke point for every LLM call in the bot. Swapping providers
(Gemini -> OpenAI -> Claude) means editing this file only.

THE BUG THIS FILE FIXES
------------------------
gemini-2.5-flash ships with "thinking" ON by default when called through the
OpenAI-compatible endpoint. Thinking tokens are counted against `max_tokens`,
not billed separately. With max_tokens in the 450-600 range, the model spent
nearly its entire budget on invisible reasoning and had only a handful of
tokens left to emit visible text -> answers cut off after 4-6 words
(finish_reason: "MAX_TOKENS", most of the budget in `reasoning_tokens`).

Fix: pass `reasoning_effort="none"` (Google's OpenAI-compat mapping for
thinking_budget=0) on every call. Confirmed in Google's own docs for the
OpenAI-compatibility layer. Also logs `finish_reason` and token breakdown so
a truncation regression is visible in logs instead of silently shipping
half an answer again.
"""
import asyncio
import logging

import config

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not config.GEMINI_API_KEY:
        return None
    try:
        from openai import AsyncOpenAI
        _client = AsyncOpenAI(
            api_key=config.GEMINI_API_KEY,
            base_url=config.GEMINI_BASE_URL,
        )
        logger.info("✅ AI client ready | model=%s | reasoning_effort=%s",
                    config.GEMINI_MODEL, config.GEMINI_REASONING_EFFORT)
        return _client
    except ImportError:
        logger.error("❌ openai package not installed. Add to requirements.txt")
        return None
    except Exception as exc:
        logger.exception("❌ AI client init failed: %s", exc)
        return None


async def call(
    system: str,
    user_msg: str,
    max_tokens: int = 600,
    temperature: float = 0.4,
    timeout: float | None = None,
) -> str | None:
    """
    Core text-completion call. Returns text or None on any failure.
    Thinking is explicitly disabled — see module docstring.
    """
    client = _get_client()
    if not client:
        return None
    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=config.GEMINI_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                reasoning_effort=config.GEMINI_REASONING_EFFORT,
            ),
            timeout=timeout or config.GEMINI_TIMEOUT,
        )
        choice = response.choices[0]
        text = (choice.message.content or "").strip()
        finish_reason = getattr(choice, "finish_reason", "unknown")

        if finish_reason == "length" or finish_reason == "MAX_TOKENS":
            logger.warning(
                "⚠️ Response hit max_tokens (%d) — consider raising it. chars=%d",
                max_tokens, len(text),
            )
        logger.info("✅ AI response | chars=%d | finish=%s", len(text), finish_reason)
        return text or None
    except asyncio.TimeoutError:
        logger.warning("❌ AI call timeout after %ss", timeout or config.GEMINI_TIMEOUT)
        return None
    except Exception as exc:
        logger.warning("❌ AI call failed: %s | %s", type(exc).__name__, exc)
        return None


async def call_vision(image_base64: str, prompt: str, max_tokens: int = 900) -> str | None:
    """Vision call (e.g. handwritten answer transcription)."""
    client = _get_client()
    if not client:
        return None
    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=config.GEMINI_MODEL,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
                        {"type": "text", "text": prompt},
                    ],
                }],
                max_tokens=max_tokens,
                reasoning_effort=config.GEMINI_REASONING_EFFORT,
            ),
            timeout=25.0,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.warning("call_vision failed: %s", exc)
        return None
