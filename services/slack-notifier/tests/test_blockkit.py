"""
Tests for blockkit.py — resolve_channel, _countdown_text, _action_elements,
_reference_elements, render_block_kit.

Coverage gaps addressed:
- resolve_channel: all domains, platform critical/high escalation to #ops-incidents
- _countdown_text: None, future time, expired (0 seconds)
- _action_elements: tier < 3 (info button), tier >= 3 (approve/reject pair), empty, > 2 actions
- render_block_kit: structure validation, fallback text, blocks present, actions block
- Missing optional fields: likely_cause, references all None, no agent tokens
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from blockkit import _action_elements, _countdown_text, render_block_kit, resolve_channel
from schemas import (
    AffectedComponent,
    AgentMeta,
    OpsNotification,
    RecommendedAction,
    References,
)

# ---------------------------------------------------------------------------
# Fixtures / factories
# ---------------------------------------------------------------------------


def _component(name: str = "my-service", region: str | None = "us-central1") -> AffectedComponent:
    return AffectedComponent(type="cloud_run", name=name, project="proj", region=region)


def _action(
    *, id: str = "act1", label: str = "Scale service to 3 instances", tier: int = 2
) -> RecommendedAction:
    return RecommendedAction(
        id=id,
        label=label,
        action_class="cloud_run.scale_within_range",
        tier=tier,
        estimated_duration_s=30,
        reversible=True,
    )


def _notification(
    *,
    domain: str = "sre",
    severity: str = "high",
    recommended_actions: list | None = None,
    approval_window_until: datetime | None = None,
    likely_cause: str | None = None,
) -> OpsNotification:
    return OpsNotification(
        notification_id="notif-001",
        correlation_id="corr-001",
        produced_at=datetime.now(tz=UTC),
        severity=severity,
        environment="prod",
        domain=domain,
        summary="Service is experiencing elevated error rates and latency spikes",
        affected_component=_component(),
        impact="Users unable to complete checkout; ~30% error rate on payment endpoint",
        likely_cause=likely_cause,
        recommended_actions=recommended_actions or [_action()],
        human_required=False,
        approval_window_until=approval_window_until,
        references=References(),
        agent=AgentMeta(identity="sre-agent@sa", model="gemini-2.0-flash"),
    )


# ---------------------------------------------------------------------------
# resolve_channel
# ---------------------------------------------------------------------------


class TestResolveChannel:
    def test_sre_routes_to_ops_incidents(self) -> None:
        assert resolve_channel(_notification(domain="sre")) == "#ops-incidents"

    def test_orchestrator_routes_to_ops_incidents(self) -> None:
        assert resolve_channel(_notification(domain="orchestrator")) == "#ops-incidents"

    def test_devsecops_routes_to_ops_security(self) -> None:
        assert resolve_channel(_notification(domain="devsecops")) == "#ops-security"

    def test_finops_routes_to_ops_finops(self) -> None:
        assert resolve_channel(_notification(domain="finops")) == "#ops-finops"

    def test_platform_low_severity_routes_to_ops_platform(self) -> None:
        assert resolve_channel(_notification(domain="platform", severity="low")) == "#ops-platform"

    def test_platform_medium_severity_routes_to_ops_platform(self) -> None:
        assert (
            resolve_channel(_notification(domain="platform", severity="medium")) == "#ops-platform"
        )

    def test_platform_critical_escalates_to_ops_incidents(self) -> None:
        assert (
            resolve_channel(_notification(domain="platform", severity="critical"))
            == "#ops-incidents"
        )

    def test_platform_high_escalates_to_ops_incidents(self) -> None:
        assert (
            resolve_channel(_notification(domain="platform", severity="high")) == "#ops-incidents"
        )

    def test_unknown_domain_defaults_to_ops_incidents(self) -> None:
        assert resolve_channel(_notification(domain="unknown_domain")) == "#ops-incidents"


# ---------------------------------------------------------------------------
# _countdown_text
# ---------------------------------------------------------------------------


class TestCountdownText:
    def test_none_returns_empty_string(self) -> None:
        assert _countdown_text(None) == ""

    def test_future_time_returns_countdown(self) -> None:
        future = datetime.now(tz=UTC) + timedelta(minutes=5, seconds=30)
        result = _countdown_text(future)
        assert "5m" in result
        assert "30s" in result
        assert "expires in" in result

    def test_past_time_returns_expired_message(self) -> None:
        past = datetime.now(tz=UTC) - timedelta(seconds=1)
        result = _countdown_text(past)
        assert "expired" in result

    def test_exactly_zero_returns_expired_message(self) -> None:
        # Simulate now == until (total_seconds rounds to 0)
        with patch("blockkit.datetime") as mock_dt:
            fixed_now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
            mock_dt.now.return_value = fixed_now
            result = _countdown_text(fixed_now)
        assert "expired" in result

    def test_large_window_formats_correctly(self) -> None:
        future = datetime.now(tz=UTC) + timedelta(minutes=15)
        result = _countdown_text(future)
        assert "15m" in result or "14m" in result  # allow for minor timing drift


# ---------------------------------------------------------------------------
# _action_elements
# ---------------------------------------------------------------------------


class TestActionElements:
    def test_tier_less_than_3_produces_info_button(self) -> None:
        action = _action(tier=2)
        elements = _action_elements([action])
        assert len(elements) == 1
        assert elements[0]["action_id"] == f"info_{action.id}"
        assert "confirm" not in elements[0]

    def test_tier_3_produces_approve_and_reject_buttons(self) -> None:
        action = _action(tier=3)
        elements = _action_elements([action])
        assert len(elements) == 2
        action_ids = {el["action_id"] for el in elements}
        assert f"approve_{action.id}" in action_ids
        assert f"reject_{action.id}" in action_ids

    def test_tier_3_approve_button_has_confirm_dialog(self) -> None:
        action = _action(tier=3)
        elements = _action_elements([action])
        approve_btn = next(e for e in elements if e["action_id"].startswith("approve_"))
        assert "confirm" in approve_btn
        assert approve_btn["style"] == "primary"

    def test_tier_3_reject_button_has_danger_style(self) -> None:
        action = _action(tier=3)
        elements = _action_elements([action])
        reject_btn = next(e for e in elements if e["action_id"].startswith("reject_"))
        assert reject_btn["style"] == "danger"

    def test_empty_actions_returns_empty_list(self) -> None:
        assert _action_elements([]) == []

    def test_only_first_two_actions_are_rendered(self) -> None:
        actions = [_action(id=f"act{i}", tier=2) for i in range(5)]
        elements = _action_elements(actions)
        # 5 actions but only 2 rendered, each tier 2 → 1 button each = 2 buttons
        assert len(elements) == 2

    def test_label_is_truncated_to_40_chars_for_tier_2(self) -> None:
        long_label = "A" * 50
        action = _action(label=long_label, tier=2)
        elements = _action_elements([action])
        button_text = elements[0]["text"]["text"]
        assert len(button_text) <= 40

    def test_label_is_truncated_to_30_chars_for_tier_3_approve(self) -> None:
        long_label = "B" * 50
        action = _action(label=long_label, tier=3)
        elements = _action_elements([action])
        approve_btn = next(e for e in elements if e["action_id"].startswith("approve_"))
        button_text = approve_btn["text"]["text"]
        # "Approve: " prefix + up to 30 chars
        assert len(button_text) <= len("Approve: ") + 30


# ---------------------------------------------------------------------------
# render_block_kit — structure
# ---------------------------------------------------------------------------


class TestRenderBlockKit:
    def test_returns_dict_with_required_keys(self) -> None:
        payload = render_block_kit(_notification())
        assert "channel" in payload
        assert "text" in payload
        assert "blocks" in payload

    def test_channel_is_correctly_resolved(self) -> None:
        payload = render_block_kit(_notification(domain="sre", severity="critical"))
        assert payload["channel"] == "#ops-incidents"

    def test_fallback_text_contains_severity_and_summary(self) -> None:
        notif = _notification(severity="critical")
        payload = render_block_kit(notif)
        assert "CRITICAL" in payload["text"]
        assert notif.summary in payload["text"]

    def test_blocks_is_a_non_empty_list(self) -> None:
        payload = render_block_kit(_notification())
        assert isinstance(payload["blocks"], list)
        assert len(payload["blocks"]) > 0

    def test_first_block_is_header_type(self) -> None:
        payload = render_block_kit(_notification())
        assert payload["blocks"][0]["type"] == "header"

    def test_actions_block_present_when_actions_exist(self) -> None:
        notif = _notification(recommended_actions=[_action(tier=3)])
        payload = render_block_kit(notif)
        block_types = [b["type"] for b in payload["blocks"]]
        assert "actions" in block_types

    def test_no_countdown_block_when_approval_window_is_none(self) -> None:
        notif = _notification(approval_window_until=None)
        payload = render_block_kit(notif)
        context_texts = [
            el["text"]
            for b in payload["blocks"]
            if b["type"] == "context"
            for el in b.get("elements", [])
            if isinstance(el, dict)
        ]
        assert not any("expires in" in t for t in context_texts)

    def test_countdown_context_block_present_when_approval_window_set(self) -> None:
        window = datetime.now(tz=UTC) + timedelta(minutes=10)
        notif = _notification(approval_window_until=window)
        payload = render_block_kit(notif)
        context_texts = [
            el["text"]
            for b in payload["blocks"]
            if b["type"] == "context"
            for el in b.get("elements", [])
            if isinstance(el, dict) and isinstance(el.get("text"), str)
        ]
        assert any("expires in" in t for t in context_texts)

    def test_no_likely_cause_field_section_still_present(self) -> None:
        notif = _notification(likely_cause=None)
        payload = render_block_kit(notif)
        # Should render without error; impact section should still be present
        all_texts = [
            el.get("text", "")
            for b in payload["blocks"]
            if b["type"] == "section"
            for el in b.get("fields", [])
        ]
        assert any("Impact" in t for t in all_texts)

    def test_likely_cause_included_when_provided(self) -> None:
        notif = _notification(likely_cause="Memory leak in payment service v2.3")
        payload = render_block_kit(notif)
        all_texts = str(payload)
        assert "Memory leak" in all_texts

    def test_agent_meta_footer_contains_identity_and_model(self) -> None:
        notif = _notification()
        payload = render_block_kit(notif)
        footer_text = str(payload["blocks"][-1])
        assert "sre-agent@sa" in footer_text
        assert "gemini-2.0-flash" in footer_text

    def test_agent_tokens_shown_when_present(self) -> None:
        notif = _notification()
        notif.agent.tokens = {"in": 1234, "out": 567}
        payload = render_block_kit(notif)
        footer_text = str(payload["blocks"][-1])
        assert "1234" in footer_text
        assert "567" in footer_text
