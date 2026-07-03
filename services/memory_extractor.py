"""
services/memory_extractor.py — Selective Memory Extraction
=============================================================
Runs periodically (every N user messages, see config.MEMORY_EXTRACTION_EVERY_N_MSGS)
rather than on every single message — keeps cost down and avoids storing noise.

Extracts only durable facts (goals, weaknesses, strengths, patterns,
preferences) and writes them to user_memories. Never stores full chat text
here — that lives in chat_messages with a TTL/rolling window instead.
"""
import logging

from prompts.mentor_persona import memory_extraction_prompt
from services import ai_provider
import config
from storage import database as db

logger = logging.getLogger(__name__)

_VALID_TAGS = {"GOAL", "WEAKNESS", "STRENGTH", "PATTERN", "PREFERENCE"}


async def maybe_extract(user_id: int, recent_messages: list[str]) -> None:
    """
    Call this after every user message. It only actually calls the AI
    every MEMORY_EXTRACTION_EVERY_N_MSGS turns, on a rolling window of
    recent messages, to keep it cheap.
    """
    turn_count = await db.increment_turn_counter(user_id)
    if turn_count % config.MEMORY_EXTRACTION_EVERY_N_MSGS != 0:
        return

    joined = "\n".join(recent_messages[-config.MEMORY_EXTRACTION_EVERY_N_MSGS:])
    result = await ai_provider.call(
        system=memory_extraction_prompt(),
        user_msg=joined,
        max_tokens=config.TOKENS_MEMORY_EXTRACT,
        temperature=0.1,
    )
    if not result or result.strip().upper() == "NONE":
        return

    for line in result.strip().splitlines():
        line = line.strip()
        if not line.startswith("["):
            continue
        try:
            tag, _, fact = line.partition("]")
            tag = tag.strip("[").strip().upper()
            fact = fact.strip(" -")
            if tag in _VALID_TAGS and fact:
                await db.upsert_memory(user_id, tag, fact)
        except Exception as exc:
            logger.warning("Memory line parse failed: %r (%s)", line, exc)
