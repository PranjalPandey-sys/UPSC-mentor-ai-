"""
services/mentor_features.py — Section-level AI logic
========================================================
One function per dashboard section that needs AI content. Handlers stay
thin (parse the callback, call the right function here, format the reply).
"""
import logging
import random

import config
from prompts import mentor_persona as mp
from services import ai_provider, context_builder
from storage import database as db

logger = logging.getLogger(__name__)


# ── Answer Writing (GS1-4) ──────────────────────────────────────────────────

GS_QUESTIONS = {
    "gs1": [
        ("The partition of India in 1947 left deep scars. Analyse the social and psychological impact on displaced communities.", "History"),
        ("Discuss the role of women in India's freedom struggle with examples.", "History"),
        ("What are the major factors responsible for seasonal and annual variation of rainfall in India?", "Geography"),
        ("Analyse the causes and consequences of urbanisation in India.", "Indian Society"),
    ],
    "gs2": [
        ("Parliamentary committees play a vital role in Indian democracy. Examine with examples.", "Polity"),
        ("Analyse India's neighbourhood-first policy and its challenges.", "IR"),
        ("Right to Health is implicit in Article 21. Discuss the judicial interventions.", "Governance"),
        ("What are the constitutional safeguards for minorities in India? Are they adequate?", "Polity"),
    ],
    "gs3": [
        ("Discuss the role of the agricultural sector in doubling farmers' income — targets and achievements.", "Economy"),
        ("What are the challenges and opportunities in India's semiconductor manufacturing sector?", "S&T"),
        ("Analyse the impact of climate change on India's monsoon patterns and agriculture.", "Environment"),
        ("Cybersecurity is the biggest threat to national security today. Discuss.", "Security"),
    ],
    "gs4": [
        ("A civil servant faces a situation where following the letter of the law harms the spirit of justice. How should they act?", "Ethics"),
        ("What are the ethical dimensions of using AI in governance and policy-making?", "Ethics"),
        ("Discuss the role of conscience in public service with reference to the concept of Nishkama Karma.", "Ethics"),
        ("Evaluate: 'Honesty may be the best policy, but it is not always the most convenient policy.'", "Ethics"),
    ],
}


def get_gs_question(paper: str) -> tuple[str, str]:
    return random.choice(GS_QUESTIONS.get(paper, GS_QUESTIONS["gs1"]))


async def get_answer_history_text(user_id: int) -> str:
    history = await db.get_performance_history(user_id, "answer_score", limit=5)
    if not history:
        return "No answers submitted yet. Pick a GS paper above to write your first one."
    avg = await db.get_performance_avg(user_id, "answer_score")
    lines = [f"Average score: {avg}/100\n"]
    for h in history:
        lines.append(f"  {h['subject'] or 'GS'} — {h['value']:.0f}/100")
    return "\n".join(lines)


# ── Mock Test ────────────────────────────────────────────────────────────────

async def generate_mcq(subject: str) -> dict | None:
    if subject == "Mixed":
        subject = random.choice(["Polity", "History", "Geography", "Economy", "Environment", "S&T"])
    raw = await ai_provider.call(
        system=mp.mock_mcq_prompt(subject),
        user_msg=f"Generate one {subject} MCQ.",
        max_tokens=config.TOKENS_MOCK_MCQ,
        temperature=0.7,
    )
    if not raw:
        return None
    parsed = {}
    for line in raw.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            parsed[k.strip().upper()] = v.strip()
    required = {"Q", "A", "B", "C", "D", "CORRECT"}
    if not required.issubset(parsed.keys()):
        return None
    return {
        "question": parsed["Q"],
        "options": [parsed["A"], parsed["B"], parsed["C"], parsed["D"]],
        "correct": parsed["CORRECT"][:1].upper(),
        "explanation": parsed.get("EXPLANATION", ""),
        "subject": subject,
    }


async def get_scorecard_text(user_id: int) -> str:
    history = await db.get_performance_history(user_id, "mock_score", limit=10)
    if not history:
        return "No mock attempts yet. Pick a subject above to start."
    avg = await db.get_performance_avg(user_id, "mock_score")
    correct = sum(1 for h in history if h["value"] == 1)
    return f"Recent accuracy: {correct}/{len(history)} correct\nOverall average: {avg}%"


# ── Current Affairs ──────────────────────────────────────────────────────────

async def get_ca_digest(category: str) -> str:
    if category in ("full_digest", "sources"):
        if category == "sources":
            return (
                "Recommended CA sources for UPSC:\n"
                "1. The Hindu / Indian Express (daily editorials)\n"
                "2. PIB (government announcements, high Prelims value)\n"
                "3. PRS India (bill and policy summaries)\n"
                "4. Monthly compilations from a standard institute (for revision)\n"
                "5. Economic Survey and Budget documents (once a year, non-negotiable)"
            )
        result = await ai_provider.call(
            system=mp.ca_category_prompt("all major categories combined"),
            user_msg="Give today's full current affairs digest across Polity, Economy, IR, Environment, S&T.",
            max_tokens=config.TOKENS_CA_SUMMARY + 150,
        )
        return result or "AI unavailable, try again shortly."

    result = await ai_provider.call(
        system=mp.ca_category_prompt(category),
        user_msg=f"Current affairs digest for: {category}",
        max_tokens=config.TOKENS_CA_SUMMARY,
    )
    return result or "AI unavailable, try again shortly."


