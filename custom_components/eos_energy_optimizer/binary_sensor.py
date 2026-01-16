"""Binary sensor platform for EOS Energy Optimizer."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import EOSData
from .const import DOMAIN
from .coordinator import EOSDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class EOSBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes EOS binary sensor entity."""

    value_fn: Callable[[EOSData], bool | None]
    attr_fn: Callable[[EOSData], dict[str, Any]] | None = None


BINARY_SENSOR_DESCRIPTIONS: tuple[EOSBinarySensorEntityDescription, ...] = (
    EOSBinarySensorEntityDescription(
        key="discharge_allowed",
        translation_key="discharge_allowed",
        name="Discharge Allowed",
        icon="mdi:battery-arrow-down",
        value_fn=lambda data: data.control.discharge_allowed,
        attr_fn=lambda data: {
            "discharge_schedule": data.optimization.discharge_allowed[:24] if data.optimization.discharge_allowed else []
        },
    ),
    EOSBinarySensorEntityDescription(
        key="override_active",
        translation_key="override_active",
        name="Override Active",
        icon="mdi:hand-back-left",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda data: data.control.override_active,
        attr_fn=lambda data: {
            "override_end_time": data.control.override_end_time.isoformat() if data.control.override_end_time else None,
            "override_power": data.control.override_power,
        },
    ),
    EOSBinarySensorEntityDescription(
        key="charging_from_grid",
        translation_key="charging_from_grid",
        name="Charging from Grid",
        icon="mdi:transmission-tower-import",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda data: data.control.ac_charge_demand > 0,
    ),
    EOSBinarySensorEntityDescription(
        key="home_appliance_released",
        translation_key="home_appliance_released",
        name="Home Appliance Released",
        icon="mdi:washing-machine",
        value_fn=lambda data: data.optimization.home_appliance_start_hour is not None and data.optimization.home_appliance_start_hour <= 0,
    ),
    EOSBinarySensorEntityDescription(
        key="optimization_ok",
        translation_key="optimization_ok",
        name="Optimization OK",
        icon="mdi:check-circle",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda data: data.optimization_state == "ok",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EOS binary sensors from a config entry."""
    coordinator: EOSDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        EOSBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    ]

    async_add_entities(entities)


class EOSBinarySensor(CoordinatorEntity[EOSDataUpdateCoordinator], BinarySensorEntity):
    """Representation of an EOS binary sensor."""

    entity_description: EOSBinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EOSDataUpdateCoordinator,
        description: EOSBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if self.coordinator.data is None or self.entity_description.attr_fn is None:
            return None
        return self.entity_description.attr_fn(self.coordinator.data)
