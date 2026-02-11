# Voice → GPT → WhatsApp → Lovable Agent

End-to-end flow: user calls → Persona gathers requirements → GPT enhances the prompt → WhatsApp agent clarifies → cost check → Lovable build link sent to user.

---

## 1. High-level flow

```
┌─────────────┐     call      ┌─────────────┐     "I'll WhatsApp you"     ┌─────────────┐
│   User      │ ────────────► │   Persona   │ ──────────────────────────► │  Backend   │
│ (phone)     │               │ (voice AI)  │     + user phone number      │ (this svc) │
└─────────────┘               └─────────────┘                             └─────┬──────┘
       │                             │                                            │
       │                             │  transcript / summary                      │
       │                             └──────────────────────────────────────────►│
       │                                                                         │
       │  WhatsApp ◄─────────────────────────────────────────────────────────────┤
       │     │      clarifying questions, cost estimate, Lovable link            │
       │     │                                                                   │
       │     └──► GPT Agent (orchestrates: clarify → estimate → build URL)       │
       │                                                                         │
       │  User opens Lovable link → signs in → app is built → preview URL        │
       └─────────────────────────────────────────────────────────────────────────
```

1. **Voice call**: User calls a number; Persona (voice AI, e.g. PersonaPlex or telephony + STT/LLM/TTS) answers.
2. **Gathering**: User describes what they want built; Persona asks clarifying questions.
3. **Handoff**: Persona says they’ll get back via WhatsApp and collects the user’s WhatsApp number (or uses caller ID if linked).
4. **Backend receives**: This service gets the **conversation transcript or a short summary** (and the user’s phone for WhatsApp).
5. **GPT prompt enhancement**: Backend sends the raw requirements to the GPT API to produce a single, clear **Lovable-style app prompt** (one short paragraph, feature-focused).
6. **WhatsApp agent**: A GPT-driven agent uses WhatsApp to:
   - Optionally ask 1–2 clarifying questions.
   - When ready: run a **cost estimate** (see below), then send the **Lovable Build-with-URL** and a short explanation.
7. **Cost check**: Before “transferring” to Lovable, we **estimate cost** and tell the user (e.g. “This will use roughly X credits; you need a Lovable Pro account or similar. Open the link to create the app in your account.”). No direct Lovable billing API; we estimate and inform.
8. **Lovable**: We do **not** call a REST API that returns a project URL. We use **Build with URL**: we build `https://lovable.dev/?autosubmit=true#prompt=ENCODED_PROMPT` and send that link to the user. The user opens it → signs into Lovable (or signs up) → chooses workspace → Lovable builds the app. The “website URL” we “return” is this **build link**; after the user completes the flow, the **live app URL** is visible inside Lovable (we can mention that in the WhatsApp message).
9. **Delivery**: User receives the Lovable link (and cost note) on WhatsApp.

---

## 2. Components

| Component | Responsibility |
|----------|----------------|
| **Persona (voice)** | Answer call, collect requirements via conversation, get WhatsApp number, send transcript/summary + phone to backend. (Implemented elsewhere; this service consumes its output.) |
| **Backend (this service)** | Receive handoff, call GPT to enhance prompt, run WhatsApp agent (GPT + WhatsApp API), estimate cost, build Lovable URL, send link + message via WhatsApp. |
| **GPT API** | (1) Turn transcript/summary into one Lovable-ready prompt. (2) Power the WhatsApp agent: decide next action (ask question / send cost + link), and generate message text. |
| **WhatsApp Cloud API** | Send messages to user; receive replies (webhook). Used by the backend to implement the “GPT agent over WhatsApp.” |
| **Lovable** | No server-side “create project” API. We only generate the **Build with URL** and send it to the user. Cost is credit-based (see below). |

---

## 3. Cost check (before “transferring” to Lovable)

- Lovable uses **credits** (not a per-project price). Rough guide: simple edit ~0.5, complex build ~2+ credits. Plans: Free (5/day, 30/mo cap), Pro from $25/mo (100+ credits), Business from $50/mo.
- **We cannot** query Lovable’s API for “price for this project” or “your balance” from our backend (no such public API).
- **What we do**:
  1. **Estimate**: From the enhanced prompt (and optionally number of clarifications), use a small **cost-estimation step** (e.g. GPT or rule-based) to map to a band: “~1–2 credits”, “~2–4 credits”, “complex (consider Pro plan)”.
  2. **Inform**: Before sending the Lovable link, the WhatsApp agent sends a short message like: “This build will roughly use X credits. You need a Lovable account (free tier has 5 credits/day). [Link]. Open the link to create the app in your Lovable workspace.”
  3. **No charge from us**: We don’t charge; we only send the link. The user uses their own Lovable subscription/credits when they open the link.

