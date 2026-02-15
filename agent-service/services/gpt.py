"""GPT: (1) enhance transcript into Lovable prompt, (2) agent next-action + message."""
from __future__ import annotations

import json
import re
from typing import Any

from openai import AsyncOpenAI

from config import settings

_client: AsyncOpenAI | None = None


def _client_get() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
    return _client


ENHANCE_SYSTEM = """You are a product assistant. Given a raw transcript or summary of a user describing an app or website they want built, output a single, clear prompt suitable for an AI app builder (Lovable).

Rules:
- One short paragraph (2-5 sentences).
- Focus on: what the app does, main features, and any style (e.g. "landing page", "dashboard", "minimal").
- No small talk or meta instructions; only the app description.
- Output ONLY the prompt text, no quotes or preamble."""

AGENT_SYSTEM = """You are an assistant that helps users get their app built via Lovable. You communicate over WhatsApp.

You have:
1. An enhanced app prompt (from the user's initial conversation).
2. The ability to ask 1-2 short clarifying questions if something is unclear.
3. When ready, you must send the user a cost estimate and the Lovable build link.

Respond with a JSON object only, no markdown:
{
  "action": "clarify" | "send_link",
  "message": "The exact message to send to the user (plain text, WhatsApp-friendly).",
  "updated_prompt": "Optional: if the user gave new details, the updated full prompt for Lovable. Omit or empty if no change."
}

- If the user's last message adds useful detail, set "updated_prompt" and then either "clarify" (one more question) or "send_link".
- If the user says they're done, or you have enough info, use "send_link". The "message" must say something like: "Here's an estimate and your link: ... [they will receive the link in a follow-up]."
- Keep messages very short (WhatsApp)."""


async def enhance_prompt(transcript_or_summary: str) -> str:
    """Turn raw transcript/summary into a single Lovable-ready prompt."""
    client = _client_get()
    messages = [
        {"role": "system", "content": ENHANCE_SYSTEM},
        {"role": "user", "content": transcript_or_summary},
    ]
    print("[GPT enhance] request:", json.dumps({"model": settings.openai_model_enhance, "temperature": 0.3, "messages": messages}, indent=2, ensure_ascii=False))
    r = await client.chat.completions.create(
        model=settings.openai_model_enhance,
        messages=messages,
        temperature=0.3,
    )
    text = (r.choices[0].message.content or "").strip()
    print("[GPT enhance] response:", repr(text))
    return text


def _parse_agent_response(content: str) -> dict[str, Any]:
    """Parse JSON from model; allow wrapped in markdown code block."""
    content = (content or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
    if m:
        content = m.group(1).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"action": "clarify", "message": "Something went wrong. Can you describe again what you'd like to build?", "updated_prompt": ""}


async def agent_next(
    enhanced_prompt: str,
    clarification_history: list[dict[str, str]],
    user_last_message: str,
) -> dict[str, Any]:
    """
    Returns dict with: action ("clarify" | "send_link"), message, updated_prompt (optional).
    """
    client = _client_get()
    messages = [
        {"role": "system", "content": AGENT_SYSTEM},
        {"role": "user", "content": f"Enhanced app prompt:\n{enhanced_prompt}"},
    ]
    for entry in clarification_history:
        messages.append({"role": entry["role"], "content": entry["content"]})
    messages.append({"role": "user", "content": user_last_message})

    print("[GPT agent] request:", json.dumps({"model": settings.openai_model_agent, "temperature": 0.2, "messages": messages}, indent=2, ensure_ascii=False))
    r = await client.chat.completions.create(
        model=settings.openai_model_agent,
        messages=messages,
        temperature=0.2,
    )
    raw = (r.choices[0].message.content or "").strip()
    print("[GPT agent] response (raw):", repr(raw))
    out = _parse_agent_response(raw)
    print("[GPT agent] response (parsed):", json.dumps(out, indent=2, ensure_ascii=False))
    return out
