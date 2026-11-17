"""Parsing what the scale and the release catalog send."""

from __future__ import annotations

import json

import pytest

from custom_components.hds.api import Probe, Release, ScaleStatus, parse_manifest, parse_probe, parse_status

# A status frame as firmware 3.1.15 sends it (addresses and names are the firmware defaults).
STATUS_FRAME = (
    '{"type":"status","status":"ok","protocol_version":1,"firmware_version":"FW: 3.1.15","grams":0.33,'
    '"ms":158651,"battery_percent":51,"battery_voltage":3.76,"charging":false,"timer_running":false,'
    '"timer_seconds":0,"display_on":true,"low_power":false,"soft_sleep":false,"events_enabled":false,'
    '"rate_hz":2,"interval_ms":500,"wifi_on_boot":true,"wifi_active":true,"wifi_connected":true,'
    '"wifi_mode":"sta","wifi_credentials_saved":true,"mdns_name":"hds","ble_enabled":false,'
    '"ble_connected":false,"ble_buttons_enabled":true,"ble_heartbeat_required":true,"auto_sleep_enabled":true,'
    '"auto_sleep_minutes":15,"quick_boot_enabled":false,"time_on_top":false,"drift_compensation_max_grams":0.050}'
)


def test_status_frame() -> None:
    assert parse_status(STATUS_FRAME) == ScaleStatus("3.1.15", 51, 3.76, False)


def test_firmware_without_prefix_and_charging() -> None:
    frame = json.dumps({"type": "status", "firmware_version": "3.1.16", "battery_percent": 100,
                        "battery_voltage": 4.2, "charging": True})
    assert parse_status(frame) == ScaleStatus("3.1.16", 100, 4.2, True)


@pytest.mark.parametrize(
    "frame",
    [
        '{"grams":0.33,"ms":158783}',  # a weight snapshot has no type
        '{"type":"rate","rate_hz":2}',
        '{"type":"status","firmware_version":"FW: 3.1.15"}',  # no battery fields
        '{"type":"status","firmware_version":"FW: 3.1.15","battery_percent":"n/a","battery_voltage":3.7}',
        "tare",
        "[1,2]",
        "",
    ],
)
def test_other_frames_are_not_status(frame: str) -> None:
    assert parse_status(frame) is None


def test_manifest() -> None:
    manifest = {"model": "hds", "version": "3.1.16",
                "release_notes_url": "https://github.com/decentespresso/openscale/releases/tag/v3.1.16", "releases": []}
    assert parse_manifest(manifest) == Release(
        "3.1.16", "https://github.com/decentespresso/openscale/releases/tag/v3.1.16"
    )


def test_manifest_without_notes_url_links_the_release() -> None:
    assert parse_manifest({"version": "3.2.0"}) == Release(
        "3.2.0", "https://github.com/decentespresso/openscale/releases/tag/v3.2.0"
    )


@pytest.mark.parametrize("manifest", [None, [], {}, {"version": ""}, {"version": "latest"}, {"version": 3}])
def test_unusable_manifest(manifest: object) -> None:
    assert parse_manifest(manifest) is None


def test_probe_names_the_scale() -> None:
    body = '{"operation_id":0,"device_id":"0123456789AB","state":"idle","connected":true,"mdns_name":"hds"}'
    assert parse_probe(body) == Probe("0123456789ab")


@pytest.mark.parametrize("body", ["", "Not found", "[]", "{}", '{"device_id":""}', '{"device_id":7}'])
def test_probe_without_an_id_is_still_an_answer(body: str) -> None:
    assert parse_probe(body) == Probe()
