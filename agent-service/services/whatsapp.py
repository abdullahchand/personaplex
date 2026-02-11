"""WhatsApp Cloud API: send message, parse webhook payload."""
from __future__ import annotations

from typing import Any

import httpx

from config import settings

SEND_URL_TEMPLATE = (
    "https://graph.facebook.com/v18.0/{phone_id}/messages"
)


def send_text(to_phone: str, text: str) -> dict[str, Any]:
    """
    Send a text message to the user. to_phone: E.164 format (e.g. +1234567890).
    """
    url = SEND_URL_TEMPLATE.format(phone_id=settings.whatsapp_phone_number_id)
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone.lstrip("+"),
        "type": "text",
        "text": {"body": text[:4096]},
    }
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_access_token}",
        "Content-Type": "application/json",
    }
    with httpx.Client() as client:
        r = client.post(url, json=payload, headers=headers, timeout=15.0)
        r.raise_for_status()
        return r.json()


def parse_incoming_message(body: dict) -> tuple[str | None, str | None]:
    """
    Extract (sender_phone, text) from WhatsApp webhook body.
    Returns (None, None) if not a simple text message we handle.
    """
    try:
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages")
        if not messages:
            return None, None
        msg = messages[0]
        if msg.get("type") != "text":
            return None, None
        from_ = msg.get("from")
        text = (msg.get("text", {}) or {}).get("body", "").strip()
        if not from_ or not text:
            return None, None
        # from_ is WhatsApp ID; we need E.164. Often it's already the number without +.
        phone = f"+{from_}" if not from_.startswith("+") else from_
        return phone, text
    except (IndexError, KeyError, TypeError):
        return None, None
