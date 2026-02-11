"""In-memory session store. Replace with DB/Redis for production."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Session state: we're either clarifying over WhatsApp or ready to send the Lovable link.
SESSION_STATE_CLARIFYING = "clarifying"
SESSION_STATE_READY_TO_BUILD = "ready_to_build"
SESSION_STATE_LINK_SENT = "link_sent"


@dataclass
class AgentSession:
    phone: str
    transcript_or_summary: str
    enhanced_prompt: str = ""
    clarification_messages: list[dict] = field(default_factory=list)  # [{"role":"user"|"assistant","content":"..."}]
    cost_estimate_band: str = ""  # e.g. "1-2 credits", "2-4 credits"
    lovable_url: str = ""
    state: str = SESSION_STATE_CLARIFYING


_sessions: dict[str, AgentSession] = {}


def get_session(phone: str) -> Optional[AgentSession]:
    return _sessions.get(phone)


def set_session(phone: str, session: AgentSession) -> None:
    _sessions[phone] = session


def create_session(phone: str, transcript_or_summary: str, enhanced_prompt: str) -> AgentSession:
    s = AgentSession(
        phone=phone,
        transcript_or_summary=transcript_or_summary,
        enhanced_prompt=enhanced_prompt,
    )
    set_session(phone, s)
    return s
