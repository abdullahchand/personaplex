# Voice conversation → transcribe → GPT → build webhook

## Flow

1. **Moshi (Persona)** ends a WebSocket session and POSTs **multipart** to **`POST /handoff`**: `audio` = stereo WAV (channel 0 = user, channel 1 = agent), optional `phone`.
2. **Whisper** (OpenAI API): transcribe the WAV to `raw_transcript`.
3. **GPT**: turn `raw_transcript` into one **clean builder specification** (`prompt`).
4. **HTTP POST** to **`BUILD_WEBHOOK_URL`** with JSON: `{ "prompt", "raw_transcript", "phone" }`.
5. **WhatsApp** (optional): if configured and `phone` present, short confirmation after handoff; replies can refine the spec and trigger another forward when the agent returns `send_link`.

## JSON handoff (testing)

`POST /handoff` with `application/json` body `{ "phone"?, "transcript" | "summary" }` skips STT but still runs cleanup + webhook.

## Session

In-memory, keyed by phone or `pending`. Holds raw transcript/summary, `enhanced_prompt` (cleaned spec), clarification history for WhatsApp, `state`.

## Files

- `routers/handoff.py` — multipart or JSON handoff
- `services/transcription.py` — Whisper API
- `services/gpt.py` — cleanup + WhatsApp agent
- `services/build_webhook.py` — forward to your builder URL
- `services/whatsapp.py` — Meta webhook + send
- `services/session.py` — session store

Historical Lovable “Build with URL” is documented only in [docs/LOVABLE_BUILD_WITH_URL.md](./docs/LOVABLE_BUILD_WITH_URL.md).
