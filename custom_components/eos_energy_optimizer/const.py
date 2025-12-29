"""Constants for the EOS Energy Optimizer integration."""
from __future__ import annotations

from enum import IntEnum
from typing import Final

DOMAIN: Final = "eos_energy_optimizer"
MANUFACTURER: Final = "EOS Energy Optimizer"

# Configuration keys
CONF_EOS_SERVER: Final = "eos_server"
CONF_EOS_PORT: Final = "eos_port"
CONF_EOS_SOURCE: Final = "eos_source"
CONF_TIME_FRAME: Final = "time_frame"
CONF_REFRESH_TIME: Final = "refresh_time"
CONF_BATTERY_CAPACITY: Final = "battery_capacity_wh"
CONF_BATTERY_CHARGE_EFFICIENCY: Final = "battery_charge_efficiency"
CONF_BATTERY_DISCHARGE_EFFICIENCY: Final = "battery_discharge_efficiency"
CONF_BATTERY_MAX_CHARGE_POWER: Final = "battery_max_charge_power_w"
CONF_BATTERY_MIN_SOC: Final = "battery_min_soc"
CONF_BATTERY_MAX_SOC: Final = "battery_max_soc"
CONF_BATTERY_SOC_SENSOR: Final = "battery_soc_sensor"
CONF_LOAD_SENSOR: Final = "load_sensor"
CONF_PV_FORECAST_SOURCE: Final = "pv_forecast_source"
CONF_PV_SYSTEMS: Final = "pv_systems"
CONF_PRICE_SOURCE: Final = "price_source"
CONF_TIBBER_TOKEN: Final = "tibber_token"
CONF_FEED_IN_PRICE: Final = "feed_in_price"
CONF_MAX_GRID_CHARGE_RATE: Final = "max_grid_charge_rate"
CONF_MAX_PV_CHARGE_RATE: Final = "max_pv_charge_rate"
CONF_CHARGING_CURVE_ENABLED: Final = "charging_curve_enabled"

# Default values
DEFAULT_EOS_PORT: Final = 8503
DEFAULT_EVOPT_PORT: Final = 7050
DEFAULT_TIME_FRAME: Final = 3600
DEFAULT_REFRESH_TIME: Final = 3
DEFAULT_BATTERY_CAPACITY: Final = 10000
DEFAULT_BATTERY_EFFICIENCY: Final = 0.93
DEFAULT_BATTERY_MAX_CHARGE: Final = 5000
DEFAULT_BATTERY_MIN_SOC: Final = 5
DEFAULT_BATTERY_MAX_SOC: Final = 95
DEFAULT_FEED_IN_PRICE: Final = 0.08

# EOS Sources
EOS_SOURCE_EOS: Final = "eos_server"
EOS_SOURCE_EVOPT: Final = "evopt"

# Price sources - use HA sensors from existing integrations
PRICE_SOURCE_HA_SENSOR: Final = "ha_sensor"
PRICE_SOURCE_FIXED: Final = "fixed_24h"

# PV Forecast sources - use HA sensors from existing integrations
PV_SOURCE_HA_SENSOR: Final = "ha_sensor"

# HA Sensor entity config keys
CONF_PV_FORECAST_ENTITY: Final = "pv_forecast_entity"
CONF_PRICE_ENTITY: Final = "price_entity"
CONF_FIXED_PRICE: Final = "fixed_price"


class InverterMode(IntEnum):
    """Inverter control modes."""

    AUTO = -2
    STARTUP = -1
    CHARGE_FROM_GRID = 0
    AVOID_DISCHARGE = 1
    DISCHARGE_ALLOWED = 2


INVERTER_MODE_NAMES: Final = {
    InverterMode.AUTO: "Auto",
    InverterMode.STARTUP: "Startup",
    InverterMode.CHARGE_FROM_GRID: "Charge from Grid",
    InverterMode.AVOID_DISCHARGE: "Avoid Discharge",
    InverterMode.DISCHARGE_ALLOWED: "Discharge Allowed",
}

# Update intervals
UPDATE_INTERVAL_OPTIMIZATION: Final = 180  # 3 minutes default
UPDATE_INTERVAL_STATUS: Final = 30  # 30 seconds for status updates

# Service names
SERVICE_SET_MODE: Final = "set_mode"
SERVICE_SET_OVERRIDE: Final = "set_override"
SERVICE_CLEAR_OVERRIDE: Final = "clear_override"
SERVICE_REFRESH_OPTIMIZATION: Final = "refresh_optimization"
SERVICE_SET_SOC_LIMITS: Final = "set_soc_limits"

# Platforms
PLATFORMS: Final = ["sensor", "binary_sensor", "select", "number", "button"]
