"""Build Lovable 'Build with URL' link. No API key; we only construct the URL."""
from __future__ import annotations

from urllib.parse import quote

LOVABLE_BASE = "https://lovable.dev/?autosubmit=true#"
MAX_PROMPT_LENGTH = 50_000  # Lovable doc limit


def build_lovable_url(prompt: str, image_urls: list[str] | None = None) -> str:
    """
    Build the Build-with-URL for Lovable.
    prompt: app description (will be URL-encoded).
    image_urls: optional list of public image URLs (max 10).
    """
    if len(prompt) > MAX_PROMPT_LENGTH:
        prompt = prompt[:MAX_PROMPT_LENGTH]
    encoded_prompt = quote(prompt, safe="")
    parts = [f"prompt={encoded_prompt}"]
    if image_urls:
        for url in image_urls[:10]:
            parts.append(f"images={quote(url, safe='')}")
    return LOVABLE_BASE + "&".join(parts)


def create_and_format_link_message(
    prompt: str,
    cost_band: str,
    intro: str | None = None,
    *,
    image_urls: list[str] | None = None,
) -> tuple[str, str]:
    """
    Link creator: from the (enhanced/returned) prompt, build the Lovable URL
    and a WhatsApp-ready message that includes the link and cost.

    Returns (lovable_url, message_to_send).
    intro: optional short line before the link (e.g. agent's greeting).
    """
    url = build_lovable_url(prompt, image_urls=image_urls)
    lines = []
    if intro and intro.strip():
        lines.append(intro.strip())
    lines.append(f"Cost estimate: {cost_band}.")
    lines.append("Open this link to create your app (Lovable account required):")
    lines.append(url)
    message = "\n".join(lines)
    return url, message
