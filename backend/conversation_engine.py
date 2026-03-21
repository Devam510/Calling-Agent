import os
from pathlib import Path
from typing import List, Dict
import groq

from backend.config import settings
from backend.models import Lead

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

def _load_system_prompt(lead: Lead) -> str:
    prompt_path = PROMPTS_DIR / "sales_system_prompt.txt"
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            template = f.read()
    except FileNotFoundError:
        return f"You are a sales agent calling {lead.owner_name} from {lead.company_name}."
    
    return template.replace("{company_name}", lead.company_name).replace("{owner_name}", lead.owner_name)


class ConversationEngine:
    def __init__(self, lead: Lead, client: groq.AsyncGroq = None):
        self.lead = lead
        self.client = client or groq.AsyncGroq(api_key=settings.groq_api_key)
        self.history: List[Dict[str, str]] = [
            {"role": "system", "content": _load_system_prompt(lead)}
        ]

    async def get_response(self, user_text: str) -> str:
        """
        Append user_text to history, call Groq API for a response, append and return the response.
        If user_text is '[CALL_STARTED]', generate the initial greeting without adding user_text to history as a normal user message.
        """
        if user_text == "[CALL_STARTED]":
            # For the first greeting, we just want the model to act. We send an invisible trigger.
            # We don't append this exact token to history as it's not a real user utterance,
            # or we can pass a system instruction "Start the conversation with a greeting."
            messages = self.history + [{"role": "system", "content": "The call has just started. Say a brief introductory hello to the customer."}]
        else:
            self.history.append({"role": "user", "content": user_text})
            messages = self.history

        try:
            response = await self.client.chat.completions.create(
                model=settings.groq_model,
                messages=messages,
                max_tokens=150,
                temperature=0.7,
            )
            reply = response.choices[0].message.content.strip()
            self.history.append({"role": "assistant", "content": reply})
            return reply
        except Exception as e:
            # Fallback handling
            fallback = "Maaf kijiyega, mujhe theek se sunai nahi diya. Kya aap dohra sakte hain?" # "Sorry, I couldn't hear properly. Can you repeat?"
            return fallback

    async def chat(self, user_text: str) -> str:
        return await self.get_response(user_text)

    def get_full_transcript(self) -> str:
        """Return the whole conversation formatted as a string."""
        lines = []
        for msg in self.history:
            lines.append(f"{msg['role']}: {msg['content']}")
        return "\n".join(lines)

