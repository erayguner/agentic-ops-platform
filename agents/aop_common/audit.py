"""aop_common.audit — emits AuditRecord events to ops.audit.

Every lifecycle phase (signal, finding, recommendation, action_requested,
action_approved, action_executed, rollback) must call AuditEmitter.record().
This is how the platform builds its immutable BigQuery audit stream.

Publishing is via google-cloud-pubsub. Publish call is stubbed in this
skeleton; the AuditRecord construction is fully functional.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from aop_common.schemas import AuditRecord, ModelUsage, PolicyDecision

logger = logging.getLogger(__name__)

# Exact topic name per INTERFACE-CONTRACT §3
_TOPIC_AUDIT = "ops.audit"


class AuditEmitter:
    """Emits AuditRecord events to the ops.audit Pub/Sub topic.

    Args:
        project: GCP project id hosting the Pub/Sub topic.
        agent_identity: SPIFFE URI or SA email of the emitting agent.
        environment: 'dev' or 'prod'.
        domain: Agent domain — sre, devsecops, platform, finops, orchestrator.
    """

    def __init__(
        self,
        project: str,
        agent_identity: str,
        environment: str,
        domain: str,
    ) -> None:
        self._project = project
        self._agent_identity = agent_identity
        self._environment = environment
        self._domain = domain
        self._topic_path = f"projects/{project}/topics/{_TOPIC_AUDIT}"
        self._publisher = self._build_publisher()

    def _build_publisher(self) -> object:
        try:
            from google.cloud import pubsub_v1  # type: ignore[import-untyped]

            return pubsub_v1.PublisherClient()
        except ImportError as exc:
            raise ImportError(
                "google-cloud-pubsub>=2.21 is required for AuditEmitter."
            ) from exc

    def record(
        self,
        *,
        correlation_id: str,
        phase: str,
        human_identity: str | None = None,
        action_class: str | None = None,
        policy_decision: PolicyDecision | None = None,
        evidence_refs: list[str] | None = None,
        model: ModelUsage | None = None,
        outcome: dict[str, Any] | None = None,
    ) -> AuditRecord:
        """Construct and publish an AuditRecord for a lifecycle phase transition.

        Args:
            correlation_id: Incident or signal correlation id.
            phase: One of: signal, finding, recommendation, action_requested,
                   action_approved, action_executed, rollback.
            human_identity: Email of the human approver, if present.
            action_class: Canonical action class string, if applicable.
            policy_decision: Policy engine decision, if applicable.
            evidence_refs: URIs of supporting evidence.
            model: Model usage stats for this phase.
            outcome: Freeform outcome dict.

        Returns:
            The constructed AuditRecord (for caller inspection / testing).

        Raises:
            NotImplementedError: Skeleton — real publish not wired.
        """
        record = AuditRecord(
            correlation_id=correlation_id,
            phase=phase,  # type: ignore[arg-type]
            agent_identity=self._agent_identity,
            human_identity=human_identity,
            environment=self._environment,  # type: ignore[arg-type]
            domain=self._domain,  # type: ignore[arg-type]
            action_class=action_class,
            policy_decision=policy_decision,
            evidence_refs=evidence_refs or [],
            model=model,
            outcome=outcome or {},
        )

        payload = record.model_dump(by_alias=True, mode="json")
        json.dumps(payload).encode("utf-8")

        logger.info(
            "AuditEmitter.record: audit_id=%s phase=%s correlation_id=%s",
            record.audit_id,
            phase,
            correlation_id,
        )

        # SKELETON: In production, call:
        #   future = self._publisher.publish(
        #       self._topic_path,
        #       data=data,
        #       ordering_key=correlation_id,
        #   )
        #   future.result()
        raise NotImplementedError(
            "AuditEmitter.record is a skeleton. "
            "Remove this guard and uncomment the publish call before connecting to Pub/Sub."
        )
