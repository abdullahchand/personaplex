"""POST /handoff: receive conversation audio (or JSON transcript), transcribe, clean, forward to build webhook."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from pydantic import BaseModel

from config import settings
from services import build_webhook, gpt, session as session_svc, transcription, whatsapp

router = APIRouter(prefix="/handoff", tags=["handoff"])


class HandoffJsonBody(BaseModel):
    phone: str | None = None
    transcript: str | None = None
    summary: str | None = None
    call_id: str | None = None

    def get_text(self) -> str:
        if self.transcript:
            return self.transcript
        if self.summary:
            return self.summary
        raise ValueError("Need transcript or summary")


def _require_handoff_secret(request: Request) -> None:
    expected = (settings.handoff_shared_secret or "").strip()
    if not expected:
        return
    got = (request.headers.get("x-handoff-secret") or "").strip()
    if got != expected:
        raise HTTPException(401, "invalid handoff secret")


def _session_id(phone: str, call_id: str) -> str:
    if call_id:
        return call_id
    return phone or "pending"


@router.post("")
async def handoff(request: Request):
    """
    Production: multipart/form-data — `audio` (stereo WAV, ch0=caller, ch1=agent),
    optional `phone`, optional `call_id` (idempotency key).
    Local/testing only: JSON `{ "phone"?, "call_id"?, "transcript" | "summary" }`.
    """
    _require_handoff_secret(request)
    ct = (request.headers.get("content-type") or "").lower()
    phone = ""
    call_id = ""
    raw_transcript = ""
    multipart = "multipart/form-data" in ct

    if multipart:
        form = await request.form()
        phone = str(form.get("phone") or "").strip()
        call_id = str(form.get("call_id") or "").strip()
        upload = form.get("audio")
        if upload is None:
            raise HTTPException(422, "multipart handoff requires form field 'audio' (file upload)")
        if not hasattr(upload, "read"):
            raise HTTPException(422, "form field 'audio' must be a file")
        raw_bytes = await upload.read()
        if len(raw_bytes) < 64:
            raise HTTPException(422, "audio file too small")
        suffix = Path(getattr(upload, "filename", None) or "conversation.wav").suffix or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw_bytes)
            tmp_path = tmp.name
        try:
            raw_transcript = await transcription.transcribe_file(tmp_path)
        finally:
            os.unlink(tmp_path)
    elif "application/json" in ct:
        try:
            data = await request.json()
        except Exception as e:
            raise HTTPException(422, f"invalid JSON: {e}") from e
        try:
            body = HandoffJsonBody.model_validate(data)
            phone = str(body.phone or "").strip()
            call_id = str(body.call_id or "").strip()
            raw_transcript = body.get_text()
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
    else:
        raise HTTPException(
            415,
            "Use multipart/form-data with fields: audio (file), optional phone, optional call_id; "
            "or application/json with transcript/summary (local testing only)",
        )

    session_id = _session_id(phone, call_id)
    cleaned = await gpt.clean_for_builder(raw_transcript)
    status, _ = await build_webhook.forward_cleaned_prompt(cleaned, raw_transcript, phone or None)

    s = session_svc.create_session(session_id, raw_transcript, cleaned)
    s.state = session_svc.SESSION_STATE_FORWARDED
    session_svc.set_session(session_id, s)

    if phone and settings.whatsapp_phone_number_id and settings.whatsapp_access_token:
        try:
            note = (
                "Thanks — we've transcribed your call and sent your specification to the builder."
                if status and status < 400
                else "Thanks — we've saved your specification; the builder handoff will retry if needed."
            )
            await whatsapp.send_text(phone, note)
        except Exception as e:
            print(f"[handoff] WhatsApp notify failed: {e}")

    payload = {
        "ok": True,
        "session_id": session_id,
        "phone": phone or None,
        "call_id": call_id or None,
        "state": s.state,
        "build_webhook_status": status,
    }
    if not multipart:
        payload["raw_transcript_preview"] = raw_transcript[:500] + ("…" if len(raw_transcript) > 500 else "")
        payload["cleaned_preview"] = cleaned[:500] + ("…" if len(cleaned) > 500 else "")

    return JSONResponse(status_code=202 if multipart else 200, content=payload)
