"""
services/context_builder.py — Compact Context Assembly
==========================================================
Called before every AI response. Builds a small, high-signal context block
instead of dumping the whole database at the model.

Order of operations (per the spec):
1. Load user profile          (level, timeline, weak subjects, phase)
2. Load important memories    (top N by recency/relevance, not everything)
3. Load recent chats          (last RECENT_CHAT_WINDOW messages)
4. Load study progress        (streak, completion %, last active)
5. Load summaries             (rolling weekly summary if one exists)
6. Build compact context      (this function's return value)
7. -> handlers pass this string into the relevant prompts.* system prompt
"""
import config
from storage import database as db


async def build_context(user_id: int) -> dict:
    profile = await db.get_user_profile(user_id)
    memories = await db.get_active_memories(user_id, limit=config.MAX_ACTIVE_MEMORIES)
    recent = await db.get_recent_messages(user_id, limit=config.RECENT_CHAT_WINDOW)
    progress = await db.get_study_progress(user_id)
    summary = await db.get_latest_summary(user_id)
    flags = await db.get_progress_flags(user_id)

    return {
        "profile": profile,
        "memories": memories,
        "recent_messages": recent,
        "progress": progress,
        "summary": summary,
        "flags": flags,
    }


def render_context_block(ctx: dict) -> str:
    """Turn the structured context dict into a compact text block for the prompt."""
    p = ctx["profile"] or {}
    lines = []

    if p:
        lines.append(
            f"Profile: level={p.get('level', 'unknown')}, "
            f"timeline={p.get('timeline_months', '?')}mo, "
            f"weak_subjects={p.get('weak_subjects', '[]')}"
        )

    if ctx["memories"]:
        mem_lines = [f"- [{m['category']}] {m['fact']}" for m in ctx["memories"]]
        lines.append("Known about this student:\n" + "\n".join(mem_lines))

    if ctx["progress"]:
        pr = ctx["progress"]
        lines.append(
            f"Progress: streak={pr.get('streak', 0)}, "
            f"days_done={pr.get('days_done', 0)}, "
            f"last_active={pr.get('last_active', 'unknown')}"
        )

    if ctx["summary"]:
        lines.append(f"Last summary: {ctx['summary']}")

    if ctx["recent_messages"]:
        lines.append("Recent conversation (most recent last):\n" + "\n".join(ctx["recent_messages"]))

    return "\n\n".join(lines) if lines else "No prior context available for this student."
