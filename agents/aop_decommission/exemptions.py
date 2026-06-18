"""aop_decommission.exemptions — policy-driven retention with a fail-SAFE loader.

The exemption policy is the operator's contract for what must survive project
closure: audit sinks, billing exports, compliance artefacts, backups, break-glass
identities, legally-held data. Rules match by resource id, type, name, service,
environment, owner, criticality, label, or Resource Manager tag, and **every rule
must carry a reason** that is reproduced in the final report.

Safety direction matters and is the inverse of the Action Broker's policy engine.
The Broker fails *closed* by denying actions. An exemption file that is missing,
malformed, or contains a match-everything rule must **halt the campaign**, because
the alternative — "protect nothing and proceed to delete" — is catastrophic. So
``ExemptionPolicy.load`` raises; only an explicit :meth:`ExemptionPolicy.empty`
expresses a deliberate "no resources are exempt".
"""

from __future__ import annotations

import fnmatch
import logging
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from aop_decommission.schemas import ExemptionMatch, ExemptionRule, Inventory, ResourceRecord

logger = logging.getLogger(__name__)


class ExemptionConfigError(Exception):
    """Raised when the exemption policy cannot be trusted — the campaign must halt."""


def _now() -> datetime:
    return datetime.now(UTC)


class ExemptionPolicy:
    """An ordered set of exemption rules with first-match-wins evaluation.

    Args:
        rules: Validated, non-empty exemption rules.
        now_fn: Injectable clock used for expiry checks.
    """

    def __init__(
        self,
        rules: list[ExemptionRule],
        *,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._rules = rules
        self._now_fn = now_fn or _now

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #

    @classmethod
    def empty(cls, *, now_fn: Callable[[], datetime] | None = None) -> ExemptionPolicy:
        """A deliberate, explicit "nothing is exempt" policy."""
        return cls([], now_fn=now_fn)

    @classmethod
    def load(
        cls, path: str | Path, *, now_fn: Callable[[], datetime] | None = None
    ) -> ExemptionPolicy:
        """Load and validate an exemption policy file, raising on any doubt.

        Raises:
            ExemptionConfigError: file missing, unreadable, not a mapping, YAML
                invalid, a rule fails schema validation, a rule omits ``reason``,
                or a rule has no match criteria (would exempt everything).
        """
        p = Path(path)
        try:
            text = p.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ExemptionConfigError(
                f"exemption policy not found: {p} — pass a real path or ExemptionPolicy.empty()"
            ) from exc
        except OSError as exc:
            raise ExemptionConfigError(f"exemption policy unreadable: {p}: {exc}") from exc

        try:
            raw = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ExemptionConfigError(f"exemption policy YAML invalid: {p}: {exc}") from exc

        if raw is None:
            raise ExemptionConfigError(f"exemption policy is empty: {p}")
        if not isinstance(raw, dict):
            raise ExemptionConfigError(f"exemption policy must be a mapping: {p}")

        entries = raw.get("exemptions", [])
        if not isinstance(entries, list):
            raise ExemptionConfigError(f"`exemptions` must be a list: {p}")

        rules = cls._parse_rules(entries, source=str(p))
        logger.info("exemptions.load: %d rule(s) from %s", len(rules), p)
        return cls(rules, now_fn=now_fn)

    @classmethod
    def from_rules(
        cls,
        entries: list[dict[str, Any]],
        *,
        source: str = "inline",
        now_fn: Callable[[], datetime] | None = None,
    ) -> ExemptionPolicy:
        """Build a policy from already-parsed rule dicts (same validation as load)."""
        return cls(cls._parse_rules(entries, source=source), now_fn=now_fn)

    @staticmethod
    def _parse_rules(entries: list[Any], *, source: str) -> list[ExemptionRule]:
        rules: list[ExemptionRule] = []
        seen_ids: set[str] = set()
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise ExemptionConfigError(f"exemption rule #{index} is not a mapping ({source})")
            try:
                rule = ExemptionRule.model_validate(entry)
            except ValidationError as exc:
                raise ExemptionConfigError(
                    f"exemption rule #{index} invalid ({source}): {exc}"
                ) from exc
            if rule.is_empty():
                raise ExemptionConfigError(
                    f"exemption rule {rule.id!r} has no match criteria — it would exempt "
                    f"every resource and disable the entire campaign ({source})"
                )
            if rule.id in seen_ids:
                raise ExemptionConfigError(f"duplicate exemption rule id {rule.id!r} ({source})")
            seen_ids.add(rule.id)
            rules.append(rule)
        return rules

    # ------------------------------------------------------------------ #
    # Evaluation
    # ------------------------------------------------------------------ #

    @property
    def rules(self) -> list[ExemptionRule]:
        return list(self._rules)

    def evaluate(self, resource: ResourceRecord) -> ExemptionMatch | None:
        """Return the first non-expired rule that protects ``resource``, or None."""
        now = self._now_fn()
        for rule in self._rules:
            if self._is_expired(rule, now):
                continue
            matched_on = _match_dimensions(rule, resource)
            if matched_on is not None:
                return ExemptionMatch(
                    resource_id=resource.resource_id,
                    rule_id=rule.id,
                    reason=rule.reason,
                    matched_on=matched_on,
                )
        return None

    def evaluate_all(self, inventory: Inventory) -> dict[str, ExemptionMatch]:
        """Map resource_id → ExemptionMatch for every exempt resource."""
        out: dict[str, ExemptionMatch] = {}
        for resource in inventory.resources:
            match = self.evaluate(resource)
            if match is not None:
                out[resource.resource_id] = match
        return out

    @staticmethod
    def _is_expired(rule: ExemptionRule, now: datetime) -> bool:
        if not rule.expires_at:
            return False
        expiry = datetime.fromisoformat(rule.expires_at)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        return now >= expiry


def _match_dimensions(rule: ExemptionRule, resource: ResourceRecord) -> list[str] | None:
    """Return the matched dimension names if the rule applies, else None.

    All populated criteria must match (AND). Each dimension yields ``None`` when
    its criterion is unset (skip), ``True`` on a match, or ``False`` on a miss
    (which fails the whole rule). An empty rule never reaches here — it is
    rejected at load time.
    """
    matched: list[str] = []
    for dimension, outcome in _dimension_outcomes(rule, resource):
        if outcome is None:
            continue
        if not outcome:
            return None
        matched.append(dimension)
    return matched or None


def _dimension_outcomes(
    rule: ExemptionRule, resource: ResourceRecord
) -> Iterator[tuple[str, bool | None]]:
    """Yield (dimension, match-result) pairs; ``None`` means the criterion is unset."""
    yield (
        "resource_id",
        (None if rule.resource_id is None else rule.resource_id == resource.resource_id),
    )
    yield "type", (None if rule.type is None else fnmatch.fnmatch(resource.type, rule.type))
    yield "name", (None if rule.name is None else fnmatch.fnmatch(resource.name, rule.name))
    yield (
        "service",
        (None if rule.service is None else fnmatch.fnmatch(resource.service, rule.service)),
    )
    yield (
        "environment",
        (
            None
            if rule.environment is None
            else (resource.environment or "").lower() == rule.environment.lower()
        ),
    )
    yield "owner", (None if rule.owner is None else (resource.owner or "") == rule.owner)
    yield (
        "criticality",
        (None if rule.criticality is None else resource.criticality == rule.criticality),
    )
    yield (
        "label",
        (
            None
            if not rule.label_selector
            else _selector_matches(rule.label_selector, resource.labels)
        ),
    )
    yield (
        "tag",
        (None if not rule.tag_selector else _selector_matches(rule.tag_selector, resource.tags)),
    )


def _selector_matches(selector: dict[str, str], actual: dict[str, str]) -> bool:
    return all(actual.get(key) == value for key, value in selector.items())
