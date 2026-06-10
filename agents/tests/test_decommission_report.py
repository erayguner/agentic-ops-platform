"""Tests for aop_decommission.report — redaction, assembly, rendering."""

from __future__ import annotations

from collections.abc import Callable

from aop_decommission.exemptions import ExemptionPolicy
from aop_decommission.planner import Planner
from aop_decommission.report import build_report, redact_text, render_markdown
from aop_decommission.schemas import (
    DecommissionPlan,
    ExecutionRecord,
    ExecutionResult,
    ResourceRecord,
    ValidationResult,
)

_KW = {"correlation_id": "inc_test", "project": "proj", "environment": "dev"}


def _plan(
    resources: list[ResourceRecord], policy: ExemptionPolicy | None = None
) -> DecommissionPlan:
    return Planner().plan(resources, policy or ExemptionPolicy.empty(), **_KW)


# --------------------------------------------------------------------------- #
# Redaction
# --------------------------------------------------------------------------- #


class TestRedaction:
    def test_google_api_key(self) -> None:
        out = redact_text("key AIzaSyD1234567890abcdefghijABCDEFG used")
        assert "AIza" not in out

    def test_secret_key_value(self) -> None:
        assert "hunter2" not in redact_text("secret: hunter2")
        assert "swordfish" not in redact_text("password=swordfish")
        assert "tok123" not in redact_text("api_key = tok123")

    def test_pem_private_key(self) -> None:
        pem = "-----BEGIN PRIVATE KEY-----\nMIIBVwIBAD\n-----END PRIVATE KEY-----"
        assert "MIIBVwIBAD" not in redact_text(pem)

    def test_long_blob(self) -> None:
        assert "«redacted»" in redact_text("digest " + "a" * 48)

    def test_bearer_token(self) -> None:
        assert "abc.def-ghi" not in redact_text("Authorization: Bearer abc.def-ghi")

    def test_email_is_masked(self) -> None:
        out = redact_text("owner john.doe@example.com")
        assert "john.doe" not in out
        assert "@example.com" in out

    def test_plain_text_unchanged(self) -> None:
        text = "compute instance vm-1 in europe-west2"
        assert redact_text(text) == text


# --------------------------------------------------------------------------- #
# build_report
# --------------------------------------------------------------------------- #


class TestBuildReport:
    def test_plan_mode_lists_exemptions_not_deletions(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        policy = ExemptionPolicy.from_rules([{"id": "keep", "reason": "r", "name": "keep"}])
        plan = _plan(
            [
                make_resource("a", management="unmanaged"),
                make_resource("keep", management="terraform", name="keep"),
            ],
            policy,
        )
        report = build_report(plan=plan, initial_count=2, mode="plan")
        assert report.deleted == []
        assert len(report.retained_exempt) == 1
        assert report.closure_ready is False

    def test_execute_mode_buckets_outcomes(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        plan = _plan([make_resource("a", management="unmanaged")])
        execution = ExecutionResult(
            correlation_id="inc_test",
            dry_run=False,
            records=[
                ExecutionRecord(resource_id="a", status="executed"),
                ExecutionRecord(resource_id="b", status="failed", error="permission: nope"),
                ExecutionRecord(resource_id="c", status="pending_approval"),
            ],
        )
        validation = ValidationResult(correlation_id="inc_test", project="proj", closure_ready=True)
        report = build_report(
            plan=plan, initial_count=3, mode="execute", execution=execution, validation=validation
        )
        assert report.deleted == ["a"]
        assert report.failed == ["b"]
        assert report.pending_approval == ["c"]
        # Pending + failed work blocks closure even though validation passed.
        assert report.closure_ready is False

    def test_closure_ready_when_clean(self, make_resource: Callable[..., ResourceRecord]) -> None:
        plan = _plan([make_resource("a", management="unmanaged")])
        execution = ExecutionResult(
            correlation_id="inc_test",
            dry_run=False,
            records=[ExecutionRecord(resource_id="a", status="executed")],
        )
        validation = ValidationResult(correlation_id="inc_test", project="proj", closure_ready=True)
        report = build_report(
            plan=plan, initial_count=1, mode="execute", execution=execution, validation=validation
        )
        assert report.closure_ready is True


# --------------------------------------------------------------------------- #
# render_markdown
# --------------------------------------------------------------------------- #


class TestRender:
    def test_render_contains_core_sections(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        plan = _plan([make_resource("a", management="unmanaged")])
        report = build_report(plan=plan, initial_count=1, mode="plan")
        md = render_markdown(report, plan=plan)
        for heading in (
            "# Decommission Report",
            "## Summary",
            "## Closure readiness",
            "## Cost impact",
        ):
            assert heading in md

    def test_not_ready_verdict_when_not_closure_ready(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        plan = _plan([make_resource("a", management="unmanaged")])
        report = build_report(plan=plan, initial_count=1, mode="plan")
        assert "NOT READY TO CLOSE" in render_markdown(report, plan=plan)

    def test_render_redacts_sensitive_reason(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        policy = ExemptionPolicy.from_rules(
            [{"id": "keep", "reason": "owner contact admin@corp.example", "name": "keep"}]
        )
        plan = _plan([make_resource("keep", management="terraform", name="keep")], policy)
        report = build_report(plan=plan, initial_count=1, mode="plan")
        md = render_markdown(report, plan=plan)
        assert "admin@corp.example" not in md
        assert "@corp.example" in md
