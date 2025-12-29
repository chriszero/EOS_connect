"""Data coordinator for EOS Energy Optimizer."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EOSApiClient, EOSData
from .const import (
    CONF_EVCC_ENABLED,
    CONF_REFRESH_TIME,
    DEFAULT_REFRESH_TIME,
    DOMAIN,
    EVCC_BATTERY_CHARGE,
    EVCC_BATTERY_HOLD,
    EVCC_BATTERY_NORMAL,
    InverterMode,
)

_LOGGER = logging.getLogger(__name__)


class EOSDataUpdateCoordinator(DataUpdateCoordinator[EOSData]):
    """Class to manage fetching EOS data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api_client: EOSApiClient,
    ) -> None:
        """Initialize the coordinator."""
        self.api_client = api_client
        self.config_entry = config_entry
        self._evcc_enabled = config_entry.data.get(CONF_EVCC_ENABLED, False)

        refresh_minutes = config_entry.data.get(CONF_REFRESH_TIME, DEFAULT_REFRESH_TIME)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=refresh_minutes),
        )

    async def _async_update_data(self) -> EOSData:
        """Fetch data from EOS."""
        try:
            # First update sensor data
            await self.api_client.async_update()

            # Update EVCC state if enabled
            if self._evcc_enabled:
                try:
                    await self.api_client.async_update_evcc()
                except Exception as evcc_err:
                    _LOGGER.warning("Failed to update EVCC state: %s", evcc_err)

            # Then run optimization
            await self.api_client.async_run_optimization()

            # Sync EVCC battery mode with EOS optimization result
            if self._evcc_enabled:
                await self._sync_evcc_battery_mode()

            return self.api_client.data

        except Exception as err:
            raise UpdateFailed(f"Error communicating with EOS: {err}") from err

    async def _sync_evcc_battery_mode(self) -> None:
        """Sync EVCC battery mode based on EOS optimization result."""
        if not self.api_client.data.control:
            return

        mode = self.api_client.data.control.mode

        # Map EOS mode to EVCC battery mode
        if mode == InverterMode.CHARGE_FROM_GRID:
            evcc_mode = EVCC_BATTERY_CHARGE
        elif mode == InverterMode.AVOID_DISCHARGE:
            evcc_mode = EVCC_BATTERY_HOLD
        else:
            # For AUTO, STARTUP, and DISCHARGE_ALLOWED: normal operation
            evcc_mode = EVCC_BATTERY_NORMAL

        try:
            success = await self.api_client.async_set_evcc_battery_mode(evcc_mode)
            if success:
                _LOGGER.debug(
                    "Synced EVCC battery mode to '%s' based on EOS mode %s",
                    evcc_mode,
                    mode.name if hasattr(mode, 'name') else mode,
                )
            else:
                _LOGGER.warning("Failed to set EVCC battery mode to '%s'", evcc_mode)
        except Exception as err:
            _LOGGER.warning("Error syncing EVCC battery mode: %s", err)

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": "EOS Energy Optimizer",
            "manufacturer": "EOS",
            "model": "Energy Optimizer",
            "sw_version": self.api_client.data.version,
        }
