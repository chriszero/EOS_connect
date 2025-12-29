"""Select platform for EOS Energy Optimizer."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, InverterMode, INVERTER_MODE_NAMES
from .coordinator import EOSDataUpdateCoordinator


MODE_OPTIONS = {
    "Auto": InverterMode.AUTO,
    "Charge from Grid": InverterMode.CHARGE_FROM_GRID,
    "Avoid Discharge": InverterMode.AVOID_DISCHARGE,
    "Discharge Allowed": InverterMode.DISCHARGE_ALLOWED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EOS select entities from a config entry."""
    coordinator: EOSDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities([EOSModeSelect(coordinator)])


class EOSModeSelect(CoordinatorEntity[EOSDataUpdateCoordinator], SelectEntity):
    """Select entity for inverter mode."""

    _attr_has_entity_name = True
    _attr_name = "Inverter Mode Control"
    _attr_icon = "mdi:solar-power"
    _attr_options = list(MODE_OPTIONS.keys())

    def __init__(self, coordinator: EOSDataUpdateCoordinator) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_mode_select"
        self._attr_device_info = coordinator.device_info

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if self.coordinator.data is None:
            return None
        mode = self.coordinator.data.control.mode
        return INVERTER_MODE_NAMES.get(mode, "Auto")

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        mode = MODE_OPTIONS.get(option, InverterMode.AUTO)
        await self.coordinator.api_client.async_set_mode(mode)
        await self.coordinator.async_request_refresh()
