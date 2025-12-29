"""API client for EOS Energy Optimizer."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

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
    CONF_FIXED_PRICE,
    CONF_LOAD_SENSOR,
    CONF_MAX_GRID_CHARGE_RATE,
    CONF_MAX_PV_CHARGE_RATE,
    CONF_PRICE_ENTITY,
    CONF_PRICE_SOURCE,
    CONF_PV_FORECAST_ENTITY,
    CONF_REFRESH_TIME,
    CONF_TIME_FRAME,
    DEFAULT_BATTERY_CAPACITY,
    DEFAULT_BATTERY_EFFICIENCY,
    DEFAULT_BATTERY_MAX_CHARGE,
    DEFAULT_BATTERY_MAX_SOC,
    DEFAULT_BATTERY_MIN_SOC,
    DEFAULT_EOS_PORT,
    DEFAULT_EVOPT_PORT,
    DEFAULT_FEED_IN_PRICE,
    DEFAULT_REFRESH_TIME,
    DEFAULT_TIME_FRAME,
    DOMAIN,
    EOS_SOURCE_EVOPT,
    InverterMode,
    PRICE_SOURCE_FIXED,
    PRICE_SOURCE_HA_SENSOR,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """Result from optimization."""

    ac_charge: list[float] = field(default_factory=list)
    dc_charge: list[float] = field(default_factory=list)
    discharge_allowed: list[bool] = field(default_factory=list)
    soc_forecast: list[float] = field(default_factory=list)
    cost_total: float = 0.0
    losses_total: float = 0.0
    grid_import: list[float] = field(default_factory=list)
    grid_export: list[float] = field(default_factory=list)
    load_forecast: list[float] = field(default_factory=list)
    home_appliance_start_hour: int | None = None
    timestamp: datetime | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass
class ControlState:
    """Current control state."""

    mode: InverterMode = InverterMode.AUTO
    ac_charge_demand: float = 0.0
    dc_charge_demand: float = 0.0
    discharge_allowed: bool = True
    override_active: bool = False
    override_end_time: datetime | None = None
    override_power: float = 0.0


@dataclass
class BatteryState:
    """Current battery state."""

    soc: float = 0.0
    usable_energy_wh: float = 0.0
    dynamic_max_charge_power: float = 0.0
    capacity_wh: float = 0.0
    min_soc: float = 0.0
    max_soc: float = 100.0


@dataclass
class EOSData:
    """All EOS data."""

    control: ControlState = field(default_factory=ControlState)
    battery: BatteryState = field(default_factory=BatteryState)
    optimization: OptimizationResult = field(default_factory=OptimizationResult)
    pv_forecast: list[float] = field(default_factory=list)
    prices: list[float] = field(default_factory=list)
    load_profile: list[float] = field(default_factory=list)
    last_update: datetime | None = None
    last_optimization: datetime | None = None
    next_optimization: datetime | None = None
    optimization_state: str = "unknown"
    version: str = "1.0.0"


class EOSApiClient:
    """API client for EOS Energy Optimizer."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Initialize the API client."""
        self.hass = hass
        self.config = config
        self._session: aiohttp.ClientSession | None = None
        self._data = EOSData()
        self._lock = asyncio.Lock()

    @property
    def data(self) -> EOSData:
        """Return current data."""
        return self._data

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = async_get_clientsession(self.hass)
        return self._session

    async def async_test_connection(self) -> bool:
        """Test connection to EOS server."""
        try:
            session = await self._get_session()
            url = self._get_eos_url()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                return resp.status in (200, 404)  # Server is reachable
        except Exception as e:
            _LOGGER.error("Connection test failed: %s", e)
            return False

    def _get_eos_url(self) -> str:
        """Get the EOS server URL."""
        server = self.config.get(CONF_EOS_SERVER, "localhost")
        source = self.config.get(CONF_EOS_SOURCE, "eos_server")
        if source == EOS_SOURCE_EVOPT:
            port = self.config.get(CONF_EOS_PORT, DEFAULT_EVOPT_PORT)
        else:
            port = self.config.get(CONF_EOS_PORT, DEFAULT_EOS_PORT)
        return f"http://{server}:{port}"

    async def async_update(self) -> EOSData:
        """Update all data."""
        async with self._lock:
            try:
                await self._update_battery_soc()
                await self._update_load_data()
                await self._update_pv_forecast()
                await self._update_prices()
                self._update_battery_state()

                self._data.last_update = dt_util.now()
                self._data.optimization_state = "ok"

            except Exception as e:
                _LOGGER.error("Failed to update EOS data: %s", e)
                self._data.optimization_state = "error"

        return self._data

    async def async_run_optimization(self) -> OptimizationResult:
        """Run optimization request to EOS server."""
        async with self._lock:
            try:
                request_data = await self._build_optimization_request()
                session = await self._get_session()

                source = self.config.get(CONF_EOS_SOURCE, "eos_server")
                if source == EOS_SOURCE_EVOPT:
                    url = f"{self._get_eos_url()}/api/optimize"
                else:
                    url = f"{self._get_eos_url()}/optimize"

                _LOGGER.debug("Sending optimization request to %s", url)

                async with session.post(
                    url,
                    json=request_data,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status == 200:
                        response_data = await resp.json()
                        self._data.optimization = self._parse_optimization_response(response_data)
                        self._update_control_state()
                        self._data.last_optimization = dt_util.now()
                        refresh_minutes = self.config.get(CONF_REFRESH_TIME, DEFAULT_REFRESH_TIME)
                        self._data.next_optimization = dt_util.now() + timedelta(minutes=refresh_minutes)
                        self._data.optimization_state = "ok"

                        # Fire event for automations
                        self._fire_control_event()
                    else:
                        _LOGGER.error("Optimization request failed: %s", resp.status)
                        self._data.optimization_state = "error"

            except Exception as e:
                _LOGGER.error("Optimization failed: %s", e)
                self._data.optimization_state = "error"

        return self._data.optimization

    async def _update_battery_soc(self) -> None:
        """Update battery SOC from Home Assistant sensor."""
        sensor_id = self.config.get(CONF_BATTERY_SOC_SENSOR)
        if sensor_id:
            state = self.hass.states.get(sensor_id)
            if state and state.state not in ("unknown", "unavailable"):
                try:
                    self._data.battery.soc = float(state.state)
                except ValueError:
                    pass

    async def _update_load_data(self) -> None:
        """Update load data from Home Assistant."""
        sensor_id = self.config.get(CONF_LOAD_SENSOR)
        if not sensor_id:
            self._data.load_profile = [400] * 48
            return

        state = self.hass.states.get(sensor_id)
        if state and state.state not in ("unknown", "unavailable"):
            try:
                current_power = float(state.state)
                # TODO: Use recorder for historical load profile
                self._data.load_profile = [current_power] * 48
            except ValueError:
                self._data.load_profile = [400] * 48
        else:
            self._data.load_profile = [400] * 48

    async def _update_pv_forecast(self) -> None:
        """Update PV forecast from Home Assistant sensor.

        Supports sensors from:
        - Solcast (ha-solcast-solar): DetailedForecast, detailedHourly attributes
        - Forecast.Solar: forecast attribute
        - Open-Meteo Solar: forecast attribute
        """
        entity_id = self.config.get(CONF_PV_FORECAST_ENTITY)
        if not entity_id:
            self._data.pv_forecast = [0] * 48
            return

        state = self.hass.states.get(entity_id)
        if not state:
            _LOGGER.warning("PV forecast entity %s not found", entity_id)
            self._data.pv_forecast = [0] * 48
            return

        forecast = [0.0] * 48
        attrs = state.attributes
        now = dt_util.now()

        try:
            # Try Solcast format (DetailedForecast or detailedHourly)
            detailed = attrs.get("DetailedForecast") or attrs.get("detailedHourly") or attrs.get("detailed_forecast")
            if detailed and isinstance(detailed, list):
                forecast = self._parse_solcast_forecast(detailed, now)
                _LOGGER.debug("Parsed Solcast forecast: %d periods", len([f for f in forecast if f > 0]))

            # Try Forecast.Solar / generic forecast format
            elif "forecast" in attrs:
                forecast_data = attrs.get("forecast", [])
                if isinstance(forecast_data, list):
                    forecast = self._parse_generic_forecast(forecast_data, now)
                    _LOGGER.debug("Parsed generic forecast: %d periods", len([f for f in forecast if f > 0]))

            # Try watt_hours / watts attributes (Forecast.Solar native)
            elif "watt_hours" in attrs or "watts" in attrs:
                wh_data = attrs.get("watt_hours") or attrs.get("watts", {})
                if isinstance(wh_data, dict):
                    forecast = self._parse_watt_hours_forecast(wh_data, now)
                    _LOGGER.debug("Parsed watt_hours forecast: %d periods", len([f for f in forecast if f > 0]))

            # Fallback: try to use state value as current hour production
            else:
                try:
                    current_power = float(state.state)
                    forecast[0] = current_power
                    _LOGGER.debug("Using current state as PV forecast: %s W", current_power)
                except (ValueError, TypeError):
                    pass

        except Exception as e:
            _LOGGER.error("Failed to parse PV forecast: %s", e)

        self._data.pv_forecast = forecast

    def _parse_solcast_forecast(self, detailed: list, now: datetime) -> list[float]:
        """Parse Solcast DetailedForecast format."""
        forecast = [0.0] * 48

        for period in detailed:
            try:
                # Get period start time
                period_start_str = period.get("period_start")
                if not period_start_str:
                    continue

                period_start = datetime.fromisoformat(period_start_str.replace("Z", "+00:00"))

                # Calculate hours from now
                hours_diff = (period_start - now).total_seconds() / 3600

                # Only use future periods within 48 hours
                if 0 <= hours_diff < 48:
                    hour_idx = int(hours_diff)
                    # Use pv_estimate (50th percentile) or pv_estimate90 for optimistic
                    power = period.get("pv_estimate", 0) or period.get("pv_estimate50", 0)
                    if power:
                        forecast[hour_idx] += float(power)
            except Exception as e:
                _LOGGER.debug("Error parsing Solcast period: %s", e)

        return forecast

    def _parse_generic_forecast(self, forecast_data: list, now: datetime) -> list[float]:
        """Parse generic forecast format with period_start and value."""
        forecast = [0.0] * 48

        for period in forecast_data:
            try:
                # Try different timestamp keys
                period_start_str = (
                    period.get("period_start") or
                    period.get("datetime") or
                    period.get("start") or
                    period.get("time")
                )
                if not period_start_str:
                    continue

                period_start = datetime.fromisoformat(str(period_start_str).replace("Z", "+00:00"))

                hours_diff = (period_start - now).total_seconds() / 3600

                if 0 <= hours_diff < 48:
                    hour_idx = int(hours_diff)
                    # Try different value keys
                    power = (
                        period.get("pv_estimate") or
                        period.get("power") or
                        period.get("watt_hours") or
                        period.get("value") or 0
                    )
                    forecast[hour_idx] += float(power)
            except Exception as e:
                _LOGGER.debug("Error parsing forecast period: %s", e)

        return forecast

    def _parse_watt_hours_forecast(self, wh_data: dict, now: datetime) -> list[float]:
        """Parse watt_hours dict format (timestamp -> value)."""
        forecast = [0.0] * 48

        for timestamp_str, value in wh_data.items():
            try:
                timestamp = datetime.fromisoformat(str(timestamp_str).replace("Z", "+00:00"))
                hours_diff = (timestamp - now).total_seconds() / 3600

                if 0 <= hours_diff < 48:
                    hour_idx = int(hours_diff)
                    forecast[hour_idx] += float(value)
            except Exception as e:
                _LOGGER.debug("Error parsing watt_hours entry: %s", e)

        return forecast

    async def _update_prices(self) -> None:
        """Update electricity prices from Home Assistant sensor.

        Supports sensors from:
        - Tibber: prices attribute with from/till/price
        - ENTSO-E: prices attribute with time/price
        - Nordpool: prices_today/prices_tomorrow or raw_today/raw_tomorrow
        - Generic: prices attribute as list of dicts or plain list
        """
        source = self.config.get(CONF_PRICE_SOURCE, PRICE_SOURCE_HA_SENSOR)

        if source == PRICE_SOURCE_FIXED:
            fixed_price = self.config.get(CONF_FIXED_PRICE, 0.30)
            self._data.prices = [fixed_price] * 48
            return

        entity_id = self.config.get(CONF_PRICE_ENTITY)
        if not entity_id:
            _LOGGER.warning("No price entity configured")
            self._data.prices = [0.30] * 48
            return

        state = self.hass.states.get(entity_id)
        if not state:
            _LOGGER.warning("Price entity %s not found", entity_id)
            self._data.prices = [0.30] * 48
            return

        prices = [0.30] * 48
        attrs = state.attributes
        now = dt_util.now()

        try:
            # Try Tibber format: prices list with from/till/price
            if "prices" in attrs:
                prices_data = attrs.get("prices", [])
                if isinstance(prices_data, list) and prices_data:
                    prices = self._parse_tibber_prices(prices_data, now)
                    _LOGGER.debug("Parsed Tibber-style prices: %d hours", len([p for p in prices if p != 0.30]))

            # Try Nordpool format: prices_today / prices_tomorrow
            elif "prices_today" in attrs or "raw_today" in attrs:
                today = attrs.get("prices_today") or attrs.get("raw_today", [])
                tomorrow = attrs.get("prices_tomorrow") or attrs.get("raw_tomorrow", [])
                prices = self._parse_nordpool_prices(today, tomorrow, now)
                _LOGGER.debug("Parsed Nordpool-style prices: %d hours", len([p for p in prices if p != 0.30]))

            # Try ENTSO-E format: list with time/price dicts
            elif "data" in attrs:
                data = attrs.get("data", [])
                if isinstance(data, list):
                    prices = self._parse_entsoe_prices(data, now)
                    _LOGGER.debug("Parsed ENTSO-E style prices: %d hours", len([p for p in prices if p != 0.30]))

            # Fallback: try to use current state as price
            else:
                try:
                    current_price = float(state.state)
                    prices = [current_price] * 48
                    _LOGGER.debug("Using current state as price: %s €/kWh", current_price)
                except (ValueError, TypeError):
                    pass

        except Exception as e:
            _LOGGER.error("Failed to parse prices: %s", e)

        self._data.prices = prices

    def _parse_tibber_prices(self, prices_data: list, now: datetime) -> list[float]:
        """Parse Tibber prices format: [{from, till, price}, ...]"""
        prices = [0.30] * 48

        for entry in prices_data:
            try:
                # Tibber format: from/till timestamps with price
                from_str = entry.get("from") or entry.get("startsAt")
                price = entry.get("price") or entry.get("total")

                if not from_str or price is None:
                    continue

                from_time = datetime.fromisoformat(str(from_str).replace("Z", "+00:00"))
                hours_diff = (from_time - now).total_seconds() / 3600

                if -1 <= hours_diff < 48:  # Include current hour
                    hour_idx = max(0, int(hours_diff))
                    if hour_idx < 48:
                        prices[hour_idx] = float(price)
            except Exception as e:
                _LOGGER.debug("Error parsing Tibber price entry: %s", e)

        return prices

    def _parse_nordpool_prices(self, today: list, tomorrow: list, now: datetime) -> list[float]:
        """Parse Nordpool prices format: list of hourly prices."""
        prices = [0.30] * 48
        current_hour = now.hour

        # Process today's prices
        if isinstance(today, list):
            for i, price in enumerate(today):
                try:
                    hour_idx = i - current_hour
                    if 0 <= hour_idx < 48:
                        # Handle both raw values and dicts
                        if isinstance(price, dict):
                            prices[hour_idx] = float(price.get("value", price.get("price", 0.30)))
                        else:
                            prices[hour_idx] = float(price) if price is not None else 0.30
                except (ValueError, TypeError):
                    pass

        # Process tomorrow's prices
        if isinstance(tomorrow, list):
            hours_until_midnight = 24 - current_hour
            for i, price in enumerate(tomorrow):
                try:
                    hour_idx = hours_until_midnight + i
                    if 0 <= hour_idx < 48:
                        if isinstance(price, dict):
                            prices[hour_idx] = float(price.get("value", price.get("price", 0.30)))
                        else:
                            prices[hour_idx] = float(price) if price is not None else 0.30
                except (ValueError, TypeError):
                    pass

        return prices

    def _parse_entsoe_prices(self, data: list, now: datetime) -> list[float]:
        """Parse ENTSO-E prices format: [{time, price}, ...]"""
        prices = [0.30] * 48

        for entry in data:
            try:
                time_str = entry.get("time") or entry.get("start") or entry.get("datetime")
                price = entry.get("price") or entry.get("value")

                if not time_str or price is None:
                    continue

                entry_time = datetime.fromisoformat(str(time_str).replace("Z", "+00:00"))
                hours_diff = (entry_time - now).total_seconds() / 3600

                if -1 <= hours_diff < 48:
                    hour_idx = max(0, int(hours_diff))
                    if hour_idx < 48:
                        # ENTSO-E often uses €/MWh, convert to €/kWh
                        price_value = float(price)
                        if price_value > 1:  # Likely €/MWh
                            price_value = price_value / 1000
                        prices[hour_idx] = price_value
            except Exception as e:
                _LOGGER.debug("Error parsing ENTSO-E price entry: %s", e)

        return prices

    def _update_battery_state(self) -> None:
        """Update calculated battery state values."""
        capacity = self.config.get(CONF_BATTERY_CAPACITY, DEFAULT_BATTERY_CAPACITY)
        min_soc = self.config.get(CONF_BATTERY_MIN_SOC, DEFAULT_BATTERY_MIN_SOC)
        max_soc = self.config.get(CONF_BATTERY_MAX_SOC, DEFAULT_BATTERY_MAX_SOC)
        max_charge = self.config.get(CONF_BATTERY_MAX_CHARGE_POWER, DEFAULT_BATTERY_MAX_CHARGE)

        self._data.battery.capacity_wh = capacity
        self._data.battery.min_soc = min_soc
        self._data.battery.max_soc = max_soc

        current_soc = self._data.battery.soc
        if current_soc > min_soc:
            usable_percent = (current_soc - min_soc) / 100
            self._data.battery.usable_energy_wh = capacity * usable_percent
        else:
            self._data.battery.usable_energy_wh = 0

        if self.config.get(CONF_CHARGING_CURVE_ENABLED, False):
            if current_soc < 80:
                self._data.battery.dynamic_max_charge_power = max_charge
            elif current_soc < 90:
                self._data.battery.dynamic_max_charge_power = max_charge * 0.7
            elif current_soc < 95:
                self._data.battery.dynamic_max_charge_power = max_charge * 0.5
            else:
                self._data.battery.dynamic_max_charge_power = max_charge * 0.3
        else:
            self._data.battery.dynamic_max_charge_power = max_charge

    async def _build_optimization_request(self) -> dict[str, Any]:
        """Build optimization request for EOS server."""
        now = dt_util.now()
        time_frame = self.config.get(CONF_TIME_FRAME, DEFAULT_TIME_FRAME)

        capacity = self.config.get(CONF_BATTERY_CAPACITY, DEFAULT_BATTERY_CAPACITY)
        charge_eff = self.config.get(CONF_BATTERY_CHARGE_EFFICIENCY, DEFAULT_BATTERY_EFFICIENCY)
        discharge_eff = self.config.get(CONF_BATTERY_DISCHARGE_EFFICIENCY, DEFAULT_BATTERY_EFFICIENCY)
        max_charge = self.config.get(CONF_BATTERY_MAX_CHARGE_POWER, DEFAULT_BATTERY_MAX_CHARGE)
        min_soc = self.config.get(CONF_BATTERY_MIN_SOC, DEFAULT_BATTERY_MIN_SOC)
        max_soc = self.config.get(CONF_BATTERY_MAX_SOC, DEFAULT_BATTERY_MAX_SOC)
        feed_in = self.config.get(CONF_FEED_IN_PRICE, DEFAULT_FEED_IN_PRICE)

        ems = {
            "pv_prognose_wh": self._data.pv_forecast[:48],
            "strompreis_euro_pro_wh": [p / 1000 for p in self._data.prices[:48]],
            "einspeiseverguetung_euro_pro_wh": [feed_in / 1000] * 48,
            "gesamtlast": self._data.load_profile[:48],
        }

        pv_akku = {
            "device_id": "battery1",
            "capacity_wh": capacity,
            "charging_efficiency": charge_eff,
            "discharging_efficiency": discharge_eff,
            "max_charge_power_w": max_charge,
            "initial_soc_percentage": self._data.battery.soc,
            "min_soc_percentage": min_soc,
            "max_soc_percentage": max_soc,
        }

        inverter = {
            "device_id": "inverter1",
            "max_power_wh": max_charge,
            "battery_id": "battery1",
        }

        request = {
            "ems": ems,
            "pv_akku": pv_akku,
            "inverter": inverter,
            "timestamp": now.isoformat(),
        }

        if time_frame != DEFAULT_TIME_FRAME:
            request["time_frame"] = time_frame

        return request

    def _parse_optimization_response(self, response: dict[str, Any]) -> OptimizationResult:
        """Parse optimization response from EOS server."""
        result = OptimizationResult()
        result.raw_response = response

        result.ac_charge = response.get("ac_charge", [0] * 48)
        result.dc_charge = response.get("dc_charge", [1] * 48)
        result.discharge_allowed = [bool(x) for x in response.get("discharge_allowed", [1] * 48)]

        if "result" in response:
            res = response["result"]
            result.soc_forecast = res.get("akku_soc_pro_stunde", [])
            result.cost_total = res.get("Gesamtkosten_Euro", 0.0)
            result.losses_total = res.get("Gesamt_Verluste", 0.0)
            result.grid_import = res.get("Netzbezug_Wh_pro_Stunde", [])
            result.grid_export = res.get("Netzeinspeisung_Wh_pro_Stunde", [])
            result.load_forecast = res.get("Last_Wh_pro_Stunde", [])

        result.home_appliance_start_hour = response.get("washingstart")
        result.timestamp = dt_util.now()

        return result

    def _update_control_state(self) -> None:
        """Update control state based on optimization result."""
        opt = self._data.optimization
        if not opt.ac_charge or not opt.dc_charge or not opt.discharge_allowed:
            return

        max_grid_charge = self.config.get(CONF_MAX_GRID_CHARGE_RATE, DEFAULT_BATTERY_MAX_CHARGE)
        max_pv_charge = self.config.get(CONF_MAX_PV_CHARGE_RATE, DEFAULT_BATTERY_MAX_CHARGE)

        if opt.ac_charge:
            self._data.control.ac_charge_demand = opt.ac_charge[0] * max_grid_charge
        if opt.dc_charge:
            self._data.control.dc_charge_demand = opt.dc_charge[0] * max_pv_charge
        if opt.discharge_allowed:
            self._data.control.discharge_allowed = opt.discharge_allowed[0]

        if not self._data.control.override_active:
            if self._data.control.ac_charge_demand > 0:
                self._data.control.mode = InverterMode.CHARGE_FROM_GRID
            elif not self._data.control.discharge_allowed:
                self._data.control.mode = InverterMode.AVOID_DISCHARGE
            else:
                self._data.control.mode = InverterMode.DISCHARGE_ALLOWED

    def _fire_control_event(self) -> None:
        """Fire control event for HA automations."""
        self.hass.bus.async_fire(
            f"{DOMAIN}_control_update",
            {
                "mode": self._data.control.mode.value,
                "mode_name": self._data.control.mode.name,
                "ac_charge_demand": self._data.control.ac_charge_demand,
                "dc_charge_demand": self._data.control.dc_charge_demand,
                "discharge_allowed": self._data.control.discharge_allowed,
            },
        )

    async def async_set_mode(self, mode: InverterMode) -> bool:
        """Set inverter mode manually."""
        self._data.control.mode = mode
        self._fire_control_event()
        return True

    async def async_set_override(self, mode: InverterMode, duration_minutes: int, charge_power: float = 0) -> bool:
        """Set mode override."""
        self._data.control.mode = mode
        self._data.control.override_active = True
        self._data.control.override_end_time = dt_util.now() + timedelta(minutes=duration_minutes)
        self._data.control.override_power = charge_power

        if mode == InverterMode.CHARGE_FROM_GRID and charge_power > 0:
            self._data.control.ac_charge_demand = charge_power

        self._fire_control_event()
        return True

    async def async_clear_override(self) -> bool:
        """Clear mode override."""
        self._data.control.override_active = False
        self._data.control.override_end_time = None
        self._data.control.override_power = 0
        await self.async_run_optimization()
        return True

    async def async_set_soc_limits(self, min_soc: float, max_soc: float) -> bool:
        """Set battery SOC limits."""
        self.config[CONF_BATTERY_MIN_SOC] = min_soc
        self.config[CONF_BATTERY_MAX_SOC] = max_soc
        self._update_battery_state()
        return True
