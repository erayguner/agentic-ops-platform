"""aop_decommission.report — the final, audit-grade decommission report.

Assembles the end report from the plan, the execution result, and the
post-decommission validation, then renders it to Markdown suitable for a
governance review. Every dynamic value is passed through :func:`redact_text`
first, so a resource name, label, or error string that happens to contain a
credential, key, or personal email never lands in the report or the logs.

The report answers the closing question directly: **is this project safe to
close?** — backed by the deleted / retained / skipped / failed / manual-review
breakdown, the cost impact, the remaining risks, and the validation evidence.
"""

from __future__ import annotations

import logging
import re

from aop_decommission.schemas import (
    DecommissionPlan,
    DecommissionReport,
    ExecutionResult,
    ValidationResult,
)

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Redaction — never leak secrets / PII into an audit artefact
# --------------------------------------------------------------------------- #

_REDACTED = "«redacted»"

# key: value / key=value where the key names a secret.
_SECRET_KV = re.compile(
    r"(?i)\b(secret|token|password|passwd|api[_-]?key|access[_-]?key|"
    r"credential|private[_-]?key|client[_-]?secret|auth)\b\s*[=:]\s*\S+"
)
# Google API keys, PEM private-key blocks, long opaque hex/base64 blobs.
_GOOGLE_API_KEY = re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}\b")
_PEM_BLOCK = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S
)
_LONG_BLOB = re.compile(r"\b[0-9a-fA-F]{40,}\b")
_BEARER = re.compile(r"(?i)\bbearer\s+[a-z0-9._\-]+")
# Email local-part masking (keep the domain for routing/accountability).
_EMAIL = re.compile(r"\b([A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]*(@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b")


def redact_text(value: str) -> str:
    """Mask secrets and personal data in a free string before it is reported."""
    if not value:
        return value
    out = _PEM_BLOCK.sub(_REDACTED, value)
    out = _SECRET_KV.sub(_REDACTED, out)
    out = _GOOGLE_API_KEY.sub(_REDACTED, out)
    out = _BEARER.sub(_REDACTED, out)
    out = _LONG_BLOB.sub(_REDACTED, out)
    out = _EMAIL.sub(lambda m: f"{m.group(1)}***{m.group(2)}", out)
    return out


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #


def build_report(
    *,
    plan: DecommissionPlan,
    initial_count: int,
    mode: str = "plan",
    execution: ExecutionResult | None = None,
    validation: ValidationResult | None = None,
) -> DecommissionReport:
    """Fold the plan + execution + validation into a single report object."""
    retained = [item.exemption for item in plan.items if item.exemption is not None]
    manual = sorted(i.resource.resource_id for i in plan.items if i.disposition == "manual_review")

    deleted: list[str] = []
    failed: list[str] = []
    failure_details: dict[str, str] = {}
    skipped: list[str] = []
    pending: list[str] = []
    if execution is not None:
        for record in execution.records:
            if record.status in ("executed", "already_done"):
                deleted.append(record.resource_id)
            elif record.status in ("failed", "denied"):
                failed.append(record.resource_id)
                failure_details[record.resource_id] = redact_text(
                    record.error or record.detail or record.broker_status or "unknown failure"
                )
            elif record.status == "pending_approval":
                pending.append(record.resource_id)
            elif record.status == "skipped" and record.action_class:
                skipped.append(record.resource_id)
    skipped.extend(i.resource.resource_id for i in plan.items if i.disposition == "skip")

    risks = list(plan.risks)
    if execution is not None and execution.halted:
        risks.append(f"Execution halted: {execution.halt_reason}")
    if pending:
        risks.append(f"{len(pending)} action(s) awaiting human approval before teardown completes")
    if failed:
        risks.append(f"{len(failed)} action(s) failed or were denied — see remediation")
    if validation is not None:
        risks.extend(f"Residual: {r.reason} {r.resource_id}" for r in validation.residual)
        risks.extend(f"Preservation gap: {rid}" for rid in validation.preservation_gaps)

    savings = (
        round(sum(_cost_of(execution, plan, rid) for rid in deleted), 2)
        if execution is not None
        else plan.estimated_monthly_savings
    )

    closure_ready = bool(
        validation is not None and validation.closure_ready and not failed and not pending
    )

    return DecommissionReport(
        correlation_id=plan.correlation_id,
        project=plan.project,
        environment=plan.environment,
        mode=mode,  # type: ignore[arg-type]
        initial_count=initial_count,
        deleted=sorted(set(deleted)),
        retained_exempt=retained,
        skipped=sorted(set(skipped)),
        failed=sorted(set(failed)),
        failure_details=failure_details,
        manual_review=manual,
        pending_approval=sorted(set(pending)),
        remaining_risks=risks,
        estimated_monthly_savings=savings,
        validation=validation,
        closure_ready=closure_ready,
    )


def _cost_of(execution: ExecutionResult, plan: DecommissionPlan, resource_id: str) -> float:
    for item in plan.items:
        if item.resource.resource_id == resource_id:
            return item.resource.monthly_cost
    return 0.0


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #


