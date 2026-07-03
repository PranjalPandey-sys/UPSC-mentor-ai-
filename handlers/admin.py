"""
handlers/admin.py — AI-focused admin panel
==============================================
Mirrors the main bot's admin panel scope but focused on AI health: this is
where you'd have caught the truncation bug in production, via the
finish_reason breakdown (a spike in 'length'/'MAX_TOKENS' with tiny
completion_tokens is the signature).
"""
import logging

from telegram import Update
from telegram.ext import ContextTypes

import config
from storage import database as db

logger = logging.getLogger(__name__)


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id not in config.ADMIN_IDS:
        await update.message.reply_text("Not authorized.")
        return

    stats = await db.get_admin_stats()
    breakdown = stats["finish_reason_breakdown_24h"]
    breakdown_lines = "\n".join(f"  {k or 'none'}: {v}" for k, v in breakdown.items()) or "  no AI calls yet"

    length_hits = breakdown.get("length", 0) + breakdown.get("MAX_TOKENS", 0)
    warning = ""
    if length_hits > 0:
        warning = (
            f"\n\nWARNING: {length_hits} response(s) in the last 24h hit the "
            "max_tokens limit. If this climbs, check GEMINI_REASONING_EFFORT "
            "is still 'none' and consider raising the relevant TOKENS_* value "
            "in config.py."
        )

    text = (
        "Admin Stats (last 24h)\n\n"
        f"Total users: {stats['total_users']}\n"
        f"Active today: {stats['active_today']}\n"
        f"AI requests today: {stats['ai_requests_today']}\n"
        f"Errors today: {stats['errors_today']}\n\n"
        f"finish_reason breakdown:\n{breakdown_lines}"
        f"{warning}"
    )
    await update.message.reply_text(text)
