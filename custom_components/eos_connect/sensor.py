"""Sensor platform for EOS Connect."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EosConnectCoordinator

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the EOS Connect sensors."""
    coordinator: EosConnectCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            EosStatusSensor(coordinator),
            EosActionSensor(coordinator),
        ]
    )


class EosStatusSensor(CoordinatorEntity, SensorEntity):
    """Representation of the EOS Connection/Optimization Status."""

    _attr_has_entity_name = True
    _attr_name = "Status"
    _attr_unique_id_suffix = "status"

    def __init__(self, coordinator: EosConnectCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self._attr_unique_id_suffix}"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self.coordinator.optimization_status


class EosActionSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing the current recommended action."""

    _attr_has_entity_name = True
    _attr_name = "Recommended Action"
    _attr_unique_id_suffix = "action"

    def __init__(self, coordinator: EosConnectCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self._attr_unique_id_suffix}"

    @property
    def native_value(self) -> str:
        """Return the state."""
        # Extract from last result
        result = self.coordinator.last_result
        if not result:
            return "Unknown"

        ac_charge = result.get("ac_charge", [])
        discharge = result.get("discharge_allowed", [])

        if not ac_charge:
            return "No Data"

        current_charge = ac_charge[0]
        current_discharge = bool(discharge[0])

        if current_charge > 0:
            return f"Charge Grid ({int(current_charge*100)}%)"
        elif not current_discharge:
            return "Hold (No Discharge)"
        else:
            return "Discharge Allowed"

    @property
    def extra_state_attributes(self):
        """Return attributes."""
        return {
            "last_result": self.coordinator.last_result
        }