def render_markdown(report: DecommissionReport, *, plan: DecommissionPlan | None = None) -> str:
    """Render the report as a governance-ready Markdown document (redacted)."""
    verdict = "✅ READY TO CLOSE" if report.closure_ready else "⛔ NOT READY TO CLOSE"
    lines: list[str] = [
        f"# Decommission Report — {redact_text(report.project)}",
        "",
        f"- **Correlation id:** `{report.correlation_id}`",
        f"- **Environment:** {report.environment}",
        f"- **Mode:** {report.mode}",
        f"- **Generated:** {report.generated_at}",
        f"- **Closure readiness:** {verdict}",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| Initial inventory | {report.initial_count} |",
        f"| Deleted | {len(report.deleted)} |",
        f"| Retained (exempt) | {len(report.retained_exempt)} |",
        f"| Skipped | {len(report.skipped)} |",
        f"| Manual review | {len(report.manual_review)} |",
        f"| Pending approval | {len(report.pending_approval)} |",
        f"| Failed | {len(report.failed)} |",
        f"| Est. monthly saving | {report.currency} {report.estimated_monthly_savings:.2f} |",
        "",
    ]

    if plan is not None:
        lines += ["## Planned teardown order", ""]
        if plan.stages:
            for stage in plan.stages:
                ids = ", ".join(f"`{redact_text(r)}`" for r in stage.resource_ids)
                lines.append(f"- **Stage {stage.index}:** {ids}")
        else:
            lines.append("- _No resources targeted for deletion._")
        lines.append("")

    lines += _section("Resources deleted", [f"`{redact_text(r)}`" for r in report.deleted])
    lines += _section(
        "Resources retained under exemption",
        [
            f"`{redact_text(m.resource_id)}` — {redact_text(m.reason)} "
            f"(rule `{m.rule_id}`, matched: {', '.join(m.matched_on)})"
            for m in report.retained_exempt
        ],
    )
    lines += _section("Resources skipped", [f"`{redact_text(r)}`" for r in report.skipped])
    lines += _section(
        "Failed / denied — remediation required",
        _remediation_lines(report, plan),
    )
    lines += _section(
        "Flagged for manual review", [f"`{redact_text(r)}`" for r in report.manual_review]
    )
    lines += _section(
        "Awaiting human approval", [f"`{redact_text(r)}`" for r in report.pending_approval]
    )
    lines += _section("Remaining risks", [redact_text(r) for r in report.remaining_risks])

    lines += ["## Cost impact", ""]
    lines.append(
        f"Estimated monthly saving from completed deletions: "
        f"**{report.currency} {report.estimated_monthly_savings:.2f}**."
    )
    lines.append("")

    lines += ["## Post-decommission validation", ""]
    if report.validation is None:
        lines.append("_No execution performed (plan-only run); re-scan not applicable._")
    else:
        v = report.validation
        lines += [
            f"- **Validated at:** {v.validated_at}",
            f"- **Residual findings:** {len(v.residual)}",
            f"- **Unexpected survivors:** {len(v.unexpected_retained)}",
            f"- **Preservation gaps:** {len(v.preservation_gaps)}",
            f"- **Retained set matches exemptions:** {'yes' if v.retained_ok else 'NO'}",
            f"- **Required artefacts preserved:** {'yes' if v.preserved_ok else 'NO'}",
            f"- **Verdict:** {redact_text(v.summary)}",
        ]
        for finding in v.residual:
            lines.append(
                f"  - `{redact_text(finding.resource_id)}` — {finding.reason} "
                f"({finding.severity}): {redact_text(finding.detail or '')}"
            )
    lines.append("")

    lines += [
        "## Closure readiness",
        "",
        f"**{verdict}** — "
        + (
            "all non-exempt resources removed, retained set matches the approved exemptions, "
            "and required artefacts are preserved."
            if report.closure_ready
            else "outstanding items above must be resolved before the project can be closed."
        ),
        "",
    ]
    return "\n".join(lines)


def _section(title: str, items: list[str]) -> list[str]:
    out = [f"## {title}", ""]
    if not items:
        out.append("- _None._")
    else:
        out.extend(f"- {item}" for item in items)
    out.append("")
    return out


def _remediation_lines(report: DecommissionReport, plan: DecommissionPlan | None) -> list[str]:
    if not report.failed:
        return []
    item_by_id = {i.resource.resource_id: i for i in plan.items} if plan else {}
    lines: list[str] = []
    for rid in report.failed:
        item = item_by_id.get(rid)
        hint = "retry after resolving the dependency/permission/lock, or tear down manually"
        if item is not None and item.resource.security_sensitive:
            hint = "security-sensitive — confirm intent, then retry or remove manually"
        detail = report.failure_details.get(rid)
        cause = f"{redact_text(detail)}; " if detail else ""
        lines.append(f"`{redact_text(rid)}` — {cause}{hint}")
    return lines
