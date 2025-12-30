"""The EOS Energy Optimizer integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .api import EOSApiClient
from .const import (
    DOMAIN,
    InverterMode,
    PLATFORMS,
    SERVICE_CLEAR_OVERRIDE,
    SERVICE_REFRESH_OPTIMIZATION,
    SERVICE_SET_MODE,
    SERVICE_SET_OVERRIDE,
    SERVICE_SET_SOC_LIMITS,
)
from .coordinator import EOSDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the EOS Energy Optimizer component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EOS Energy Optimizer from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create API client
    api_client = EOSApiClient(hass, dict(entry.data))

    # Test connection
    if not await api_client.async_test_connection():
        _LOGGER.warning("Could not connect to EOS server, will retry")

    # Create coordinator
    coordinator = EOSDataUpdateCoordinator(hass, entry, api_client)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    await _async_setup_services(hass)

    # Listen for config updates
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def _async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for EOS Energy Optimizer."""

    async def _get_coordinator(call: ServiceCall) -> EOSDataUpdateCoordinator | None:
        """Get coordinator from service call."""
        entry_id = call.data.get("entry_id")
        if entry_id:
            return hass.data[DOMAIN].get(entry_id)
        # Return first coordinator if only one exists
        if len(hass.data[DOMAIN]) == 1:
            return next(iter(hass.data[DOMAIN].values()))
        return None

    async def handle_set_mode(call: ServiceCall) -> None:
        """Handle set_mode service call."""
        coordinator = await _get_coordinator(call)
        if coordinator:
            mode_str = call.data.get("mode", "auto")
            mode_map = {
                "auto": InverterMode.AUTO,
                "charge_from_grid": InverterMode.CHARGE_FROM_GRID,
                "avoid_discharge": InverterMode.AVOID_DISCHARGE,
                "discharge_allowed": InverterMode.DISCHARGE_ALLOWED,
            }
            mode = mode_map.get(mode_str.lower(), InverterMode.AUTO)
            await coordinator.api_client.async_set_mode(mode)
            await coordinator.async_request_refresh()

    async def handle_set_override(call: ServiceCall) -> None:
        """Handle set_override service call."""
        coordinator = await _get_coordinator(call)
        if coordinator:
            mode_str = call.data.get("mode", "charge_from_grid")
            duration = call.data.get("duration_minutes", 60)
            power = call.data.get("charge_power", 0)

            mode_map = {
                "charge_from_grid": InverterMode.CHARGE_FROM_GRID,
                "avoid_discharge": InverterMode.AVOID_DISCHARGE,
                "discharge_allowed": InverterMode.DISCHARGE_ALLOWED,
            }
            mode = mode_map.get(mode_str.lower(), InverterMode.CHARGE_FROM_GRID)
            await coordinator.api_client.async_set_override(mode, duration, power)
            await coordinator.async_request_refresh()

    async def handle_clear_override(call: ServiceCall) -> None:
        """Handle clear_override service call."""
        coordinator = await _get_coordinator(call)
        if coordinator:
            await coordinator.api_client.async_clear_override()
            await coordinator.async_request_refresh()

    async def handle_refresh_optimization(call: ServiceCall) -> None:
        """Handle refresh_optimization service call."""
        coordinator = await _get_coordinator(call)
        if coordinator:
            await coordinator.api_client.async_run_optimization()
            await coordinator.async_request_refresh()

    async def handle_set_soc_limits(call: ServiceCall) -> None:
        """Handle set_soc_limits service call."""
        coordinator = await _get_coordinator(call)
        if coordinator:
            min_soc = call.data.get("min_soc", 5)
            max_soc = call.data.get("max_soc", 95)
            await coordinator.api_client.async_set_soc_limits(min_soc, max_soc)
            await coordinator.async_request_refresh()

    # Register services if not already registered
    if not hass.services.has_service(DOMAIN, SERVICE_SET_MODE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_MODE,
            handle_set_mode,
            schema=vol.Schema(
                {
                    vol.Optional("entry_id"): cv.string,
                    vol.Required("mode"): cv.string,
                }
            ),
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_OVERRIDE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_OVERRIDE,
            handle_set_override,
            schema=vol.Schema(
                {
                    vol.Optional("entry_id"): cv.string,
                    vol.Required("mode"): cv.string,
                    vol.Required("duration_minutes"): cv.positive_int,
                    vol.Optional("charge_power", default=0): cv.positive_float,
                }
            ),
        )

    if not hass.services.has_service(DOMAIN, SERVICE_CLEAR_OVERRIDE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CLEAR_OVERRIDE,
            handle_clear_override,
            schema=vol.Schema(
                {
                    vol.Optional("entry_id"): cv.string,
                }
            ),
        )

    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH_OPTIMIZATION):
        hass.services.async_register(
            DOMAIN,
            SERVICE_REFRESH_OPTIMIZATION,
            handle_refresh_optimization,
            schema=vol.Schema(
                {
                    vol.Optional("entry_id"): cv.string,
                }
            ),
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_SOC_LIMITS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_SOC_LIMITS,
            handle_set_soc_limits,
            schema=vol.Schema(
                {
                    vol.Optional("entry_id"): cv.string,
                    vol.Required("min_soc"): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
                    vol.Required("max_soc"): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
                }
            ),
        )
