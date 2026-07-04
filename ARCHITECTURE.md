# UPSC Mentor AI — Testing Bot

Separate Telegram bot for testing AI mentor features before folding them
into your main UPSC bot. Does not touch the main bot's code or database.

**v2 update:** now mirrors the main bot's full navigation tree
button-for-button (see §2), adds the mentor.txt Phase 2 improvements
listed in §4, and includes a Render keep-awake mechanism (§8).

## 1. Root cause of the "cuts off after 4-6 words" bug (v1, still fixed)

`gemini-2.5-flash` via the OpenAI-compatible endpoint has thinking ON by
default, and thinking tokens are billed against `max_tokens`. Fixed in
`services/ai_provider.py` with `reasoning_effort="none"`. Apply the same
fix to your main bot's `services/gemini.py`.

## 2. Navigation tree (mirrors upsc_master_bot/keyboards.py exactly)

```
Home
├── Ask a Doubt / Revision Due
├── Answer Writing → GS1 / GS2 / GS3 / GS4 Ethics / My Answer History / Upload Photo / Home
├── Mock Test → Polity / History / Geography / Economy / Environment / S&T / Mixed Prelims / My Score Card / Home
├── Current Affairs → Economy / Environment / IR / Polity / S&T / Social / Security / Agriculture / Full Digest / CA Sources / Home
├── Essay → Get Topic / Get Outline / Submit Essay / My Essays / Essay Tips / Home
├── Ethics → Case Study / Submit Analysis / 7-Step Framework / Key Thinkers / My Performance / Home
├── Optional → Today's Task / Resources / Coverage Tracker / Answer Practice / Home
├── Progress → Subject Coverage / Weekly Report / Mock Scores / Answer Stats / My Badges / Weak Areas / Home
├── Streak → Leaderboard / Badges / Streak Shields / XP History / Home
├── AI Planner → Ask a Doubt / Flash Questions / CA Summary / Plan Analysis / Weekly Mentor Report* / Monthly Review* / Home
├── Settings → Mentor Persona* / Response Length* / Change Study Plan / Delete My Data / Home
└── Weekly Plan / Help
```
`*` = new in this bot, not in the original (mentor.txt Phase 2 additions).

Every button leads to a real handler in `handlers/dashboard.py`. Streak
(badges/XP/leaderboard) genuinely lives in the main bot's gamification
system and isn't duplicated here — the bot says so honestly rather than
faking numbers.

## 3. Feature map

| Section | Backing logic | AI-generated? |
|---|---|---|
| Ask a Doubt / AI Planner | `handlers/mentor_chat.py` | Yes — full context + 15-msg memory |
| Answer Writing (GS1-4) | `services/mentor_features.py` + `handlers/evaluate.py` | Question bank + AI evaluation (100-pt rubric) |
| Upload Photo (answer) | `services/ai_provider.py::call_vision` | Yes — transcribe then evaluate |
| Mock Test | `mentor_features.generate_mcq` | Yes — freshly generated MCQ per request |
| Current Affairs | `mentor_features.get_ca_digest` | Yes — per category, linked to GS papers |
| Essay (topic/outline/eval/tips) | `mentor_features` + `evaluate.py` | Yes |
| Ethics (case/framework/thinkers/eval) | `mentor_features` + `evaluate.py` | Yes |
| Optional Subject guidance | `mentor_features.get_optional_guidance` | Yes |
| Progress analysis | `mentor_features.get_progress_analysis` | Yes — 8-point structure from mentor.txt |
| Weekly/Monthly Mentor Report | `mentor_features.get_weekly_report` / `get_monthly_report` | Yes, new |
| Streak/Badges/XP | main bot only | No — shown for layout parity, not duplicated |
| Admin AI-health panel | `handlers/admin.py` | `/admin`, finish_reason breakdown |

## 4. mentor.txt Phase 2 improvements implemented

