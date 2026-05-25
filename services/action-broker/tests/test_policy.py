"""
Tests for policy.py — PolicyEngine and _check_bounds.

Coverage gaps addressed:
- PolicyEngine.load() with valid file, missing file, malformed YAML
- PolicyEngine.decide() for all paths: no rule, denied rule, bounds violation, approved
- _check_bounds() for each bound key (max_instances, min_instances, max_blast_radius)
- Edge cases: unknown environment, wildcard miss, exact match
"""
import textwrap
from pathlib import Path

import pytest

from policy import PolicyEngine, _check_bounds


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_YAML = textwrap.dedent("""\
    action_classes:
      - name: cloud_run.scale_within_range
        environments:
          - env: dev
            tier: 2
            allowed: true
            required_approvers: 0
            bounds:
              min_instances: 0
              max_instances: 20
          - env: prod
            tier: 3
            allowed: true
            required_approvers: 1
            bounds:
              min_instances: 1
              max_instances: 10
      - name: forbidden.action
        environments:
          - env: prod
            tier: 4
            allowed: false
            deny_reason: action_not_permitted_in_prod
            bounds: {}
""")


@pytest.fixture
def policy_file(tmp_path: Path) -> Path:
    p = tmp_path / "action_classes.yaml"
    p.write_text(VALID_YAML)
    return p


@pytest.fixture
def engine(policy_file: Path) -> PolicyEngine:
    return PolicyEngine.load(policy_file)


# ---------------------------------------------------------------------------
# PolicyEngine.load
# ---------------------------------------------------------------------------

