"""Rough cost (credit) estimate for Lovable. No Lovable API; we estimate from prompt."""
from __future__ import annotations

# Lovable: simple ~0.5, medium ~1, complex ~2+. We map prompt length/complexity to a band.
def estimate_credit_band(prompt: str) -> str:
    """
    Returns a short string like "~1-2 credits" or "~2-4 credits" for the user message.
    """
    n = len(prompt)
    if n < 200:
        return "~0.5-1 credit"
    if n < 600:
        return "~1-2 credits"
    if n < 1500:
        return "~2-4 credits"
    return "~3-6 credits (complex build)"
