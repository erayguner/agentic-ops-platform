"""
Belt-and-braces output redaction pass.

Runs regex-based substitution to strip common secret patterns, bearer tokens,
emails (where not already operator-facing) and GCP service-account keys from
strings before they are embedded in Slack Block Kit payloads.

This is NOT a replacement for Model Armor (which screens Pub/Sub ingress);
it is the defence-in-depth layer on the *output* path of the Slack-notifier.
"""
from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Pattern catalogue
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[str, str]] = [
    # GCP SA key "private_key" value
    (r'-----BEGIN (RSA|EC|PRIVATE) KEY-----[\s\S]{0,4096}-----END \1 KEY-----', "[REDACTED:PRIVATE_KEY]"),
    # Bearer / OAuth2 tokens (Authorization header style, also raw)
    (r'(?i)(bearer\s+)[A-Za-z0-9\-_=+/.]{20,}', r"\1[REDACTED:BEARER_TOKEN]"),
    (r'ya29\.[A-Za-z0-9\-_]{10,}', "[REDACTED:GCLOUD_TOKEN]"),
    # API keys (common patterns: AIza..., GOCSPX-, sk-...)
    (r'AIza[A-Za-z0-9\-_]{35}', "[REDACTED:GOOGLE_API_KEY]"),
    (r'GOCSPX-[A-Za-z0-9\-_]{28}', "[REDACTED:OAUTH_SECRET]"),
    (r'sk-[A-Za-z0-9]{20,}', "[REDACTED:SK_TOKEN]"),
    # Slack tokens
    (r'xox[bpars]-[0-9A-Za-z\-]{20,}', "[REDACTED:SLACK_TOKEN]"),
    # Generic high-entropy hex strings that look like secrets (≥32 hex chars)
    (r'\b[0-9a-fA-F]{32,}\b', "[REDACTED:HEX_SECRET]"),
    # Email addresses — suppress if they look like SA emails embedded in payloads
    (r'[a-z0-9\-]+@[a-z0-9\-]+\.iam\.gserviceaccount\.com', "[REDACTED:SA_EMAIL]"),
    # Password fields in JSON-like text
    (r'(?i)"?(password|passwd|secret|credential|token)"?\s*[:=]\s*"?[^\s",]{6,}"?',
     r'"\1": "[REDACTED]"'),
]

_COMPILED: list[tuple[re.Pattern[str], str]] = [
    (re.compile(p), repl) for p, repl in _PATTERNS
]


def redact(text: str) -> str:
    """Apply all redaction patterns to *text* and return the cleaned string."""
    for pattern, replacement in _COMPILED:
        text = pattern.sub(replacement, text)
    return text


def redact_dict(obj: Any) -> Any:
    """Recursively redact string values inside a nested dict / list structure."""
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, dict):
        return {k: redact_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_dict(item) for item in obj]
    return obj
