"""Transcribe audio files via OpenAI Whisper API."""
from __future__ import annotations

import asyncio

from openai import OpenAI

from config import settings


def _transcribe_sync(path: str) -> str:
    """Sync Whisper call (runs in a thread pool from async handlers)."""
    client = OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )
    with open(path, "rb") as f:
        r = client.audio.transcriptions.create(
            model=settings.openai_whisper_model,
            file=f,
        )
    return (getattr(r, "text", None) or "").strip()


async def transcribe_file(path: str) -> str:
    """Transcribe a local audio file (e.g. WAV); returns plain text."""
    print(f"[transcription] transcribing file={path!r} model={settings.openai_whisper_model}")
    text = await asyncio.to_thread(_transcribe_sync, path)
    print(f"[transcription] raw length={len(text)} chars")
    return text
