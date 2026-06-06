"""aop_common.memory — Phase 7 (Zero Trust for AI Agents) memory safeguards.

The Vertex AI Agent Engine **Memory Bank** is wired in Terraform
(`terraform/modules/agent-runtime/`) with a retention TTL, but the provider
does not enforce the app-layer controls the *Zero Trust for AI Agents* brief
calls out in Phase 7 ("Safeguard agent memory"). This module is the runtime
guard that sits in front of every memory ``store`` and ``recall``:

- **Memory isolation** — cross-session / cross-tenant retrieval is denied by
  construction (scope binding), not by convention.
- **Context-integrity validation** — every stored item is content-hashed; a
  recall whose content no longer matches its hash is treated as poisoned and
  dropped (or rejected), per "reject the suspect context and alert".
- **Retention** — TTL is enforced at *retrieval* time as well as at storage,
  so an expired memory can never re-enter a prompt.
- **Re-filtering retrieved memory as untrusted** — retrieved content is
  *spotlighted* (clearly delimited) and screened for injection markers before
  it is allowed back into a model context. Retrieved memory is treated with the
  same suspicion as raw user input — it is data, not instructions.

Pure-Python + Pydantic; no cloud imports at module load, so the safeguards are
unit-testable without infrastructure. Storage/recall transport (Memory Bank,
Firestore) calls these functions; this module owns the *policy*, not the I/O.

Maps to GOVERNANCE-MAPPING §19 "Memory and sessions" and ASI06.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

_CFG = ConfigDict(strict=True, populate_by_name=True)

# Sources whose content is never trusted as instructions by default. Anything an
# attacker can influence — user turns, tool output, RAG hits, peer-agent text —
# is untrusted; only the platform's own system/agent content is trusted.
_UNTRUSTED_SOURCES: frozenset[str] = frozenset({"user", "tool", "retrieved", "external"})

MemorySource = Literal["user", "tool", "agent", "retrieved", "system", "external"]
MemoryTrust = Literal["trusted", "untrusted"]

# Spotlighting delimiters. The brief notes spotlighting cuts indirect-injection
# success from >50% to <2% by clearly fencing untrusted content so the model
# treats it as data. The markers are deliberately unusual to resist forgery.
SPOTLIGHT_OPEN = "<<<AOP_UNTRUSTED_MEMORY source=%s>>>"
SPOTLIGHT_CLOSE = "<<<END_AOP_UNTRUSTED_MEMORY>>>"

# Curated injection markers. This is a screen (flag + log), not a content
# blocker — Model Armor PI&Jailbreak remains the primary filter; this catches
# instruction-shaped text that slips into stored memory.
_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ignore_previous",
        re.compile(r"ignore\s+(?:all\s+|the\s+)?previous\s+(?:instructions|prompts?)", re.I),
    ),
    (
        "disregard_prior",
        re.compile(
            r"disregard\s+(?:all\s+|the\s+)?(?:previous|above|prior)\s+(?:instructions|context)",
            re.I,
        ),
    ),
    ("role_override", re.compile(r"you\s+are\s+now\b", re.I)),
    ("system_prompt_ref", re.compile(r"system\s+prompt\b", re.I)),
    ("new_instructions", re.compile(r"\bnew\s+instructions?\b", re.I)),
    ("special_token", re.compile(r"<\|.*?\|>")),
    ("exfiltration", re.compile(r"\b(?:exfiltrat|leak)\w*\b", re.I)),
    (
        "guardrail_override",
        re.compile(r"override\s+(?:the\s+)?(?:policy|guardrail|safety|filter)", re.I),
    ),
    (
        "reveal_secrets",
        re.compile(
            r"reveal\s+(?:your\s+)?(?:system\s+prompt|instructions|secrets?|credentials?)", re.I
        ),
    ),
)


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #


class MemorySafeguardError(Exception):
    """Base class for all memory-safeguard violations."""


class MemoryIsolationError(MemorySafeguardError):
    """Raised when a recall would cross a session or tenant boundary."""


class MemoryIntegrityError(MemorySafeguardError):
    """Raised when a record's content no longer matches its content hash."""


