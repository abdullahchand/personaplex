"""
Voice → GPT → WhatsApp → Lovable agent service.

- POST /handoff: receive transcript + phone from Persona
- GET/POST /webhooks/whatsapp: WhatsApp webhook
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import handoff, webhooks

app = FastAPI(
    title="Voice-to-Lovable Agent",
    description="Handoff from Persona voice call → GPT enhancement → WhatsApp clarification → Lovable build link",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(handoff.router)
app.include_router(webhooks.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"service": "voice-to-lovable-agent", "docs": "/docs"}
