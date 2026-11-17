"""Shared fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.hds.api import Probe, Release, ScaleStatus

AWAKE = ScaleStatus(firmware="3.1.15", battery_percent=51, battery_voltage=3.76, charging=False)
LATEST = Release(version="3.1.16", url="https://github.com/decentespresso/openscale/releases/tag/v3.1.16")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom_components/hds."""


DEVICE_ID = "0123456789ab"


@pytest.fixture
def scale() -> Iterator[AsyncMock]:
    """The scale's answer to `status`; set return_value to None for an asleep scale.

    The HTTP probe follows it (awake exactly when `status` would answer) and is at `scale.probe`.
    """
    fetch = AsyncMock(return_value=AWAKE)
    fetch.probe = AsyncMock(side_effect=lambda *_: Probe(DEVICE_ID) if fetch.return_value is not None else None)
    with (
        patch("custom_components.hds.coordinator.async_fetch_status", fetch),
        patch("custom_components.hds.config_flow.async_fetch_status", fetch),
        patch("custom_components.hds.coordinator.async_probe", fetch.probe),
        patch("custom_components.hds.config_flow.async_probe", fetch.probe),
    ):
        yield fetch


@pytest.fixture
def catalog() -> Iterator[AsyncMock]:
    """The release catalog's answer; set return_value to None for a failed check."""
    with patch("custom_components.hds.coordinator.async_fetch_release", AsyncMock(return_value=LATEST)) as fetch:
        yield fetch
