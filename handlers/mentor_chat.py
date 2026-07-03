"""
handlers/mentor_chat.py — General mentor Q&A
================================================
This is the main "talk to your mentor" flow: context is built, memory is
consulted, the AI answers in the structured mentor format, and the
extractor runs in the background to keep memory current.
"""
import logging
import time

from telegram import Update
from telegram.ext import ContextTypes

import config
from prompts.mentor_persona import doubt_prompt
from services import ai_provider, context_builder, memory_extractor
from storage import database as db

logger = logging.getLogger(__name__)

_FALLBACK = (
    "AI temporarily unavailable.\n\n"
    "For this topic, refer to standard sources: NCERTs for fundamentals, "
    "Laxmikanth for Polity, Shankar IAS for Environment, Spectrum for "
    "Modern History, and the Economic Survey for Economy.\n\n"
    "Try again in a moment."
)


async def handle_doubt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    question = (update.message.text or "").strip()

    if len(question) < 5:
        await update.message.reply_text("Please type a complete question (at least 5 characters).")
        return

    await db.ensure_user(user.id, user.username or "", user.full_name or "")
    await db.log_message(user.id, "user", question, feature="doubt")

    ctx = await context_builder.build_context(user.id)
    context_block = context_builder.render_context_block(ctx)
    profile = ctx["profile"] or {}

    system = doubt_prompt(
        level=profile.get("level", "intermediate"),
        phase=profile.get("phase", ""),
        subject="",
    )
    user_msg = f"{context_block}\n\nStudent's question: {question}"

    start = time.monotonic()
    result = await ai_provider.call(system, user_msg, max_tokens=config.TOKENS_DOUBT)
    latency_ms = int((time.monotonic() - start) * 1000)

    await db.log_ai_session(
        user.id, "doubt",
        completion_tokens=len(result.split()) if result else 0,
        finish_reason="stop" if result else "error",
        latency_ms=latency_ms,
        success=bool(result),
    )

    reply = result if result else _FALLBACK
    await update.message.reply_text(reply)

    if result:
        await db.log_message(user.id, "assistant", result, feature="doubt")
        recent = await db.get_recent_messages(user.id, limit=config.RECENT_CHAT_WINDOW)
        await memory_extractor.maybe_extract(user.id, recent)
