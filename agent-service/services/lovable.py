"""Build Lovable 'Build with URL' link. No API key; we only construct the URL."""
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
