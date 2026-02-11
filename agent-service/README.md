# Voice → GPT → WhatsApp → Lovable Agent

Backend for the flow: **User calls** → Persona gathers requirements → **Handoff** to this service → **GPT** enhances the prompt → **WhatsApp** agent clarifies (optional) → **Cost estimate** → **Lovable Build-with-URL** sent to user.

## Flow

1. **Persona** (voice) collects what the user wants to build and gets their WhatsApp number, then calls **POST /handoff** with `phone` and `transcript` or `summary`.
2. This service enhances the text with the **GPT API** and sends the first **WhatsApp** message (intro or clarifying question).
3. User replies on **WhatsApp** → **webhook** → GPT agent decides: ask more or send link.
4. When sending the link: we compute a **cost estimate** (credit band), build the **Lovable Build-with-URL**, and send both in WhatsApp. The user opens the link and creates the app in their Lovable account.

See [ARCHITECTURE.md](./ARCHITECTURE.md) for details.

## Setup

1. **Env**
   ```bash
   cp .env.example .env
   # Edit .env: OPENAI_API_KEY, WHATSAPP_*, WEBHOOK_VERIFY_TOKEN, BASE_URL
   ```

2. **WhatsApp Cloud API**
   - Create a Meta app and add WhatsApp product.
   - Set webhook URL to `https://<your-domain>/webhooks/whatsapp` and subscribe to `messages`.
   - Use the same `WEBHOOK_VERIFY_TOKEN` in `.env`.

3. **Install and run**
   ```bash
   pip install -r requirements.txt
   uvicorn main:app --reload --port 8000
   ```

4. **Handoff from Persona**
   - After the voice call, your Persona backend should POST to `https://<your-domain>/handoff`:
   ```json
   { "phone": "+1234567890", "transcript": "User said they want a todo app with dark mode..." }
   ```

## Cost check

We do **not** call a Lovable API to get price or balance. We **estimate** a credit band from the prompt length and send that to the user before the link (e.g. “~1–2 credits”). The user uses their own Lovable subscription when they open the link.

## API

- **POST /handoff** — Body: `{ "phone": "+...", "transcript" or "summary": "..." }`. Creates session, enhances prompt, sends first WhatsApp message.
- **GET /webhooks/whatsapp** — Meta verification (query: `hub.mode`, `hub.verify_token`, `hub.challenge`).
- **POST /webhooks/whatsapp** — Incoming WhatsApp messages; agent replies.
- **GET /health** — Health check.
