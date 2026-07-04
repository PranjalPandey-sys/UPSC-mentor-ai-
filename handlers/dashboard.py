"""
handlers/dashboard.py — Full navigation router
===================================================
Mirrors upsc_master_bot's handlers/*.py show_* + *_callback pattern,
section by section, but every section here is backed by the mentor AI
(services/mentor_features.py) instead of static content where the original
used static banks.

Text-capture flows (submit an answer, submit an essay, etc.) use a simple
`context.user_data["awaiting"]` state machine — same approach as the
original bot's multi-step handlers, just centralized here in one file
instead of spread across many, since this bot's flows are still small
enough to keep in one place without getting lost.
"""
import logging

from telegram import Update
from telegram.ext import ContextTypes

import config
import keyboards as kb
from handlers import evaluate as eval_handlers
from prompts import mentor_persona as mp
from services import ai_provider, context_builder, mentor_features as mf
from storage import database as db

logger = logging.getLogger(__name__)


async def _respond(update_or_query, text: str, keyboard=None) -> None:
    """Works whether called from a CallbackQuery or a plain Message."""
    if hasattr(update_or_query, "edit_message_text"):
        try:
            await update_or_query.edit_message_text(text, reply_markup=keyboard)
            return
        except Exception:
            await update_or_query.message.reply_text(text, reply_markup=keyboard)
    else:
        await update_or_query.reply_text(text, reply_markup=keyboard)


# ── Home ────────────────────────────────────────────────────────────────────

async def show_home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await db.ensure_user(user.id, user.username or "", user.full_name or "")
    text = (
        "UPSC Mentor AI — testing environment.\n\n"
        "Same navigation as your main bot. Every section here is answered "
        "by your mentor AI, personalized to what it knows about you."
    )
    query = update.callback_query
    if query:
        await query.answer()
        await _respond(query, text, kb.kb_home())
    else:
        await update.message.reply_text(text, reply_markup=kb.kb_home())


NAV_MAP = {
    "doubt": "ai_planner",   # legacy alias
}


async def nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    context.user_data["awaiting"] = None
    section = query.data.split(":", 1)[1]
    section = NAV_MAP.get(section, section)

    dispatch = {
        "home": show_home,
        "revision": show_revision,
        "answer_writing": show_answer_writing,
        "mock": show_mock,
        "current_affairs": show_ca,
        "essay": show_essay,
        "ethics": show_ethics,
        "optional": show_optional,
        "progress": show_progress,
        "streak": show_streak,
        "ai_planner": show_ai_planner,
        "settings": show_settings,
        "weekly_plan": show_weekly_plan,
        "help": show_help,
    }
    handler = dispatch.get(section)
    if handler:
        await handler(update, context)


# ── Revision (lightweight — full scheduling logic lives in the main bot) ────

async def show_revision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Revision tracking (due dates, spaced repetition) lives in your "
        "main bot. What I can do here: tell me a topic and I'll quiz you "
        "or explain it again for revision.\n\n"
        "Type a topic, or go back."
    )
    context.user_data["awaiting"] = "doubt"
    await _respond(update.callback_query, text, kb.kb_revision())


# ── Answer Writing ──────────────────────────────────────────────────────────

async def show_answer_writing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    hist = await mf.get_answer_history_text(user_id)
    text = (
        "Answer Writing Practice\n\n"
        "Master UPSC Mains answer writing with AI evaluation against the "
        "standard 100-point rubric.\n\n"
        f"Your stats:\n{hist}\n\n"
        "Choose a paper below to get a question."
    )
    await _respond(update.callback_query, text, kb.kb_answer_writing())


async def aw_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":", 1)[1]

    if action in ("gs1", "gs2", "gs3", "gs4"):
        question, subject = mf.get_gs_question(action)
        context.user_data["pending_question"] = question
        context.user_data["pending_gs_paper"] = action.upper()
        context.user_data["pending_subject"] = subject
        context.user_data["awaiting"] = "answer_text"
        await _respond(
            query,
            f"{action.upper()} — {subject}\n\n{question}\n\nType your answer when ready.",
            kb.kb_cancel_writing(),
        )
    elif action == "history":
        text = await mf.get_answer_history_text(query.from_user.id)
        await _respond(query, f"Your answer history:\n\n{text}", kb.kb_after_answer_eval())
    elif action == "photo":
        context.user_data["awaiting"] = "answer_photo"
        await _respond(
            query,
            "Send a photo of your handwritten answer. I'll transcribe and evaluate it "
            "the same way as typed answers.",
            kb.kb_cancel_writing(),
        )


