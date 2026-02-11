"""POST /handoff: receive transcript + phone from Persona, create session, send first WhatsApp message."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from pydantic import BaseModel

from services import gpt, lovable, cost_estimate, session as session_svc, whatsapp

router = APIRouter(prefix="/handoff", tags=["handoff"])


class HandoffBody(BaseModel):
    phone: str
    transcript: str | None = None
    summary: str | None = None

    def get_text(self) -> str:
        if self.transcript:
            return self.transcript
        if self.summary:
            return self.summary
        raise ValueError("Need transcript or summary")


@router.post("")
async def handoff(body: HandoffBody):
    """
    Called by Persona (or voice pipeline) after the call. Creates a session,
    enhances the prompt with GPT, and sends the first WhatsApp message
    (either a clarifying question or the cost + Lovable link).
    """
    try:
        text = body.get_text()
    except ValueError as e:
        raise HTTPException(422, str(e))

    phone = body.phone.strip()
    if not phone:
        raise HTTPException(422, "phone required")

    enhanced = await gpt.enhance_prompt(text)
    s = session_svc.create_session(phone, text, enhanced)

    # First message after handoff: intro and offer to clarify or send link.
    # We pass a synthetic "user" message so the agent produces the first assistant reply.
    out = await gpt.agent_next(
        enhanced_prompt=enhanced,
        clarification_history=[],
        user_last_message="[System: First contact after voice call. Send a short hello and either one optional clarifying question or say we'll send the build link now.]",
    )

    msg = out.get("message", "We've got your request. We'll send you a link to build your app in a moment.")
    if out.get("updated_prompt"):
        s.enhanced_prompt = out["updated_prompt"]

    if out.get("action") == "send_link":
        s.cost_estimate_band = cost_estimate.estimate_credit_band(s.enhanced_prompt)
        s.lovable_url = lovable.build_lovable_url(s.enhanced_prompt)
        s.state = session_svc.SESSION_STATE_READY_TO_BUILD
        session_svc.set_session(phone, s)
        whatsapp.send_text(phone, msg)
        whatsapp.send_text(
            phone,
            f"Cost estimate: {s.cost_estimate_band}. Open this link to create your app (you'll need a Lovable account):\n{s.lovable_url}",
        )
        s.state = session_svc.SESSION_STATE_LINK_SENT
        session_svc.set_session(phone, s)
    else:
        s.clarification_messages.append({"role": "assistant", "content": msg})
        session_svc.set_session(phone, s)
        whatsapp.send_text(phone, msg)

    return {"ok": True, "phone": phone, "state": s.state}
