"""Battery level and voltage."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfElectricPotential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import ScaleStatus
from .coordinator import HdsConfigEntry, HdsCoordinator
from .entity import HdsEntity


@dataclass(frozen=True, kw_only=True)
class HdsSensorDescription(SensorEntityDescription):
    value: Callable[[ScaleStatus], float | int]


SENSORS: tuple[HdsSensorDescription, ...] = (
    HdsSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda status: status.battery_percent,
    ),
    HdsSensorDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        value=lambda status: status.battery_voltage,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: HdsConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities(HdsSensor(entry.runtime_data, description) for description in SENSORS)


class HdsSensor(HdsEntity, SensorEntity):
    entity_description: HdsSensorDescription

    def __init__(self, coordinator: HdsCoordinator, description: HdsSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | int | None:
        status = self.coordinator.data.status
        return self.entity_description.value(status) if status else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """When the scale last answered: the value above is from then, not from now."""
        seen = self.coordinator.data.last_seen
        return {"last_seen": seen.isoformat()} if seen else None
