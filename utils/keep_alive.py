"""
utils/keep_alive.py — Render free-tier keep-awake
======================================================
Render's free web-service tier spins the dyno down after ~15 minutes of no
inbound HTTP traffic. A Telegram bot on long-polling never receives inbound
HTTP requests (it makes outbound requests to Telegram), so without this,
Render will put the bot to sleep and it stops responding until the next
request wakes it back up — which for a polling bot may never come.

This runs a background thread that pings this service's own /ping endpoint
every PING_INTERVAL_SECONDS, using Render's auto-provided
RENDER_EXTERNAL_URL env var. That counts as inbound traffic and resets
Render's idle timer.

Safe no-op anywhere else: if RENDER_EXTERNAL_URL isn't set (local dev,
other hosts, Render paid tier), the thread logs once and exits quietly.
"""
import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

PING_INTERVAL_SECONDS = 10 * 60  # 10 minutes — comfortably under Render's ~15 min idle window


def _ping_loop(url: str) -> None:
    import urllib.request
    import urllib.error

    ping_url = url.rstrip("/") + "/ping"
    logger.info("🟢 Keep-awake thread started, pinging %s every %d min", ping_url, PING_INTERVAL_SECONDS // 60)

    while True:
        time.sleep(PING_INTERVAL_SECONDS)
        try:
            with urllib.request.urlopen(ping_url, timeout=15) as resp:
                logger.info("🏓 Keep-awake ping ok (status %s)", resp.status)
        except urllib.error.URLError as exc:
            logger.warning("🏓 Keep-awake ping failed: %s", exc)
        except Exception as exc:
            logger.warning("🏓 Keep-awake ping error: %s", exc)


def start_keep_alive() -> None:
    """Call once at startup, after the Flask keep-alive server has started."""
    url = os.environ.get("RENDER_EXTERNAL_URL", "").strip()
    if not url:
        logger.info("RENDER_EXTERNAL_URL not set — keep-awake disabled (fine for local/non-Render hosts).")
        return

    thread = threading.Thread(target=_ping_loop, args=(url,), daemon=True)
    thread.start()
