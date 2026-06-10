"""Test configuration for the agents component.

Adds the ``agents/`` directory to ``sys.path`` so tests can import the
``aop_common`` / ``aop_decommission`` packages, and exposes a ``make_resource``
factory fixture used across the decommission test suite.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from aop_decommission.schemas import ResourceRecord

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def make_resource() -> Callable[..., ResourceRecord]:
    """Return a factory that builds a ResourceRecord with sensible defaults."""
    from aop_decommission.schemas import ResourceRecord

    def _make(resource_id: str, **overrides: Any) -> ResourceRecord:
        fields: dict[str, Any] = {
            "resource_id": resource_id,
            "name": overrides.pop("name", resource_id.rsplit("/", 1)[-1] or resource_id),
            "type": overrides.pop("type", "compute.googleapis.com/Instance"),
            "service": overrides.pop("service", "compute"),
            "project": overrides.pop("project", "proj"),
        }
        fields.update(overrides)
        return ResourceRecord(**fields)

    return _make