class MemoryExpiredError(MemorySafeguardError):
    """Raised when an expired record is used on a path that forbids dropping."""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _now_rfc3339() -> str:
    return datetime.now(UTC).isoformat()


def compute_content_hash(source: str, content: str) -> str:
    """Return the canonical integrity hash for a memory item.

    The hash binds the content to its source so a tool output cannot be
    silently relabelled as a trusted system note without invalidating the hash.
    """
    digest = hashlib.sha256(f"{source}\x00{content}".encode())
    return f"sha256:{digest.hexdigest()}"


def _default_trust(source: str) -> MemoryTrust:
    return "untrusted" if source in _UNTRUSTED_SOURCES else "trusted"


# --------------------------------------------------------------------------- #
# Scope — the unit of isolation
# --------------------------------------------------------------------------- #


class MemoryScope(BaseModel):
    """The isolation boundary a memory item belongs to.

    Two scopes may exchange memory only if their ``tenant_id``,
    ``agent_identity`` and ``environment`` match. ``session_id`` additionally
    isolates per-session unless the caller explicitly opts into same-tenant,
    same-agent cross-session sharing.
    """

    model_config = _CFG

    tenant_id: str = Field(..., min_length=1, description="User or tenant the memory belongs to.")
    agent_identity: str = Field(
        ..., min_length=1, description="SPIFFE URI or SA email of the owning agent."
    )
    session_id: str = Field(..., min_length=1, description="Conversation/session id.")
    environment: Literal["dev", "prod"]

    def isolation_key(self, *, allow_cross_session: bool = False) -> tuple[str, ...]:
        """Return the tuple that two scopes must share to exchange memory."""
        base = (self.environment, self.tenant_id, self.agent_identity)
        return base if allow_cross_session else (*base, self.session_id)


# --------------------------------------------------------------------------- #
# Record
# --------------------------------------------------------------------------- #


class MemoryRecord(BaseModel):
    """A single stored memory item with its integrity and retention metadata.

    Construct via :func:`new_memory_record` so the content hash and timestamp
    are computed consistently. Direct construction is allowed (e.g. when
    re-hydrating from a store) but then the caller owns hash correctness.
    """

    model_config = _CFG

    record_id: str = Field(..., min_length=1)
    scope: MemoryScope
    source: MemorySource
    content: str
    content_hash: str = Field(..., description="Output of compute_content_hash(source, content).")
    created_at: str = Field(default_factory=_now_rfc3339)
    ttl_s: int = Field(0, ge=0, description="Lifetime in seconds; 0 means no expiry.")
    trust: MemoryTrust

    def verify_integrity(self) -> bool:
        """Return True iff the content still matches the stored hash."""
        return compute_content_hash(self.source, self.content) == self.content_hash

    def is_expired(self, now: datetime | None = None) -> bool:
        """Return True iff the record has outlived its TTL."""
        if self.ttl_s == 0:
            return False
        moment = now or datetime.now(UTC)
        created = datetime.fromisoformat(self.created_at)
        age_s = (moment - created).total_seconds()
        return age_s >= self.ttl_s


def new_memory_record(
    *,
    record_id: str,
    scope: MemoryScope,
    source: MemorySource,
    content: str,
    ttl_s: int = 0,
    trust: MemoryTrust | None = None,
) -> MemoryRecord:
    """Build a :class:`MemoryRecord`, computing its hash and default trust."""
    return MemoryRecord(
        record_id=record_id,
        scope=scope,
        source=source,
        content=content,
        content_hash=compute_content_hash(source, content),
        ttl_s=ttl_s,
        trust=trust or _default_trust(source),
    )


# --------------------------------------------------------------------------- #
# Isolation
# --------------------------------------------------------------------------- #