So “check cost before transferring” = **estimate + inform the user over WhatsApp**, not “transfer a website from a Lovable subscription” (we don’t move billing; we send a build link).

---

## 4. Data flow (backend only)

- **Input**: `{ "phone": "+1234567890", "transcript" | "summary": "..." }` (from Persona / voice pipeline).
- **Internal**: Stored in a **session** (in-memory or DB) keyed by phone (or session_id). Session holds: raw input, enhanced_prompt, clarification_rounds, cost_estimate, state (e.g. `clarifying` | `ready_to_build` | `link_sent`).
- **GPT**: 
  - One call to get **enhanced_prompt** from transcript/summary.
  - Per user WhatsApp message: GPT decides “ask a question” vs “send cost + Lovable link” and returns (action, message_text, optional updated_prompt).
- **Lovable**: `lovable_url = build_lovable_url(enhanced_prompt)` (and optional image URLs); no server-side project creation.
- **WhatsApp**: Send text (and optionally media) via Cloud API; receive incoming messages via webhook → update session → call GPT → send reply.

---

## 5. API surface of this service

- **POST /handoff** (from Persona): Body `{ "phone": "+...", "transcript" or "summary": "..." }`. Creates session, runs GPT to get enhanced prompt, sends first WhatsApp message (e.g. “We have your request. A few quick questions: …” or “Here’s an estimate and your link: …”).
- **POST /webhooks/whatsapp** (from Meta): WhatsApp Cloud API webhook. Verify token on GET; on POST, parse incoming message, find session by phone, call GPT, send reply (and optionally send Lovable link + cost message when state = ready_to_build).
- **GET /health**: Health check.

(Optional later: GET /session/:id for debugging.)

---

## 6. Lovable “return URL” clarification

- We **do not** get back a “created website URL” from Lovable programmatically. We only generate and send the **Build with URL**.
- The **returned value to the user** is: the **Lovable build link**. When the user opens it and completes the flow in the browser, Lovable creates the app in their workspace and they see the preview/live app URL there. We can tell them in WhatsApp: “Open this link to build your app; when it’s done, you’ll see the live link inside Lovable.”

---

## 7. Tech stack (this repo)

- **Language**: Python 3.11+.
- **Framework**: FastAPI (async, easy webhook + JSON).
- **GPT**: OpenAI API (or compatible) for prompt enhancement and WhatsApp agent logic.
- **WhatsApp**: Meta WhatsApp Cloud API (send messages + webhook for incoming).
- **Lovable**: URL builder only (no API key; optional image URLs in hash).
- **Storage**: Start with in-memory session store; later SQLite/Postgres/Redis for persistence.

---

## 8. Environment variables

- `OPENAI_API_KEY`: GPT API.
- `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`: WhatsApp Cloud API.
- `WEBHOOK_VERIFY_TOKEN`: For GET /webhooks/whatsapp verification.
- `BASE_URL` or `PUBLIC_URL`: For webhook URL and any links in messages (e.g. future status page).
- Optional: `LOVABLE_*` if Lovable ever adds auth-based API (currently not used).

---

## 9. File layout (scaffold)

```
agent-service/
├── ARCHITECTURE.md          # this file
├── README.md                # run, env, deploy notes
├── .env.example
├── requirements.txt
├── main.py                  # FastAPI app, routes
├── config.py                # settings from env
├── services/
│   ├── __init__.py
│   ├── gpt.py               # prompt enhancement + agent (next action + message)
│   ├── whatsapp.py          # send message, parse webhook
│   ├── lovable.py           # build Build-with-URL
│   ├── cost_estimate.py     # rough credit band from prompt
│   └── session.py           # in-memory session store
└── routers/
    ├── __init__.py
    ├── handoff.py           # POST /handoff
    └── webhooks.py          # GET/POST /webhooks/whatsapp
```

---

## 10. Sequence (summary)

1. Persona sends **handoff** → backend creates session, enhances prompt with GPT, sends first WhatsApp message (clarify or link).
2. User replies on WhatsApp → **webhook** → backend loads session, calls GPT (agent) → GPT says “ask X” or “send link + cost” → backend sends reply (and optionally Lovable link).
3. When agent decides “ready”: backend runs **cost estimate**, then sends one WhatsApp message with estimate text + **Lovable Build-with-URL**. User opens link and completes flow in Lovable.

This keeps Persona for voice, GPT for prompt and agent logic, WhatsApp for async follow-up and delivery, and Lovable for the actual app creation via the only supported mechanism (Build with URL).
