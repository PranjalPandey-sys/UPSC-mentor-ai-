# UPSC Mentor AI — Testing Bot

Separate Telegram bot for testing AI mentor features (doubt-solving, answer
evaluation, essay/ethics review, mock tests, current affairs, optional
guidance) before folding them into the main UPSC bot. Fully isolated: its
own token, its own database, mirrors the main bot's navigation tree exactly.

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full write-up — the
response-truncation bug and its fix, the complete navigation map, feature
list, mentor.txt improvements implemented, database schema, and the
integration plan back into the main bot.

## Quickstart

```
pip install -r requirements.txt
export MENTOR_BOT_TOKEN=...      # new token from @BotFather, not the main bot's
export GEMINI_API_KEY=...
export ADMIN_IDS=123456789
python bot.py
```

Deploying to Render: no extra setup needed for keep-awake — it activates
automatically via Render's `RENDER_EXTERNAL_URL` env var (see
ARCHITECTURE.md §8).
