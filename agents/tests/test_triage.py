"""Tests for aop_common.triage — dwell-time computation and first-pass triage."""

from datetime import UTC, datetime, timedelta

import pytest
from aop_common.schemas import OpsSignal
from aop_common.triage import (
    TriageQueue,
    TriageVerdict,
    compute_dwell_seconds,
    emit_triage_log,
)


def _signal(*, produced_at: str | None = None, severity: str = "high") -> OpsSignal:
    kwargs: dict[str, object] = {
        "source": "monitoring",
        "source_ref": "monitoring://alert/123",
        "environment": "prod",
        "severity": severity,
    }
    if produced_at is not None:
        kwargs["produced_at"] = produced_at
    return OpsSignal(**kwargs)  # type: ignore[arg-type]


def _verdict(
    disposition: str,
    *,
    domain: str | None = None,
) -> TriageVerdict:
    return TriageVerdict(
        disposition=disposition,  # type: ignore[arg-type]
        confidence=0.9,
        rationale="test rationale",
        recommended_domain=domain,  # type: ignore[arg-type]
    )


# --------------------------------------------------------------------------- #
# compute_dwell_seconds
# --------------------------------------------------------------------------- #


class TestDwell:
    def test_positive_dwell(self) -> None:
        detected = datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC)
        triaged = detected + timedelta(seconds=90)
        assert compute_dwell_seconds(detected.isoformat(), triaged.isoformat()) == 90.0

    def test_floors_at_zero_when_triage_precedes_detection(self) -> None:
        detected = datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC)
        triaged = detected - timedelta(seconds=30)
        assert compute_dwell_seconds(detected.isoformat(), triaged.isoformat()) == 0.0

    def test_defaults_triaged_to_now(self) -> None:
        recent = (datetime.now(UTC) - timedelta(seconds=2)).isoformat()
        assert compute_dwell_seconds(recent) >= 0.0


# --------------------------------------------------------------------------- #
# TriageQueue.triage
# --------------------------------------------------------------------------- #


class TestTriage:
    def test_triage_stamps_dwell_and_routes(self) -> None:
        detected = datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC)
        signal = _signal(produced_at=detected.isoformat())
        queue = TriageQueue(classifier=lambda _s: _verdict("investigate", domain="sre"))

        disp = queue.triage(signal, now=detected + timedelta(seconds=45))

        assert disp.dwell_seconds == 45.0
        assert disp.routed_to_human is True
        assert disp.recommended_domain == "sre"
        assert disp.correlation_id == signal.correlation_id
        assert disp.severity == "high"
        assert disp.evidence_refs == [signal.source_ref]

    @pytest.mark.parametrize(
        ("disposition", "routed"),
        [
            ("investigate", True),
            ("escalate", True),
            ("auto_close", False),
            ("suppress_duplicate", False),
        ],
    )
    def test_routed_to_human_matches_disposition(self, disposition: str, routed: bool) -> None:
        queue = TriageQueue(classifier=lambda _s: _verdict(disposition))
        disp = queue.triage(_signal())
        assert disp.routed_to_human is routed

    def test_default_classifier_is_skeleton(self) -> None:
        with pytest.raises(NotImplementedError):
            TriageQueue().triage(_signal())


# --------------------------------------------------------------------------- #
# emit_triage_log
# --------------------------------------------------------------------------- #


class TestEmit:
    def test_emit_logs_structured_payload(self, caplog: pytest.LogCaptureFixture) -> None:
        queue = TriageQueue(classifier=lambda _s: _verdict("escalate"))
        disp = queue.triage(_signal())
        with caplog.at_level("INFO"):
            emit_triage_log(disp)
        assert any("triage.disposition" in r.message for r in caplog.records)
