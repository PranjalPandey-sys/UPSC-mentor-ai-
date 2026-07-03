# UPSC Mentor AI — Testing Bot

Separate Telegram bot for testing AI mentor features before folding them
into your main UPSC bot. Does not touch the main bot's code or database.

## 1. Root cause of the "cuts off after 4-6 words" bug

Your old `services/gemini.py` called `gemini-2.5-flash` through the OpenAI-
compatible endpoint with no `reasoning_effort` set. As of the current
model, **thinking is ON by default** on that endpoint, and thinking tokens
are billed against `max_tokens` — not tracked separately. At
`max_tokens=450-600`, the model was spending nearly its whole budget on
invisible reasoning and had only a few tokens of headroom left for visible
text, so responses got cut mid-word ("Acknow[ledge]", "Spread of
Misinformation & Dis[information]" — matches your screenshots exactly).

Fix, applied in `services/ai_provider.py::call`:
```python
reasoning_effort=config.GEMINI_REASONING_EFFORT   # "none"
```
This disables thinking entirely for 2.5-series models (confirmed in
Google's OpenAI-compatibility docs). Token budgets were also raised
slightly in `config.py` (`TOKENS_*`) since they're no longer being eaten
by invisible reasoning. `ai_sessions.finish_reason` is now logged on every
call, and the admin panel (`/admin`) surfaces a warning if truncations
start happening again — that's the tripwire that would have caught this
in production instead of you finding it by reading screenshots.

**Apply the same one-line fix to your main bot's `services/gemini.py`** —
its `_call()` function has the identical issue.

## 2. Feature map

| Feature | Handler | Notes |
|---|---|---|
| General doubt-solving | `handlers/mentor_chat.py` | Structured mentor format, memory-aware |
| Answer evaluation | `handlers/evaluate.py::evaluate_answer` | 100-pt rubric |
| Essay evaluation | `handlers/evaluate.py::evaluate_essay` | 125-pt rubric |
| Ethics case study | `handlers/evaluate.py::evaluate_ethics` | 7-step framework |
| Current affairs summary | `bot.py::on_message` (ca_topic) | Prelims + Mains angle |
| Progress view | `bot.py::on_menu` (menu_progress) | From `study_progress` table |
| Admin AI-health panel | `handlers/admin.py` | `/admin`, finish_reason breakdown |
| Memory extraction | `services/memory_extractor.py` | Runs every N turns, background |
| Photo/PDF analysis | `services/ai_provider.py::call_vision` | Wired, not yet hooked to a handler — see §6 |

Not yet built (flagged so nothing is silently assumed done): PYQ analysis,
adaptive weekly/admin cohort insights, daily digest scheduler, gamified
memory streaks. The architecture (context builder + AI provider + prompts)
is built so each of these is a new handler + a new function in
`prompts/mentor_persona.py`, not a redesign.

## 3. Flow

```
/start -> home menu
  -> "Ask a Doubt"        -> free text -> handlers/mentor_chat.handle_doubt
  -> "Submit Answer"      -> question, then answer -> handlers/evaluate.evaluate_answer
  -> "Submit Essay"       -> topic, then essay -> handlers/evaluate.evaluate_essay
  -> "Ethics Case Study"  -> scenario, then analysis -> handlers/evaluate.evaluate_ethics
  -> "Current Affairs"    -> topic -> ai_provider.call(ca_summary_prompt)
  -> "My Progress"        -> storage/database.get_study_progress

Every AI-touching flow:
  1. context_builder.build_context()   — profile + memories + recent chat + progress
  2. prompts/mentor_persona.*          — builds the system prompt
  3. ai_provider.call()                — the ONLY place that talks to Gemini
  4. storage/database.log_ai_session() — records finish_reason/tokens/latency
  5. memory_extractor.maybe_extract()  — every N turns, pulls durable facts
```

## 4. Database

SQLite for this testing bot (`storage/database.py`) so it runs standalone
with zero infra. Schema mirrors `storage/migrations/001_init.sql`
(PostgreSQL) field-for-field — swap `DB_ENGINE=postgres` + `DATABASE_URL`
and re-point the driver calls when you're ready for production; nothing
above the storage layer changes.

Tables: `users`, `chat_messages` (rolling 50/user), `user_memories`,
`user_summaries`, `mentor_insights`, `study_progress`,
`performance_trends`, `uploaded_documents`, `news_history`,
`user_preferences`, `analytics`, `events`, `ai_sessions`.

`ai_sessions` is the operational table — it's what lets `/admin` show you
truncation regressions immediately instead of you finding out from a
screenshot.

## 5. Memory system

Only durable facts are stored (`[GOAL]`, `[WEAKNESS]`, `[STRENGTH]`,
`[PATTERN]`, `[PREFERENCE]`) — never full chat transcripts. Extraction
runs every `MEMORY_EXTRACTION_EVERY_N_MSGS` (default 6) user turns on a
rolling window, not on every message, to control cost. Every AI call gets
at most `MAX_ACTIVE_MEMORIES` (default 25) most-recently-updated facts —
compact context, not a database dump.

## 6. Integration plan (folding this into the main bot)

1. Point `storage/database.import_user_from_main_bot()` at your main bot's
   SQLite/Postgres reader so a user's `level`/`timeline_months`/
   `weak_subjects` seed this bot's `users` row instead of starting cold.
2. Move `services/ai_provider.py`, `prompts/`, and `services/
   memory_extractor.py` into the main bot's `services/` folder as-is —
   they have no dependency on this bot's Telegram layer.
3. Replace the main bot's `services/gemini.py` calls with
   `ai_provider.call()` one function at a time, keeping the main bot's
   existing fallback strings.
4. Add `user_memories` / `ai_sessions` tables to the main bot's DB via
   `storage/migrations/001_init.sql` (safe to run alongside its existing
   tables — no name collisions with your current schema).
5. Wire the AI menu buttons into the main bot's existing keyboard/handler
   registration instead of this bot's standalone `/start` menu.

## 7. Running it

```
pip install -r requirements.txt
export MENTOR_BOT_TOKEN=...      # new token from @BotFather, NOT the main bot's
export GEMINI_API_KEY=...
export ADMIN_IDS=123456789
python bot.py
```

`/admin` (from an ID in `ADMIN_IDS`) shows request counts and the
`finish_reason` breakdown — watch for `length`/`MAX_TOKENS` climbing.
