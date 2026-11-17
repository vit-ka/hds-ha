"""Polls the scale and the release catalog; keeps the last answers while the scale sleeps (docs/adr/0001)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Self

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .api import Release, ScaleStatus, async_fetch_release, async_fetch_status, async_probe
from .const import DOMAIN, RECHECK_INTERVAL, RELEASE_INTERVAL, SCAN_INTERVAL, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)

type HdsConfigEntry = ConfigEntry[HdsCoordinator]


@dataclass(frozen=True)
class HdsData:
    """The last status the scale gave, when it gave it, and the newest firmware known."""

    status: ScaleStatus | None = None
    last_seen: datetime | None = None
    release: Release | None = None
    release_checked: datetime | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            ScaleStatus.from_dict(data["status"]) if data.get("status") else None,
            dt_util.parse_datetime(data["last_seen"]) if data.get("last_seen") else None,
            Release.from_dict(data["release"]) if data.get("release") else None,
            dt_util.parse_datetime(data["release_checked"]) if data.get("release_checked") else None,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.as_dict() if self.status else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "release": self.release.as_dict() if self.release else None,
            "release_checked": self.release_checked.isoformat() if self.release_checked else None,
        }


class HdsCoordinator(DataUpdateCoordinator[HdsData]):
    config_entry: HdsConfigEntry

    def __init__(self, hass: HomeAssistant, entry: HdsConfigEntry) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.host: str = entry.data[CONF_HOST]
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self._known = HdsData()
        # Not stored: after a restart the first probe that finds the scale awake asks once.
        self._was_awake = False
        self._asked: datetime | None = None

    async def async_load(self) -> None:
        if stored := await self._store.async_load():
            try:
                self._known = HdsData.from_dict(stored)
            except (KeyError, TypeError, ValueError):
                _LOGGER.warning("Ignoring unreadable stored state for %s", self.host)

    def _should_ask(self, now: datetime) -> bool:
        """Whether an awake scale gets a `status` request on this poll.

        Each request restarts its 15-minute auto-off countdown, so one per wake. While it charges it
        stays awake anyway, and if it is still awake long after the last request something else is
        keeping it awake, so asking again costs nothing.
        """
        status = self._known.status
        return (not self._was_awake or status is None or status.charging or self._asked is None
                or now - self._asked >= RECHECK_INTERVAL)

    async def _async_update_data(self) -> HdsData:
        """Never fails: no answer from the scale is its normal state, and the catalog can wait."""
        session, now, known = async_get_clientsession(self.hass), dt_util.utcnow(), self._known
        awake = await async_probe(session, self.host) is not None
        if awake and self._should_ask(now) and (status := await async_fetch_status(session, self.host)):
            known, self._asked = replace(known, status=status, last_seen=now), now
        self._was_awake = awake
        if known.release_checked is None or now - known.release_checked >= RELEASE_INTERVAL:
            # A failed check keeps the release already known and is retried on the next poll.
            if release := await async_fetch_release(session):
                known = replace(known, release=release, release_checked=now)
        if known != self._known:
            self._known = known
            self._store.async_delay_save(known.as_dict, 5)
        return known
