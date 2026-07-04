"""
keyboards.py — UPSC Mentor AI Keyboard Builders
===================================================
Deliberately mirrors upsc_master_bot/keyboards.py button-for-button so the
mentor bot feels like a natural extension of the main bot, not a different
product. Every section your aspirants already know how to navigate is here;
each one is now backed by the mentor AI instead of static content.

New (mentor.txt Phase 2): AI Planner gets 2 extra buttons (Weekly Report,
Monthly Report) since proactive mentor reporting is a mentor.txt requirement
that had no home in the original bot's AI Planner section.
"""
from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Markup


# ── Onboarding (lightweight — full onboarding stays in the main bot) ──────────

def kb_select_level() -> Markup:
    return Markup([
        [Btn("Beginner", callback_data="set_level:beginner")],
        [Btn("Intermediate", callback_data="set_level:intermediate")],
        [Btn("Advanced", callback_data="set_level:advanced")],
    ])


# ── Main Dashboard ──────────────────────────────────────────────────────────

def kb_home() -> Markup:
    return Markup([
        [Btn("Ask a Doubt", callback_data="nav:doubt"),
         Btn("Revision Due", callback_data="nav:revision")],
        [Btn("Answer Writing", callback_data="nav:answer_writing"),
         Btn("Mock Test", callback_data="nav:mock")],
        [Btn("Current Affairs", callback_data="nav:current_affairs"),
         Btn("Essay", callback_data="nav:essay")],
        [Btn("Ethics", callback_data="nav:ethics"),
         Btn("Optional", callback_data="nav:optional")],
        [Btn("Progress", callback_data="nav:progress"),
         Btn("Streak", callback_data="nav:streak")],
        [Btn("AI Planner", callback_data="nav:ai_planner"),
         Btn("Settings", callback_data="nav:settings")],
        [Btn("Weekly Plan", callback_data="nav:weekly_plan"),
         Btn("Help", callback_data="nav:help")],
    ])


def kb_back_home() -> Markup:
    return Markup([[Btn("Home", callback_data="nav:home")]])


def kb_back_section(section: str) -> Markup:
    return Markup([
        [Btn("Back", callback_data=f"nav:{section}"), Btn("Home", callback_data="nav:home")],
    ])


# ── Revision ────────────────────────────────────────────────────────────────

def kb_revision() -> Markup:
    return Markup([
        [Btn("Mark All Revised", callback_data="rev:mark_all"),
         Btn("See Full List", callback_data="rev:list")],
        [Btn("Set Next Revision", callback_data="rev:reschedule")],
        [Btn("Home", callback_data="nav:home")],
    ])


# ── Answer Writing (GS1 / GS2 / GS3 / GS4 / History / Upload Photo / Home) ────

def kb_answer_writing() -> Markup:
    return Markup([
        [Btn("GS1 Question", callback_data="aw:gs1"),
         Btn("GS2 Question", callback_data="aw:gs2")],
        [Btn("GS3 Question", callback_data="aw:gs3"),
         Btn("GS4 Ethics", callback_data="aw:gs4")],
        [Btn("My Answer History", callback_data="aw:history"),
         Btn("Upload Photo", callback_data="aw:photo")],
        [Btn("Home", callback_data="nav:home")],
    ])


def kb_after_answer_eval() -> Markup:
    return Markup([
        [Btn("Write Another", callback_data="nav:answer_writing"),
         Btn("My History", callback_data="aw:history")],
        [Btn("Home", callback_data="nav:home")],
    ])


def kb_cancel_writing() -> Markup:
    return Markup([[Btn("Cancel", callback_data="nav:answer_writing")]])


# ── Mock Test (Polity / History / Geography / Economy / Environment / S&T /
#    Mixed Prelims / My Score Card / Home) ────────────────────────────────────

