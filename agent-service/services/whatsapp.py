"""WhatsApp via pywa: send messages and handle incoming webhook (agent logic)."""
from __future__ import annotations

from pywa_async import WhatsApp, filters, types
from pywa_async.handlers import MessageHandler
from config import settings

_wa: WhatsApp | None = None


def init_whatsapp(app):
    """
    Create the WhatsApp client and register the webhook route on the FastAPI app.
    Call this from main after creating the app. Registers GET/POST at webhook_endpoint.
    """
    global _wa
    # Only pass callback_url when app_id and app_secret are set (pywa requires both to register the webhook)
    has_app_creds = bool(settings.whatsapp_app_id and settings.whatsapp_app_secret)
    callback_url = (settings.base_url or "").rstrip("/") if has_app_creds else None
    _wa = WhatsApp(
        phone_id=settings.whatsapp_phone_number_id,
        token=settings.whatsapp_access_token,
        server=app,
        webhook_endpoint="/webhooks/whatsapp",
        verify_token=settings.webhook_verify_token,
        callback_url=callback_url,
        app_id=settings.whatsapp_app_id if has_app_creds else None,
        app_secret=settings.whatsapp_app_secret if has_app_creds else None,
    )
    _wa.add_handlers(MessageHandler(_handle_message, filters.text, priority=1))
    return _wa


async def _handle_message(client: WhatsApp, msg: types.Message):
    """Handle incoming text: find session, call GPT agent, send reply (and forward spec when done)."""
    from services import build_webhook, gpt, session as session_svc

    text = (msg.text or "").strip() if msg.text else ""
    if not text:
        return
    # wa_id is the sender's WhatsApp ID (number as string, no +)
    from_wa_id = getattr(msg.from_user, "wa_id", None) or ""
    phone = f"+{from_wa_id}" if from_wa_id and not from_wa_id.startswith("+") else from_wa_id

    s = session_svc.get_session(phone)
    if not s:
        await client.send_message(to=phone, text=(
            "We don't have an active request for this number. "
            "Please start by calling us so we can collect your requirements."
        ))
        return

    s.clarification_messages.append({"role": "user", "content": text})
    out = await gpt.agent_next(
        enhanced_prompt=s.enhanced_prompt,
        clarification_history=s.clarification_messages[:-1],
        user_last_message=text,
    )

    if out.get("updated_prompt"):
        s.enhanced_prompt = out["updated_prompt"]

    msg_text = out.get("message", "Got it. We'll update the builder shortly.")

    if out.get("action") == "send_link":
        status, _ = await build_webhook.forward_cleaned_prompt(
            s.enhanced_prompt,
            s.transcript_or_summary,
            phone,
        )
        print(f"[WhatsApp] send_link: build_webhook status={status}")
        s.state = session_svc.SESSION_STATE_READY_TO_BUILD
        session_svc.set_session(phone, s)
        await client.send_message(to=phone, text=msg_text)
        follow = (
            "Your specification has been sent to the builder."
            if status and status < 400
            else "We've saved your latest specification. If automatic forwarding failed, we'll follow up."
        )
        await client.send_message(to=phone, text=follow)
        s.state = session_svc.SESSION_STATE_FORWARDED
        session_svc.set_session(phone, s)
    else:
        s.clarification_messages.append({"role": "assistant", "content": msg_text})
        session_svc.set_session(phone, s)
        await client.send_message(to=phone, text=msg_text)


async def send_text(to_phone: str, text: str) -> None:
    """Send a text message. to_phone: E.164 format (e.g. +1234567890). Requires init_whatsapp() first."""
    if _wa is None:
        raise RuntimeError("WhatsApp client not initialized; call init_whatsapp(app) first.")
    to = to_phone.lstrip("+") if to_phone.startswith("+") else to_phone
    await _wa.send_message(to=to, text=text[:4096])
