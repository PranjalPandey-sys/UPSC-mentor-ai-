"""
bot.py — UPSC Mentor AI (Testing Bot) — Entry Point
=======================================================
Same production-grade startup sequence as the main UPSC Master Bot:
1. Logging
2. DB init
3. Handler registration
4. Flask keep-alive thread (separate port from the main bot)
5. Polling start

Deliberately kept structurally close to the main bot's bot.py so this can
be folded back in later with minimal surprise (see README §5).

Python 3.11.9 | python-telegram-bot 20.7
"""
import asyncio
import logging
import threading

from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from utils.logger import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

import config
from storage import database as db
from keyboards import home_keyboard, back_home_keyboard
from handlers import mentor_chat, admin
from handlers import evaluate as eval_handlers
from prompts.mentor_persona import ca_summary_prompt
from services import ai_provider


# ── Flask keep-alive ────────────────────────────────────────────────────────

def _start_flask() -> None:
    try:
        from flask import Flask, jsonify
        app = Flask("mentor_ai_keepalive")

        @app.route("/ping")
        def ping():
            return "pong", 200

        @app.route("/")
        def index():
            return jsonify({"status": "ok", "service": "UPSC Mentor AI (testing)"}), 200

        app.run(host="0.0.0.0", port=config.PORT, debug=False, use_reloader=False)
    except ImportError:
        logger.warning("Flask not installed — skipping keep-alive server")
    except Exception as exc:
        logger.error("Flask server error: %s", exc)


# ── Conversation "mode" tracking (lightweight, no FSM library) ─────────────
# user_data["awaiting"] in {"answer_question", "answer_text", "essay_topic",
#                            "essay_text", "ethics_scenario", "ethics_text", None}

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await db.ensure_user(user.id, user.username or "", user.full_name or "")
    text = (
        "UPSC Mentor AI — testing environment.\n\n"
        "I'm your mentor for doubt-solving, answer evaluation, essay review, "
        "and ethics case studies. Everything here runs separately from your "
        "main bot, so nothing you do here touches it.\n\n"
        "Pick something below, or just type a UPSC question directly."
    )
    await update.message.reply_text(text, reply_markup=home_keyboard())


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await admin.admin_stats(update, context)


async def on_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action = query.data
    context.user_data["awaiting"] = None

    if action == "menu_home":
        await query.edit_message_text("Home.", reply_markup=home_keyboard())
    elif action == "menu_doubt":
        context.user_data["awaiting"] = "doubt"
        await query.edit_message_text("Type your UPSC question.", reply_markup=back_home_keyboard())
    elif action == "menu_evaluate":
        context.user_data["awaiting"] = "answer_question"
        await query.edit_message_text("Send the question first, then the answer as a separate message.",
                                       reply_markup=back_home_keyboard())
    elif action == "menu_essay":
        context.user_data["awaiting"] = "essay_topic"
        await query.edit_message_text("Send the essay topic first, then the essay text.",
                                       reply_markup=back_home_keyboard())
    elif action == "menu_ethics":
        context.user_data["awaiting"] = "ethics_scenario"
        await query.edit_message_text("Send the case-study scenario first, then your analysis.",
                                       reply_markup=back_home_keyboard())
    elif action == "menu_ca":
        context.user_data["awaiting"] = "ca_topic"
        await query.edit_message_text("Type a current affairs topic (e.g. 'RBI rate decision').",
                                       reply_markup=back_home_keyboard())
    elif action == "menu_progress":
        stats = await db.get_study_progress(query.from_user.id)
        stats = stats or {}
        await query.edit_message_text(
            f"Streak: {stats.get('streak', 0)}\n"
            f"Answers written: {stats.get('answers_written', 0)}\n"
            f"Mocks taken: {stats.get('mocks_taken', 0)}",
            reply_markup=back_home_keyboard(),
        )


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    awaiting = context.user_data.get("awaiting")
    text = (update.message.text or "").strip()
    user_id = update.effective_user.id

    if awaiting == "answer_question":
        context.user_data["pending_question"] = text
        context.user_data["awaiting"] = "answer_text"
        await update.message.reply_text("Got the question. Now send your answer text.")
        return

    if awaiting == "answer_text":
        question = context.user_data.pop("pending_question", "")
        context.user_data["awaiting"] = None
        await update.message.reply_text("Evaluating your answer, one moment.")
        result = await eval_handlers.evaluate_answer(user_id, question, text)
        await update.message.reply_text(_format_answer_eval(result), reply_markup=back_home_keyboard())
        return

    if awaiting == "essay_topic":
        context.user_data["pending_topic"] = text
        context.user_data["awaiting"] = "essay_text"
        await update.message.reply_text("Got the topic. Now send your essay text.")
        return

    if awaiting == "essay_text":
        topic = context.user_data.pop("pending_topic", "")
        context.user_data["awaiting"] = None
        await update.message.reply_text("Evaluating your essay, one moment.")
        result = await eval_handlers.evaluate_essay(user_id, topic, text)
        await update.message.reply_text(_format_essay_eval(result), reply_markup=back_home_keyboard())
        return

    if awaiting == "ethics_scenario":
        context.user_data["pending_scenario"] = text
        context.user_data["awaiting"] = "ethics_text"
        await update.message.reply_text("Got the scenario. Now send your analysis.")
        return

    if awaiting == "ethics_text":
        scenario = context.user_data.pop("pending_scenario", "")
        context.user_data["awaiting"] = None
        await update.message.reply_text("Evaluating your case study, one moment.")
        result = await eval_handlers.evaluate_ethics(user_id, scenario, text)
        await update.message.reply_text(_format_ethics_eval(result), reply_markup=back_home_keyboard())
        return

    if awaiting == "ca_topic":
        context.user_data["awaiting"] = None
        result = await ai_provider.call(ca_summary_prompt(), f"UPSC CA summary on: {text}",
                                         max_tokens=config.TOKENS_CA_SUMMARY)
        await update.message.reply_text(result or "AI unavailable, try again shortly.",
                                         reply_markup=back_home_keyboard())
        return

    # Default: treat any free text as a doubt.
    await mentor_chat.handle_doubt(update, context)


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


def _format_essay_eval(r: dict) -> str:
    return f"Score: {r['score']}/125\n\nImprovements: {r['improvements']}\n\nStrongest line: {r['best_line']}"


def _format_ethics_eval(r: dict) -> str:
    return (
        f"Score: {r['score']}/100\n\n"
        f"Steps covered: {r['steps_covered']}\n\n"
        f"Strengths: {r['strengths']}\n\n"
        f"Gaps: {r['gaps']}\n\n"
        f"Improvements: {r['improvements']}"
    )


async def _post_init(application: Application) -> None:
    await application.bot.set_my_commands([
        BotCommand("start", "Start / home menu"),
        BotCommand("admin", "Admin stats (admins only)"),
    ])
    logger.info("✅ Bot commands registered")


def main() -> None:
    if not config.BOT_TOKEN:
        logger.error("❌ MENTOR_BOT_TOKEN not set. Get a token from @BotFather and set it as an env var.")
        return

    db.init_db()

    threading.Thread(target=_start_flask, daemon=True).start()

    application = Application.builder().token(config.BOT_TOKEN).post_init(_post_init).build()

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("admin", cmd_admin))
    application.add_handler(CallbackQueryHandler(on_menu, pattern="^menu_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    logger.info("🚀 UPSC Mentor AI (testing bot) starting polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
