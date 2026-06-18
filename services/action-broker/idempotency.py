"""
Firestore-backed idempotency store.

Key: sha256(correlation_id + action_class + target_hash)
Check before execution; record completion with outcome.

LIVE_MODE=False: all operations are no-ops (log only).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

LIVE_MODE = os.environ.get("LIVE_MODE", "false").lower() == "true"
_COLLECTION = "aop_idempotency_keys"


def _make_key(correlation_id: str, action_class: str, target: dict[str, Any]) -> str:
    target_hash = hashlib.sha256(json.dumps(target, sort_keys=True).encode()).hexdigest()[:16]
    raw = f"{correlation_id}:{action_class}:{target_hash}"
    return hashlib.sha256(raw.encode()).hexdigest()


class IdempotencyStore:
    def __init__(self, firestore_client) -> None:
        self._client = firestore_client

    def check(
        self,
        correlation_id: str,
        action_class: str,
        target: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Return the previously recorded outcome if this action was already
        executed, or None if it has not.
        """
        key = _make_key(correlation_id, action_class, target)

        if not LIVE_MODE or self._client is None:
            logger.info("[DRY-RUN] Idempotency check key=%s (no Firestore)", key)
            return None

        doc = self._client.collection(_COLLECTION).document(key).get()
        if doc.exists:
            logger.info("Idempotency hit key=%s", key)
            return doc.to_dict()
        return None

    def record(
        self,
        correlation_id: str,
        action_class: str,
        target: dict[str, Any],
        outcome: dict[str, Any],
    ) -> None:
        """Record a completed execution so future duplicates are short-circuited."""
        key = _make_key(correlation_id, action_class, target)
        record = {
            "correlation_id": correlation_id,
            "action_class": action_class,
            "target": target,
            "outcome": outcome,
            "recorded_at": datetime.now(tz=UTC).isoformat(),
        }

        if not LIVE_MODE or self._client is None:
            logger.info("[DRY-RUN] Idempotency record key=%s outcome=%s", key, outcome)
            return

        self._client.collection(_COLLECTION).document(key).set(record)
        logger.info("Idempotency recorded key=%s", key)
