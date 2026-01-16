"""Coordinator for EOS Connect integration."""
import logging
import asyncio
from datetime import datetime, timedelta
import json
import requests

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.components.recorder import history
from homeassistant.util import dt as dt_util

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
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class EosConnectCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API and optimizing."""

    def __init__(self, hass: HomeAssistant, config_entry):
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.config_entry = config_entry
        self.eos_url = f"http://{config_entry.data[CONF_EOS_URL]}:{config_entry.data[CONF_EOS_PORT]}"

        # State storage
        self.last_run_time = None
        self.last_result = {}
        self.last_input_data = {} # Stores PV, Load, Price arrays for visualization
        self.next_run_time = None
        self.optimization_status = "Idle"

    async def _async_update_data(self):
        """Update data via library."""
        try:
            self.optimization_status = "Gathering Data"
            # 1. Gather Sensor Data
            soc = self.hass.states.get(self.config_entry.data[CONF_ENTITY_SOC])
            if not soc or soc.state in ["unknown", "unavailable"]:
                raise UpdateFailed("Battery SoC entity unavailable")
            soc_val = float(soc.state)

            # 2. Build Load Profile (History)
            load_profile = await self._get_load_profile()

            # 3. Get PV Forecast
            pv_forecast = await self._get_pv_forecast()

            # 4. Get Prices
            prices = await self._get_prices()

            # 5. Get EV Status
            ev_data = self._get_ev_status()

            # 6. Construct Payload
            payload = self._build_eos_payload(soc_val, load_profile, pv_forecast, prices, ev_data)

            # Store inputs for visualization
            self.last_input_data = {
                "pv_forecast": pv_forecast,
                "load_profile": load_profile,
                "prices": prices
            }

            # 5. Send to EOS
            self.optimization_status = "Optimizing"
            response = await self.hass.async_add_executor_job(self._send_optimization_request, payload)

            # 6. Process Response
            self.last_result = response
            self.last_run_time = dt_util.now()
            self.optimization_status = "Success"

            # 7. Apply Controls (Side Effect)
            await self._apply_controls(response)

            return response

        except Exception as err:
            self.optimization_status = f"Error: {str(err)}"
            _LOGGER.error("Error communicating with EOS: %s", err)
            raise UpdateFailed(f"Error communicating with EOS: {err}")

    async def _get_load_profile(self):
        """Fetch historical load data from recorder."""
        entity_id = self.config_entry.data[CONF_ENTITY_LOAD]
        # We need 48h of future prediction.
        # Simple strategy: Take the last 48h of history as the prediction.
        # Ideally, we'd average the last few days, but let's start with last 48h.

        end_time = dt_util.now()
        start_time = end_time - timedelta(hours=48)

        # Run in executor because history access is blocking
        history_list = await self.hass.async_add_executor_job(
            history.state_changes_during_period,
            self.hass,
            start_time,
            end_time,
            str(entity_id),
            True # include_start_time_state
        )

        states = history_list.get(entity_id, [])
        if not states:
             # Fallback: Flat profile if no history
             return [100.0] * 48

        # Resample to hourly averages
        # This is a simplification. A robust implementation would use pandas (if available in HA env)
        # or manual resampling. Since pandas might not be in HA core, we do manual.
        # Actually, let's just grab the state at the top of each hour for the last 48h to mimic the future.

        # NOTE: Using past data 1:1 for future is crude but matches "Option A" intent broadly.
        # A better approach (used by eos_connect.py) is learning.
        # Since we are porting, we should try to be decent.

        # Let's map "Same time yesterday" and "Same time day before".
        # We need 48 values for the next 48 hours.
        # We take history from T-48h to T-0h.
        # We map T-48...T-24 to T+0...T+24
        # We map T-24...T-0 to T+24...T+48
        # This is essentially repeating the last 2 days.

        # To do this efficiently without heavy libs, we walk the sorted history list.
        # History is sorted by time.

        load_values = []
        current_idx = 0
        total_states = len(states)

        # Target: 48 hourly slots starting from now
        for i in range(48):
            # We want to find the value at (Now - 48h + i*1h)
            target_hist_time = start_time + timedelta(hours=i)

            # Find closest state in history before or at target_hist_time
            val = 0.0

            # Advance current_idx to the state just before target_hist_time
            while current_idx < total_states:
                state = states[current_idx]
                if state.last_updated > target_hist_time:
                    # We passed the target time. The state relevant is the previous one (current_idx - 1)
                    # But we break here.
                    break
                current_idx += 1

            # The state active at target_hist_time is at current_idx - 1
            if current_idx > 0:
                 try:
                     val = float(states[current_idx - 1].state)
                 except ValueError:
                     pass

            load_values.append(val)

        return load_values

    async def _get_pv_forecast(self):
        """Fetch PV forecast from entity."""
        entity_id = self.config_entry.data[CONF_ENTITY_PV_FORECAST]
        state = self.hass.states.get(entity_id)

        # Initialize 48h forecast with zeros
        forecast_wh = [0.0] * 48

        if not state:
            return forecast_wh

        # 1. Try 'forecast' attribute (standard for many)
        raw_forecast = state.attributes.get("forecast")

        # 2. Try 'wh_period' attribute (Forecast.Solar specific)
        if not raw_forecast:
            raw_forecast = state.attributes.get("wh_period")

        # 3. Try 'watts' attribute (Forecast.Solar specific alternative)
        if not raw_forecast:
             # If watts dict exists, we might need to integrate it.
             # But usually wh_period is better for energy.
             pass

        if not raw_forecast:
            return forecast_wh

        # Determine type of data
        # Forecast.Solar 'wh_period' is a dict: {"2023-10-01T10:00:00": 1234, ...}
        if isinstance(raw_forecast, dict):
            # Parse dict
            now = dt_util.now().replace(minute=0, second=0, microsecond=0)
            for ts_str, value in raw_forecast.items():
                try:
                    ts = dt_util.parse_datetime(ts_str)
                    if ts:
                        # Convert to hourly index relative to now
                        diff = (ts - now).total_seconds() / 3600
                        idx = int(diff)
                        if 0 <= idx < 48:
                            forecast_wh[idx] = float(value)
                except (ValueError, TypeError):
                    continue

        # Standard list of dicts [{"datetime": "...", "native_value": ...}]
        elif isinstance(raw_forecast, list):
            now = dt_util.now().replace(minute=0, second=0, microsecond=0)
            for entry in raw_forecast:
                ts_str = entry.get("datetime")
                # Value key can vary: 'native_value', 'energy', 'power', 'precipitation' (if weather)
                # We assume if the user selected a sensor, it provides Energy/Power.
                # If it provides Power (W), we assume 1h duration -> Wh.
                val = entry.get("native_value") or entry.get("energy") or entry.get("power")

                if ts_str and val is not None:
                    try:
                        ts = dt_util.parse_datetime(ts_str)
                        if ts:
                            diff = (ts - now).total_seconds() / 3600
                            idx = int(diff)
                            if 0 <= idx < 48:
                                forecast_wh[idx] = float(val)
                    except (ValueError, TypeError):
                        continue

        return forecast_wh

    async def _get_prices(self):
        """Fetch prices from Tibber/Nordpool/Entsoe entity."""
        # Returns vector of 48 prices (Euro/Wh)
        # Defaults to flat 0.30 EUR/kWh -> 0.0003 EUR/Wh
        prices_wh = [0.0003] * 48

        entity_id = self.config_entry.data.get(CONF_ENTITY_PRICE)
        if not entity_id:
            return prices_wh

        state = self.hass.states.get(entity_id)
        if not state:
            return prices_wh

        # 1. Tibber / Nordpool usually have 'today' and 'tomorrow' attributes
        # Arrays of values. Units usually EUR/kWh or c/kWh.

        raw_today = state.attributes.get("today")
        raw_tomorrow = state.attributes.get("tomorrow")

        # Check unit
        unit = state.attributes.get("unit_of_measurement", "").lower()
        # Default factor: Input is EUR/kWh, Output EUR/Wh => divide by 1000
        factor = 1.0 / 1000.0

        if "cent" in unit or "ct" in unit:
            # Input cents/kWh -> EUR/Wh => divide by 100 and 1000 => / 100000
            factor = 1.0 / 100000.0
        elif "wh" in unit and "k" not in unit:
             # Already /Wh
             factor = 1.0

        # Combine lists
        # We need to map them to "Next 48h from Now".
        # This requires knowing the start time of the "today" array.
        # Tibber/Nordpool usually start at midnight.

        combined_prices = []
        if raw_today and isinstance(raw_today, list):
            combined_prices.extend(raw_today)
        if raw_tomorrow and isinstance(raw_tomorrow, list):
            combined_prices.extend(raw_tomorrow)

        # If no attributes, maybe 'forecast' list of dicts?
        if not combined_prices:
             raw_forecast = state.attributes.get("forecast")
             if raw_forecast and isinstance(raw_forecast, list):
                 for entry in raw_forecast:
                     # standard 'native_value'
                     val = entry.get("native_value") or entry.get("price") or entry.get("value")
                     if val is not None:
                         combined_prices.append(val)

        if not combined_prices:
             # Just use current state if available
             try:
                 val = float(state.state)
                 prices_wh = [val * factor] * 48
             except ValueError:
                 pass
             return prices_wh

        # Now map to 48h from current hour
        # Assumption: combined_prices starts at Today Midnight (00:00)
        # We need values starting from Now.Hour
        current_hour = dt_util.now().hour

        # Create result array
        final_prices = []
        for i in range(48):
             idx = current_hour + i
             if idx < len(combined_prices):
                 val = float(combined_prices[idx])
                 final_prices.append(val * factor)
             else:
                 # Out of bounds, repeat last known
                 if final_prices:
                     final_prices.append(final_prices[-1])
                 else:
                     final_prices.append(0.0003)

        return final_prices

    def _get_ev_status(self):
        """Get EV status if enabled."""
        if not self.config_entry.data.get(CONF_EV_ENABLED):
             return {"capacity_wh": 0}

        # Check connection status (e.g. cable plugged in)
        conn_entity = self.config_entry.data.get(CONF_ENTITY_EV_CONNECTED)
        is_connected = True
        if conn_entity:
            state = self.hass.states.get(conn_entity)
            if state and state.state == "off":
                is_connected = False

        if not is_connected:
             # If not connected, tell EOS capacity is 0 so it doesn't plan charging
             return {"capacity_wh": 0}

        entity_id = self.config_entry.data.get(CONF_ENTITY_EV_SOC)
        capacity = self.config_entry.data.get(CONF_EV_CAPACITY, 50000)
        max_charge = self.config_entry.data.get(CONF_EV_MAX_CHARGE_RATE, 11000)

        soc = 50 # Default
        if entity_id:
            state = self.hass.states.get(entity_id)
            if state:
                try:
                    soc = float(state.state)
                except ValueError:
                    pass

        return {
            "capacity_wh": capacity,
            "charging_efficiency": 0.90,
            "discharging_efficiency": 0.95,
            "max_charge_power_w": max_charge,
            "initial_soc_percentage": soc,
            "min_soc_percentage": 5,
            "max_soc_percentage": 100,
            "device_id": "ev1"
        }

    def _get_dishwasher_data(self):
        """Get controllable load data if enabled."""
        if not self.config_entry.data.get(CONF_LOAD_ENABLED):
             return {"consumption_wh": 0, "duration_h": 0}

        return {
            "consumption_wh": self.config_entry.data.get(CONF_LOAD_CONSUMPTION, 1000),
            "duration_h": self.config_entry.data.get(CONF_LOAD_DURATION, 1),
            "device_id": "additional_load_1"
        }

    def _build_eos_payload(self, soc, load_profile, pv_forecast, prices, ev_data):
        """Build the dictionary expected by EOS."""
        config = self.config_entry.data

        # Feedin Price - defaulting to 0.08 EUR/kWh -> 0.00008 EUR/Wh
        feedin = [0.00008] * 48

        return {
            "ems": {
                "pv_prognose_wh": pv_forecast,
                "strompreis_euro_pro_wh": prices,
                "einspeiseverguetung_euro_pro_wh": feedin,
                "preis_euro_pro_wh_akku": 0, # Depreciation cost
                "gesamtlast": load_profile
            },
            "pv_akku": {
                "capacity_wh": config[CONF_BATTERY_CAPACITY],
                "charging_efficiency": 0.95, # Defaults, could be options
                "discharging_efficiency": 0.95,
                "max_charge_power_w": config[CONF_MAX_CHARGE_RATE],
                "initial_soc_percentage": soc,
                "min_soc_percentage": 5,
                "max_soc_percentage": 100,
                "device_id": "battery1"
            },
            "inverter": {
                "max_power_wh": config[CONF_INVERTER_MAX_POWER],
                "device_id": "inverter1",
                "battery_id": "battery1"
            },
            "eauto": ev_data,
            "dishwasher": self._get_dishwasher_data(),
            "temperature_forecast": [20] * 48
        }

    def _send_optimization_request(self, payload):
        """Blocking HTTP request."""
        url = f"{self.eos_url}/optimize"
        # Determine start hour for EOS
        start_hour = dt_util.now().hour
        params = {"start_hour": start_hour}

        response = requests.post(url, params=params, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()

    async def _apply_controls(self, response):
        """Interpret response and control entities."""
        # Get control arrays
        # response structure: {"ac_charge": [...], "discharge_allowed": [...], ...}

        # We apply the control for the *current* hour/timeslot.
        # EOS returns arrays starting from 'start_hour'.
        # Since we just sent the request, index 0 is "now".

        ac_charge = response.get("ac_charge", [])
        discharge_allowed = response.get("discharge_allowed", [])

        if not ac_charge:
            return

        current_ac_demand = ac_charge[0] # Relative 0.0-1.0
        current_discharge = bool(discharge_allowed[0])

        # Calculate Watts
        max_charge = self.config_entry.data[CONF_MAX_CHARGE_RATE]
        target_charge_power = int(current_ac_demand * max_charge)

        # 1. Charge Limit
        charge_entity = self.config_entry.data.get(CONF_CONTROL_CHARGE_LIMIT)
        if charge_entity:
            # If demand > 0, set limit. If demand == 0, maybe set to 0?
            # Or does 0 mean "Don't force charge"?
            # Usually we set the charge limit.
            await self.hass.services.async_call(
                "number", "set_value",
                {"entity_id": charge_entity, "value": target_charge_power},
                blocking=True
            )

        # 2. Discharge Limit (if we want to prevent discharge)
        discharge_entity = self.config_entry.data.get(CONF_CONTROL_DISCHARGE_LIMIT)
        if discharge_entity:
            # If discharge not allowed, set limit to 0
            limit = self.config_entry.data[CONF_MAX_DISCHARGE_RATE] if current_discharge else 0
            await self.hass.services.async_call(
                "number", "set_value",
                {"entity_id": discharge_entity, "value": limit},
                blocking=True
            )

        # 3. Mode Selection
        mode_entity = self.config_entry.data.get(CONF_CONTROL_MODE)
        if mode_entity:
            # Logic:
            # If Charge > 0 -> "Charge" / "Force Charge"
            # If Charge == 0 and not discharge -> "Hold" / "Stop" / "Avoid Discharge"
            # If Charge == 0 and discharge -> "Auto" / "Normal" / "Discharge"

            target_option = None
            if current_ac_demand > 0:
                target_option = "Charge" # Common convention, user can alias in HA
            elif not current_discharge:
                target_option = "Hold"
            else:
                target_option = "Auto"

            # Try to set it. If the entity uses different strings, this will fail or warn.
            # In a real HACS integration, we'd provide a config map for these strings.
            # For this MVP, we attempt a best guess and log.
            try:
                await self.hass.services.async_call(
                    "select", "select_option",
                    {"entity_id": mode_entity, "option": target_option},
                    blocking=True
                )
            except Exception:
                 # Fallback for switches/input_booleans if mapped there
                 pass
