"""Constants for the EOS Connect integration."""

DOMAIN = "eos_connect"
CONF_EOS_URL = "eos_url"
CONF_EOS_PORT = "eos_port"

# System Specs
CONF_BATTERY_CAPACITY = "battery_capacity_wh"
CONF_MAX_CHARGE_RATE = "max_charge_rate_w"
CONF_MAX_DISCHARGE_RATE = "max_discharge_rate_w"
CONF_INVERTER_MAX_POWER = "inverter_max_power_w"

# Sensor Mappings
CONF_ENTITY_LOAD = "entity_load"
CONF_ENTITY_PV_FORECAST = "entity_pv_forecast"
CONF_ENTITY_SOC = "entity_soc"

# Control Mappings
CONF_CONTROL_CHARGE_LIMIT = "control_charge_limit"
CONF_CONTROL_DISCHARGE_LIMIT = "control_discharge_limit"
CONF_CONTROL_MODE = "control_mode"

# Defaults
DEFAULT_EOS_URL = "192.168.1.1"
DEFAULT_EOS_PORT = 8503
DEFAULT_SCAN_INTERVAL = 900  # 15 minutes
