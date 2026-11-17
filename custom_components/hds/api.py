"""Talking to the scale (WebSocket `status`) and to the firmware release catalog."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Self

import aiohttp

from .const import MANIFEST_URL, PROBE_TIMEOUT, RELEASE_TIMEOUT, RELEASE_URL, STATUS_TIMEOUT

VERSION = re.compile(r"\d+\.\d+\.\d+(?:[-.][0-9A-Za-z.]+)?")


@dataclass(frozen=True)
class ScaleStatus:
    """What one `status` frame says about power and firmware."""

    firmware: str
    battery_percent: int
    battery_voltage: float
    charging: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(str(data["firmware"]), int(data["battery_percent"]), float(data["battery_voltage"]),
                   bool(data["charging"]))

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Release:
    """The newest published stable firmware."""

    version: str
    url: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(str(data["version"]), str(data["url"]))

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_status(text: str) -> ScaleStatus | None:
    """A status frame, or None for anything else the socket sends (weight snapshots, acks, junk)."""
    try:
        frame = json.loads(text)
        if not isinstance(frame, dict) or frame.get("type") != "status":
            return None
        # The scale reports "FW: 3.1.16"; keep the bare version so it compares with the catalog's.
        version = VERSION.search(str(frame["firmware_version"]))
        return ScaleStatus(version.group() if version else str(frame["firmware_version"]).strip(),
                           int(frame["battery_percent"]), float(frame["battery_voltage"]), bool(frame["charging"]))
    except (ValueError, KeyError, TypeError):
        return None


def parse_manifest(manifest: Any) -> Release | None:
    """The catalog's top-level entry is the latest stable release."""
    if not isinstance(manifest, dict) or not VERSION.fullmatch(version := str(manifest.get("version", ""))):
        return None
    return Release(version, str(manifest.get("release_notes_url") or RELEASE_URL.format(version=version)))


@dataclass(frozen=True)
class Probe:
    """An answer to a plain HTTP request: the scale is awake. Firmware 3.1.15+ also names itself."""

    device_id: str | None = None


def parse_probe(text: str) -> Probe:
    try:
        device_id = json.loads(text).get("device_id")
    except (ValueError, AttributeError):
        return Probe()
    return Probe(device_id.lower() if isinstance(device_id, str) and device_id else None)


async def async_probe(session: aiohttp.ClientSession, host: str) -> Probe | None:
    """Is the scale awake? Plain HTTP, which unlike a WebSocket client does not keep it from sleeping.

    Any HTTP answer counts, so firmware without this route (a 404) still reads as awake.
    """
    try:
        async with asyncio.timeout(PROBE_TIMEOUT), session.get(f"http://{host}/setup/wifi/status") as response:
            return parse_probe(await response.text()) if response.ok else Probe()
    except (aiohttp.ClientError, TimeoutError, OSError):
        return None


async def async_fetch_status(session: aiohttp.ClientSession, host: str) -> ScaleStatus | None:
    """Ask the scale for its status. None means it did not answer, which is what an asleep scale does.

    While this connection is open the scale counts a WebSocket client and restarts its auto-off
    countdown, so callers ration it (docs/adr/0001).
    """
    try:
        async with asyncio.timeout(STATUS_TIMEOUT), session.ws_connect(f"ws://{host}/snapshot") as ws:
            await ws.send_str("status")
            async for message in ws:
                if message.type is aiohttp.WSMsgType.TEXT and (status := parse_status(message.data)):
                    return status
    except (aiohttp.ClientError, TimeoutError, OSError):
        return None
    return None


async def async_fetch_release(session: aiohttp.ClientSession) -> Release | None:
    """The latest stable firmware from GitHub. None when it cannot be read."""
    try:
        async with asyncio.timeout(RELEASE_TIMEOUT), session.get(MANIFEST_URL) as response:
            response.raise_for_status()
            # GitHub serves release assets as application/octet-stream.
            return parse_manifest(json.loads(await response.text()))
    except (aiohttp.ClientError, TimeoutError, OSError, ValueError):
        return None
