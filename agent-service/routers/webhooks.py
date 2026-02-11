"""WhatsApp webhook: verify (GET), receive messages (POST)."""
from __future__ import annotations

from fastapi import APIRouter, Request, Query
from fastapi.responses import PlainTextResponse

from config import settings
from services import gpt, lovable, cost_estimate, session as session_svc, whatsapp

router = APIRouter(prefix="/webhooks/whatsapp", tags=["webhooks"])


@router.get("", response_class=PlainTextResponse)
async def verify(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    """Meta sends GET to verify the webhook. Return hub.challenge if token matches."""
    if hub_mode == "subscribe" and hub_verify_token == settings.webhook_verify_token:
        return PlainTextResponse(hub_challenge)
    return PlainTextResponse("", status_code=403)


@router.post("")
async def incoming(request: Request):
    """Meta sends POST with incoming message. Process and reply via WhatsApp."""
    body = await request.json()

    phone, text = whatsapp.parse_incoming_message(body)
    if not phone or not text:
        return {"ok": True}  # ack anyway

    s = session_svc.get_session(phone)
    if not s:
        whatsapp.send_text(
            phone,
            "We don't have an active request for this number. Please start by calling us so we can collect your requirements.",
        )
        return {"ok": True}

    s.clarification_messages.append({"role": "user", "content": text})
    out = await gpt.agent_next(
        enhanced_prompt=s.enhanced_prompt,
        clarification_history=s.clarification_messages[:-1],
        user_last_message=text,
    )

    if out.get("updated_prompt"):
        s.enhanced_prompt = out["updated_prompt"]

    msg = out.get("message", "Got it. We'll send your link shortly.")

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

    return {"ok": True}
