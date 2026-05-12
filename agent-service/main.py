"""
Conversation audio → transcribe → OpenAI cleanup → build webhook (+ optional WhatsApp).

- POST /handoff: multipart audio or JSON transcript from Persona
- GET/POST /webhooks/whatsapp: WhatsApp webhook (handled by pywa)
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import handoff
from services import whatsapp as whatsapp_svc

app = FastAPI(
    title="Voice-to-builder agent",
    description="Handoff: conversation WAV → Whisper → GPT cleanup → POST BUILD_WEBHOOK_URL; optional WhatsApp",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(handoff.router)
whatsapp_svc.init_whatsapp(app)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"service": "voice-to-builder-agent", "docs": "/docs"}
