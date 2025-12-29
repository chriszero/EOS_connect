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
    DEFAULT_EVOPT_PORT,
    DEFAULT_FEED_IN_PRICE,
    DEFAULT_REFRESH_TIME,
    DEFAULT_TIME_FRAME,
    DOMAIN,
    EOS_SOURCE_EVOPT,
    InverterMode,
    PRICE_SOURCE_AKKUDOKTOR,
    PRICE_SOURCE_TIBBER,
    PV_SOURCE_AKKUDOKTOR,
    PV_SOURCE_FORECAST_SOLAR,
    PV_SOURCE_OPENMETEO,
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
        """Update PV forecast."""
        source = self.config.get(CONF_PV_FORECAST_SOURCE, PV_SOURCE_AKKUDOKTOR)
        pv_systems = self.config.get(CONF_PV_SYSTEMS, [])

        if not pv_systems:
            self._data.pv_forecast = [0] * 48
            return

        try:
            if source == PV_SOURCE_AKKUDOKTOR:
                await self._fetch_akkudoktor_pv(pv_systems)
            elif source == PV_SOURCE_OPENMETEO:
                await self._fetch_openmeteo_pv(pv_systems)
            elif source == PV_SOURCE_FORECAST_SOLAR:
                await self._fetch_forecast_solar_pv(pv_systems)
            else:
                self._data.pv_forecast = [0] * 48
        except Exception as e:
            _LOGGER.error("Failed to fetch PV forecast: %s", e)
            self._data.pv_forecast = [0] * 48

    async def _fetch_akkudoktor_pv(self, pv_systems: list[dict]) -> None:
        """Fetch PV forecast from Akkudoktor."""
        session = await self._get_session()
        total_forecast = [0.0] * 48

        for system in pv_systems:
            lat = system.get("latitude", 52.52)
            lon = system.get("longitude", 13.405)
            power = system.get("power_wp", 10000)
            azimuth = system.get("azimuth", 0)
            tilt = system.get("tilt", 30)

            url = (
                f"https://api.akkudoktor.net/forecast?"
                f"lat={lat}&lon={lon}&power={power}&azimuth={azimuth}&tilt={tilt}"
            )

            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if "hourly" in data:
                            for i, val in enumerate(data["hourly"][:48]):
                                total_forecast[i] += float(val.get("power", 0))
            except Exception as e:
                _LOGGER.warning("Failed to fetch Akkudoktor PV: %s", e)

        self._data.pv_forecast = total_forecast

    async def _fetch_openmeteo_pv(self, pv_systems: list[dict]) -> None:
        """Fetch PV forecast from Open-Meteo."""
        session = await self._get_session()
        total_forecast = [0.0] * 48

        for system in pv_systems:
            lat = system.get("latitude", 52.52)
            lon = system.get("longitude", 13.405)
            power = system.get("power_wp", 10000)

            url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}&hourly=direct_radiation,diffuse_radiation"
            )

            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if "hourly" in data:
                            hourly = data["hourly"]
                            for i in range(min(48, len(hourly.get("direct_radiation", [])))):
                                direct = hourly.get("direct_radiation", [0])[i] or 0
                                diffuse = hourly.get("diffuse_radiation", [0])[i] or 0
                                irradiance = direct + diffuse
                                pv_power = (irradiance * power) / 1000
                                total_forecast[i] += pv_power
            except Exception as e:
                _LOGGER.warning("Failed to fetch Open-Meteo PV: %s", e)

        self._data.pv_forecast = total_forecast

    async def _fetch_forecast_solar_pv(self, pv_systems: list[dict]) -> None:
        """Fetch PV forecast from Forecast.Solar."""
        session = await self._get_session()
        total_forecast = [0.0] * 48

        for system in pv_systems:
            lat = system.get("latitude", 52.52)
            lon = system.get("longitude", 13.405)
            power = system.get("power_wp", 10000)
            azimuth = system.get("azimuth", 0)
            tilt = system.get("tilt", 30)
            power_kwp = power / 1000

            url = f"https://api.forecast.solar/estimate/{lat}/{lon}/{tilt}/{azimuth}/{power_kwp}"

            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if "result" in data and "watt_hours_period" in data["result"]:
                            wh = data["result"]["watt_hours_period"]
                            now_hour = dt_util.now().hour
                            for i, (ts, val) in enumerate(wh.items()):
                                if i < 48:
                                    total_forecast[i] += float(val)
            except Exception as e:
                _LOGGER.warning("Failed to fetch Forecast.Solar PV: %s", e)

        self._data.pv_forecast = total_forecast

    async def _update_prices(self) -> None:
        """Update electricity prices."""
        source = self.config.get(CONF_PRICE_SOURCE, PRICE_SOURCE_AKKUDOKTOR)

        try:
            if source == PRICE_SOURCE_TIBBER:
                await self._fetch_tibber_prices()
            elif source == PRICE_SOURCE_AKKUDOKTOR:
                await self._fetch_akkudoktor_prices()
            else:
                fixed_price = self.config.get("fixed_price", 0.30)
                self._data.prices = [fixed_price] * 48
        except Exception as e:
            _LOGGER.error("Failed to fetch prices: %s", e)
            self._data.prices = [0.30] * 48

    async def _fetch_tibber_prices(self) -> None:
        """Fetch prices from Tibber."""
        token = self.config.get(CONF_TIBBER_TOKEN)
        if not token:
            self._data.prices = [0.30] * 48
            return

        session = await self._get_session()
        url = "https://api.tibber.com/v1-beta/gql"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        query = {
            "query": """{
                viewer {
                    homes {
                        currentSubscription {
                            priceInfo {
                                today { total }
                                tomorrow { total }
                            }
                        }
                    }
                }
            }"""
        }

        try:
            async with session.post(url, json=query, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    prices = []
                    homes = data.get("data", {}).get("viewer", {}).get("homes", [])
                    if homes:
                        price_info = homes[0].get("currentSubscription", {}).get("priceInfo", {})
                        for entry in price_info.get("today", []) + price_info.get("tomorrow", []):
                            prices.append(float(entry.get("total", 0.30)))
                        while len(prices) < 48:
                            prices.append(prices[-1] if prices else 0.30)
                        self._data.prices = prices[:48]
                else:
                    self._data.prices = [0.30] * 48
        except Exception as e:
            _LOGGER.warning("Failed to fetch Tibber prices: %s", e)
            self._data.prices = [0.30] * 48

    async def _fetch_akkudoktor_prices(self) -> None:
        """Fetch prices from Akkudoktor."""
        session = await self._get_session()
        url = "https://api.akkudoktor.net/prices"

        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    prices = []
                    if "hourly" in data:
                        for entry in data["hourly"][:48]:
                            prices.append(float(entry.get("price", 0.30)))
                    while len(prices) < 48:
                        prices.append(prices[-1] if prices else 0.30)
                    self._data.prices = prices[:48]
                else:
                    self._data.prices = [0.30] * 48
        except Exception as e:
            _LOGGER.warning("Failed to fetch Akkudoktor prices: %s", e)
            self._data.prices = [0.30] * 48

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
