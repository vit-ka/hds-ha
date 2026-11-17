"""Config flow: one entry per address, and the scale has to answer."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.hds.api import Probe
from custom_components.hds.const import DOMAIN

from .conftest import AWAKE, DEVICE_ID


async def test_creates_entry_and_normalizes_address(hass: HomeAssistant, scale: AsyncMock, catalog: AsyncMock) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM and not result["errors"]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: " http://HDS.local/ "})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Half Decent Scale" and result["data"] == {CONF_HOST: "hds.local"}

    assert result["result"].unique_id == DEVICE_ID

    # The same scale at a new address is the same entry, which follows it there.
    again = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    again = await hass.config_entries.flow.async_configure(again["flow_id"], {CONF_HOST: "192.0.2.10"})
    assert again["type"] is FlowResultType.ABORT and again["reason"] == "already_configured"
    assert result["result"].data == {CONF_HOST: "192.0.2.10"}


async def test_older_firmware_without_an_id_is_keyed_by_address(
    hass: HomeAssistant, scale: AsyncMock, catalog: AsyncMock
) -> None:
    scale.probe.side_effect = lambda *_: Probe()
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "hds.local"})
    assert result["type"] is FlowResultType.CREATE_ENTRY and result["result"].unique_id == "hds.local"


async def test_asleep_scale_is_refused_then_accepted(hass: HomeAssistant, scale: AsyncMock, catalog: AsyncMock) -> None:
    scale.return_value = None
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "hds.local"})
    assert result["type"] is FlowResultType.FORM and result["errors"] == {"base": "cannot_connect"}

    scale.return_value = AWAKE
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "hds.local"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
