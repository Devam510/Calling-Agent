"""
conversation_engine.py — Groq LLM inference for the sales conversation.

Maintains message history per call and provides a single `chat()` entrypoint.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from groq import Groq

from backend.config import settings
from backend.models import Lead

logger = logging.getLogger(__name__)

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"


def _load_system_prompt(lead: Lead) -> str:
    """Load and format the sales system prompt with lead-specific data."""
    template = (_PROMPT_DIR / "sales_system_prompt.txt").read_text(encoding="utf-8")
    return template.format(
        owner_name=lead.owner_name,
        company_name=lead.company_name,
        business_type=lead.business_type,
        city=lead.city,
    )


class ConversationEngine:
    """
    Wraps Groq API with a stateful message history for one call.

    Usage:
        engine = ConversationEngine(lead)
        reply = engine.chat("नमस्ते, कौन है?")
    """

    def __init__(self, lead: Lead) -> None:
        self._client = Groq(api_key=settings.groq_api_key)
        self._system_prompt = _load_system_prompt(lead)
        self._history: list[dict] = []

    def chat(self, user_message: str) -> str:
        """
        Send user message, get agent reply.

        Args:
            user_message: Transcribed speech from the customer.

        Returns:
            Agent response text to be synthesized by TTS.
        """
        self._history.append({"role": "user", "content": user_message})

        messages = [
            {"role": "system", "content": self._system_prompt},
            *self._history,
        ]

        response = self._client.chat.completions.create(
            model=settings.groq_model,
            messages=messages,
            max_tokens=150,   # keep replies short for phone conversation
            temperature=0.7,
        )

        reply = response.choices[0].message.content.strip()
        self._history.append({"role": "assistant", "content": reply})
        logger.debug("LLM reply: %.80r", reply)
        return reply

    def get_full_transcript(self) -> str:
        """
        Return the full conversation as a transcript string.
        Format: "Customer: ...\nAgent: ..."
        """
        lines = []
        for msg in self._history:
            role = "Customer" if msg["role"] == "user" else "Agent (Riya)"
            lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines)
