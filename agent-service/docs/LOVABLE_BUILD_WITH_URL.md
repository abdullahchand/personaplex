# Lovable “Build with URL” (historical)

This project **no longer** generates Lovable links in the runtime pipeline. This document describes the old pattern for reference.

## What it was

Lovable lets users start a project from a text prompt by opening a URL. There is **no public API** to create projects server-side; the supported approach is to send users a link that pre-fills the prompt.

## URL shape

Base pattern (see Lovable docs for current parameters):

```text
https://lovable.dev/?autosubmit=true#prompt=<URL_ENCODED_PROMPT>
```

- `prompt` is the full app specification, **percent-encoded** (no unencoded spaces or `#` in the fragment).
- Optional `images=` parameters can repeat for image URLs (limits apply on Lovable’s side).

Example (conceptual):

```text
https://lovable.dev/?autosubmit=true#prompt=Build%20a%20minimal%20landing%20page...
```

## Behavior

1. After the voice/WhatsApp flow produced a **clean, single prompt**, the backend called `urllib.parse.quote(prompt, safe="")` and appended it to the fragment.
2. The user opened the link in a browser, signed in to Lovable if needed, and the builder consumed the prompt.

## Why we moved away

The product flow was changed to: **record the full call as audio → transcribe → refine with OpenAI → POST JSON to your own build service URL**. That keeps the integration point as a normal webhook instead of encoding prompts into a third-party URL.

If you still want Lovable, you can implement the same URL construction in your **build webhook** service and redirect or message the user from there.