def kb_mock_menu() -> Markup:
    return Markup([
        [Btn("Polity MCQs", callback_data="mock:Polity"),
         Btn("History MCQs", callback_data="mock:History")],
        [Btn("Geography", callback_data="mock:Geography"),
         Btn("Economy", callback_data="mock:Economy")],
        [Btn("Environment", callback_data="mock:Environment"),
         Btn("S&T", callback_data="mock:S&T")],
        [Btn("Mixed Prelims", callback_data="mock:Mixed"),
         Btn("My Score Card", callback_data="mock:scorecard")],
        [Btn("Home", callback_data="nav:home")],
    ])


def kb_mock_answer(idx: int) -> Markup:
    return Markup([
        [Btn("A", callback_data=f"mcq:{idx}:0"), Btn("B", callback_data=f"mcq:{idx}:1"),
         Btn("C", callback_data=f"mcq:{idx}:2"), Btn("D", callback_data=f"mcq:{idx}:3")],
        [Btn("End Test", callback_data="mock:end")],
    ])


def kb_after_mock() -> Markup:
    return Markup([
        [Btn("Try Another", callback_data="nav:mock"), Btn("Score Card", callback_data="mock:scorecard")],
        [Btn("Home", callback_data="nav:home")],
    ])


# ── Current Affairs (Economy / Environment / IR / Polity / S&T / Social /
#    Security / Agriculture / Full Digest / CA Sources / Home) ────────────────

def kb_ca() -> Markup:
    return Markup([
        [Btn("Economy", callback_data="ca:Economy"),
         Btn("Environment", callback_data="ca:Environment")],
        [Btn("IR", callback_data="ca:International Relations"),
         Btn("Polity", callback_data="ca:Polity & Governance")],
        [Btn("S&T", callback_data="ca:Science & Technology"),
         Btn("Social", callback_data="ca:Social Issues")],
        [Btn("Security", callback_data="ca:Security & Defence"),
         Btn("Agriculture", callback_data="ca:Agriculture")],
        [Btn("Full Digest", callback_data="ca:full_digest"),
         Btn("CA Sources", callback_data="ca:sources")],
        [Btn("Home", callback_data="nav:home")],
    ])


# ── Essay (Get Topic / Get Outline / Submit Essay / My Essays / Essay Tips) ───

def kb_essay() -> Markup:
    return Markup([
        [Btn("Get Topic", callback_data="essay:topic"),
         Btn("Get Outline", callback_data="essay:outline")],
        [Btn("Submit Essay", callback_data="essay:submit"),
         Btn("My Essays", callback_data="essay:history")],
        [Btn("Essay Tips", callback_data="essay:tips")],
        [Btn("Home", callback_data="nav:home")],
    ])


def kb_essay_after() -> Markup:
    return Markup([
        [Btn("Write Another", callback_data="nav:essay"), Btn("History", callback_data="essay:history")],
        [Btn("Home", callback_data="nav:home")],
    ])


# ── Ethics (Case Study / Submit Analysis / 7-Step Framework / Key Thinkers /
#    My Performance) ───────────────────────────────────────────────────────────

def kb_ethics() -> Markup:
    return Markup([
        [Btn("Case Study", callback_data="ethics:case"),
         Btn("Submit Analysis", callback_data="ethics:submit")],
        [Btn("7-Step Framework", callback_data="ethics:framework"),
         Btn("Key Thinkers", callback_data="ethics:thinkers")],
        [Btn("My Performance", callback_data="ethics:history")],
        [Btn("Home", callback_data="nav:home")],
    ])


# ── Optional (Today's Task / Resources / Coverage Tracker / Answer Practice) ──

def kb_optional() -> Markup:
    return Markup([
        [Btn("Today's Optional Task", callback_data="opt:today"),
         Btn("Resources", callback_data="opt:resources")],
        [Btn("Coverage Tracker", callback_data="opt:tracker"),
         Btn("Answer Practice", callback_data="opt:answer")],
        [Btn("Home", callback_data="nav:home")],
    ])


