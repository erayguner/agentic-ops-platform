"""aop_common.memory_store — pluggable memory transport behind the Phase-7 policy.

``aop_common.memory`` owns the SAFEGUARD POLICY (isolation, integrity,
spotlighting); this module owns the I/O TRANSPORT. Splitting them lets the
platform swap a Preview backend (Vertex AI Agent Engine Memory Bank) for a GA one
(Firestore) without touching the safeguards — the concrete "GA fallback" the
design review promises and the ``ga-only`` deployment profile selects.

- ``MemoryStore``        — the transport protocol (put / query raw records).
- ``InMemoryStore``      — dict-backed, for tests and local dev (no cloud, no creds).
- ``FirestoreMemoryStore`` — GA backend (google-cloud-firestore); lazy client.
- ``GuardedMemory``      — composes a MemoryStore with the memory.py policy so
  callers get isolation + integrity + spotlighting for free.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from aop_common.memory import (
    MemoryRecord,
    MemoryScope,
    MemorySource,
    MemoryTrust,
    new_memory_record,
    prepare_recall,
)


@runtime_checkable
class MemoryStore(Protocol):
    """Raw memory transport. Implementations do I/O only — no policy."""

    def put(self, record: MemoryRecord) -> None:
        """Persist a single record."""
        ...

    def query(self, scope: MemoryScope, *, allow_cross_session: bool = False) -> list[MemoryRecord]:
        """Return records sharing ``scope``'s isolation key (pre-policy)."""
        ...


class InMemoryStore:
    """Dict-backed :class:`MemoryStore` for tests and local dev (no cloud)."""

    def __init__(self) -> None:
        self._records: list[MemoryRecord] = []

    def put(self, record: MemoryRecord) -> None:
        self._records.append(record)

    def query(self, scope: MemoryScope, *, allow_cross_session: bool = False) -> list[MemoryRecord]:
        key = scope.isolation_key(allow_cross_session=allow_cross_session)
        return [
            r
            for r in self._records
            if r.scope.isolation_key(allow_cross_session=allow_cross_session) == key
        ]


class FirestoreMemoryStore:
    """GA :class:`MemoryStore` backed by Firestore — the Memory Bank GA fallback.

    The Firestore client is constructed lazily on first I/O, so this object can be
    built offline (no credentials). Records are stored as their pydantic dict and
    rehydrated on read; scope components are indexed for isolation-scoped queries.
    """

    def __init__(
        self, *, project: str, database: str = "(default)", collection: str = "aop_memory"
    ) -> None:
        self._project = project
        self._database = database
        self._collection = collection
        self._client: Any = None

    def _db(self) -> Any:
        if self._client is None:
            from google.cloud import firestore

            self._client = firestore.Client(project=self._project, database=self._database)
        return self._client

    def put(self, record: MemoryRecord) -> None:
        self._db().collection(self._collection).add(record.model_dump())

    def query(self, scope: MemoryScope, *, allow_cross_session: bool = False) -> list[MemoryRecord]:
        col = self._db().collection(self._collection)
        q = (
            col.where("scope.environment", "==", scope.environment)
            .where("scope.tenant_id", "==", scope.tenant_id)
            .where("scope.agent_identity", "==", scope.agent_identity)
        )
        if not allow_cross_session:
            q = q.where("scope.session_id", "==", scope.session_id)
        return [MemoryRecord(**doc.to_dict()) for doc in q.stream()]


class GuardedMemory:
    """A :class:`MemoryStore` wrapped in the ``aop_common.memory`` safeguard policy.

    ``store`` hashes + stamps via ``new_memory_record``; ``recall`` runs the full
    Phase-7 guard (isolation, expiry, integrity, spotlighting) via
    ``prepare_recall`` and returns prompt-safe strings.
    """

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def store(
        self,
        *,
        record_id: str,
        scope: MemoryScope,
        source: MemorySource,
        content: str,
        ttl_s: int = 0,
        trust: MemoryTrust | None = None,
    ) -> MemoryRecord:
        record = new_memory_record(
            record_id=record_id,
            scope=scope,
            source=source,
            content=content,
            ttl_s=ttl_s,
            trust=trust,
        )
        self._store.put(record)
        return record

    def recall(
        self, requester: MemoryScope, *, allow_cross_session: bool = False, now: Any = None
    ) -> list[str]:
        raw = self._store.query(requester, allow_cross_session=allow_cross_session)
        return prepare_recall(raw, requester, now=now, allow_cross_session=allow_cross_session)


def select_memory_store(settings: Any) -> MemoryStore:
    """Return the MemoryStore for the configured deployment profile.

    Both profiles currently bind the GA Firestore backend; when a Preview Memory
    Bank store is added, the ``preview`` profile will select it here while
    ``ga-only`` stays on Firestore.
    """
    return FirestoreMemoryStore(project=settings.project, database=settings.firestore_database)
