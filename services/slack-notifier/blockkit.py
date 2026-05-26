"""
Block Kit renderer for OpsNotification v1.

Produces a ``chat.postMessage`` payload (``blocks`` + ``text`` fallback)
matching the layout sketched in DESIGN-REVIEW §6.6. The canonical channel
routing table lives below in `_DOMAIN_CHANNEL`.

Channel routing — (domain, severity) → Slack channel:
  Critical/High operational (sre/platform/orchestrator) → #ops-incidents
  devsecops (any severity)                              → #ops-security
  finops (any severity)                                 → #ops-finops
  platform drift/low                                    → #ops-platform
  eval-related                                          → #ops-eval
  Tier-2 after-the-fact audit                           → #ops-audit
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from schemas import OpsNotification, RecommendedAction

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Severity decorations
# ---------------------------------------------------------------------------

_SEVERITY_EMOJI: dict[str, str] = {
    "critical": ":red_circle:",
    "high": ":large_orange_circle:",
    "medium": ":large_yellow_circle:",
    "low": ":large_green_circle:",
    "info": ":white_circle:",
}

_SEVERITY_LABEL: dict[str, str] = {
    "critical": "CRITICAL",
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
    "info": "INFO",
}

# ---------------------------------------------------------------------------
# Channel routing — domain-level dispatch; platform escalates critical/high to incidents.
# ---------------------------------------------------------------------------

_DOMAIN_CHANNEL: dict[str, str] = {
    "devsecops": "#ops-security",
    "finops": "#ops-finops",
    "platform": "#ops-platform",  # overridden for critical/high below
    "sre": "#ops-incidents",
    "orchestrator": "#ops-incidents",
}
_HIGH_SEVERITY = {"critical", "high"}


def resolve_channel(notification: OpsNotification) -> str:
    """Return the canonical Slack channel for this notification."""
    ch = _DOMAIN_CHANNEL.get(notification.domain, "#ops-incidents")
    if notification.domain == "platform" and notification.severity in _HIGH_SEVERITY:
        ch = "#ops-incidents"
    return ch


# ---------------------------------------------------------------------------
# Approval-window countdown
# ---------------------------------------------------------------------------


def _countdown_text(until: datetime | None) -> str:
    if until is None:
        return ""
    now = datetime.now(tz=UTC)
    delta = until - now
    total_secs = max(0, int(delta.total_seconds()))
    mins, secs = divmod(total_secs, 60)
    if total_secs == 0:
        return "Approval window *expired*."
    return f"Approval window expires in *{mins}m {secs:02d}s*."


# ---------------------------------------------------------------------------
# Action button builder
# ---------------------------------------------------------------------------


def _action_elements(actions: list[RecommendedAction]) -> list[dict]:
    """
    Build Block Kit button elements for the first two Tier-3+ actions.
    Tier-0/1/2 actions get a plain button with no ``confirm`` dialog.
    """
    elements: list[dict] = []
    for action in actions[:2]:
        if action.tier >= 3:
            elements.append(
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": f"Approve: {action.label[:30]}"},
                    "style": "primary",
                    "action_id": f"approve_{action.id}",
                    "value": action.id,
                    "confirm": {
                        "title": {"type": "plain_text", "text": "Confirm approval"},
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"*{action.label}*\n"
                                f"Tier {action.tier} · "
                                f"{'Reversible' if action.reversible else 'Irreversible'} · "
                                f"~{action.estimated_duration_s or '?'}s"
                            ),
                        },
                        "confirm": {"type": "plain_text", "text": "Approve"},
                        "deny": {"type": "plain_text", "text": "Cancel"},
                    },
                }
            )
            elements.append(
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Reject"},
                    "style": "danger",
                    "action_id": f"reject_{action.id}",
                    "value": action.id,
                }
            )
        else:
            elements.append(
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": action.label[:40]},
                    "action_id": f"info_{action.id}",
                    "value": action.id,
                }
            )
    return elements


# ---------------------------------------------------------------------------
# Reference footer
# ---------------------------------------------------------------------------


def _reference_elements(refs) -> list[str]:
    parts: list[str] = []
    if refs.logs:
        parts.append(f"<{refs.logs}|:scroll: Logs>")
    if refs.dashboard:
        parts.append(f"<{refs.dashboard}|:chart_with_upwards_trend: Dashboard>")
    if refs.trace:
        parts.append(f"<{refs.trace}|:mag: Trace>")
    if refs.runbook:
        parts.append(f"<{refs.runbook}|:book: Runbook>")
    if refs.scc:
        parts.append(f"<{refs.scc}|:shield: SCC>")
    if refs.ticket:
        label = refs.ticket.split("/")[-1] if refs.ticket else "Ticket"
        parts.append(f"<{refs.ticket}|:ticket: {label}>")
    if refs.workflow:
        parts.append(f"<{refs.workflow}|:gear: Workflow>")
    return parts


# ---------------------------------------------------------------------------
# Main renderer
# ---------------------------------------------------------------------------


def render_block_kit(notification: OpsNotification) -> dict:
    """
    Render an OpsNotification into a Slack ``chat.postMessage`` payload.

    Returns a dict with keys: ``channel``, ``text`` (fallback), ``blocks``.
    """
    sev = notification.severity
    badge = (
        f"{_SEVERITY_EMOJI.get(sev, ':white_circle:')} *{_SEVERITY_LABEL.get(sev, sev.upper())}*"
    )
    comp = notification.affected_component
    component_line = f"*{comp.name}*" + (f" · {comp.region}" if comp.region else "")

    blocks: list[dict] = [
        # ── Header ──────────────────────────────────────────────────────────
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{_SEVERITY_LABEL.get(sev, sev.upper())} · {notification.domain.upper()} · {notification.environment}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{badge} · {notification.domain.upper()} · {notification.environment}\n{component_line}",
            },
            "accessory": {
                "type": "overflow",
                "action_id": "notification_overflow",
                "options": [
                    {
                        "text": {"type": "plain_text", "text": "Copy notification ID"},
                        "value": notification.notification_id,
                    },
                    {
                        "text": {"type": "plain_text", "text": "Copy correlation ID"},
                        "value": notification.correlation_id,
                    },
                ],
            },
        },
        {"type": "divider"},
        # ── Summary ─────────────────────────────────────────────────────────
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": notification.summary},
        },
        # ── Impact / Cause ───────────────────────────────────────────────────
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Impact*\n{notification.impact}"},
                *(
                    [{"type": "mrkdwn", "text": f"*Likely cause*\n{notification.likely_cause}"}]
                    if notification.likely_cause
                    else []
                ),
            ],
        },
        {"type": "divider"},
    ]

    # ── Recommended actions ──────────────────────────────────────────────────
    if notification.recommended_actions:
        first = notification.recommended_actions[0]
        action_text = (
            f"*Recommended next step*\n"
            f"{first.label} "
            f"(Tier {first.tier} · ~{first.estimated_duration_s or '?'}s · "
            f"{'reversible' if first.reversible else 'irreversible'})"
        )
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": action_text}})

        elements = _action_elements(notification.recommended_actions)
        if elements:
            blocks.append({"type": "actions", "elements": elements})

    # ── Approval countdown ───────────────────────────────────────────────────
    countdown = _countdown_text(notification.approval_window_until)
    if countdown:
        blocks.append(
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": countdown}],
            }
        )

    blocks.append({"type": "divider"})

    # ── Reference footer ────────────────────────────────────────────────────
    ref_parts = _reference_elements(notification.references)
    if ref_parts:
        blocks.append(
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": "  ·  ".join(ref_parts)}],
            }
        )

    # ── Agent meta footer ─────────────────────────────────────────────────
    token_info = ""
    if notification.agent.tokens:
        t = notification.agent.tokens
        token_info = f" · tokens in/out: {t.get('in', '?')}/{t.get('out', '?')}"
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        f"Agent: `{notification.agent.identity}` · model: `{notification.agent.model}`"
                        f"{token_info}"
                        + (
                            f" · trace: `{notification.agent.trace_id}`"
                            if notification.agent.trace_id
                            else ""
                        )
                    ),
                }
            ],
        }
    )

    return {
        "channel": resolve_channel(notification),
        "text": f"[{sev.upper()}] {notification.summary}",  # fallback / notification preview
        "blocks": blocks,
    }