# ── Progress (Subject Coverage / Weekly Report / Mock Scores / Answer Stats /
#    My Badges / Weak Areas) ───────────────────────────────────────────────────

def kb_progress() -> Markup:
    return Markup([
        [Btn("Subject Coverage", callback_data="prog:subjects"),
         Btn("Weekly Report", callback_data="prog:weekly")],
        [Btn("Mock Scores", callback_data="prog:mocks"),
         Btn("Answer Stats", callback_data="prog:answers")],
        [Btn("My Badges", callback_data="prog:badges"),
         Btn("Weak Areas", callback_data="prog:weak")],
        [Btn("Home", callback_data="nav:home")],
    ])


# ── Streak ──────────────────────────────────────────────────────────────────

def kb_streak() -> Markup:
    return Markup([
        [Btn("Leaderboard", callback_data="streak:leaderboard"),
         Btn("Badges", callback_data="streak:badges")],
        [Btn("Streak Shields", callback_data="streak:shields"),
         Btn("XP History", callback_data="streak:xp_log")],
        [Btn("Home", callback_data="nav:home")],
    ])


# ── AI Planner (Ask a Doubt / Flash Questions / CA Summary / Plan Analysis /
#    + NEW: Weekly Report / Monthly Report — mentor.txt Phase 2 §3-4) ─────────

def kb_ai_planner() -> Markup:
    return Markup([
        [Btn("Ask a Doubt", callback_data="ai:doubt"),
         Btn("Flash Questions", callback_data="ai:flashcard")],
        [Btn("CA Summary", callback_data="ai:ca"),
         Btn("Plan Analysis", callback_data="ai:analysis")],
        [Btn("Weekly Mentor Report", callback_data="ai:weekly_report"),
         Btn("Monthly Review", callback_data="ai:monthly_report")],
        [Btn("Home", callback_data="nav:home")],
    ])


def kb_cancel_doubt() -> Markup:
    return Markup([[Btn("Cancel", callback_data="nav:ai_planner")]])


# ── Settings ────────────────────────────────────────────────────────────────

def kb_settings() -> Markup:
    return Markup([
        [Btn("Mentor Persona", callback_data="set:persona")],
        [Btn("Response Length", callback_data="set:length")],
        [Btn("Change Study Plan", callback_data="set:change_plan")],
        [Btn("Delete My Data", callback_data="set:delete_data")],
        [Btn("Home", callback_data="nav:home")],
    ])


def kb_persona_choice() -> Markup:
    """mentor.txt Phase 2 §26 — Mentor Personas."""
    return Markup([
        [Btn("Strict Mentor", callback_data="persona:strict"),
         Btn("Friendly Mentor", callback_data="persona:friendly")],
        [Btn("Strategy Mentor", callback_data="persona:strategy"),
         Btn("Answer Writing Mentor", callback_data="persona:answer_writing")],
        [Btn("Default (Balanced)", callback_data="persona:default")],
        [Btn("Home", callback_data="nav:home")],
    ])


def kb_confirm_delete() -> Markup:
    return Markup([
        [Btn("Yes, Delete Everything", callback_data="set:confirm_delete")],
        [Btn("Cancel", callback_data="nav:settings")],
    ])


# ── Admin Panel ─────────────────────────────────────────────────────────────

def kb_admin() -> Markup:
    return Markup([
        [Btn("Stats", callback_data="adm:stats"), Btn("Users", callback_data="adm:users")],
        [Btn("AI Insights", callback_data="adm:ai_insights"), Btn("Error Log", callback_data="adm:errors")],
        [Btn("Memory Stats", callback_data="adm:memory_stats"), Btn("Cost Tracking", callback_data="adm:cost")],
        [Btn("Broadcast", callback_data="adm:broadcast")],
        [Btn("Home", callback_data="nav:home")],
    ])
