"""Sensor platform for EOS Energy Optimizer."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import EOSData
from .const import DOMAIN, INVERTER_MODE_NAMES
from .coordinator import EOSDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class EOSSensorEntityDescription(SensorEntityDescription):
    """Describes EOS sensor entity."""

    value_fn: Callable[[EOSData], Any]
    attr_fn: Callable[[EOSData], dict[str, Any]] | None = None


SENSOR_DESCRIPTIONS: tuple[EOSSensorEntityDescription, ...] = (
    # Control sensors
    EOSSensorEntityDescription(
        key="inverter_mode",
        translation_key="inverter_mode",
        name="Inverter Mode",
        icon="mdi:solar-power",
        value_fn=lambda data: INVERTER_MODE_NAMES.get(data.control.mode, "Unknown"),
        attr_fn=lambda data: {"mode_value": data.control.mode.value},
    ),
    EOSSensorEntityDescription(
        key="ac_charge_demand",
        translation_key="ac_charge_demand",
        name="AC Charge Demand",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:transmission-tower-import",
        value_fn=lambda data: round(data.control.ac_charge_demand, 0),
    ),
    EOSSensorEntityDescription(
        key="dc_charge_demand",
        translation_key="dc_charge_demand",
        name="DC Charge Demand",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:solar-power-variant",
        value_fn=lambda data: round(data.control.dc_charge_demand, 0),
    ),
    # Battery sensors
    EOSSensorEntityDescription(
        key="battery_soc",
        translation_key="battery_soc",
        name="Battery SOC",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery",
        value_fn=lambda data: round(data.battery.soc, 1),
    ),
    EOSSensorEntityDescription(
        key="battery_usable_energy",
        translation_key="battery_usable_energy",
        name="Battery Usable Energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery-charging",
        value_fn=lambda data: round(data.battery.usable_energy_wh, 0),
    ),
    EOSSensorEntityDescription(
        key="battery_dynamic_max_charge",
        translation_key="battery_dynamic_max_charge",
        name="Battery Dynamic Max Charge Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery-arrow-up",
        value_fn=lambda data: round(data.battery.dynamic_max_charge_power, 0),
    ),
    # Optimization sensors
    EOSSensorEntityDescription(
        key="optimization_cost",
        translation_key="optimization_cost",
        name="Optimization Total Cost",
        native_unit_of_measurement="€",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:currency-eur",
        value_fn=lambda data: round(data.optimization.cost_total, 2),
    ),
    EOSSensorEntityDescription(
        key="optimization_losses",
        translation_key="optimization_losses",
        name="Optimization Total Losses",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:lightning-bolt-outline",
        value_fn=lambda data: round(data.optimization.losses_total, 0),
    ),
    EOSSensorEntityDescription(
        key="home_appliance_start",
        translation_key="home_appliance_start",
        name="Home Appliance Start Hour",
        icon="mdi:washing-machine",
        value_fn=lambda data: data.optimization.home_appliance_start_hour,
    ),
    EOSSensorEntityDescription(
        key="current_price",
        translation_key="current_price",
        name="Current Electricity Price",
        native_unit_of_measurement="€/kWh",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:currency-eur",
        value_fn=lambda data: round(data.prices[0], 4) if data.prices else None,
        attr_fn=lambda data: {"prices_48h": data.prices[:48] if data.prices else []},
    ),
    EOSSensorEntityDescription(
        key="current_pv_forecast",
        translation_key="current_pv_forecast",
        name="Current PV Forecast",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:solar-power",
        value_fn=lambda data: round(data.pv_forecast[0], 0) if data.pv_forecast else None,
        attr_fn=lambda data: {"forecast_48h": data.pv_forecast[:48] if data.pv_forecast else []},
    ),
    # Forecast sensors with 48h data as attributes
    EOSSensorEntityDescription(
        key="soc_forecast",
        translation_key="soc_forecast",
        name="SOC Forecast",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        icon="mdi:battery-clock",
        value_fn=lambda data: round(data.optimization.soc_forecast[0], 1) if data.optimization.soc_forecast else None,
        attr_fn=lambda data: {"forecast_48h": data.optimization.soc_forecast[:48] if data.optimization.soc_forecast else []},
    ),
    EOSSensorEntityDescription(
        key="grid_import_forecast",
        translation_key="grid_import_forecast",
        name="Grid Import Forecast",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        icon="mdi:transmission-tower-import",
        value_fn=lambda data: round(data.optimization.grid_import[0], 0) if data.optimization.grid_import else None,
        attr_fn=lambda data: {"forecast_48h": data.optimization.grid_import[:48] if data.optimization.grid_import else []},
    ),
    EOSSensorEntityDescription(
        key="grid_export_forecast",
        translation_key="grid_export_forecast",
        name="Grid Export Forecast",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        icon="mdi:transmission-tower-export",
        value_fn=lambda data: round(data.optimization.grid_export[0], 0) if data.optimization.grid_export else None,
        attr_fn=lambda data: {"forecast_48h": data.optimization.grid_export[:48] if data.optimization.grid_export else []},
    ),
    # Status sensors
    EOSSensorEntityDescription(
        key="optimization_state",
        translation_key="optimization_state",
        name="Optimization State",
        icon="mdi:state-machine",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.optimization_state,
    ),
    EOSSensorEntityDescription(
        key="last_optimization",
        translation_key="last_optimization",
        name="Last Optimization",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:clock-check",
        value_fn=lambda data: data.last_optimization,
    ),
    EOSSensorEntityDescription(
        key="next_optimization",
        translation_key="next_optimization",
        name="Next Optimization",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:clock-fast",
        value_fn=lambda data: data.next_optimization,
    ),
    EOSSensorEntityDescription(
        key="override_end_time",
        translation_key="override_end_time",
        name="Override End Time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:timer-off",
        value_fn=lambda data: data.control.override_end_time,
    ),
    EOSSensorEntityDescription(
        key="override_power",
        translation_key="override_power",
        name="Override Charge Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:flash",
        value_fn=lambda data: round(data.control.override_power, 0) if data.control.override_active else 0,
    ),
    # Savings sensors
    EOSSensorEntityDescription(
        key="savings_today",
        translation_key="savings_today",
        name="Savings Today",
        native_unit_of_measurement="€",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:piggy-bank",
        value_fn=lambda data: round(data.savings.today_savings_eur, 2),
        attr_fn=lambda data: {
            "grid_cost_today": round(data.savings.today_grid_cost_eur, 2),
            "avg_charge_price": round(data.savings.avg_charge_price, 4),
            "avg_discharge_price": round(data.savings.avg_discharge_price, 4),
        },
    ),
    EOSSensorEntityDescription(
        key="savings_total",
        translation_key="savings_total",
        name="Savings Total",
        native_unit_of_measurement="€",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:cash-multiple",
        value_fn=lambda data: round(data.savings.total_savings_eur, 2),
        attr_fn=lambda data: {
            "total_grid_cost": round(data.savings.total_grid_cost_eur, 2),
            "total_feed_in_revenue": round(data.savings.total_feed_in_revenue_eur, 2),
            "total_charged_kwh": round(data.savings.total_charged_kwh, 2),
            "total_discharged_kwh": round(data.savings.total_discharged_kwh, 2),
            "total_pv_charged_kwh": round(data.savings.total_pv_charged_kwh, 2),
            "total_grid_charged_kwh": round(data.savings.total_grid_charged_kwh, 2),
            "total_grid_import_kwh": round(data.savings.total_grid_import_kwh, 2),
            "total_grid_export_kwh": round(data.savings.total_grid_export_kwh, 2),
        },
    ),
    EOSSensorEntityDescription(
        key="session_savings",
        translation_key="session_savings",
        name="Session Savings",
        native_unit_of_measurement="€",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:timer-sand",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: round(data.savings.session_savings_eur, 2),
        attr_fn=lambda data: {
            "session_charged_kwh": round(data.savings.session_charged_kwh, 2),
            "session_discharged_kwh": round(data.savings.session_discharged_kwh, 2),
            "session_pv_charged_kwh": round(data.savings.session_pv_charged_kwh, 2),
            "session_grid_charged_kwh": round(data.savings.session_grid_charged_kwh, 2),
        },
    ),
    EOSSensorEntityDescription(
        key="pv_charged_today",
        translation_key="pv_charged_today",
        name="PV Charged Today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:solar-power",
        value_fn=lambda data: round(data.savings.today_pv_charged_kwh, 2),
        attr_fn=lambda data: {
            "total_pv_charged_kwh": round(data.savings.total_pv_charged_kwh, 2),
            "pv_charge_value_eur": round(data.savings.today_pv_charged_kwh * 0.08, 2),  # Opportunity cost
        },
    ),
    EOSSensorEntityDescription(
        key="grid_charged_today",
        translation_key="grid_charged_today",
        name="Grid Charged Today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:transmission-tower-import",
        value_fn=lambda data: round(data.savings.today_grid_charged_kwh, 2),
        attr_fn=lambda data: {
            "total_grid_charged_kwh": round(data.savings.total_grid_charged_kwh, 2),
            "grid_cost_today_eur": round(data.savings.today_grid_cost_eur, 2),
        },
    ),
    EOSSensorEntityDescription(
        key="avg_charge_price",
        translation_key="avg_charge_price",
        name="Average Charge Price",
        native_unit_of_measurement="€/kWh",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery-arrow-down-outline",
        value_fn=lambda data: round(data.savings.avg_charge_price, 4) if data.savings.avg_charge_price > 0 else None,
    ),
    EOSSensorEntityDescription(
        key="avg_discharge_price",
        translation_key="avg_discharge_price",
        name="Average Discharge Price",
        native_unit_of_measurement="€/kWh",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery-arrow-up-outline",
        value_fn=lambda data: round(data.savings.avg_discharge_price, 4) if data.savings.avg_discharge_price > 0 else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EOS sensors from a config entry."""
    coordinator: EOSDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        EOSSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    ]

    async_add_entities(entities)


class EOSSensor(CoordinatorEntity[EOSDataUpdateCoordinator], SensorEntity):
    """Representation of an EOS sensor."""

    entity_description: EOSSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EOSDataUpdateCoordinator,
        description: EOSSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if self.coordinator.data is None or self.entity_description.attr_fn is None:
            return None
        return self.entity_description.attr_fn(self.coordinator.data)
