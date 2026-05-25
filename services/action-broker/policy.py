"""
Typed-rule policy engine.

Loads ``policy/action_classes.yaml`` and evaluates each proposed action
against the declared tier, bounds, and environment constraints.

The engine always fails CLOSED: if the policy file is missing or malformed,
all requests are denied with reason ``policy_engine_unavailable``.

Usage:
    engine = PolicyEngine.load()
    decision = engine.decide("cloud_run.scale_within_range", "prod", target, params)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

_POLICY_PATH = Path(__file__).parent / "policy" / "action_classes.yaml"


@dataclass
class PolicyRule:
    action_class: str
    environment: str
    tier: int
    allowed: bool
    required_approvers: int
    bounds: Dict[str, Any]
    deny_reason: Optional[str]


@dataclass
class Decision:
    tier: int
    allowed: bool
    required_approvers: int
    bounds: Dict[str, Any]
    deny_reason: Optional[str] = None
    rule_matched: str = "default-deny"


class PolicyEngine:
    def __init__(self, rules: List[PolicyRule]) -> None:
        self._rules: Dict[tuple[str, str], PolicyRule] = {
            (r.action_class, r.environment): r for r in rules
        }

    @classmethod
    def load(cls, path: Path = _POLICY_PATH) -> "PolicyEngine":
        try:
            raw = yaml.safe_load(path.read_text())
        except FileNotFoundError:
            logger.error("Policy file not found: %s — engine in DENY mode", path)
            return cls([])
        except yaml.YAMLError as exc:
            logger.error("Policy YAML parse error: %s — engine in DENY mode", exc)
            return cls([])

        rules: List[PolicyRule] = []
        for entry in raw.get("action_classes", []):
            for env in entry.get("environments", []):
                rules.append(PolicyRule(
                    action_class=entry["name"],
                    environment=env["env"],
                    tier=env.get("tier", 1),
                    allowed=env.get("allowed", True),
                    required_approvers=env.get("required_approvers", 1),
                    bounds=env.get("bounds", {}),
                    deny_reason=env.get("deny_reason"),
                ))
        logger.info("PolicyEngine loaded %d rules from %s", len(rules), path)
        return cls(rules)

    def decide(
        self,
        action_class: str,
        environment: str,
        target: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Decision:
        """
        Return a ``Decision`` for the proposed action.

        Falls through to the default-deny rule if no entry matches.
        Validates ``params`` against declared ``bounds`` where present.
        """
        key = (action_class, environment)
        rule = self._rules.get(key)

        if rule is None:
            logger.warning(
                "No policy rule for action_class=%s env=%s — default DENY",
                action_class, environment,
            )
            return Decision(
                tier=0,
                allowed=False,
                required_approvers=0,
                bounds={},
                deny_reason="no_policy_rule_for_action_class_env",
                rule_matched="default-deny",
            )

        if not rule.allowed:
            return Decision(
                tier=rule.tier,
                allowed=False,
                required_approvers=0,
                bounds=rule.bounds,
                deny_reason=rule.deny_reason or "action_class_denied_in_policy",
                rule_matched=f"{action_class}:{environment}",
            )

        # Bounds validation (best-effort on known keys)
        bounds_violation = _check_bounds(params, rule.bounds)
        if bounds_violation:
            return Decision(
                tier=rule.tier,
                allowed=False,
                required_approvers=0,
                bounds=rule.bounds,
                deny_reason=f"bounds_violation:{bounds_violation}",
                rule_matched=f"{action_class}:{environment}",
            )

        return Decision(
            tier=rule.tier,
            allowed=True,
            required_approvers=rule.required_approvers,
            bounds=rule.bounds,
            rule_matched=f"{action_class}:{environment}",
        )


def _check_bounds(params: Dict[str, Any], bounds: Dict[str, Any]) -> Optional[str]:
    """
    Validate params against bounds.  Returns a violation string or None.

    Supported bound keys: min_instances, max_instances, max_blast_radius.
    """
    if "max_instances" in bounds and "instances" in params:
        if params["instances"] > bounds["max_instances"]:
            return f"instances={params['instances']} > max={bounds['max_instances']}"
    if "min_instances" in bounds and "instances" in params:
        if params["instances"] < bounds["min_instances"]:
            return f"instances={params['instances']} < min={bounds['min_instances']}"
    if "max_blast_radius" in bounds and "target_count" in params:
        if params["target_count"] > bounds["max_blast_radius"]:
            return f"target_count={params['target_count']} > max={bounds['max_blast_radius']}"
    return None