# ── Essay ────────────────────────────────────────────────────────────────────

async def get_essay_topic() -> str:
    result = await ai_provider.call(mp.essay_topic_prompt(), "Give one essay topic.", max_tokens=config.TOKENS_ESSAY_TOPIC)
    return result or "Has technology made us more isolated or more connected?"


async def get_essay_outline(topic: str) -> str:
    result = await ai_provider.call(mp.essay_outline_prompt(), f"Topic: {topic}", max_tokens=config.TOKENS_ESSAY_TOPIC + 150)
    return result or "AI unavailable, try again shortly."


async def get_essay_tips() -> str:
    result = await ai_provider.call(mp.essay_tips_prompt(), "Give essay tips.", max_tokens=300)
    return result or "AI unavailable, try again shortly."


async def get_essay_history_text(user_id: int) -> str:
    history = await db.get_performance_history(user_id, "essay_score", limit=5)
    if not history:
        return "No essays submitted yet."
    avg = await db.get_performance_avg(user_id, "essay_score")
    return f"Average score: {avg}/125\n" + "\n".join(f"  {h['value']:.0f}/125" for h in history)


# ── Ethics ───────────────────────────────────────────────────────────────────

async def get_ethics_case() -> str:
    result = await ai_provider.call(mp.ethics_case_prompt(), "Give one ethics case study.", max_tokens=350)
    return result or "AI unavailable, try again shortly."


async def get_ethics_framework() -> str:
    result = await ai_provider.call(mp.ethics_framework_prompt(), "Explain the framework.", max_tokens=config.TOKENS_ETHICS_FRAMEWORK)
    return result or "AI unavailable, try again shortly."


async def get_ethics_thinkers() -> str:
    result = await ai_provider.call(mp.ethics_thinkers_prompt(), "List key thinkers.", max_tokens=350)
    return result or "AI unavailable, try again shortly."


async def get_ethics_history_text(user_id: int) -> str:
    history = await db.get_performance_history(user_id, "ethics_score", limit=5)
    if not history:
        return "No ethics case studies submitted yet."
    avg = await db.get_performance_avg(user_id, "ethics_score")
    return f"Average score: {avg}/100\n" + "\n".join(f"  {h['value']:.0f}/100" for h in history)


# ── Optional ─────────────────────────────────────────────────────────────────

async def get_optional_guidance(user_id: int, area: str) -> str:
    profile = await db.get_user_profile(user_id) or {}
    subject = profile.get("optional_subject", "")
    result = await ai_provider.call(
        mp.optional_guidance_prompt(subject, area),
        f"Give guidance for area: {area}",
        max_tokens=config.TOKENS_OPTIONAL_GUIDANCE,
    )
    return result or "AI unavailable, try again shortly."


# ── Progress / Reports ───────────────────────────────────────────────────────

async def get_progress_analysis(user_id: int) -> str:
    ctx = await context_builder.build_context(user_id)
    block = context_builder.render_context_block(ctx)

    avg_answer = await db.get_performance_avg(user_id, "answer_score")
    avg_essay = await db.get_performance_avg(user_id, "essay_score")
    avg_ethics = await db.get_performance_avg(user_id, "ethics_score")
    stats_block = (
        f"\n\nRecorded averages: answer writing {avg_answer}/100, "
        f"essay {avg_essay}/125, ethics {avg_ethics}/100."
    )

    result = await ai_provider.call(
        mp.progress_analysis_prompt(),
        block + stats_block,
        max_tokens=config.TOKENS_STUDY_ANALYSIS,
    )
    return result or "AI unavailable, try again shortly."


async def get_weekly_report(user_id: int) -> str:
    ctx = await context_builder.build_context(user_id)
    block = context_builder.render_context_block(ctx)
    result = await ai_provider.call(mp.progress_analysis_prompt(), block, max_tokens=config.TOKENS_WEEKLY)
    if result:
        await db.save_summary(user_id, "weekly", result[:600])
    return result or "AI unavailable, try again shortly."


async def get_monthly_report(user_id: int) -> str:
    ctx = await context_builder.build_context(user_id)
    block = context_builder.render_context_block(ctx)
    result = await ai_provider.call(mp.monthly_review_prompt(), block, max_tokens=config.TOKENS_MONTHLY)
    if result:
        await db.save_summary(user_id, "monthly", result[:800])
    return result or "AI unavailable, try again shortly."
