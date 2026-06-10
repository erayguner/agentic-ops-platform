"""aop_decommission.inventory — discovery, reconciliation and classification.

Builds the complete pre-decommission :class:`Inventory` by fanning out across
injectable :class:`ResourceProvider` sources and reconciling their views:

* **Terraform state** — the IaC source of truth (``terraform show -json``).
* **Cloud Asset Inventory** — the *live* estate, including resources no IaC
  declares (manually created / drifted).
* **Recommender / Monitoring** — activity + idle signals used for classification.

Reconciliation is where the value is, and it is pure + offline-testable:

* in state **and** live → ``terraform`` (managed, present)
* live but **not** in state → ``unmanaged`` (or ``drifted`` if it claims IaC ownership)
* in state but **not** live → ``ghost`` (already gone / deleted out of band)

On top of management state, deterministic rules classify each resource as
dormant / stale / unattached / orphaned, mark it billable, and flag
security-sensitive types. The cloud I/O lives behind the provider seam so the
classification logic runs without infrastructure.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any, Protocol

from aop_decommission.schemas import (
    DiscoverySource,
    Inventory,
    ManagementState,
    ResourceCondition,
    ResourceRecord,
)

logger = logging.getLogger(__name__)

# Asset-type substrings that are security-sensitive: deleting one can sever
# access, destroy key material, or break the audit trail. Flagged so the planner
# can raise their risk and the operator can exempt them deliberately.
_SECURITY_SENSITIVE_MARKERS: tuple[str, ...] = (
    "iam.",
    "serviceaccount",
    "secretmanager",
    "cloudkms",
    "kms",
    "logging.googleapis.com/loglink",
    "logging.googleapis.com/logbucket",
    "logging.googleapis.com/logsink",
    "audit",
    "binaryauthorization",
    "privateca",
    "essentialcontacts",
)

# Asset types that are "attachable" — meaningful to flag as unattached.
_ATTACHABLE_MARKERS: tuple[str, ...] = (
    "compute.googleapis.com/disk",
    "compute.googleapis.com/address",
    "compute.googleapis.com/networkendpointgroup",
    "compute.googleapis.com/subnetwork",
)

# Labels that signal a resource claims IaC ownership even when state disagrees.
_IAC_OWNERSHIP_LABELS: tuple[str, ...] = ("managed_by", "managed-by", "terraform")
_IAC_OWNERSHIP_VALUES: frozenset[str] = frozenset({"terraform", "iac", "opentofu", "terragrunt"})


class ResourceProvider(Protocol):
    """A discovery source. ``discover`` returns records tagged with its origin."""

    source: DiscoverySource

    def discover(self) -> list[ResourceRecord]: ...


# --------------------------------------------------------------------------- #
# Pure classification helpers
# --------------------------------------------------------------------------- #


def is_security_sensitive(asset_type: str) -> bool:
    """True if the asset type is identity/secret/key/audit-related."""
    lowered = asset_type.lower()
    return any(marker in lowered for marker in _SECURITY_SENSITIVE_MARKERS)


def _is_attachable(asset_type: str) -> bool:
    lowered = asset_type.lower()
    return any(marker in lowered for marker in _ATTACHABLE_MARKERS)


def _age_seconds(timestamp: str | None, now: datetime) -> float | None:
    if not timestamp:
        return None
    moment = datetime.fromisoformat(timestamp)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return (now - moment).total_seconds()


def classify_conditions(
    record: ResourceRecord,
    *,
    now: datetime,
    dormant_after_days: int = 30,
    stale_after_days: int = 90,
) -> list[ResourceCondition]:
    """Return the lifecycle conditions a resource exhibits (deterministic).

    Conditions already present on the record (e.g. ``orphaned`` asserted by a
    provider that knows the parent is gone) are preserved and merged with the
    age/attachment-derived ones.
    """
    conditions: set[ResourceCondition] = set(record.conditions)

    age_s = _age_seconds(record.last_activity_at, now)
    if age_s is not None:
        if age_s >= stale_after_days * 86_400:
            conditions.add("stale")
        if age_s >= dormant_after_days * 86_400:
            conditions.add("dormant")

    # An attachable resource that nothing depends on is unattached, and an
    # unattached attachable that is also dormant reads as orphaned.
    if _is_attachable(record.type) and not record.dependencies:
        conditions.add("unattached")
        if "dormant" in conditions:
            conditions.add("orphaned")

    return sorted(conditions)


def infer_management(
    record: ResourceRecord,
    *,
    ran_sources: frozenset[DiscoverySource],
) -> ManagementState:
    """Infer IaC management state from which sources saw the resource.

    Respects an explicit non-``unknown`` value already on the record (a provider
    that authoritatively knows). ``ran_sources`` is the set of provider origins
    that actually executed this scan — needed to tell ``ghost`` (state has it,
    Asset Inventory ran and did not) from "we simply never looked".
    """
    if record.management != "unknown":
        return record.management

    seen = set(record.discovered_by)
    in_state = "terraform_state" in seen
    in_estate = "asset_inventory" in seen

    if in_state and in_estate:
        return "terraform"
    if in_state and not in_estate:
        return "ghost" if "asset_inventory" in ran_sources else "terraform"
    if in_estate:
        for key in _IAC_OWNERSHIP_LABELS:
            value = record.labels.get(key, "").lower()
            if value in _IAC_OWNERSHIP_VALUES:
                return "drifted"
        return "unmanaged"
    return "unknown"


# --------------------------------------------------------------------------- #
# Scanner
# --------------------------------------------------------------------------- #


class InventoryScanner:
    """Fans out across providers, merges by ``resource_id``, classifies the result.

    Args:
        providers: Discovery sources to query. Order matters only for field
            precedence on merge (earlier-listed non-empty values win ties).
        dormant_after_days: Inactivity threshold for the ``dormant`` condition.
        stale_after_days: Inactivity threshold for the ``stale`` condition.
        now_fn: Injectable clock for deterministic tests.
    """

    def __init__(
        self,
        providers: Sequence[ResourceProvider],
        *,
        dormant_after_days: int = 30,
        stale_after_days: int = 90,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._providers = list(providers)
        self._dormant_after_days = dormant_after_days
        self._stale_after_days = stale_after_days
        self._now_fn = now_fn or (lambda: datetime.now(UTC))

    def scan(self, *, project: str, environment: str) -> Inventory:
        """Discover, reconcile and classify the full estate into an Inventory."""
        ran_sources: set[DiscoverySource] = set()
        merged: dict[str, ResourceRecord] = {}

        for provider in self._providers:
            try:
                discovered = provider.discover()
            except NotImplementedError:
                logger.warning(
                    "inventory.scan: provider source=%s not wired — skipped",
                    getattr(provider, "source", "?"),
                )
                continue
            ran_sources.add(provider.source)
            for record in discovered:
                merged[record.resource_id] = _merge(merged.get(record.resource_id), record)

        now = self._now_fn()
        ran = frozenset(ran_sources)
        resources: list[ResourceRecord] = []
        for record in merged.values():
            record.management = infer_management(record, ran_sources=ran)
            record.billable = record.billable or record.monthly_cost > 0
            record.security_sensitive = record.security_sensitive or is_security_sensitive(
                record.type
            )
            record.conditions = classify_conditions(
                record,
                now=now,
                dormant_after_days=self._dormant_after_days,
                stale_after_days=self._stale_after_days,
            )
            resources.append(record)

        resources.sort(key=lambda r: r.resource_id)
        logger.info(
            "inventory.scan: project=%s sources=%s resources=%d",
            project,
            sorted(ran),
            len(resources),
        )
        return Inventory(
            project=project,
            environment=environment,
            captured_at=now.isoformat(),
            resources=resources,
        )


def _merge(existing: ResourceRecord | None, incoming: ResourceRecord) -> ResourceRecord:
    """Combine two views of the same resource_id, unioning provenance + facts."""
    if existing is None:
        return incoming.model_copy(deep=True)

    merged = existing.model_copy(deep=True)
    merged.discovered_by = sorted(set(existing.discovered_by) | set(incoming.discovered_by))
    merged.conditions = sorted(set(existing.conditions) | set(incoming.conditions))
    merged.dependencies = sorted(set(existing.dependencies) | set(incoming.dependencies))
    merged.labels = {**incoming.labels, **existing.labels}
    merged.tags = {**incoming.tags, **existing.tags}
    merged.monthly_cost = max(existing.monthly_cost, incoming.monthly_cost)
    merged.billable = existing.billable or incoming.billable
    merged.security_sensitive = existing.security_sensitive or incoming.security_sensitive

    # Prefer the more specific / authoritative value for scalar fields.
    if existing.management == "unknown" and incoming.management != "unknown":
        merged.management = incoming.management
    merged.terraform_address = existing.terraform_address or incoming.terraform_address
    merged.owner = existing.owner or incoming.owner
    merged.environment = existing.environment or incoming.environment
    if existing.criticality == "unknown":
        merged.criticality = incoming.criticality
    merged.created_at = existing.created_at or incoming.created_at
    merged.last_activity_at = existing.last_activity_at or incoming.last_activity_at
    return merged


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #


class StaticSource:
    """A provider that returns pre-built records. Used in tests and for feeding
    an already-collected inventory back through the pipeline."""

    def __init__(
        self, records: list[ResourceRecord], *, source: DiscoverySource = "manual"
    ) -> None:
        self.source = source
        self._records = records

    def discover(self) -> list[ResourceRecord]:
        return [r.model_copy(deep=True) for r in self._records]


class TerraformStateSource:
    """Parses ``terraform show -json`` output into ResourceRecords.

    The state JSON is injected (already produced by the CI/Terraform runner)
    rather than shelled out to here, keeping discovery pure and the parser
    unit-testable. Only ``google*`` managed resources are mapped.
    """

    source: DiscoverySource = "terraform_state"

    def __init__(self, state_json: dict[str, Any] | None, *, project: str) -> None:
        self._state = state_json
        self._project = project

    def discover(self) -> list[ResourceRecord]:
        if self._state is None:
            raise NotImplementedError(
                "TerraformStateSource needs `terraform show -json` output; none supplied."
            )
        root = self._state.get("values", {}).get("root_module", {})
        records: list[ResourceRecord] = []
        self._walk_module(root, records)
        return records

    def _walk_module(self, module: dict[str, Any], out: list[ResourceRecord]) -> None:
        for res in module.get("resources", []):
            record = self._map_resource(res)
            if record is not None:
                out.append(record)
        for child in module.get("child_modules", []):
            self._walk_module(child, out)

    def _map_resource(self, res: dict[str, Any]) -> ResourceRecord | None:
        res_type = str(res.get("type", ""))
        if not res_type.startswith("google"):
            return None
        values = res.get("values", {})
        if not isinstance(values, dict):
            return None
        resource_id = str(values.get("id") or res.get("address", ""))
        if not resource_id:
            return None
        labels = {str(k): str(v) for k, v in (values.get("labels") or {}).items()}
        return ResourceRecord(
            resource_id=resource_id,
            name=str(values.get("name") or res.get("name", resource_id)),
            type=res_type,
            service=res_type.split("_", 2)[1] if "_" in res_type else res_type,
            project=str(values.get("project") or self._project),
            location=str(values.get("location") or values.get("region") or "global"),
            # management is inferred by the scanner from provenance (discovered_by)
            # + which sources ran — so a state-only resource can be flagged `ghost`.
            terraform_address=str(res.get("address", "")) or None,
            labels=labels,
            discovered_by=["terraform_state"],
        )


class AssetInventorySource:
    """Maps Cloud Asset Inventory assets into ResourceRecords.

    The live asset list is injected (fetched upstream via the Asset Inventory
    MCP / API). With no assets supplied the provider declares itself unwired so
    the scanner degrades gracefully rather than failing the whole inventory.
    """

    source: DiscoverySource = "asset_inventory"

    def __init__(self, assets: list[dict[str, Any]] | None, *, project: str) -> None:
        self._assets = assets
        self._project = project

    def discover(self) -> list[ResourceRecord]:
        if self._assets is None:
            raise NotImplementedError(
                "AssetInventorySource needs Cloud Asset Inventory results; none supplied."
            )
        records: list[ResourceRecord] = []
        for asset in self._assets:
            name = str(asset.get("name", ""))
            asset_type = str(asset.get("assetType", asset.get("asset_type", "")))
            if not name or not asset_type:
                continue
            resource = asset.get("resource", {})
            data = resource.get("data", {}) if isinstance(resource, dict) else {}
            labels = {str(k): str(v) for k, v in (data.get("labels") or {}).items()}
            records.append(
                ResourceRecord(
                    resource_id=name,
                    name=str(data.get("name") or name.rsplit("/", 1)[-1]),
                    type=asset_type,
                    service=asset_type.split(".", 1)[0],
                    project=str(asset.get("project") or self._project),
                    location=str(asset.get("location") or "global"),
                    labels=labels,
                    last_activity_at=asset.get("updateTime") or asset.get("update_time"),
                    discovered_by=["asset_inventory"],
                )
            )
        return records