async def aw_photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the photo message when awaiting == answer_photo."""
    import base64
    user_id = update.effective_user.id
    photo = update.message.photo[-1]
    tg_file = await photo.get_file()
    file_bytes = await tg_file.download_as_bytearray()
    b64 = base64.b64encode(bytes(file_bytes)).decode()

    await update.message.reply_text("Reading your handwriting, one moment.")
    transcription = await ai_provider.call_vision(
        b64, "Transcribe this handwritten UPSC answer sheet exactly as written, no commentary."
    )
    context.user_data["awaiting"] = None
    if not transcription:
        await update.message.reply_text("Couldn't read that clearly. Try a clearer, well-lit photo.",
                                         reply_markup=kb.kb_cancel_writing())
        return

    question = context.user_data.get("pending_question", "General UPSC Mains question")
    gs_paper = context.user_data.get("pending_gs_paper", "GS1")
    await update.message.reply_text("Evaluating your transcribed answer, one moment.")
    result = await eval_handlers.evaluate_answer(user_id, question, transcription, gs_paper=gs_paper)
    await update.message.reply_text(_format_answer_eval(result), reply_markup=kb.kb_after_answer_eval())


# ── Mock Test ────────────────────────────────────────────────────────────────

async def show_mock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = "Mock Test\n\nPick a subject. Each question is freshly generated at Prelims difficulty."
    await _respond(update.callback_query, text, kb.kb_mock_menu())


async def mock_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    subject = query.data.split(":", 1)[1]

    if subject == "scorecard":
        text = await mf.get_scorecard_text(query.from_user.id)
        await _respond(query, f"Score Card\n\n{text}", kb.kb_after_mock())
        return
    if subject == "end":
        await _respond(query, "Test ended.", kb.kb_after_mock())
        return

    await query.edit_message_text("Generating your question, one moment.")
    mcq = await mf.generate_mcq(subject)
    if not mcq:
        await _respond(query, "AI unavailable, try again shortly.", kb.kb_mock_menu())
        return

    context.user_data["current_mcq"] = mcq
    opts = mcq["options"]
    text = f"{mcq['subject']}\n\n{mcq['question']}\n\nA. {opts[0]}\nB. {opts[1]}\nC. {opts[2]}\nD. {opts[3]}"
    await _respond(query, text, kb.kb_mock_answer(0))


async def mcq_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    choice_idx = int(query.data.split(":")[2])
    choice_letter = ["A", "B", "C", "D"][choice_idx]
    mcq = context.user_data.get("current_mcq")
    if not mcq:
        await _respond(query, "That question expired — pick a new one.", kb.kb_mock_menu())
        return

    correct = choice_letter == mcq["correct"]
    await db.record_performance(query.from_user.id, "mock_score", 1 if correct else 0, subject=mcq["subject"])

    verdict = "Correct." if correct else f"Incorrect — correct answer was {mcq['correct']}."
    text = f"{verdict}\n\n{mcq['explanation']}"
    await _respond(query, text, kb.kb_after_mock())


# ── Current Affairs ──────────────────────────────────────────────────────────

async def show_ca(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = "Current Affairs\n\nPick a category for an AI-generated, UPSC-relevant digest."
    await _respond(update.callback_query, text, kb.kb_ca())


async def ca_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    category = query.data.split(":", 1)[1]
    await query.edit_message_text("Pulling that together, one moment.")
    text = await mf.get_ca_digest(category)
    await _respond(query, text, kb.kb_back_section("current_affairs"))


# ── Essay ────────────────────────────────────────────────────────────────────

async def show_essay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    hist = await mf.get_essay_history_text(update.effective_user.id)
    text = f"Essay Practice\n\n{hist}\n\nWhat would you like to do?"
    await _respond(update.callback_query, text, kb.kb_essay())


async def essay_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":", 1)[1]

    if action == "topic":
        topic = await mf.get_essay_topic()
        await _respond(query, f"Essay Topic:\n\n{topic}", kb.kb_essay_after())
    elif action == "outline":
        context.user_data["awaiting"] = "essay_outline_topic"
        await _respond(query, "Send the essay topic you want an outline for.", kb.kb_cancel_writing())
    elif action == "submit":
        context.user_data["awaiting"] = "essay_topic"
        await _respond(query, "Send the essay topic first, then your full essay text.", kb.kb_cancel_writing())
    elif action == "history":
        text = await mf.get_essay_history_text(query.from_user.id)
        await _respond(query, f"Your essay history:\n\n{text}", kb.kb_essay_after())
    elif action == "tips":
        tips = await mf.get_essay_tips()
        await _respond(query, tips, kb.kb_essay_after())


# ── Ethics ───────────────────────────────────────────────────────────────────

async def show_ethics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    hist = await mf.get_ethics_history_text(update.effective_user.id)
    text = f"GS4 Ethics\n\n{hist}\n\nWhat would you like to do?"
    await _respond(update.callback_query, text, kb.kb_ethics())


async def ethics_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":", 1)[1]

    if action == "case":
        case = await mf.get_ethics_case()
        await _respond(query, f"Case Study:\n\n{case}\n\nTap Submit Analysis when ready to answer it.",
                       kb.kb_ethics())
    elif action == "submit":
        context.user_data["awaiting"] = "ethics_scenario"
        await _respond(query, "Send the case-study scenario first, then your full analysis.",
                       kb.kb_cancel_writing())
    elif action == "framework":
        text = await mf.get_ethics_framework()
        await _respond(query, text, kb.kb_ethics())
    elif action == "thinkers":
        text = await mf.get_ethics_thinkers()
        await _respond(query, text, kb.kb_ethics())
    elif action == "history":
        text = await mf.get_ethics_history_text(query.from_user.id)
        await _respond(query, f"Your ethics performance:\n\n{text}", kb.kb_ethics())


# ── Optional ─────────────────────────────────────────────────────────────────

async def show_optional(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = await db.get_user_profile(update.effective_user.id) or {}
    subj = profile.get("optional_subject") or "not set — use Settings to set one"
    text = f"Optional Subject: {subj}\n\nWhat do you need?"
    await _respond(update.callback_query, text, kb.kb_optional())


async def opt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    area = query.data.split(":", 1)[1]
    await query.edit_message_text("One moment.")
    text = await mf.get_optional_guidance(query.from_user.id, area)
    await _respond(query, text, kb.kb_optional())


# ── Progress ─────────────────────────────────────────────────────────────────

async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = "Progress\n\nPick what you want the mentor to look at."
    await _respond(update.callback_query, text, kb.kb_progress())


async def prog_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":", 1)[1]
    user_id = query.from_user.id

    if action == "weekly":
        await query.edit_message_text("Building your weekly report, one moment.")
        text = await mf.get_weekly_report(user_id)
        await _respond(query, text, kb.kb_progress())
    elif action == "mocks":
        text = await mf.get_scorecard_text(user_id)
        await _respond(query, f"Mock Scores\n\n{text}", kb.kb_progress())
    elif action == "answers":
        text = await mf.get_answer_history_text(user_id)
        await _respond(query, f"Answer Writing Stats\n\n{text}", kb.kb_progress())
    elif action == "weak":
        memories = await db.get_active_memories(user_id, limit=30)
        weak = [m["fact"] for m in memories if m["category"] == "WEAKNESS"]
        text = "Weak Areas\n\n" + ("\n".join(f"- {w}" for w in weak) if weak else
                                    "Nothing flagged yet — keep chatting with your mentor and this will fill in.")
        await _respond(query, text, kb.kb_progress())
    elif action == "subjects":
        await query.edit_message_text("Analysing, one moment.")
        text = await mf.get_progress_analysis(user_id)
        await _respond(query, text, kb.kb_progress())
    elif action == "badges":
        await _respond(query, "Badges and XP are tracked in your main bot — this testing bot "
                              "focuses on the AI-mentor sections.", kb.kb_progress())


# ── Streak (gamification lives in the main bot) ─────────────────────────────

async def show_streak(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = ("Streak, XP, badges, and leaderboard are tracked in your main bot. "
            "This testing bot mirrors the layout so the two feel consistent, "
            "but the gamification data itself isn't duplicated here.")
    await _respond(update.callback_query, text, kb.kb_streak())


async def streak_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await _respond(query, "This is tracked in your main bot.", kb.kb_streak())


# ── AI Planner ───────────────────────────────────────────────────────────────

async def show_ai_planner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = "AI Planner\n\nAsk anything, get a current affairs summary, or request a report."
    await _respond(update.callback_query, text, kb.kb_ai_planner())


async def ai_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":", 1)[1]
    user_id = query.from_user.id

    if action == "doubt":
        context.user_data["awaiting"] = "doubt"
        await _respond(query, "Type your question.", kb.kb_cancel_doubt())
    elif action == "ca":
        context.user_data["awaiting"] = "ca_search"
        await _respond(query, "Type a current affairs topic (e.g. 'RBI rate decision').", kb.kb_cancel_doubt())
    elif action == "flashcard":
        await query.edit_message_text("Generating, one moment.")
        result = await ai_provider.call(
            "Generate one UPSC flashcard: a short factual Q on one line prefixed 'Q:' and "
            "the answer on the next line prefixed 'A:'. Nothing else.",
            "Generate a flashcard.", max_tokens=150, temperature=0.7,
        )
        await _respond(query, result or "AI unavailable, try again shortly.", kb.kb_ai_planner())
    elif action == "analysis":
        await query.edit_message_text("Analysing your plan, one moment.")
        text = await mf.get_progress_analysis(user_id)
        await _respond(query, text, kb.kb_ai_planner())
    elif action == "weekly_report":
        await query.edit_message_text("Building your weekly mentor report, one moment.")
        text = await mf.get_weekly_report(user_id)
        await _respond(query, text, kb.kb_ai_planner())
    elif action == "monthly_report":
        await query.edit_message_text("Building your monthly review, one moment.")
        text = await mf.get_monthly_report(user_id)
        await _respond(query, text, kb.kb_ai_planner())


# ── Settings ─────────────────────────────────────────────────────────────────

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    prefs = await db.get_preferences(update.effective_user.id)
    text = (
        f"Settings\n\n"
        f"Mentor persona: {prefs.get('persona') or 'default'}\n"
        f"Response length: {prefs.get('response_length', 'standard')}"
    )
    await _respond(update.callback_query, text, kb.kb_settings())


async def set_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":", 1)[1]

    if action == "persona":
        await _respond(query, "Choose a mentor persona for this testing bot:", kb.kb_persona_choice())
    elif action == "length":
        context.user_data["awaiting"] = "set_length"
        await _respond(query, "Reply with: brief, standard, or detailed.", kb.kb_back_section("settings"))
    elif action == "change_plan":
        await _respond(query, "Changing your study plan happens in the main bot — this testing bot "
                              "doesn't own that data.", kb.kb_settings())
    elif action == "delete_data":
        await _respond(query, "This will delete all your data from THIS testing bot only "
                              "(not your main bot). Confirm?", kb.kb_confirm_delete())
    elif action == "confirm_delete":
        await db.update_user_profile(query.from_user.id, level="beginner", weak_subjects="[]")
        await _respond(query, "Your testing-bot data has been reset.", kb.kb_settings())


async def persona_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    persona = query.data.split(":", 1)[1]
    await db.set_preference(query.from_user.id, persona=persona)
    await _respond(query, f"Mentor persona set to: {persona.replace('_', ' ')}.", kb.kb_settings())


# ── Weekly Plan / Help ───────────────────────────────────────────────────────

async def show_weekly_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await query_or_msg_edit(update, "Weekly plan and roadmap live in your main bot. Use AI Planner "
                                     "here for a mentor-generated weekly report instead.", kb.kb_back_home())


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "This is the UPSC Mentor AI testing bot — same layout as your main bot, "
        "AI-powered mentor behind every section.\n\n"
        "Ask a Doubt / AI Planner: free-form mentor Q&A with memory.\n"
        "Answer Writing, Essay, Ethics: AI evaluation against real rubrics.\n"
        "Mock Test: freshly generated MCQs.\n"
        "Progress: AI analysis of your recorded performance.\n"
        "Streak/Badges: tracked in your main bot, shown here for layout parity only."
    )
    await query_or_msg_edit(update, text, kb.kb_back_home())


async def query_or_msg_edit(update: Update, text: str, keyboard) -> None:
    query = update.callback_query
    if query:
        await query.answer()
        await _respond(query, text, keyboard)
    else:
        await update.message.reply_text(text, reply_markup=keyboard)


def _format_answer_eval(r: dict) -> str:
    return (
        f"Score: {r['score']}/100\n\n"
        f"Introduction: {r['introduction']}/20\n"
        f"Content: {r['content']}/30\n"
        f"Examples: {r['examples']}/20\n"
        f"Structure: {r['structure']}/15\n"
        f"Conclusion: {r['conclusion']}/15\n\n"
        f"Strengths: {r['strengths']}\n\n"
        f"Improvements: {r['improvements']}\n\n"
        f"Model Approach: {r['model_approach']}"
    )
