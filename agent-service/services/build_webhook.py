"""Forward cleaned builder spec to a separate HTTP endpoint."""
from __future__ import annotations

import json

import httpx

from config import settings


async def forward_cleaned_prompt(
    cleaned_prompt: str,
    raw_transcript: str,
    phone: str | None,
) -> tuple[int, str]:
    """
    POST JSON to BUILD_WEBHOOK_URL. Returns (status_code, response_body_snippet).
    If URL is unset, returns (0, "skipped").
    """
    url = (settings.build_webhook_url or "").strip()
    if not url:
        print("[build_webhook] BUILD_WEBHOOK_URL not set; skipping forward")
        return 0, "skipped"
    payload = {
        "prompt": cleaned_prompt,
        "raw_transcript": raw_transcript,
        "phone": phone or None,
    }
    print("[build_webhook] POST", url, "payload keys:", list(payload.keys()))
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(url, json=payload)
    body = (r.text or "")[:2000]
    print(f"[build_webhook] status={r.status_code} body_snippet={body!r}")
    return r.status_code, body
