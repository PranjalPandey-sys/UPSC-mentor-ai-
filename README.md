# UPSC Mentor AI — Testing Bot

Separate Telegram bot for testing AI mentor features (doubt-solving, answer
evaluation, essay review, ethics case studies) before folding them into the
main UPSC bot. Fully isolated: its own token, its own database.

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full write-up — root cause
of the response-truncation bug, feature map, data flow, database schema,
memory system, and the integration plan back into the main bot.

## Quickstart

```
pip install -r requirements.txt
export MENTOR_BOT_TOKEN=...      # new token from @BotFather, not the main bot's
export GEMINI_API_KEY=...
export ADMIN_IDS=123456789
python bot.py
```
