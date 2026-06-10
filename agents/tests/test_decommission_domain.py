"""Lock-step test: the `decommission` domain is accepted by every shared schema.

Adding a specialist domain touches the domain Literal on Finding, OpsNotification,
AuditRecord and TriageDisposition. This guards that the edit stayed in lock-step
(and that an unknown domain is still rejected by the strict models).
"""

from __future__ import annotations

import pytest
from aop_common.schemas import (
    AffectedComponent,
    AuditRecord,
    Finding,
    ModelUsage,
    NotificationAgent,
    NotificationReferences,
    OpsNotification,
    TriageDisposition,
)
from pydantic import ValidationError


def test_finding_accepts_decommission_domain() -> None:
    finding = Finding(
        correlation_id="inc_1",
        agent_identity="sa-decommission@proj.iam.gserviceaccount.com",
        domain="decommission",
        summary="estate inventoried; 12 non-exempt resources planned for teardown",
        confidence=0.9,
        impact="project closure readiness",
        model=ModelUsage(id="gemini-3-pro"),
    )
    assert finding.domain == "decommission"


def test_ops_notification_accepts_decommission_domain() -> None:
    notification = OpsNotification(
        correlation_id="inc_1",
        severity="medium",
        environment="dev",
        domain="decommission",
        summary="decommission campaign requires approval for 3 destroys",
        affected_component=AffectedComponent(type="project", name="proj", project="proj"),
        impact="resources will be permanently destroyed",
        human_required=True,
        references=NotificationReferences(),
        agent=NotificationAgent(identity="sa-decommission", model="gemini-3-pro"),
    )
    assert notification.domain == "decommission"


def test_audit_record_accepts_decommission_domain() -> None:
    record = AuditRecord(
        correlation_id="inc_1",
        phase="recommendation",
        agent_identity="sa-decommission",
        environment="prod",
        domain="decommission",
    )
    assert record.domain == "decommission"


def test_triage_disposition_accepts_decommission_domain() -> None:
    disposition = TriageDisposition(
        signal_id="sig_1",
        correlation_id="inc_1",
        environment="dev",
        severity="low",
        detected_at="2026-06-10T12:00:00Z",
        dwell_seconds=1.0,
        disposition="investigate",
        routed_to_human=True,
        recommended_domain="decommission",
        confidence=0.8,
        rationale="closure request",
    )
    assert disposition.recommended_domain == "decommission"


def test_unknown_domain_still_rejected() -> None:
    with pytest.raises(ValidationError):
        Finding(
            correlation_id="inc_1",
            agent_identity="sa",
            domain="bogus",  # type: ignore[arg-type]
            summary="x",
            confidence=0.5,
            impact="y",
            model=ModelUsage(id="m"),
        )