def assert_scope_access(
    stored: MemoryScope,
    requester: MemoryScope,
    *,
    allow_cross_session: bool = False,
) -> None:
    """Raise :class:`MemoryIsolationError` if ``requester`` may not read ``stored``.

    Cross-tenant and cross-agent reads are always denied. Cross-session reads
    are denied unless ``allow_cross_session`` is set (same tenant + agent only).
    """
    if stored.isolation_key(allow_cross_session=allow_cross_session) != requester.isolation_key(
        allow_cross_session=allow_cross_session
    ):
        raise MemoryIsolationError(
            "memory isolation violation: "
            f"stored=({stored.environment}/{stored.tenant_id}/{stored.agent_identity}/{stored.session_id}) "
            f"requester=({requester.environment}/{requester.tenant_id}/{requester.agent_identity}/{requester.session_id}) "
            f"allow_cross_session={allow_cross_session}"
        )


# --------------------------------------------------------------------------- #
# Re-filtering retrieved memory as untrusted input
# --------------------------------------------------------------------------- #


def screen_for_injection(content: str) -> list[str]:
    """Return the names of any injection markers found in ``content``.

    A non-empty list is a flag, not a hard block — it is logged and surfaced so
    behavioural monitoring can alert; the primary blocker is Model Armor.
    """
    return [name for name, pattern in _INJECTION_PATTERNS if pattern.search(content)]


def spotlight(content: str, *, source: str) -> str:
    """Fence ``content`` in untrusted-data delimiters for safe prompt insertion."""
    return f"{SPOTLIGHT_OPEN % source}\n{content}\n{SPOTLIGHT_CLOSE}"


def sanitize_retrieved(record: MemoryRecord, *, now: datetime | None = None) -> str:
    """Validate, expire-check and spotlight a single retrieved record.

    Returns the prompt-safe (spotlighted) string. Raises on integrity failure
    or expiry — callers on the recall path should prefer :func:`prepare_recall`,
    which drops rather than raises.
    """
    if not record.verify_integrity():
        raise MemoryIntegrityError(f"integrity check failed for record_id={record.record_id}")
    if record.is_expired(now):
        raise MemoryExpiredError(f"record_id={record.record_id} is past its TTL")
    flags = screen_for_injection(record.content)
    if flags:
        logger.warning(
            "memory.sanitize_retrieved: injection markers in record_id=%s flags=%s",
            record.record_id,
            ",".join(flags),
        )
    return spotlight(record.content, source=record.source)


def prepare_recall(
    records: list[MemoryRecord],
    requester: MemoryScope,
    *,
    now: datetime | None = None,
    allow_cross_session: bool = False,
) -> list[str]:
    """Turn a raw recall result into prompt-safe, isolated, fresh, fenced strings.

    The full Phase-7 recall guard: for each candidate record it enforces scope
    isolation, drops expired items, drops items that fail integrity (poisoned),
    spotlights survivors, and screens them for injection markers. Violations are
    logged and dropped rather than raised so one poisoned item cannot deny the
    whole recall — the safe default for a retrieval path.
    """
    safe: list[str] = []
    for record in records:
        try:
            assert_scope_access(record.scope, requester, allow_cross_session=allow_cross_session)
        except MemoryIsolationError as exc:
            logger.warning(
                "memory.prepare_recall: dropped record_id=%s — %s", record.record_id, exc
            )
            continue
        if record.is_expired(now):
            logger.info("memory.prepare_recall: dropped expired record_id=%s", record.record_id)
            continue
        if not record.verify_integrity():
            logger.warning(
                "memory.prepare_recall: dropped poisoned record_id=%s (integrity mismatch)",
                record.record_id,
            )
            continue
        flags = screen_for_injection(record.content)
        if flags:
            logger.warning(
                "memory.prepare_recall: injection markers in record_id=%s flags=%s",
                record.record_id,
                ",".join(flags),
            )
        safe.append(spotlight(record.content, source=record.source))
    return safe
