"""Number platform for EOS Energy Optimizer."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import EOSData
from .const import (
    CONF_BATTERY_MAX_SOC,
    CONF_BATTERY_MIN_SOC,
    CONF_MAX_GRID_CHARGE_RATE,
    DEFAULT_BATTERY_MAX_CHARGE,
    DEFAULT_BATTERY_MAX_SOC,
    DEFAULT_BATTERY_MIN_SOC,
    DOMAIN,
)
from .coordinator import EOSDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class EOSNumberEntityDescription(NumberEntityDescription):
    """Describes EOS number entity."""

    value_fn: Callable[[EOSData, dict], float | None]
    set_fn: Callable[[EOSDataUpdateCoordinator, float], Any]


NUMBER_DESCRIPTIONS: tuple[EOSNumberEntityDescription, ...] = (
    EOSNumberEntityDescription(
        key="min_soc",
        translation_key="min_soc",
        name="Minimum SOC",
        icon="mdi:battery-low",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=50,
        native_step=1,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data, config: config.get(CONF_BATTERY_MIN_SOC, DEFAULT_BATTERY_MIN_SOC),
        set_fn=lambda coord, val: coord.api_client.async_set_soc_limits(
            val, coord.config_entry.data.get(CONF_BATTERY_MAX_SOC, DEFAULT_BATTERY_MAX_SOC)
        ),
    ),
    EOSNumberEntityDescription(
        key="max_soc",
        translation_key="max_soc",
        name="Maximum SOC",
        icon="mdi:battery-high",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=50,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data, config: config.get(CONF_BATTERY_MAX_SOC, DEFAULT_BATTERY_MAX_SOC),
        set_fn=lambda coord, val: coord.api_client.async_set_soc_limits(
            coord.config_entry.data.get(CONF_BATTERY_MIN_SOC, DEFAULT_BATTERY_MIN_SOC), val
        ),
    ),
    EOSNumberEntityDescription(
        key="override_charge_power",
        translation_key="override_charge_power",
        name="Override Charge Power",
        icon="mdi:flash",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=NumberDeviceClass.POWER,
        native_min_value=0,
        native_max_value=50000,
        native_step=100,
        mode=NumberMode.BOX,
        value_fn=lambda data, config: data.control.override_power if data.control.override_active else config.get(CONF_MAX_GRID_CHARGE_RATE, DEFAULT_BATTERY_MAX_CHARGE),
        set_fn=lambda coord, val: None,  # Will be handled by button/service
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EOS number entities from a config entry."""
    coordinator: EOSDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        EOSNumber(coordinator, description)
        for description in NUMBER_DESCRIPTIONS
    ]

    async_add_entities(entities)


class EOSNumber(CoordinatorEntity[EOSDataUpdateCoordinator], NumberEntity):
    """Representation of an EOS number entity."""

    entity_description: EOSNumberEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EOSDataUpdateCoordinator,
        description: EOSNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(
            self.coordinator.data,
            dict(self.coordinator.config_entry.data),
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        set_fn = self.entity_description.set_fn
        if set_fn:
            result = set_fn(self.coordinator, value)
            if hasattr(result, "__await__"):
                await result
            await self.coordinator.async_request_refresh()
