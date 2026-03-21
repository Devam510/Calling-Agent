"""
transcript_analyzer.py — Post-call analysis using Groq.

Design notes:
  - L004: Never use regex on mixed-language transcripts.
  - Uses two Groq attempts with progressively stricter prompts.
  - Falls back to CallResult(status=FAILED) — never crashes the orchestrator.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from groq import Groq

from backend.config import settings
from backend.models import CallResult, CallStatus

logger = logging.getLogger(__name__)

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"


def _load_analysis_prompt(transcript: str) -> str:
    template = (_PROMPT_DIR / "analysis_prompt.txt").read_text(encoding="utf-8")
    # Use simple replace(), NOT str.format() — the template contains JSON braces
    # like {"status": ...} that str.format() would try to resolve as placeholders.
    return template.replace("{transcript}", transcript)


def _safe_default(reason: str) -> CallResult:
    """Return a safe default result to prevent orchestrator crashes."""
    logger.error("Analysis failed — returning FAILED default. Reason: %s", reason)
    return CallResult(
        status=CallStatus.FAILED,
        summary=f"Analysis failed: {reason}",
        followup_date=None,
        recording_path="",
    )


def _parse_json(raw: str) -> Optional[CallResult]:
    """Attempt to parse a Groq response into a CallResult."""
    try:
        data = json.loads(raw.strip())
        return CallResult(
            status=CallStatus(data["status"]),
            summary=str(data.get("summary", "")),
            followup_date=data.get("followup_date") or None,
        )
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning("JSON parse failed: %s | raw=%r", exc, raw[:200])
        return None


def analyze_transcript(transcript: str) -> CallResult:
    """
    Analyze a call transcript and return a CallResult.

    Strategy (L004):
      1. First Groq call with normal prompt.
      2. If JSON parse fails → second call with stricter single-word status prompt.
      3. If both fail → return FAILED default.
    """
    if not transcript.strip():
        return _safe_default("Empty transcript provided")

    client = Groq(api_key=settings.groq_api_key)

    # ── Attempt 1: normal analysis prompt ────────────────────────────────
    try:
        prompt = _load_analysis_prompt(transcript)
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0,   # deterministic for parsing reliability
        )
        raw = response.choices[0].message.content.strip()
        result = _parse_json(raw)
        if result is not None:
            logger.info("Analysis succeeded on attempt 1: status=%s", result.status)
            return result
    except Exception as exc:
        logger.error("Groq attempt 1 failed: %s", exc)

    # ── Attempt 2: stricter prompt (L004) ─────────────────────────────────
    strict_prompt = f"""
You are a call analyst. Read this transcript and respond with ONLY a JSON object.
No explanation. No markdown.

Transcript:
{transcript}

Valid statuses: interested, not_interested, follow_up, no_answer, busy, wrong_number, do_not_call, failed
Return format: {{"status":"<status>","summary":"<2-3 sentences>","followup_date":null}}
"""
    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "user", "content": strict_prompt}],
            max_tokens=200,
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()
        result = _parse_json(raw)
        if result is not None:
            logger.info("Analysis succeeded on attempt 2: status=%s", result.status)
            return result
    except Exception as exc:
        logger.error("Groq attempt 2 failed: %s", exc)

    return _safe_default("Both Groq attempts failed or returned unparseable JSON")
