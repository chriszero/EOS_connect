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
CONF_ENTITY_PRICE = "entity_price"

# EV Settings
CONF_EV_ENABLED = "ev_enabled"
CONF_ENTITY_EV_SOC = "entity_ev_soc"
CONF_ENTITY_EV_CONNECTED = "entity_ev_connected"
CONF_EV_CAPACITY = "ev_capacity_wh"
CONF_EV_MAX_CHARGE_RATE = "ev_max_charge_rate_w"

# Controllable Load (Dishwasher)
CONF_LOAD_ENABLED = "load_enabled"
CONF_LOAD_CONSUMPTION = "load_consumption_wh"
CONF_LOAD_DURATION = "load_duration_h"

# Control Mappings
CONF_CONTROL_CHARGE_LIMIT = "control_charge_limit"
CONF_CONTROL_DISCHARGE_LIMIT = "control_discharge_limit"
CONF_CONTROL_MODE = "control_mode"

# Defaults
DEFAULT_EOS_URL = "192.168.1.1"
DEFAULT_EOS_PORT = 8503
DEFAULT_SCAN_INTERVAL = 900  # 15 minutes
