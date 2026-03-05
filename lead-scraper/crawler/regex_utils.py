"""Regex patterns for lead extraction."""

from __future__ import annotations

import re

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

SOCIAL_PATTERNS = {
    "instagram": re.compile(r"instagram\.com/([a-zA-Z0-9_.]+)", re.I),
    "facebook": re.compile(r"facebook\.com/([a-zA-Z0-9_.-]+)", re.I),
    "linkedin": re.compile(r"linkedin\.com/(company|in)/([a-zA-Z0-9_.-]+)", re.I),
    "x": re.compile(r"(?:x\.com|twitter\.com)/([a-zA-Z0-9_]+)", re.I),
    "tiktok": re.compile(r"tiktok\.com/@([a-zA-Z0-9_.]+)", re.I),
    "pinterest": re.compile(r"pinterest\.com/([a-zA-Z0-9_.-]+)", re.I),
}
