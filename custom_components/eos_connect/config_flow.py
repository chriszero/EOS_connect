"""Config flow for EOS Connect integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_EOS_URL,
    CONF_EOS_PORT,
    CONF_BATTERY_CAPACITY,
    CONF_MAX_CHARGE_RATE,
    CONF_MAX_DISCHARGE_RATE,
    CONF_INVERTER_MAX_POWER,
    CONF_ENTITY_LOAD,
    CONF_ENTITY_PV_FORECAST,
    CONF_ENTITY_SOC,
    CONF_ENTITY_PRICE,
    CONF_EV_ENABLED,
    CONF_ENTITY_EV_SOC,
    CONF_ENTITY_EV_CONNECTED,
    CONF_EV_CAPACITY,
    CONF_EV_MAX_CHARGE_RATE,
    CONF_LOAD_ENABLED,
    CONF_LOAD_CONSUMPTION,
    CONF_LOAD_DURATION,
    CONF_CONTROL_CHARGE_LIMIT,
    CONF_CONTROL_DISCHARGE_LIMIT,
    CONF_CONTROL_MODE,
    DEFAULT_EOS_URL,
    DEFAULT_EOS_PORT,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EOS_URL, default=DEFAULT_EOS_URL): str,
        vol.Required(CONF_EOS_PORT, default=DEFAULT_EOS_PORT): int,
        vol.Required(CONF_BATTERY_CAPACITY, default=10000): int,
        vol.Required(CONF_MAX_CHARGE_RATE, default=5000): int,
        vol.Required(CONF_MAX_DISCHARGE_RATE, default=5000): int,
        vol.Required(CONF_INVERTER_MAX_POWER, default=10000): int,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EOS Connect."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._config = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step (Connection & System Specs)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._config.update(user_input)
            return await self.async_step_sensors()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the sensor mappings step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._config.update(user_input)
            return await self.async_step_ev()

        schema = vol.Schema(
            {
                vol.Required(CONF_ENTITY_SOC): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_ENTITY_LOAD): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_ENTITY_PV_FORECAST): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["sensor", "weather"])
                ),
                vol.Optional(CONF_ENTITY_PRICE): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            }
        )

        return self.async_show_form(
            step_id="sensors", data_schema=schema, errors=errors
        )

    async def async_step_ev(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the EV step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._config.update(user_input)
            return await self.async_step_load()

        schema = vol.Schema(
            {
                vol.Required(CONF_EV_ENABLED, default=False): bool,
                vol.Optional(CONF_ENTITY_EV_SOC): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_ENTITY_EV_CONNECTED): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),
                vol.Optional(CONF_EV_CAPACITY, default=50000): int,
                vol.Optional(CONF_EV_MAX_CHARGE_RATE, default=11000): int,
            }
        )
        return self.async_show_form(step_id="ev", data_schema=schema, errors=errors)

    async def async_step_load(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the Controllable Load step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._config.update(user_input)
            return await self.async_step_controls()

        schema = vol.Schema(
            {
                vol.Required(CONF_LOAD_ENABLED, default=False): bool,
                vol.Optional(CONF_LOAD_CONSUMPTION, default=1000): int,
                vol.Optional(CONF_LOAD_DURATION, default=2): int,
            }
        )
        return self.async_show_form(step_id="load", data_schema=schema, errors=errors)

    async def async_step_controls(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the control mappings step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._config.update(user_input)
            return self.async_create_entry(title="EOS Connect", data=self._config)

        schema = vol.Schema(
            {
                vol.Optional(CONF_CONTROL_CHARGE_LIMIT): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["number", "input_number"])
                ),
                vol.Optional(CONF_CONTROL_DISCHARGE_LIMIT): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["number", "input_number"])
                ),
                vol.Optional(CONF_CONTROL_MODE): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["select", "input_select"]
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="controls", data_schema=schema, errors=errors
        )
