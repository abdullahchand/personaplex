"""GPT: (1) clean raw transcript for a builder webhook, (2) WhatsApp agent next-action + message."""
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


CLEAN_FOR_BUILDER_SYSTEM = """You are a product assistant. Given a raw transcript of a conversation (user and possibly an assistant) about an app or website the user wants built, output a single, clear specification suitable for an automated builder or downstream service.

Rules:
- One short paragraph (2-5 sentences).
- Focus on: what the product does, main features, and any style (e.g. "landing page", "dashboard", "minimal").
- No small talk, filler, or meta instructions; only the product specification.
- Output ONLY the specification text, no quotes or preamble."""


AGENT_SYSTEM = """You are an assistant that helps users get their app built. You communicate over WhatsApp.

You have:
1. A cleaned app specification (from their voice conversation).
2. The ability to ask 1-2 short clarifying questions if something is unclear.
3. When ready, you confirm you're sending their specification to the build system (the server will forward it; you do not have a URL to paste).

Respond with a JSON object only, no markdown:
{
  "action": "clarify" | "send_link",
  "message": "The exact message to send to the user (plain text, WhatsApp-friendly).",
  "updated_prompt": "Optional: if the user gave new details, the updated full specification. Omit or empty if no change."
}

- Use "send_link" when the user is done or you have enough info (name kept for compatibility). Your message should say their spec is being sent to the builder, not that they will get a Lovable URL.
- Keep messages very short (WhatsApp)."""


async def clean_for_builder(raw_transcript: str) -> str:
    """Turn raw STT / transcript into a single builder-ready specification."""
    client = _client_get()
    messages = [
        {"role": "system", "content": CLEAN_FOR_BUILDER_SYSTEM},
        {"role": "user", "content": raw_transcript},
    ]
    print("[GPT clean] request:", json.dumps({"model": settings.openai_model_enhance, "temperature": 0.3, "messages": messages}, indent=2, ensure_ascii=False))
    r = await client.chat.completions.create(
        model=settings.openai_model_enhance,
        messages=messages,
        temperature=0.3,
    )
    text = (r.choices[0].message.content or "").strip()
    print("[GPT clean] response:", repr(text))
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
        {"role": "user", "content": f"App specification:\n{enhanced_prompt}"},
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
