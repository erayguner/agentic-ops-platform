"""Tests for aop_common.memory_store — the GA memory fallback and its composition
with the Phase-7 safeguard policy.

All offline: InMemoryStore needs no cloud, and FirestoreMemoryStore builds its
client lazily so it constructs without credentials.
"""

from __future__ import annotations

from aop_common.memory import MemoryScope
from aop_common.memory_store import (
    FirestoreMemoryStore,
    GuardedMemory,
    InMemoryStore,
    MemoryStore,
)


def _scope(*, session: str = "s1", tenant: str = "t1") -> MemoryScope:
    return MemoryScope(
        tenant_id=tenant,
        agent_identity="sa-finops@p.iam.gserviceaccount.com",
        session_id=session,
        environment="dev",
    )


class TestGuardedMemory:
    def test_store_then_recall_spotlights_untrusted(self) -> None:
        mem = GuardedMemory(InMemoryStore())
        mem.store(record_id="r1", scope=_scope(), source="tool", content="spend up 40%")

        out = mem.recall(_scope())

        assert len(out) == 1
        assert "spend up 40%" in out[0]
        # A 'tool'-sourced record is untrusted → fenced for safe prompt insertion.
        assert "AOP_UNTRUSTED_MEMORY" in out[0]

    def test_cross_tenant_recall_is_isolated(self) -> None:
        mem = GuardedMemory(InMemoryStore())
        mem.store(record_id="r1", scope=_scope(tenant="t1"), source="agent", content="secret")

        assert mem.recall(_scope(tenant="t2")) == []


def test_inmemory_store_satisfies_protocol() -> None:
    assert isinstance(InMemoryStore(), MemoryStore)


def test_firestore_store_constructs_offline() -> None:
    # Lazy client: constructing the GA store must not need credentials.
    store = FirestoreMemoryStore(project="proj")
    assert isinstance(store, MemoryStore)


def test_ga_only_is_the_default_profile() -> None:
    from aop_common.config import AopSettings

    settings = AopSettings(
        project="proj",
        agent_identity="sa@proj.iam.gserviceaccount.com",
        action_broker_mcp_endpoint="https://broker.example/mcp",
        org_context_mcp_endpoint="https://orgctx.example/mcp",
    )
    assert settings.deployment_profile == "ga-only"
