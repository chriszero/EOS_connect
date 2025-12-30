"""Switch platform for EOS Energy Optimizer."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import EOSDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


SWITCH_DESCRIPTIONS: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="15min_refinement",
        translation_key="15min_refinement",
        name="15-Minute Price Refinement",
        icon="mdi:clock-fast",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EOS switch entities."""
    coordinator: EOSDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        EOS15MinRefinementSwitch(coordinator, description)
        for description in SWITCH_DESCRIPTIONS
    ]

    async_add_entities(entities)


class EOS15MinRefinementSwitch(CoordinatorEntity[EOSDataUpdateCoordinator], SwitchEntity):
    """Switch to enable/disable 15-minute price refinement."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EOSDataUpdateCoordinator,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool:
        """Return true if 15-min refinement is enabled."""
        return self.coordinator.refinement_15min_enabled

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on 15-minute refinement."""
        await self.coordinator.async_set_15min_refinement(True)
        self.async_write_ha_state()
        _LOGGER.info("15-minute price refinement enabled")

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off 15-minute refinement."""
        await self.coordinator.async_set_15min_refinement(False)
        self.async_write_ha_state()
        _LOGGER.info("15-minute price refinement disabled")

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional state attributes."""
        data = self.coordinator.data
        if not data:
            return {}

        # Get current 15-min slot info
        now = dt_util.now()
        current_slot = now.hour * 4 + now.minute // 15

        # Get prices for current hour (4 slots)
        hour_start_slot = now.hour * 4
        hour_prices = data.prices_15min[hour_start_slot:hour_start_slot + 4] if data.prices_15min else []

        return {
            "current_15min_slot": current_slot,
            "current_hour_prices": hour_prices,
            "current_15min_price": data.prices_15min[current_slot] if data.prices_15min and current_slot < len(data.prices_15min) else None,
            "hourly_avg_price": data.prices[now.hour] if data.prices and now.hour < len(data.prices) else None,
        }
