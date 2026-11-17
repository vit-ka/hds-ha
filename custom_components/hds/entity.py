"""Shared entity base: one device per scale; entities keep their last value while the scale sleeps."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import HdsCoordinator


class HdsEntity(CoordinatorEntity[HdsCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: HdsCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=NAME,
            manufacturer="Decent Espresso",
            model=NAME,
            configuration_url=f"http://{coordinator.host}",
        )

    @property
    def available(self) -> bool:
        """Available once the scale has answered at least once, asleep or not (docs/adr/0001)."""
        return self.coordinator.data is not None and self.coordinator.data.status is not None
