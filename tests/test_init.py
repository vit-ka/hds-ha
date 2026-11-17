"""Setup, entities, and what happens while the scale sleeps."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import CONF_HOST, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.hds.const import DOMAIN, RECHECK_INTERVAL, RELEASE_INTERVAL, SCAN_INTERVAL

from .conftest import AWAKE, LATEST

BATTERY = "sensor.half_decent_scale_battery"
VOLTAGE = "sensor.half_decent_scale_battery_voltage"
CHARGING = "binary_sensor.half_decent_scale_charging"
FIRMWARE = "update.half_decent_scale_firmware"


async def setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "hds.local"}, unique_id="hds.local")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory, after: timedelta = SCAN_INTERVAL) -> None:
    freezer.tick(after)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_awake_scale(hass: HomeAssistant, scale: AsyncMock, catalog: AsyncMock) -> None:
    await setup(hass)
    battery = hass.states.get(BATTERY)
    assert battery.state == "51" and battery.attributes["device_class"] == "battery"
    assert dt_util.parse_datetime(battery.attributes["last_seen"]) is not None
    assert hass.states.get(VOLTAGE).state == "3.76"
    assert hass.states.get(CHARGING).state == STATE_OFF
    firmware = hass.states.get(FIRMWARE)
    assert firmware.state == STATE_ON
    assert firmware.attributes["installed_version"] == "3.1.15" and firmware.attributes["latest_version"] == "3.1.16"
    assert firmware.attributes["release_url"] == LATEST.url
    assert not firmware.attributes["supported_features"]  # reports only, cannot install


async def test_up_to_date_firmware(hass: HomeAssistant, scale: AsyncMock, catalog: AsyncMock) -> None:
    scale.return_value = replace(AWAKE, firmware="3.1.16", charging=True)
    await setup(hass)
    assert hass.states.get(FIRMWARE).state == STATE_OFF
    assert hass.states.get(CHARGING).state == STATE_ON


async def test_never_seen_scale_is_unavailable_until_it_answers(
    hass: HomeAssistant, scale: AsyncMock, catalog: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    scale.return_value = None
    await setup(hass)
    assert all(hass.states.get(entity).state == STATE_UNAVAILABLE for entity in (BATTERY, VOLTAGE, CHARGING, FIRMWARE))
    scale.return_value = AWAKE
    await poll(hass, freezer)
    assert hass.states.get(BATTERY).state == "51"


async def test_asleep_scale_keeps_last_values(
    hass: HomeAssistant, scale: AsyncMock, catalog: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    await setup(hass)
    seen = hass.states.get(BATTERY).attributes["last_seen"]
    scale.return_value = None
    await poll(hass, freezer)
    battery = hass.states.get(BATTERY)
    assert battery.state == "51" and battery.attributes["last_seen"] == seen
    assert hass.states.get(FIRMWARE).attributes["installed_version"] == "3.1.15"

    scale.return_value = replace(AWAKE, battery_percent=48)
    await poll(hass, freezer)
    battery = hass.states.get(BATTERY)
    assert battery.state == "48" and battery.attributes["last_seen"] != seen


async def test_status_is_asked_once_per_wake_on_battery(
    hass: HomeAssistant, scale: AsyncMock, catalog: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """Each `status` request restarts the scale's auto-off countdown, so staying awake is not a reason to ask."""
    await setup(hass)
    assert scale.await_count == 1
    await poll(hass, freezer)
    await poll(hass, freezer)
    assert scale.await_count == 1 and scale.probe.await_count == 3

    scale.return_value = None  # asleep: probed, never asked
    await poll(hass, freezer)
    assert scale.await_count == 1
    scale.return_value = replace(AWAKE, battery_percent=47)  # the next wake is asked once
    await poll(hass, freezer)
    await poll(hass, freezer)
    assert scale.await_count == 2 and hass.states.get(BATTERY).state == "47"


async def test_status_is_asked_again_when_still_awake_after_the_recheck_interval(
    hass: HomeAssistant, scale: AsyncMock, catalog: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    await setup(hass)
    await poll(hass, freezer, RECHECK_INTERVAL - SCAN_INTERVAL)
    assert scale.await_count == 1
    await poll(hass, freezer)
    assert scale.await_count == 2


async def test_charging_scale_is_asked_every_poll(
    hass: HomeAssistant, scale: AsyncMock, catalog: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """It stays awake while charging whatever we do, and the level is moving."""
    scale.return_value = replace(AWAKE, charging=True)
    await setup(hass)
    await poll(hass, freezer)
    scale.return_value = replace(AWAKE, charging=True, battery_percent=60)
    await poll(hass, freezer)
    assert scale.await_count == 3 and hass.states.get(BATTERY).state == "60"

    scale.return_value = replace(AWAKE, charging=False, battery_percent=61)  # unplugged: seen once, then rationed
    await poll(hass, freezer)
    await poll(hass, freezer)
    assert scale.await_count == 4 and hass.states.get(CHARGING).state == STATE_OFF


async def test_failed_catalog_claims_no_update_and_is_retried(
    hass: HomeAssistant, scale: AsyncMock, catalog: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    catalog.return_value = None
    await setup(hass)
    firmware = hass.states.get(FIRMWARE)
    assert firmware.state == STATE_OFF and firmware.attributes["latest_version"] == "3.1.15"
    catalog.return_value = LATEST
    await poll(hass, freezer)  # retried on the next poll, not after RELEASE_INTERVAL
    assert hass.states.get(FIRMWARE).state == STATE_ON


async def test_catalog_is_read_every_release_interval_even_while_asleep(
    hass: HomeAssistant, scale: AsyncMock, catalog: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    await setup(hass)
    scale.return_value = None
    await poll(hass, freezer)
    assert catalog.await_count == 1
    catalog.return_value = replace(LATEST, version="3.1.17")
    await poll(hass, freezer, RELEASE_INTERVAL + SCAN_INTERVAL)
    assert catalog.await_count == 2
    assert hass.states.get(FIRMWARE).attributes["latest_version"] == "3.1.17"


async def test_values_survive_a_restart_while_asleep(
    hass: HomeAssistant,
    scale: AsyncMock,
    catalog: AsyncMock,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    entry = await setup(hass)
    await poll(hass, freezer, timedelta(seconds=10))  # let the delayed save run
    stored = hass_storage[f"{DOMAIN}.{entry.entry_id}"]["data"]
    assert stored["status"] == AWAKE.as_dict() and stored["release"] == LATEST.as_dict()

    scale.return_value = None
    catalog.return_value = None
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(BATTERY).state == "51"
    assert hass.states.get(FIRMWARE).attributes["latest_version"] == "3.1.16"


async def test_unreadable_store_is_ignored(
    hass: HomeAssistant, scale: AsyncMock, catalog: AsyncMock, hass_storage: dict[str, Any]
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "hds.local"}, unique_id="hds.local")
    hass_storage[f"{DOMAIN}.{entry.entry_id}"] = {"version": 1, "minor_version": 1, "key": f"{DOMAIN}.{entry.entry_id}",
                                                  "data": {"status": {"firmware": "3.1.15"}}}
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(BATTERY).state == "51"


async def test_unload(hass: HomeAssistant, scale: AsyncMock, catalog: AsyncMock) -> None:
    entry = await setup(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert hass.states.get(BATTERY).state == STATE_UNAVAILABLE
