"""Config flow for EOS Energy Optimizer integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_BATTERY_CAPACITY,
    CONF_BATTERY_CHARGE_EFFICIENCY,
    CONF_BATTERY_DISCHARGE_EFFICIENCY,
    CONF_BATTERY_MAX_CHARGE_POWER,
    CONF_BATTERY_MAX_SOC,
    CONF_BATTERY_MIN_SOC,
    CONF_BATTERY_SOC_SENSOR,
    CONF_CHARGING_CURVE_ENABLED,
    CONF_EOS_PORT,
    CONF_EOS_SERVER,
    CONF_EOS_SOURCE,
    CONF_FEED_IN_PRICE,
    CONF_LOAD_SENSOR,
    CONF_MAX_GRID_CHARGE_RATE,
    CONF_MAX_PV_CHARGE_RATE,
    CONF_PRICE_SOURCE,
    CONF_PV_FORECAST_SOURCE,
    CONF_PV_SYSTEMS,
    CONF_REFRESH_TIME,
    CONF_TIBBER_TOKEN,
    CONF_TIME_FRAME,
    DEFAULT_BATTERY_CAPACITY,
    DEFAULT_BATTERY_EFFICIENCY,
    DEFAULT_BATTERY_MAX_CHARGE,
    DEFAULT_BATTERY_MAX_SOC,
    DEFAULT_BATTERY_MIN_SOC,
    DEFAULT_EOS_PORT,
    DEFAULT_FEED_IN_PRICE,
    DEFAULT_REFRESH_TIME,
    DEFAULT_TIME_FRAME,
    DOMAIN,
    EOS_SOURCE_EOS,
    EOS_SOURCE_EVOPT,
    PRICE_SOURCE_AKKUDOKTOR,
    PRICE_SOURCE_FIXED,
    PRICE_SOURCE_TIBBER,
    PV_SOURCE_AKKUDOKTOR,
    PV_SOURCE_FORECAST_SOLAR,
    PV_SOURCE_OPENMETEO,
)

_LOGGER = logging.getLogger(__name__)


async def validate_eos_connection(hass: HomeAssistant, data: dict[str, Any]) -> bool:
    """Validate the EOS server connection."""
    server = data.get(CONF_EOS_SERVER, "localhost")
    port = data.get(CONF_EOS_PORT, DEFAULT_EOS_PORT)
    url = f"http://{server}:{port}"

    session = async_get_clientsession(hass)
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            return resp.status in (200, 404)
    except Exception:
        return False


class EOSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EOS Energy Optimizer."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - EOS Server configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)

            # Validate connection
            if await validate_eos_connection(self.hass, user_input):
                return await self.async_step_battery()
            else:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EOS_SERVER, default="localhost"): str,
                    vol.Required(CONF_EOS_PORT, default=DEFAULT_EOS_PORT): int,
                    vol.Required(CONF_EOS_SOURCE, default=EOS_SOURCE_EOS): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=EOS_SOURCE_EOS, label="EOS Server"),
                                selector.SelectOptionDict(value=EOS_SOURCE_EVOPT, label="EVopt Server"),
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(CONF_REFRESH_TIME, default=DEFAULT_REFRESH_TIME): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=1, max=60, step=1, unit_of_measurement="min")
                    ),
                    vol.Required(CONF_TIME_FRAME, default=DEFAULT_TIME_FRAME): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value="3600", label="Hourly (3600s)"),
                                selector.SelectOptionDict(value="900", label="15 Minutes (900s)"),
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_battery(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle battery configuration step."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_pv()

        return self.async_show_form(
            step_id="battery",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BATTERY_CAPACITY, default=DEFAULT_BATTERY_CAPACITY): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=1000, max=100000, step=100, unit_of_measurement="Wh")
                    ),
                    vol.Required(CONF_BATTERY_MAX_CHARGE_POWER, default=DEFAULT_BATTERY_MAX_CHARGE): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=100, max=50000, step=100, unit_of_measurement="W")
                    ),
                    vol.Required(CONF_BATTERY_MIN_SOC, default=DEFAULT_BATTERY_MIN_SOC): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=50, step=1, unit_of_measurement="%")
                    ),
                    vol.Required(CONF_BATTERY_MAX_SOC, default=DEFAULT_BATTERY_MAX_SOC): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=50, max=100, step=1, unit_of_measurement="%")
                    ),
                    vol.Required(CONF_BATTERY_CHARGE_EFFICIENCY, default=DEFAULT_BATTERY_EFFICIENCY): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0.8, max=1.0, step=0.01)
                    ),
                    vol.Required(CONF_BATTERY_DISCHARGE_EFFICIENCY, default=DEFAULT_BATTERY_EFFICIENCY): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0.8, max=1.0, step=0.01)
                    ),
                    vol.Optional(CONF_BATTERY_SOC_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(CONF_CHARGING_CURVE_ENABLED, default=False): bool,
                }
            ),
        )

    async def async_step_pv(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle PV configuration step."""
        if user_input is not None:
            # Parse PV systems
            pv_systems = []
            if user_input.get("pv_latitude") and user_input.get("pv_power_wp"):
                pv_systems.append({
                    "latitude": user_input.get("pv_latitude", 52.52),
                    "longitude": user_input.get("pv_longitude", 13.405),
                    "azimuth": user_input.get("pv_azimuth", 0),
                    "tilt": user_input.get("pv_tilt", 30),
                    "power_wp": user_input.get("pv_power_wp", 10000),
                })

            self._data[CONF_PV_SYSTEMS] = pv_systems
            self._data[CONF_PV_FORECAST_SOURCE] = user_input.get(CONF_PV_FORECAST_SOURCE, PV_SOURCE_AKKUDOKTOR)
            return await self.async_step_price()

        return self.async_show_form(
            step_id="pv",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PV_FORECAST_SOURCE, default=PV_SOURCE_AKKUDOKTOR): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=PV_SOURCE_AKKUDOKTOR, label="Akkudoktor"),
                                selector.SelectOptionDict(value=PV_SOURCE_OPENMETEO, label="Open-Meteo"),
                                selector.SelectOptionDict(value=PV_SOURCE_FORECAST_SOLAR, label="Forecast.Solar"),
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional("pv_latitude", default=52.52): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=-90, max=90, step=0.0001)
                    ),
                    vol.Optional("pv_longitude", default=13.405): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=-180, max=180, step=0.0001)
                    ),
                    vol.Optional("pv_power_wp", default=10000): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=100, max=100000, step=100, unit_of_measurement="Wp")
                    ),
                    vol.Optional("pv_azimuth", default=0): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=-180, max=180, step=1, unit_of_measurement="°")
                    ),
                    vol.Optional("pv_tilt", default=30): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=90, step=1, unit_of_measurement="°")
                    ),
                }
            ),
        )

    async def async_step_price(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle price configuration step."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_load()

        return self.async_show_form(
            step_id="price",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PRICE_SOURCE, default=PRICE_SOURCE_AKKUDOKTOR): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=PRICE_SOURCE_AKKUDOKTOR, label="Akkudoktor"),
                                selector.SelectOptionDict(value=PRICE_SOURCE_TIBBER, label="Tibber"),
                                selector.SelectOptionDict(value=PRICE_SOURCE_FIXED, label="Fixed Price"),
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(CONF_TIBBER_TOKEN): str,
                    vol.Required(CONF_FEED_IN_PRICE, default=DEFAULT_FEED_IN_PRICE): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=0.5, step=0.001, unit_of_measurement="€/kWh")
                    ),
                    vol.Optional("fixed_price", default=0.30): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=1.0, step=0.01, unit_of_measurement="€/kWh")
                    ),
                }
            ),
        )

    async def async_step_load(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle load sensor configuration step."""
        if user_input is not None:
            self._data.update(user_input)

            # Set additional defaults
            self._data.setdefault(CONF_MAX_GRID_CHARGE_RATE, self._data.get(CONF_BATTERY_MAX_CHARGE_POWER, DEFAULT_BATTERY_MAX_CHARGE))
            self._data.setdefault(CONF_MAX_PV_CHARGE_RATE, self._data.get(CONF_BATTERY_MAX_CHARGE_POWER, DEFAULT_BATTERY_MAX_CHARGE))

            # Convert time_frame to int
            if CONF_TIME_FRAME in self._data:
                self._data[CONF_TIME_FRAME] = int(self._data[CONF_TIME_FRAME])

            # Create entry
            return self.async_create_entry(
                title="EOS Energy Optimizer",
                data=self._data,
            )

        return self.async_show_form(
            step_id="load",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_LOAD_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(CONF_MAX_GRID_CHARGE_RATE, default=DEFAULT_BATTERY_MAX_CHARGE): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=100, max=50000, step=100, unit_of_measurement="W")
                    ),
                    vol.Optional(CONF_MAX_PV_CHARGE_RATE, default=DEFAULT_BATTERY_MAX_CHARGE): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=100, max=50000, step=100, unit_of_measurement="W")
                    ),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get the options flow for this handler."""
        return EOSOptionsFlow(config_entry)


class EOSOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for EOS Energy Optimizer."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow."""
        if user_input is not None:
            # Merge with existing data
            new_data = {**self.config_entry.data, **user_input}
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REFRESH_TIME, default=current.get(CONF_REFRESH_TIME, DEFAULT_REFRESH_TIME)): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=1, max=60, step=1, unit_of_measurement="min")
                    ),
                    vol.Required(CONF_BATTERY_MIN_SOC, default=current.get(CONF_BATTERY_MIN_SOC, DEFAULT_BATTERY_MIN_SOC)): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=50, step=1, unit_of_measurement="%")
                    ),
                    vol.Required(CONF_BATTERY_MAX_SOC, default=current.get(CONF_BATTERY_MAX_SOC, DEFAULT_BATTERY_MAX_SOC)): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=50, max=100, step=1, unit_of_measurement="%")
                    ),
                    vol.Required(CONF_MAX_GRID_CHARGE_RATE, default=current.get(CONF_MAX_GRID_CHARGE_RATE, DEFAULT_BATTERY_MAX_CHARGE)): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=100, max=50000, step=100, unit_of_measurement="W")
                    ),
                    vol.Required(CONF_MAX_PV_CHARGE_RATE, default=current.get(CONF_MAX_PV_CHARGE_RATE, DEFAULT_BATTERY_MAX_CHARGE)): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=100, max=50000, step=100, unit_of_measurement="W")
                    ),
                    vol.Required(CONF_FEED_IN_PRICE, default=current.get(CONF_FEED_IN_PRICE, DEFAULT_FEED_IN_PRICE)): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=0.5, step=0.001, unit_of_measurement="€/kWh")
                    ),
                    vol.Optional(CONF_CHARGING_CURVE_ENABLED, default=current.get(CONF_CHARGING_CURVE_ENABLED, False)): bool,
                }
            ),
        )
