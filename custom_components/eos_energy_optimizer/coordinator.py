"""Data coordinator for EOS Energy Optimizer."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EOSApiClient, EOSData
from .const import CONF_REFRESH_TIME, DEFAULT_REFRESH_TIME, DOMAIN

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

            # Then run optimization
            await self.api_client.async_run_optimization()

            return self.api_client.data

        except Exception as err:
            raise UpdateFailed(f"Error communicating with EOS: {err}") from err

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
