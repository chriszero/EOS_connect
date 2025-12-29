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
            EosGraphSensor(coordinator),
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


class EosGraphSensor(CoordinatorEntity, SensorEntity):
    """Sensor exposing data arrays for visualization (ApexCharts)."""

    _attr_has_entity_name = True
    _attr_name = "Plan Data"
    _attr_unique_id_suffix = "plan_data"

    def __init__(self, coordinator: EosConnectCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self._attr_unique_id_suffix}"

    @property
    def native_value(self) -> str:
        """Return timestamp of last update."""
        if self.coordinator.last_run_time:
            return self.coordinator.last_run_time.isoformat()
        return "Unknown"

    @property
    def extra_state_attributes(self):
        """Return arrays for graphing."""
        from homeassistant.util import dt as dt_util
        from datetime import timedelta

        inputs = self.coordinator.last_input_data
        result = self.coordinator.last_result

        if not inputs or not result:
            return {}

        # Time Array (Next 48h)
        now = dt_util.now().replace(minute=0, second=0, microsecond=0)
        time_axis = [(now + timedelta(hours=i)).isoformat() for i in range(48)]

        return {
            "time": time_axis,
            "pv_forecast": inputs.get("pv_forecast", []),
            "load_forecast": inputs.get("load_profile", []),
            "price_forecast": inputs.get("prices", []),
            "plan_ac_charge": result.get("ac_charge", []), # Relative 0-1
            "plan_discharge_allowed": result.get("discharge_allowed", []), # 0/1
            # Can add derived Watts if needed by multiplying with capacity/max_power
        }
