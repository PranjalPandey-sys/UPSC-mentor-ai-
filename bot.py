"""
bot.py — UPSC Mentor AI (Testing Bot) — Entry Point
=======================================================
Registers the full navigation tree mirrored from the main UPSC bot
(handlers/dashboard.py) plus the AI Q&A flows (handlers/mentor_chat.py,
handlers/evaluate.py). See README.md / ARCHITECTURE.md for the full map.

Python 3.11.9 | python-telegram-bot 20.7
"""
import logging
import threading
import time

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
import keyboards as kb
from handlers import admin, dashboard, mentor_chat
from handlers import evaluate as eval_handlers
from prompts.mentor_persona import ca_category_prompt
from services import ai_provider
from utils.keep_alive import start_keep_alive


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


# ── Commands ────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await dashboard.show_home(update, context)


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await admin.admin_stats(update, context)


# ── Text state machine (multi-step capture flows) ──────────────────────────

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    awaiting = context.user_data.get("awaiting")
    text = (update.message.text or "").strip()
    user_id = update.effective_user.id

    if awaiting == "answer_text":
        question = context.user_data.get("pending_question", "")
        gs_paper = context.user_data.get("pending_gs_paper", "GS1")
        context.user_data["awaiting"] = None
        await update.message.reply_text("Evaluating your answer, one moment.")
        result = await eval_handlers.evaluate_answer(user_id, question, text, gs_paper=gs_paper)
        await update.message.reply_text(dashboard._format_answer_eval(result), reply_markup=kb.kb_after_answer_eval())
        return

    if awaiting == "essay_outline_topic":
        context.user_data["awaiting"] = None
        from services import mentor_features as mf
        outline = await mf.get_essay_outline(text)
        await update.message.reply_text(f"Outline:\n\n{outline}", reply_markup=kb.kb_essay_after())
        return

    if awaiting == "essay_topic":
        context.user_data["pending_essay_topic"] = text
        context.user_data["awaiting"] = "essay_text"
        await update.message.reply_text("Got the topic. Now send your essay text.")
        return

    if awaiting == "essay_text":
        topic = context.user_data.pop("pending_essay_topic", "")
        context.user_data["awaiting"] = None
        await update.message.reply_text("Evaluating your essay, one moment.")
        result = await eval_handlers.evaluate_essay(user_id, topic, text)
        await update.message.reply_text(
            f"Score: {result['score']}/125\n\nImprovements: {result['improvements']}\n\n"
            f"Strongest line: {result['best_line']}",
            reply_markup=kb.kb_essay_after(),
        )
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
        await update.message.reply_text(
            f"Score: {result['score']}/100\n\nSteps covered: {result['steps_covered']}\n\n"
            f"Strengths: {result['strengths']}\n\nGaps: {result['gaps']}\n\n"
            f"Improvements: {result['improvements']}",
            reply_markup=kb.kb_ethics(),
        )
        return

    if awaiting == "ca_search":
        context.user_data["awaiting"] = None
        result = await ai_provider.call(ca_category_prompt(text), f"Current affairs on: {text}",
                                         max_tokens=config.TOKENS_CA_SUMMARY)
        await update.message.reply_text(result or "AI unavailable, try again shortly.",
                                         reply_markup=kb.kb_back_home())
        return

    if awaiting == "set_length":
        length = text.lower().strip()
        if length not in ("brief", "standard", "detailed"):
            await update.message.reply_text("Please reply with one of: brief, standard, detailed.")
            return
        context.user_data["awaiting"] = None
        await db.set_preference(user_id, response_length=length)
        await update.message.reply_text(f"Response length set to: {length}.", reply_markup=kb.kb_settings())
        return

    # Default: treat any free text as a doubt (also covers "doubt" awaiting state).
    await mentor_chat.handle_doubt(update, context)


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get("awaiting") == "answer_photo":
        await dashboard.aw_photo_handler(update, context)
    else:
        await update.message.reply_text(
            "Photo received, but I'm not expecting one right now. Go to Answer Writing > "
            "Upload Photo if you want me to evaluate a handwritten answer.",
            reply_markup=kb.kb_back_home(),
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
    time.sleep(1.5)  # let Flask bind its port before the keep-awake thread starts pinging it
    start_keep_alive()

    application = Application.builder().token(config.BOT_TOKEN).post_init(_post_init).build()

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("admin", cmd_admin))

    application.add_handler(CallbackQueryHandler(dashboard.nav_callback, pattern=r"^nav:"))
    application.add_handler(CallbackQueryHandler(dashboard.aw_callback, pattern=r"^aw:"))
    application.add_handler(CallbackQueryHandler(dashboard.mock_callback, pattern=r"^mock:"))
    application.add_handler(CallbackQueryHandler(dashboard.mcq_callback, pattern=r"^mcq:"))
    application.add_handler(CallbackQueryHandler(dashboard.ca_callback, pattern=r"^ca:"))
    application.add_handler(CallbackQueryHandler(dashboard.essay_callback, pattern=r"^essay:"))
    application.add_handler(CallbackQueryHandler(dashboard.ethics_callback, pattern=r"^ethics:"))
    application.add_handler(CallbackQueryHandler(dashboard.opt_callback, pattern=r"^opt:"))
    application.add_handler(CallbackQueryHandler(dashboard.prog_callback, pattern=r"^prog:"))
    application.add_handler(CallbackQueryHandler(dashboard.streak_callback, pattern=r"^streak:"))
    application.add_handler(CallbackQueryHandler(dashboard.ai_callback, pattern=r"^ai:"))
    application.add_handler(CallbackQueryHandler(dashboard.set_callback, pattern=r"^set:"))
    application.add_handler(CallbackQueryHandler(dashboard.persona_callback, pattern=r"^persona:"))

    application.add_handler(MessageHandler(filters.PHOTO, on_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    logger.info("🚀 UPSC Mentor AI (testing bot) starting polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
