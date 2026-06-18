"""Tests for aop_decommission.inventory — discovery, reconciliation, classification."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from aop_decommission.inventory import (
    AssetInventorySource,
    InventoryScanner,
    StaticSource,
    TerraformStateSource,
    classify_conditions,
    infer_management,
    is_security_sensitive,
)
from aop_decommission.schemas import ResourceRecord

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)


def _ago(days: int) -> str:
    return (_NOW - timedelta(days=days)).isoformat()


# --------------------------------------------------------------------------- #
# is_security_sensitive
# --------------------------------------------------------------------------- #


class TestSecuritySensitive:
    @pytest.mark.parametrize(
        "asset_type",
        [
            "iam.googleapis.com/ServiceAccount",
            "iam.googleapis.com/ServiceAccountKey",
            "secretmanager.googleapis.com/Secret",
            "cloudkms.googleapis.com/CryptoKey",
            "logging.googleapis.com/LogSink",
        ],
    )
    def test_sensitive_types(self, asset_type: str) -> None:
        assert is_security_sensitive(asset_type) is True

    @pytest.mark.parametrize(
        "asset_type",
        [
            "compute.googleapis.com/Instance",
            "run.googleapis.com/Service",
            "storage.googleapis.com/Bucket",
        ],
    )
    def test_non_sensitive_types(self, asset_type: str) -> None:
        assert is_security_sensitive(asset_type) is False


# --------------------------------------------------------------------------- #
# classify_conditions
# --------------------------------------------------------------------------- #


class TestClassifyConditions:
    def test_dormant_and_stale_for_old_activity(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        r = make_resource("r1", last_activity_at=_ago(100))
        conditions = classify_conditions(r, now=_NOW)
        assert "dormant" in conditions
        assert "stale" in conditions

    def test_dormant_not_stale_in_between(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        r = make_resource("r1", last_activity_at=_ago(40))
        conditions = classify_conditions(r, now=_NOW)
        assert "dormant" in conditions
        assert "stale" not in conditions

    def test_recent_activity_is_neither(self, make_resource: Callable[..., ResourceRecord]) -> None:
        r = make_resource("r1", last_activity_at=_ago(5))
        conditions = classify_conditions(r, now=_NOW)
        assert "dormant" not in conditions
        assert "stale" not in conditions

    def test_unknown_activity_yields_no_age_conditions(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        r = make_resource("r1", last_activity_at=None)
        assert classify_conditions(r, now=_NOW) == []

    def test_unattached_disk_with_no_dependencies(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        r = make_resource("d1", type="compute.googleapis.com/Disk", dependencies=[])
        assert "unattached" in classify_conditions(r, now=_NOW)

    def test_dormant_unattached_disk_is_orphaned(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        r = make_resource("d1", type="compute.googleapis.com/Disk", last_activity_at=_ago(120))
        conditions = classify_conditions(r, now=_NOW)
        assert "orphaned" in conditions
        assert "unattached" in conditions

    def test_attached_disk_is_not_unattached(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        r = make_resource("d1", type="compute.googleapis.com/Disk", dependencies=["vm1"])
        assert "unattached" not in classify_conditions(r, now=_NOW)

    def test_provider_conditions_are_preserved(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        r = make_resource("r1", conditions=["orphaned"], last_activity_at=_ago(2))
        assert "orphaned" in classify_conditions(r, now=_NOW)


# --------------------------------------------------------------------------- #
# infer_management
# --------------------------------------------------------------------------- #


class TestInferManagement:
    def test_state_and_estate_is_terraform(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        r = make_resource("r1", discovered_by=["terraform_state", "asset_inventory"])
        assert (
            infer_management(r, ran_sources=frozenset({"terraform_state", "asset_inventory"}))
            == "terraform"
        )

    def test_state_only_with_asset_scan_is_ghost(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        r = make_resource("r1", discovered_by=["terraform_state"])
        assert (
            infer_management(r, ran_sources=frozenset({"terraform_state", "asset_inventory"}))
            == "ghost"
        )

    def test_state_only_without_asset_scan_is_terraform(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        r = make_resource("r1", discovered_by=["terraform_state"])
        assert infer_management(r, ran_sources=frozenset({"terraform_state"})) == "terraform"

    def test_estate_only_is_unmanaged(self, make_resource: Callable[..., ResourceRecord]) -> None:
        r = make_resource("r1", discovered_by=["asset_inventory"])
        assert infer_management(r, ran_sources=frozenset({"asset_inventory"})) == "unmanaged"

    def test_estate_only_with_iac_label_is_drifted(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        r = make_resource(
            "r1", discovered_by=["asset_inventory"], labels={"managed_by": "terraform"}
        )
        assert infer_management(r, ran_sources=frozenset({"asset_inventory"})) == "drifted"

    def test_explicit_management_is_respected(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        r = make_resource("r1", management="iac_other", discovered_by=["asset_inventory"])
        assert infer_management(r, ran_sources=frozenset({"asset_inventory"})) == "iac_other"


# --------------------------------------------------------------------------- #
# InventoryScanner
# --------------------------------------------------------------------------- #


class TestInventoryScanner:
    def test_scan_merges_sources_and_infers_terraform(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        tf = StaticSource(
            [
                make_resource(
                    "r1", discovered_by=["terraform_state"], terraform_address="module.a.x"
                )
            ],
            source="terraform_state",
        )
        asset = StaticSource(
            [make_resource("r1", discovered_by=["asset_inventory"], last_activity_at=_ago(100))],
            source="asset_inventory",
        )
        scanner = InventoryScanner([tf, asset], now_fn=lambda: _NOW)
        inv = scanner.scan(project="proj", environment="dev")

        assert inv.count == 1
        record = inv.resources[0]
        assert record.management == "terraform"
        assert set(record.discovered_by) == {"terraform_state", "asset_inventory"}
        assert "dormant" in record.conditions

    def test_scan_sets_billable_from_cost(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        src = StaticSource(
            [make_resource("r1", monthly_cost=12.5, discovered_by=["asset_inventory"])]
        )
        scanner = InventoryScanner([src], now_fn=lambda: _NOW)
        inv = scanner.scan(project="proj", environment="dev")
        assert inv.resources[0].billable is True

    def test_scan_flags_security_sensitive_by_type(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        src = StaticSource(
            [
                make_resource(
                    "sa1",
                    type="iam.googleapis.com/ServiceAccount",
                    discovered_by=["asset_inventory"],
                )
            ]
        )
        scanner = InventoryScanner([src], now_fn=lambda: _NOW)
        inv = scanner.scan(project="proj", environment="dev")
        assert inv.resources[0].security_sensitive is True

    def test_scan_skips_unwired_provider(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        good = StaticSource([make_resource("r1", discovered_by=["asset_inventory"])])
        unwired = TerraformStateSource(None, project="proj")  # raises NotImplementedError
        scanner = InventoryScanner([unwired, good], now_fn=lambda: _NOW)
        inv = scanner.scan(project="proj", environment="dev")
        assert inv.count == 1


# --------------------------------------------------------------------------- #
# Source adapters
# --------------------------------------------------------------------------- #


class TestTerraformStateSource:
    def test_parses_root_and_child_modules(self) -> None:
        state = {
            "values": {
                "root_module": {
                    "resources": [
                        {
                            "address": "google_storage_bucket.a",
                            "type": "google_storage_bucket",
                            "name": "a",
                            "values": {"id": "bucket-a", "name": "a", "project": "proj"},
                        }
                    ],
                    "child_modules": [
                        {
                            "resources": [
                                {
                                    "address": "module.run.google_cloud_run_service.svc",
                                    "type": "google_cloud_run_service",
                                    "name": "svc",
                                    "values": {"id": "svc-1", "name": "svc", "project": "proj"},
                                }
                            ]
                        }
                    ],
                }
            }
        }
        records = TerraformStateSource(state, project="proj").discover()
        ids = {r.resource_id for r in records}
        assert ids == {"bucket-a", "svc-1"}
        assert all(r.discovered_by == ["terraform_state"] for r in records)
        assert all(r.terraform_address for r in records)

    def test_ignores_non_google_resources(self) -> None:
        state = {
            "values": {
                "root_module": {
                    "resources": [
                        {
                            "address": "random_id.x",
                            "type": "random_id",
                            "name": "x",
                            "values": {"id": "z"},
                        }
                    ]
                }
            }
        }
        assert TerraformStateSource(state, project="proj").discover() == []

    def test_unwired_raises(self) -> None:
        with pytest.raises(NotImplementedError):
            TerraformStateSource(None, project="proj").discover()


class TestAssetInventorySource:
    def test_maps_assets(self) -> None:
        assets = [
            {
                "name": "//run.googleapis.com/projects/proj/locations/europe-west2/services/api",
                "assetType": "run.googleapis.com/Service",
                "updateTime": "2026-01-01T00:00:00Z",
                "resource": {"data": {"name": "api", "labels": {"team": "ops"}}},
            }
        ]
        records = AssetInventorySource(assets, project="proj").discover()
        assert len(records) == 1
        assert records[0].service == "run"
        assert records[0].labels == {"team": "ops"}
        assert records[0].discovered_by == ["asset_inventory"]

    def test_unwired_raises(self) -> None:
        with pytest.raises(NotImplementedError):
            AssetInventorySource(None, project="proj").discover()
