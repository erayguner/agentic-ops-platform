"""Tests for aop_decommission.exemptions — policy loading + first-match retention."""

from __future__ import annotations

import textwrap
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from aop_decommission.exemptions import ExemptionConfigError, ExemptionPolicy
from aop_decommission.schemas import ResourceRecord

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)

VALID_YAML = textwrap.dedent("""\
    exemptions:
      - id: keep-audit
        reason: "audit sinks are legally retained"
        type: "logging.googleapis.com/LogSink"
      - id: keep-bucket
        reason: "tf state bucket"
        resource_id: "//storage.googleapis.com/projects/_/buckets/tfstate"
""")


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "exemptions.yaml"
    p.write_text(text)
    return p


# --------------------------------------------------------------------------- #
# Loading — fail SAFE (raise) on any doubt
# --------------------------------------------------------------------------- #


class TestLoad:
    def test_load_valid_file(self, tmp_path: Path) -> None:
        policy = ExemptionPolicy.load(_write(tmp_path, VALID_YAML))
        assert len(policy.rules) == 2

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ExemptionConfigError, match="not found"):
            ExemptionPolicy.load(tmp_path / "nope.yaml")

    def test_malformed_yaml_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ExemptionConfigError, match="YAML invalid"):
            ExemptionPolicy.load(_write(tmp_path, "exemptions: [::::"))

    def test_empty_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ExemptionConfigError, match="empty"):
            ExemptionPolicy.load(_write(tmp_path, "\n"))

    def test_non_mapping_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ExemptionConfigError, match="must be a mapping"):
            ExemptionPolicy.load(_write(tmp_path, "- just\n- a\n- list\n"))

    def test_exemptions_not_a_list_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ExemptionConfigError, match="must be a list"):
            ExemptionPolicy.load(_write(tmp_path, "exemptions: not-a-list\n"))

    def test_rule_missing_reason_raises(self, tmp_path: Path) -> None:
        bad = "exemptions:\n  - id: x\n    type: foo\n"
        with pytest.raises(ExemptionConfigError, match="invalid"):
            ExemptionPolicy.load(_write(tmp_path, bad))

    def test_match_everything_rule_raises(self, tmp_path: Path) -> None:
        bad = "exemptions:\n  - id: catch-all\n    reason: oops\n"
        with pytest.raises(ExemptionConfigError, match="no match criteria"):
            ExemptionPolicy.load(_write(tmp_path, bad))

    def test_duplicate_id_raises(self, tmp_path: Path) -> None:
        dup = textwrap.dedent("""\
            exemptions:
              - id: a
                reason: r
                service: run
              - id: a
                reason: r2
                service: compute
        """)
        with pytest.raises(ExemptionConfigError, match="duplicate"):
            ExemptionPolicy.load(_write(tmp_path, dup))

    def test_empty_policy_is_explicit(self) -> None:
        policy = ExemptionPolicy.empty()
        assert policy.rules == []


# --------------------------------------------------------------------------- #
# Matching dimensions
# --------------------------------------------------------------------------- #