- **Conversational memory**: context window raised from 8 to 15 messages
  (`config.RECENT_CHAT_WINDOW`), and the rendered context block now
  actually includes recent conversation text so the model can resolve
  "explain it further" / "what about India" without re-asking.
- **Deep personal memory**: extraction categories expanded to `[MISTAKE]`
  and `[RESOURCE]` alongside goal/weakness/strength/pattern/preference.
- **Proactive mentoring / burnout detection**: `database.get_progress_flags()`
  is a small, explainable heuristic (inactivity ≥3/7 days, streak reset) —
  deliberately not a black-box model, since a wrong "you seem stressed"
  from an opaque signal does more harm than good. Flags are woven into the
  doubt prompt as one factual sentence, never a lecture.
- **Mentor personas**: Strict / Friendly / Strategy / Answer-Writing /
  Default, layered on top of the base persona via `Settings → Mentor
  Persona`, stored in `user_preferences.persona`.
- **Weekly & Monthly Mentor Reports**: new AI Planner buttons, structured
  per mentor.txt §3/§4, saved to `user_summaries`.
- **AI Action Engine footer**: `prompts.mentor_persona.ACTION_FOOTER`
  (Key Takeaways / Recommended Actions / Next Steps).
- **Knowledge-graph thinking**: the doubt prompt explicitly instructs the
  model to draw topic linkages (Federalism → GST Council → Finance
  Commission, etc.) when it strengthens the answer.

Not implemented (flagged, not silently skipped): interview mentor/DAF
analysis, note/timetable-photo analysis beyond answer sheets, adaptive
MCQ difficulty, gamification (XP/badges — intentionally left to the main
bot), daily morning/evening briefings as scheduled pushes (the study
journal prompt exists in `prompts/mentor_persona.py` but isn't wired to a
scheduler yet).

## 5. Database

SQLite for local testing (`storage/database.py`), schema mirrors
`storage/migrations/001_init.sql` (PostgreSQL) field-for-field. New:
`user_preferences.persona`; `performance_trends` now also stores
`mock_score` (1/0 per MCQ) alongside `answer_score`/`essay_score`/`ethics_score`.

## 6. Integration plan (folding this into the main bot)

1. Point `storage/database.import_user_from_main_bot()` at your main bot's
   reader so a user's `level`/`weak_subjects` seed this bot instead of
   starting cold.
2. Move `services/ai_provider.py`, `prompts/`, `services/memory_extractor.py`,
   `services/mentor_features.py` into the main bot's `services/` folder —
   no dependency on this bot's Telegram layer.
3. Replace the main bot's static content in `handlers/answer_writing.py`,
   `handlers/essay.py`, etc. with calls into `mentor_features.py` one
   section at a time, reusing the main bot's existing keyboards.
4. Add `user_memories` / `ai_sessions` / `user_preferences.persona` to the
   main bot's DB via `storage/migrations/001_init.sql`.

## 7. Running it

```
pip install -r requirements.txt
export MENTOR_BOT_TOKEN=...      # new token from @BotFather, NOT the main bot's
export GEMINI_API_KEY=...
export ADMIN_IDS=123456789
python bot.py
```

`/admin` shows request counts and the `finish_reason` breakdown — watch
for `length`/`MAX_TOKENS` climbing.

## 8. Keep-awake (Render free tier)

Render's free web-service tier spins the dyno down after ~15 minutes with
no inbound HTTP traffic — polling Telegram in the background doesn't count
as traffic, so the bot goes to sleep and stops responding.

`utils/keep_alive.py` runs a background thread that pings this service's
own `/ping` endpoint every 10 minutes, using Render's auto-provided
`RENDER_EXTERNAL_URL` env var. This keeps it from ever going idle, without
needing an external cron/uptime service.

If you deploy anywhere other than Render (or on Render's paid tier, which
doesn't spin down), this is a no-op — it silently does nothing if
`RENDER_EXTERNAL_URL` isn't set, so it's safe to leave in either way.
