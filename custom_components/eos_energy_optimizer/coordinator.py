"""Data coordinator for EOS Energy Optimizer."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import EOSApiClient, EOSData
from .const import (
    CONF_15MIN_REFINEMENT_ENABLED,
    CONF_BATTERY_CAPACITY,
    CONF_EVCC_ENABLED,
    CONF_FEED_IN_PRICE,
    CONF_REFRESH_TIME,
    DEFAULT_15MIN_REFINEMENT_ENABLED,
    DEFAULT_BATTERY_CAPACITY,
    DEFAULT_FEED_IN_PRICE,
    DEFAULT_REFRESH_TIME,
    DOMAIN,
    EVCC_BATTERY_CHARGE,
    EVCC_BATTERY_HOLD,
    EVCC_BATTERY_NORMAL,
    InverterMode,
    UPDATE_INTERVAL_15MIN,
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
        self._refinement_15min_enabled = config_entry.data.get(
            CONF_15MIN_REFINEMENT_ENABLED, DEFAULT_15MIN_REFINEMENT_ENABLED
        )
        self._15min_unsub = None
        self._last_evcc_mode: str | None = None

        # Savings tracking
        self._last_soc: float | None = None
        self._battery_capacity_wh = config_entry.data.get(
            CONF_BATTERY_CAPACITY, DEFAULT_BATTERY_CAPACITY
        )
        self._feed_in_price = config_entry.data.get(
            CONF_FEED_IN_PRICE, DEFAULT_FEED_IN_PRICE
        )

        refresh_minutes = config_entry.data.get(CONF_REFRESH_TIME, DEFAULT_REFRESH_TIME)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=refresh_minutes),
        )

    @property
    def refinement_15min_enabled(self) -> bool:
        """Return if 15-minute refinement is enabled."""
        return self._refinement_15min_enabled

    async def async_set_15min_refinement(self, enabled: bool) -> None:
        """Enable or disable 15-minute refinement."""
        self._refinement_15min_enabled = enabled

        if enabled:
            # Start 15-minute scheduler if not already running
            if self._15min_unsub is None:
                self._15min_unsub = async_track_time_interval(
                    self.hass,
                    self._async_15min_update,
                    timedelta(seconds=UPDATE_INTERVAL_15MIN),
                )
                _LOGGER.info("Started 15-minute refinement scheduler")
                # Run immediately
                await self._async_15min_update(None)
        else:
            # Stop 15-minute scheduler
            if self._15min_unsub is not None:
                self._15min_unsub()
                self._15min_unsub = None
                _LOGGER.info("Stopped 15-minute refinement scheduler")

    async def _async_15min_update(self, _now) -> None:
        """Handle 15-minute refinement update."""
        if not self._refinement_15min_enabled:
            return

        if not self._evcc_enabled:
            _LOGGER.debug("15-min refinement: EVCC not enabled, skipping")
            return

        await self._sync_evcc_battery_mode_15min()

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

            # Track savings based on SOC changes
            self._update_savings()

            # Sync EVCC battery mode with EOS optimization result
            if self._evcc_enabled:
                await self._sync_evcc_battery_mode()

            return self.api_client.data

        except Exception as err:
            raise UpdateFailed(f"Error communicating with EOS: {err}") from err

    def _update_savings(self) -> None:
        """Update savings based on battery SOC changes and current prices.

        Distinguishes between:
        - PV charging: Cost = feed-in price (opportunity cost)
        - Grid charging: Cost = current electricity price
        - Discharging: Savings = (grid price - avg charge price) × energy
        """
        data = self.api_client.data
        if not data.battery or not data.prices:
            return

        current_soc = data.battery.soc
        current_price = data.prices[0] if data.prices else 0.30
        eos_mode = data.control.mode if data.control else InverterMode.AUTO

        # Check if day changed - reset today's values
        today = dt_util.now().strftime("%Y-%m-%d")
        if data.savings.today_date != today:
            data.savings.today_date = today
            data.savings.today_savings_eur = 0.0
            data.savings.today_grid_cost_eur = 0.0
            data.savings.today_pv_charged_kwh = 0.0
            data.savings.today_grid_charged_kwh = 0.0

        # Skip first update (no previous SOC to compare)
        if self._last_soc is None:
            self._last_soc = current_soc
            return

        # Calculate energy flow from SOC change
        soc_change = current_soc - self._last_soc
        energy_wh = (soc_change / 100) * self._battery_capacity_wh
        energy_kwh = energy_wh / 1000

        if abs(energy_kwh) < 0.01:  # Skip tiny changes
            self._last_soc = current_soc
            return

        if energy_kwh > 0:
            # Battery charged - determine source (PV or Grid)
            if eos_mode == InverterMode.CHARGE_FROM_GRID:
                # Grid charging: use current electricity price
                charge_price = current_price
                source = "grid"
                data.savings.total_grid_import_kwh += energy_kwh
                data.savings.total_grid_cost_eur += energy_kwh * current_price
                data.savings.today_grid_cost_eur += energy_kwh * current_price
                data.savings.total_grid_charged_kwh += energy_kwh
                data.savings.session_grid_charged_kwh += energy_kwh
                data.savings.today_grid_charged_kwh += energy_kwh
            else:
                # PV charging: use feed-in price as opportunity cost
                charge_price = self._feed_in_price
                source = "PV"
                data.savings.total_pv_charged_kwh += energy_kwh
                data.savings.session_pv_charged_kwh += energy_kwh
                data.savings.today_pv_charged_kwh += energy_kwh

            data.savings.total_charged_kwh += energy_kwh
            data.savings.session_charged_kwh += energy_kwh

            # Update weighted average charge price
            old_total = data.savings.total_charged_kwh - energy_kwh
            if old_total > 0:
                data.savings.avg_charge_price = (
                    (data.savings.avg_charge_price * old_total + charge_price * energy_kwh)
                    / data.savings.total_charged_kwh
                )
            else:
                data.savings.avg_charge_price = charge_price

            _LOGGER.debug(
                "Battery charged %.2f kWh from %s at %.4f €/kWh (avg: %.4f €/kWh)",
                energy_kwh, source, charge_price, data.savings.avg_charge_price,
            )

        else:
            # Battery discharged
            discharged_kwh = abs(energy_kwh)
            data.savings.total_discharged_kwh += discharged_kwh
            data.savings.session_discharged_kwh += discharged_kwh

            # Track discharge price (current grid price we're avoiding)
            data.savings.avg_discharge_price = current_price

            # Calculate savings: difference between current price and avg charge price
            # This represents what we would have paid for grid power vs what we paid to charge
            if data.savings.avg_charge_price > 0:
                price_diff = current_price - data.savings.avg_charge_price
                savings = price_diff * discharged_kwh

                data.savings.total_savings_eur += savings
                data.savings.session_savings_eur += savings
                data.savings.today_savings_eur += savings

                _LOGGER.debug(
                    "Battery discharged %.2f kWh at %.4f €/kWh (charged at %.4f €/kWh) = %.2f € %s",
                    discharged_kwh, current_price, data.savings.avg_charge_price,
                    abs(savings), "saved" if savings > 0 else "lost",
                )

        self._last_soc = current_soc

    async def _sync_evcc_battery_mode(self) -> None:
        """Sync EVCC battery mode based on EOS optimization result.

        If 15-min refinement is enabled, this is handled by _sync_evcc_battery_mode_15min instead.
        """
        # Skip if 15-min refinement is handling this
        if self._refinement_15min_enabled:
            _LOGGER.debug("Skipping hourly sync, 15-min refinement is active")
            return

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

        await self._set_evcc_mode_if_changed(evcc_mode, f"EOS mode {mode}")

    async def _sync_evcc_battery_mode_15min(self) -> None:
        """Sync EVCC battery mode with 15-minute price refinement.

        Logic:
        - AVOID_DISCHARGE: Always hold (no refinement)
        - CHARGE_FROM_GRID: Only charge in cheapest 15-min slots of the hour
        - DISCHARGE_ALLOWED: Only discharge in most expensive 15-min slots
        - AUTO: Decide based on 15-min price vs hourly average
        """
        data = self.api_client.data
        if not data.control:
            return

        now = dt_util.now()
        current_hour = now.hour
        current_15min_slot = current_hour * 4 + now.minute // 15

        # Get prices
        prices_15min = data.prices_15min or []
        prices_hourly = data.prices or []

        if not prices_15min or current_15min_slot >= len(prices_15min):
            _LOGGER.warning("No 15-min price data available for slot %d", current_15min_slot)
            return

        current_15min_price = prices_15min[current_15min_slot]
        hourly_avg = prices_hourly[current_hour] if current_hour < len(prices_hourly) else current_15min_price

        # Get 4 prices for current hour
        hour_start_slot = current_hour * 4
        hour_prices = prices_15min[hour_start_slot:hour_start_slot + 4] if len(prices_15min) >= hour_start_slot + 4 else []
        hour_min = min(hour_prices) if hour_prices else current_15min_price
        hour_max = max(hour_prices) if hour_prices else current_15min_price

        eos_mode = data.control.mode
        evcc_mode = EVCC_BATTERY_NORMAL

        if eos_mode == InverterMode.AVOID_DISCHARGE:
            # Always hold - no refinement needed
            evcc_mode = EVCC_BATTERY_HOLD
            reason = "EOS AVOID_DISCHARGE"

        elif eos_mode == InverterMode.CHARGE_FROM_GRID:
            # Only charge in cheaper slots (below or equal to hourly average)
            if current_15min_price <= hourly_avg or current_15min_price == hour_min:
                evcc_mode = EVCC_BATTERY_CHARGE
                reason = f"15min price {current_15min_price:.4f} <= avg {hourly_avg:.4f}"
            else:
                evcc_mode = EVCC_BATTERY_HOLD  # Wait for cheaper slot
                reason = f"15min price {current_15min_price:.4f} > avg {hourly_avg:.4f}, waiting"

        elif eos_mode == InverterMode.DISCHARGE_ALLOWED:
            # Only discharge in expensive slots (above hourly average)
            if current_15min_price >= hourly_avg or current_15min_price == hour_max:
                evcc_mode = EVCC_BATTERY_NORMAL  # Allow discharge
                reason = f"15min price {current_15min_price:.4f} >= avg {hourly_avg:.4f}"
            else:
                evcc_mode = EVCC_BATTERY_HOLD  # Hold for more expensive slot
                reason = f"15min price {current_15min_price:.4f} < avg {hourly_avg:.4f}, holding"

        else:
            # AUTO mode: decide based on price
            if current_15min_price <= hour_min * 1.1:  # Within 10% of minimum
                evcc_mode = EVCC_BATTERY_CHARGE
                reason = f"AUTO: cheap slot {current_15min_price:.4f}"
            elif current_15min_price >= hour_max * 0.9:  # Within 10% of maximum
                evcc_mode = EVCC_BATTERY_NORMAL
                reason = f"AUTO: expensive slot {current_15min_price:.4f}"
            else:
                evcc_mode = EVCC_BATTERY_HOLD
                reason = f"AUTO: mid-price slot {current_15min_price:.4f}"

        await self._set_evcc_mode_if_changed(evcc_mode, reason)

    async def _set_evcc_mode_if_changed(self, evcc_mode: str, reason: str) -> None:
        """Set EVCC battery mode only if it changed."""
        if evcc_mode == self._last_evcc_mode:
            return

        try:
            success = await self.api_client.async_set_evcc_battery_mode(evcc_mode)
            if success:
                self._last_evcc_mode = evcc_mode
                _LOGGER.info(
                    "Set EVCC battery mode to '%s' (%s)",
                    evcc_mode,
                    reason,
                )
            else:
                _LOGGER.warning("Failed to set EVCC battery mode to '%s'", evcc_mode)
        except Exception as err:
            _LOGGER.warning("Error setting EVCC battery mode: %s", err)

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": "EOS Energy Optimizer",
            "manufacturer": "EOS",
            "model": "Energy Optimizer",
            "sw_version": self.api_client.data.eos_version,
        }