class TestPolicyEngineLoad:
    def test_load_valid_file_populates_rules(self, policy_file: Path) -> None:
        eng = PolicyEngine.load(policy_file)
        # 3 environment entries across 2 action classes
        assert len(eng._rules) == 3

    def test_load_missing_file_returns_empty_deny_engine(self, tmp_path: Path) -> None:
        eng = PolicyEngine.load(tmp_path / "nonexistent.yaml")
        # Engine should still work, denying everything
        decision = eng.decide("any.action", "dev", {}, {})
        assert decision.allowed is False
        assert decision.deny_reason == "no_policy_rule_for_action_class_env"

    def test_load_malformed_yaml_returns_empty_deny_engine(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("this: is: not: valid: yaml: :")
        eng = PolicyEngine.load(bad)
        decision = eng.decide("any.action", "dev", {}, {})
        assert decision.allowed is False

    def test_load_empty_action_classes_list(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.yaml"
        p.write_text("action_classes: []\n")
        eng = PolicyEngine.load(p)
        assert len(eng._rules) == 0

    def test_load_uses_default_path_when_no_arg_given(self) -> None:
        # Ensure the real policy file is loadable (smoke test)
        eng = PolicyEngine.load()
        assert isinstance(eng, PolicyEngine)
        assert len(eng._rules) > 0


# ---------------------------------------------------------------------------
# PolicyEngine.decide — routing paths
# ---------------------------------------------------------------------------

class TestPolicyEngineDecide:
    def test_unknown_action_class_returns_default_deny(self, engine: PolicyEngine) -> None:
        decision = engine.decide("unknown.action", "dev", {}, {})
        assert decision.allowed is False
        assert decision.deny_reason == "no_policy_rule_for_action_class_env"
        assert decision.rule_matched == "default-deny"

    def test_known_action_class_unknown_environment_returns_default_deny(
        self, engine: PolicyEngine
    ) -> None:
        decision = engine.decide("cloud_run.scale_within_range", "staging", {}, {})
        assert decision.allowed is False
        assert decision.rule_matched == "default-deny"

    def test_explicitly_denied_rule_returns_deny_with_reason(
        self, engine: PolicyEngine
    ) -> None:
        decision = engine.decide("forbidden.action", "prod", {}, {})
        assert decision.allowed is False
        assert decision.deny_reason == "action_not_permitted_in_prod"
        assert decision.rule_matched == "forbidden.action:prod"

    def test_approved_rule_within_bounds_returns_allow(self, engine: PolicyEngine) -> None:
        decision = engine.decide(
            "cloud_run.scale_within_range", "dev", {}, {"instances": 5}
        )
        assert decision.allowed is True
        assert decision.tier == 2
        assert decision.required_approvers == 0

    def test_approved_rule_at_min_bound_returns_allow(self, engine: PolicyEngine) -> None:
        decision = engine.decide(
            "cloud_run.scale_within_range", "dev", {}, {"instances": 0}
        )
        assert decision.allowed is True

    def test_approved_rule_at_max_bound_returns_allow(self, engine: PolicyEngine) -> None:
        decision = engine.decide(
            "cloud_run.scale_within_range", "dev", {}, {"instances": 20}
        )
        assert decision.allowed is True

    def test_exceeds_max_instances_returns_bounds_violation(
        self, engine: PolicyEngine
    ) -> None:
        decision = engine.decide(
            "cloud_run.scale_within_range", "dev", {}, {"instances": 21}
        )
        assert decision.allowed is False
        assert "bounds_violation" in (decision.deny_reason or "")

    def test_below_min_instances_prod_returns_bounds_violation(
        self, engine: PolicyEngine
    ) -> None:
        decision = engine.decide(
            "cloud_run.scale_within_range", "prod", {}, {"instances": 0}
        )
        assert decision.allowed is False
        assert "bounds_violation" in (decision.deny_reason or "")

    def test_rule_matched_includes_action_and_env(self, engine: PolicyEngine) -> None:
        decision = engine.decide(
            "cloud_run.scale_within_range", "dev", {}, {"instances": 1}
        )
        assert decision.rule_matched == "cloud_run.scale_within_range:dev"

    def test_tier_3_rule_has_correct_required_approvers(
        self, engine: PolicyEngine
    ) -> None:
        decision = engine.decide(
            "cloud_run.scale_within_range", "prod", {}, {"instances": 3}
        )
        assert decision.allowed is True
        assert decision.tier == 3
        assert decision.required_approvers == 1

    def test_no_bounds_params_do_not_trigger_violation(
        self, engine: PolicyEngine
    ) -> None:
        # cloud_run.scale_within_range/dev with no 'instances' key → no bounds check
        decision = engine.decide("cloud_run.scale_within_range", "dev", {}, {})
        assert decision.allowed is True


# ---------------------------------------------------------------------------
# _check_bounds (module-level pure function)
# ---------------------------------------------------------------------------

class TestCheckBounds:
    def test_within_max_instances_returns_none(self) -> None:
        assert _check_bounds({"instances": 5}, {"max_instances": 10}) is None

    def test_exceeds_max_instances_returns_violation_string(self) -> None:
        result = _check_bounds({"instances": 11}, {"max_instances": 10})
        assert result is not None
        assert "instances=11" in result
        assert "max=10" in result

    def test_exactly_at_max_instances_is_allowed(self) -> None:
        assert _check_bounds({"instances": 10}, {"max_instances": 10}) is None

    def test_below_min_instances_returns_violation_string(self) -> None:
        result = _check_bounds({"instances": 0}, {"min_instances": 1})
        assert result is not None
        assert "min=1" in result

    def test_exactly_at_min_instances_is_allowed(self) -> None:
        assert _check_bounds({"instances": 1}, {"min_instances": 1}) is None

    def test_exceeds_max_blast_radius_returns_violation_string(self) -> None:
        result = _check_bounds({"target_count": 6}, {"max_blast_radius": 5})
        assert result is not None
        assert "target_count=6" in result

    def test_within_blast_radius_returns_none(self) -> None:
        assert _check_bounds({"target_count": 2}, {"max_blast_radius": 5}) is None

    def test_empty_bounds_always_returns_none(self) -> None:
        assert _check_bounds({"instances": 999}, {}) is None

    def test_bounds_key_absent_from_params_skips_check(self) -> None:
        # max_instances declared but 'instances' not in params — should pass
        assert _check_bounds({}, {"max_instances": 10}) is None

    def test_min_checked_before_max_does_not_double_fire(self) -> None:
        # params violates min, bounds also has max — only one violation returned
        result = _check_bounds(
            {"instances": 0}, {"min_instances": 1, "max_instances": 20}
        )
        assert result is not None
        # Should mention the min violation
        assert "min=1" in result
