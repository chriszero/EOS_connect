"""Config flow for EOS Energy Optimizer integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
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
    CONF_EVCC_ENABLED,
    CONF_EVCC_URL,
    CONF_FEED_IN_PRICE,
    CONF_FIXED_PRICE,
    CONF_LOAD_SENSOR,
    CONF_MAX_GRID_CHARGE_RATE,
    CONF_MAX_PV_CHARGE_RATE,
    CONF_PRICE_ENTITY,
    CONF_PRICE_SOURCE,
    CONF_PV_FORECAST_ENTITY,
    CONF_REFRESH_TIME,
    DEFAULT_BATTERY_CAPACITY,
    DEFAULT_BATTERY_EFFICIENCY,
    DEFAULT_BATTERY_MAX_CHARGE,
    DEFAULT_BATTERY_MAX_SOC,
    DEFAULT_BATTERY_MIN_SOC,
    DEFAULT_EOS_PORT,
    DEFAULT_FEED_IN_PRICE,
    DEFAULT_REFRESH_TIME,
    DOMAIN,
    PRICE_SOURCE_FIXED,
    PRICE_SOURCE_HA_SENSOR,
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
                    vol.Required(CONF_REFRESH_TIME, default=DEFAULT_REFRESH_TIME): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=1, max=60, step=1, unit_of_measurement="min")
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
        """Handle PV forecast configuration step.

        Select a PV forecast sensor from existing integrations like:
        - Solcast (ha-solcast-solar)
        - Forecast.Solar
        - Open-Meteo Solar
        """
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_price()

        return self.async_show_form(
            step_id="pv",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_PV_FORECAST_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor",
                            multiple=False,
                        )
                    ),
                }
            ),
            description_placeholders={
                "supported_integrations": "Solcast, Forecast.Solar, Open-Meteo Solar"
            },
        )

    async def async_step_price(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle electricity price configuration step.

        Select a price sensor from existing integrations like:
        - Tibber
        - ENTSO-E
        - Nordpool
        - Awattar
        - EPEX Spot
        """
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_load()

        return self.async_show_form(
            step_id="price",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PRICE_SOURCE, default=PRICE_SOURCE_HA_SENSOR): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=PRICE_SOURCE_HA_SENSOR, label="Home Assistant Sensor (Tibber, ENTSO-E, Nordpool, etc.)"),
                                selector.SelectOptionDict(value=PRICE_SOURCE_FIXED, label="Fixed Price"),
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(CONF_PRICE_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor",
                            multiple=False,
                        )
                    ),
                    vol.Optional(CONF_FIXED_PRICE, default=0.30): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=1.0, step=0.01, unit_of_measurement="€/kWh")
                    ),
                    vol.Required(CONF_FEED_IN_PRICE, default=DEFAULT_FEED_IN_PRICE): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=0.5, step=0.001, unit_of_measurement="€/kWh")
                    ),
                }
            ),
            description_placeholders={
                "supported_integrations": "Tibber, ENTSO-E, Nordpool, Awattar, EPEX Spot"
            },
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

            return await self.async_step_evcc()

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

    async def async_step_evcc(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle EVCC configuration step (optional).

        EVCC can be used for:
        - Monitoring EV charging status
        - Battery control via EVCC's external battery mode
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)

            # Validate EVCC connection if enabled
            if user_input.get(CONF_EVCC_ENABLED) and user_input.get(CONF_EVCC_URL):
                evcc_url = user_input[CONF_EVCC_URL].rstrip("/")
                self._data[CONF_EVCC_URL] = evcc_url
                if not await self._validate_evcc_connection(evcc_url):
                    errors["base"] = "evcc_cannot_connect"
                else:
                    return self.async_create_entry(
                        title="EOS Energy Optimizer",
                        data=self._data,
                    )
            else:
                # EVCC not enabled, proceed
                return self.async_create_entry(
                    title="EOS Energy Optimizer",
                    data=self._data,
                )

        return self.async_show_form(
            step_id="evcc",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_EVCC_ENABLED, default=False): bool,
                    vol.Optional(CONF_EVCC_URL, default=""): str,
                }
            ),
            errors=errors,
        )

    async def _validate_evcc_connection(self, url: str) -> bool:
        """Validate EVCC connection."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                f"{url}/api/state",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                return resp.status == 200
        except Exception:
            return False

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
                    vol.Optional(CONF_PV_FORECAST_ENTITY, default=current.get(CONF_PV_FORECAST_ENTITY)): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(CONF_PRICE_ENTITY, default=current.get(CONF_PRICE_ENTITY)): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
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
