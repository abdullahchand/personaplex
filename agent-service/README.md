# Voice conversation → transcribe → OpenAI → build webhook

Backend for: **full call audio** → **speech-to-text** → **OpenAI cleanup** (builder-ready spec) → **HTTP POST** to your own URL that runs the actual build flow.

Historical note: we previously embedded prompts in a **Lovable Build-with-URL**; that is documented only in [docs/LOVABLE_BUILD_WITH_URL.md](./docs/LOVABLE_BUILD_WITH_URL.md) and is not used by the service anymore.

## Flow

1. **Moshi** (Persona) ends a WebSocket session and POSTs **multipart** form data to **`POST /handoff`**: field `audio` = stereo WAV (left = user, right = agent), optional `phone`.
2. This service **transcribes** the audio (OpenAI **Whisper** API by default).
3. **GPT** turns the raw transcript into a **single clean specification** for your builder.
4. **`BUILD_WEBHOOK_URL`** receives a JSON body: `prompt`, `raw_transcript`, `phone` (optional).
5. **WhatsApp** (optional): if configured and `phone` is present, the user gets a short confirmation; follow-up chat can still refine the stored spec and re-forward when the agent says “done”.

## Setup

1. **Env**

   ```bash
   cp .env.example .env
   ```

   Set at least:

   - `OPENAI_API_KEY` — used for Whisper + cleanup model
   - `BUILD_WEBHOOK_URL` — your HTTPS endpoint that accepts the JSON payload (leave empty to skip forward; useful for local testing)

   Optional: WhatsApp Cloud API vars and `BASE_URL` as before if you use the webhook.

2. **Install and run**

   ```bash
   pip install -r requirements.txt
   uvicorn main:app --reload --port 8000
   ```

3. **Moshi**

   Point **`--handoff-url`** at `http(s)://<agent-service>/handoff`. Moshi sends **multipart** with the conversation WAV, not JSON.

## API

- **`POST /handoff`** (preferred): `multipart/form-data` with `audio` (WAV file), optional `phone`.
- **`POST /handoff`**: `application/json` body `{ "phone"?, "transcript" | "summary" }` — skips STT; still cleans and forwards (for tests or non-audio clients).
- **`GET /webhooks/whatsapp`** / **`POST /webhooks/whatsapp`** — Meta WhatsApp webhook (optional).
- **`GET /health`**

See [ARCHITECTURE.md](./ARCHITECTURE.md) for more structure (may still mention older naming in places).
