"""aop_common.triage — model-at-front-of-alert-queue + dwell/coverage metrics.

Phase 8 of the *Zero Trust for AI Agents* brief ("Measure what matters") says
to put a model at the front of the alert queue and to instrument two metrics
before anything else: **dwell time** (anomaly occurrence -> human awareness) and
**coverage** (the fraction of alerts that actually get investigated). These are
the metrics AI-assisted automation has the most leverage to move, and they
matter most as exploit windows shorten.

This module is the read-only triage pass. Every inbound :class:`OpsSignal` gets
an automated first-pass :class:`TriageDisposition` — auto-close, suppress a
duplicate, route for investigation, or escalate — *before* a human sees it. It
computes dwell time and emits a structured disposition that the
`aop_alert_dwell_seconds` and `aop_alert_triage_total` log-based metrics in
`terraform/modules/observability/main.tf` extract for the SLO/dashboard.

The classifier (the model reasoning) is injectable so the triage path is unit
testable; the default classifier is the ADK model call and is a skeleton until
the model is wired (matching `aop_common/models.py`). The dwell computation and
structured emission are fully functional.

The brief's guardrail is respected: **automate the bookkeeping, not the
decisions.** Triage may auto-close low-severity noise, but a disposition only
*routes*; containment/disclosure stay with humans via the existing Action
Broker approval gate.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from aop_common.schemas import ModelUsage, OpsSignal, TriageDisposition

logger = logging.getLogger(__name__)

Disposition = Literal["auto_close", "investigate", "escalate", "suppress_duplicate"]

# Dispositions that count as "routed for investigation" — the coverage numerator.
_ROUTED_DISPOSITIONS: frozenset[str] = frozenset({"investigate", "escalate"})


@dataclass(frozen=True)
class TriageVerdict:
    """The classifier's decision for a single signal, before dwell/coverage are stamped."""

    disposition: Disposition
    confidence: float
    rationale: str
    recommended_domain: Literal["sre", "devsecops", "platform", "finops", "decommission"] | None = (
        None
    )
    model: ModelUsage | None = None


# A classifier turns a signal into a verdict. Inject a stub in tests; the default
# is the model-backed classifier below.
Classifier = Callable[[OpsSignal], TriageVerdict]


def compute_dwell_seconds(detected_at: str, triaged_at: str | None = None) -> float:
    """Return seconds between anomaly occurrence and triage, never negative.

    Args:
        detected_at: RFC3339 timestamp of when the signal/anomaly occurred.
        triaged_at: RFC3339 timestamp of the triage pass; defaults to now.
    """
    triage_moment = datetime.fromisoformat(triaged_at) if triaged_at else datetime.now(UTC)
    detected = datetime.fromisoformat(detected_at)
    return max(0.0, (triage_moment - detected).total_seconds())


class TriageQueue:
    """Runs the first-pass triage on inbound signals.

    Args:
        classifier: Callable producing a :class:`TriageVerdict` from a signal.
            Defaults to the model-backed (skeleton) classifier.
    """

    def __init__(self, *, classifier: Classifier | None = None) -> None:
        self._classifier = classifier or self.classify_with_model

    def triage(self, signal: OpsSignal, *, now: datetime | None = None) -> TriageDisposition:
        """Produce a dwell-stamped, coverage-labelled disposition for one signal."""
        verdict = self._classifier(signal)
        triaged_at = (now or datetime.now(UTC)).isoformat()
        dwell_seconds = compute_dwell_seconds(signal.produced_at, triaged_at)
        return TriageDisposition(
            signal_id=signal.signal_id,
            correlation_id=signal.correlation_id,
            environment=signal.environment,
            severity=signal.severity,
            detected_at=signal.produced_at,
            triaged_at=triaged_at,
            dwell_seconds=dwell_seconds,
            disposition=verdict.disposition,
            routed_to_human=verdict.disposition in _ROUTED_DISPOSITIONS,
            recommended_domain=verdict.recommended_domain,
            confidence=verdict.confidence,
            rationale=verdict.rationale,
            evidence_refs=[signal.source_ref],
            model=verdict.model,
        )

    def classify_with_model(self, signal: OpsSignal) -> TriageVerdict:
        """Model-backed classifier (skeleton).

        ADK 2.x model call — confirm against `aop_common/models.py:ModelFactory`.
        The prompt instructs the model to return a structured verdict (a
        constrained tool-call / structured output), never free text, and to
        default to ``escalate`` under uncertainty (fail-safe).

        Raises:
            NotImplementedError: Skeleton — wire ModelFactory before connecting.
        """
        raise NotImplementedError(
            "TriageQueue.classify_with_model is a skeleton. Wire ModelFactory "
            "(aop_common/models.py) and a structured-output contract, or inject "
            "a classifier, before connecting to the model API."
        )


def emit_triage_log(disposition: TriageDisposition) -> None:
    """Emit the structured triage line the dwell/coverage log-based metrics read.

    The google-cloud-logging structured handler maps ``extra['json_fields']`` to
    the log entry's ``jsonPayload``; the Terraform metrics extract
    ``jsonPayload.dwell_seconds`` and count by ``jsonPayload.disposition``.
    Under plain logging (tests/local) the fields are attached harmlessly.
    """
    payload = disposition.model_dump(by_alias=True, mode="json")
    logger.info(
        "triage.disposition signal_id=%s disposition=%s dwell_s=%.1f routed=%s",
        disposition.signal_id,
        disposition.disposition,
        disposition.dwell_seconds,
        disposition.routed_to_human,
        extra={"json_fields": payload},
    )
