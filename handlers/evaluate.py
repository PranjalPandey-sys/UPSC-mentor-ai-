"""
handlers/evaluate.py — Answer / Essay / Ethics evaluation
=============================================================
Each function parses the structured mentor output into a dict and stores
the score in performance_trends so progress can be charted later.
"""
import logging
import time

import config
from prompts.mentor_persona import evaluate_answer_prompt, essay_prompt, ethics_prompt
from services import ai_provider
from storage import database as db

logger = logging.getLogger(__name__)


def _parse_fields(raw: str) -> dict:
    parsed = {}
    for line in raw.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            parsed[k.strip().upper()] = v.strip()
    return parsed


def _extract_score(raw: str, max_pts: int) -> int:
    try:
        return min(max_pts, int(str(raw).split("(")[0].split("/")[0].strip().split()[0]))
    except Exception:
        return 0


async def evaluate_answer(user_id: int, question: str, answer_text: str,
                           gs_paper: str = "GS1", answer_type: str = "GS") -> dict:
    system = evaluate_answer_prompt(gs_paper, answer_type)
    user_msg = f"Question:\n{question}\n\nStudent's Answer:\n{answer_text}"

    start = time.monotonic()
    result = await ai_provider.call(system, user_msg, max_tokens=config.TOKENS_EVALUATE)
    latency_ms = int((time.monotonic() - start) * 1000)

    await db.log_ai_session(user_id, "evaluate", len(result.split()) if result else 0,
                             "stop" if result else "error", latency_ms, bool(result))

    if not result:
        return {"score": 0, "feedback": "AI evaluation unavailable. Please retry.", "raw": ""}

    parsed = _parse_fields(result)
    score = _extract_score(parsed.get("SCORE", "0"), 100)
    await db.record_performance(user_id, "answer_score", score, subject=gs_paper)

    return {
        "score": score,
        "introduction": _extract_score(parsed.get("INTRO", "0"), 20),
        "content": _extract_score(parsed.get("CONTENT", "0"), 30),
        "examples": _extract_score(parsed.get("EXAMPLES", "0"), 20),
        "structure": _extract_score(parsed.get("STRUCTURE", "0"), 15),
        "conclusion": _extract_score(parsed.get("CONCLUSION", "0"), 15),
        "strengths": parsed.get("STRENGTHS", ""),
        "improvements": parsed.get("IMPROVEMENTS", ""),
        "model_approach": parsed.get("MODEL_APPROACH", ""),
        "raw": result,
    }


async def evaluate_essay(user_id: int, topic: str, essay_text: str) -> dict:
    system = essay_prompt()
    result = await ai_provider.call(
        system, f"Topic: {topic}\n\nEssay:\n{essay_text}", max_tokens=config.TOKENS_ESSAY
    )
    await db.log_ai_session(user_id, "essay", len(result.split()) if result else 0,
                             "stop" if result else "error", 0, bool(result))
    if not result:
        return {"score": 0, "feedback": "AI evaluation unavailable.", "raw": ""}

    parsed = _parse_fields(result)
    score = _extract_score(parsed.get("SCORE", "0"), 125)
    await db.record_performance(user_id, "essay_score", score)

    return {
        "score": score,
        "improvements": parsed.get("IMPROVEMENTS", ""),
        "best_line": parsed.get("BEST_LINE", ""),
        "raw": result,
    }


async def evaluate_ethics(user_id: int, scenario: str, analysis_text: str) -> dict:
    system = ethics_prompt()
    result = await ai_provider.call(
        system, f"Scenario:\n{scenario}\n\nAnalysis:\n{analysis_text}", max_tokens=config.TOKENS_ETHICS
    )
    await db.log_ai_session(user_id, "ethics", len(result.split()) if result else 0,
                             "stop" if result else "error", 0, bool(result))
    if not result:
        return {"score": 0, "feedback": "AI evaluation unavailable.", "raw": ""}

    parsed = _parse_fields(result)
    score = _extract_score(parsed.get("SCORE", "0"), 100)
    await db.record_performance(user_id, "ethics_score", score)

    return {
        "score": score,
        "steps_covered": parsed.get("STEPS_COVERED", ""),
        "strengths": parsed.get("STRENGTHS", ""),
        "gaps": parsed.get("GAPS", ""),
        "improvements": parsed.get("IMPROVEMENTS", ""),
        "raw": result,
    }