class TestMatching:
    def test_match_by_resource_id(self, make_resource: Callable[..., ResourceRecord]) -> None:
        policy = ExemptionPolicy.from_rules([{"id": "x", "reason": "r", "resource_id": "rid-1"}])
        assert policy.evaluate(make_resource("rid-1")) is not None
        assert policy.evaluate(make_resource("rid-2")) is None

    def test_match_by_type_glob(self, make_resource: Callable[..., ResourceRecord]) -> None:
        policy = ExemptionPolicy.from_rules(
            [{"id": "x", "reason": "r", "type": "iam.googleapis.com/*"}]
        )
        assert (
            policy.evaluate(make_resource("r", type="iam.googleapis.com/ServiceAccount"))
            is not None
        )
        assert policy.evaluate(make_resource("r", type="run.googleapis.com/Service")) is None

    def test_match_by_name_glob(self, make_resource: Callable[..., ResourceRecord]) -> None:
        policy = ExemptionPolicy.from_rules([{"id": "x", "reason": "r", "name": "breakglass-*"}])
        assert policy.evaluate(make_resource("r", name="breakglass-sa")) is not None
        assert policy.evaluate(make_resource("r", name="regular-sa")) is None

    def test_match_by_service(self, make_resource: Callable[..., ResourceRecord]) -> None:
        policy = ExemptionPolicy.from_rules([{"id": "x", "reason": "r", "service": "bigquery"}])
        assert policy.evaluate(make_resource("r", service="bigquery")) is not None

    def test_match_by_environment_case_insensitive(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        policy = ExemptionPolicy.from_rules([{"id": "x", "reason": "r", "environment": "PROD"}])
        assert policy.evaluate(make_resource("r", environment="prod")) is not None

    def test_match_by_owner(self, make_resource: Callable[..., ResourceRecord]) -> None:
        policy = ExemptionPolicy.from_rules([{"id": "x", "reason": "r", "owner": "team@x.io"}])
        assert policy.evaluate(make_resource("r", owner="team@x.io")) is not None
        assert policy.evaluate(make_resource("r", owner="other@x.io")) is None

    def test_match_by_criticality(self, make_resource: Callable[..., ResourceRecord]) -> None:
        policy = ExemptionPolicy.from_rules([{"id": "x", "reason": "r", "criticality": "critical"}])
        assert policy.evaluate(make_resource("r", criticality="critical")) is not None
        assert policy.evaluate(make_resource("r", criticality="low")) is None

    def test_match_by_label_selector(self, make_resource: Callable[..., ResourceRecord]) -> None:
        policy = ExemptionPolicy.from_rules(
            [{"id": "x", "reason": "r", "label_selector": {"purpose": "billing-export"}}]
        )
        assert policy.evaluate(make_resource("r", labels={"purpose": "billing-export"})) is not None
        assert policy.evaluate(make_resource("r", labels={"purpose": "other"})) is None

    def test_match_by_tag_selector(self, make_resource: Callable[..., ResourceRecord]) -> None:
        policy = ExemptionPolicy.from_rules(
            [{"id": "x", "reason": "r", "tag_selector": {"legal-hold": "true"}}]
        )
        assert policy.evaluate(make_resource("r", tags={"legal-hold": "true"})) is not None
        assert policy.evaluate(make_resource("r", tags={})) is None

    def test_and_semantics_require_all_criteria(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        policy = ExemptionPolicy.from_rules(
            [{"id": "x", "reason": "r", "service": "run", "name": "keep-*"}]
        )
        assert policy.evaluate(make_resource("r", service="run", name="keep-me")) is not None
        # service matches but name does not → no match
        assert policy.evaluate(make_resource("r", service="run", name="drop-me")) is None

    def test_matched_on_records_dimensions(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        policy = ExemptionPolicy.from_rules(
            [{"id": "x", "reason": "r", "service": "run", "criticality": "high"}]
        )
        match = policy.evaluate(make_resource("r", service="run", criticality="high"))
        assert match is not None
        assert set(match.matched_on) == {"service", "criticality"}


# --------------------------------------------------------------------------- #
# Ordering + expiry
# --------------------------------------------------------------------------- #


class TestOrderingExpiry:
    def test_first_match_wins(self, make_resource: Callable[..., ResourceRecord]) -> None:
        policy = ExemptionPolicy.from_rules(
            [
                {"id": "first", "reason": "specific", "name": "keep-me"},
                {"id": "second", "reason": "broad", "service": "compute"},
            ]
        )
        match = policy.evaluate(make_resource("r", name="keep-me", service="compute"))
        assert match is not None
        assert match.rule_id == "first"

    def test_expired_rule_does_not_protect(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        policy = ExemptionPolicy.from_rules(
            [
                {
                    "id": "x",
                    "reason": "temporary",
                    "service": "run",
                    "expires_at": "2026-01-01T00:00:00Z",
                }
            ],
            now_fn=lambda: _NOW,
        )
        assert policy.evaluate(make_resource("r", service="run")) is None

    def test_future_expiry_still_protects(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        policy = ExemptionPolicy.from_rules(
            [
                {
                    "id": "x",
                    "reason": "temporary",
                    "service": "run",
                    "expires_at": "2026-12-31T00:00:00Z",
                }
            ],
            now_fn=lambda: _NOW,
        )
        assert policy.evaluate(make_resource("r", service="run")) is not None

    def test_evaluate_all_maps_exempt_resources(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        from aop_decommission.schemas import Inventory

        policy = ExemptionPolicy.from_rules([{"id": "x", "reason": "r", "service": "run"}])
        inv = Inventory(
            project="proj",
            environment="dev",
            resources=[
                make_resource("a", service="run"),
                make_resource("b", service="compute"),
            ],
        )
        result = policy.evaluate_all(inv)
        assert set(result) == {"a"}
