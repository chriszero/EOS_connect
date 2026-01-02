"""
Battery Price Calculation Handler

This module provides dynamic battery energy price calculation functionality
by analyzing historical charging events and attributing energy sources (PV vs Grid).
"""

import logging
from datetime import datetime, timedelta, tzinfo
import threading
from typing import Dict, List, Optional, Tuple, Any
import pytz

logger = logging.getLogger("__main__")
logger.info("[BATTERY-PRICE] loading module")


class BatteryPriceHandler:
    """
    Handler for calculating battery energy prices based on historical charging data.

    The handler uses a forensic analysis approach to determine the cost of energy
    currently stored in the battery. It works by:
    1. Identifying historical charging periods from battery power data.
    2. Attributing energy sources (PV surplus vs Grid import) for each period.
    3. Applying historical electricity prices to grid-charged energy.
    4. Calculating a weighted average price (€/Wh) for the total energy charged.

    This approach is more accurate than live-only tracking because it can reconstruct
    the cost of energy that was charged hours or days ago.
    """

    # pylint: disable=too-many-instance-attributes

    # Constants for algorithm tuning
    MAX_GAP_SECONDS_IDENTIFY = 600  # Gap tolerance when identifying charging events
    MAX_GAP_MINUTES_MERGE = 30  # Gap tolerance when merging fetch ranges
    BUFFER_HOURS_LOOKBACK = 12  # Extra history to fetch for session reconstruction
    DEFAULT_DELTA_SECONDS = 300  # Fallback time delta between points

    def __init__(self, config: Dict[str, Any], load_interface=None, timezone=None):
        """
        Initialize the battery price handler.

        Args:
            config: Configuration dictionary with battery and sensor settings
            load_interface: Optional LoadInterface instance for historical data access
            timezone: Optional timezone object
        """
        self.config = config
        self.load_interface = load_interface
        self.timezone: Optional[tzinfo] = timezone

        # Configuration
        self.source = config.get("source", "homeassistant")
        self.url = config.get("url", "")
        self.access_token = config.get("access_token", "")
        self.price_calculation_enabled = config.get("price_calculation_enabled", False)
        self.price_update_interval = config.get("price_update_interval", 900)  # 15 min
        self.price_history_lookback_hours = config.get(
            "price_history_lookback_hours", 48
        )

        # Sensor configuration
        self.battery_power_sensor = config.get("battery_power_sensor", "")
        self.pv_power_sensor = config.get("pv_power_sensor", "")
        self.grid_power_sensor = config.get("grid_power_sensor", "")
        self.load_power_sensor = config.get("load_power_sensor", "")
        self.price_sensor = config.get("price_sensor", "")

        # Battery parameters
        self.charge_efficiency = config.get("charge_efficiency", 0.95)
        self.capacity_wh = config.get("capacity_wh", 10000)
        self.min_soc_percentage = config.get("min_soc_percentage", 10)
        self.price_euro_per_wh_accu = config.get("price_euro_per_wh_accu", 0.00004)

        # Thresholds to filter sensor noise and transients
        self.charging_threshold_w = config.get("charging_threshold_w", 50.0)
        self.grid_charge_threshold_w = config.get("grid_charge_threshold_w", 100.0)

        # State
        self.price_euro_per_wh = self.price_euro_per_wh_accu
        self.last_price_calculation: Optional[datetime] = (
            (datetime.now(self.timezone) if self.timezone else datetime.now())
            if self.price_calculation_enabled
            else None
        )
        self.battery_power_convention: Optional[str] = None  # Will be auto-detected
        self.last_analysis_results = {
            "stored_energy_price": self.price_euro_per_wh_accu,
            "duration_of_analysis": 0,
            "charged_energy": 0.0,
            "charged_from_pv": 0.0,
            "charged_from_grid": 0.0,
            "ratio": 0.0,
            "charging_sessions": [],
            "last_update": None,
        }

        # Validation
        if self.price_calculation_enabled:
            self._validate_configuration()
            logger.info(
                "[BATTERY-PRICE] Dynamic price calculation enabled (Interval: %ss, Lookback: %sh)",
                self.price_update_interval,
                self.price_history_lookback_hours,
            )
        else:
            logger.info(
                "[BATTERY-PRICE] Dynamic price calculation is disabled in config"
            )

    def _validate_configuration(self):
        """Validate that required configuration is present."""
        required_sensors = [
            self.battery_power_sensor,
            self.pv_power_sensor,
            self.grid_power_sensor,
            self.load_power_sensor,
            self.price_sensor,
        ]

        missing = [s for s in required_sensors if not s]
        if missing:
            raise ValueError(f"Missing required sensors: {missing}")

        # If we have a load_interface, we use its connection settings
        if not self.load_interface:
            if not self.url:
                raise ValueError("URL is required when no LoadInterface is provided")
            if self.source == "homeassistant" and not self.access_token:
                raise ValueError("Access token is required for Home Assistant")

    def calculate_battery_price_from_history(
        self, lookback_hours: Optional[int] = None, inventory_wh: Optional[float] = None
    ) -> Optional[float]:
        """
        Calculate battery price by analyzing historical charging data.

        The algorithm performs the following steps:
        1. Fetches battery power history for the lookback period.
        2. Identifies "charging events" where battery power > threshold.
        3. For each event, fetches aligned PV, Grid, and Load power data.
        4. Splits the charging energy into PV-sourced and Grid-sourced.
        5. Calculates costs per event.
        6. If inventory_wh is provided, it uses an "inventory" approach:
           - It goes backwards through sessions until the inventory_wh is reached.
           - This ensures the price reflects the energy actually stored.

        Args:
            lookback_hours: Hours of history to analyze (overrides config)
            inventory_wh: Current energy stored in battery (Wh) to use for inventory calculation

        Returns:
            Weighted average price in €/Wh, or None if calculation failed
        """
        if lookback_hours is None:
            lookback_hours = self.price_history_lookback_hours

        try:
            logger.info(
                "[BATTERY-PRICE] Starting historical analysis (%sh lookback, Inventory: %s Wh)",
                lookback_hours,
                round(inventory_wh, 1) if inventory_wh is not None else "N/A",
            )

            # Fetch all required sensors for the full lookback period
            keys_to_fetch = [
                "battery_power",
                "pv_power",
                "grid_power",
                "load_power",
                "price_data",
            ]

            logger.debug("[BATTERY-PRICE] Fetching historical power data...")
            historical_data = self._fetch_historical_power_data(
                lookback_hours,
                keys=keys_to_fetch,
            )
            logger.debug("[BATTERY-PRICE] Historical power data fetch complete")

            if not historical_data or not historical_data.get("battery_power"):
                logger.warning("[BATTERY-PRICE] No battery power data available")
                self.last_analysis_results["last_update"] = self._get_now_iso()
                return None

            # Log data points received
            logger.debug(
                "[BATTERY-PRICE] Data points received - Battery: %d, PV: %d, Grid: %d, Load: %d, Price: %d",
                len(historical_data.get("battery_power", [])),
                len(historical_data.get("pv_power", [])),
                len(historical_data.get("grid_power", [])),
                len(historical_data.get("load_power", [])),
                len(historical_data.get("price_data", [])),
            )

            # Reconstruct charging events
            logger.debug("[BATTERY-PRICE] Identifying charging periods...")
            charging_events = self._identify_charging_periods(historical_data)
            logger.info(
                "[BATTERY-PRICE] Found %s charging events", len(charging_events)
            )

            if not charging_events:
                logger.info(
                    "[BATTERY-PRICE] No charging events found, keeping current price"
                )
                self.last_analysis_results = {
                    "stored_energy_price": round(self.price_euro_per_wh, 6),
                    "duration_of_analysis": lookback_hours,
                    "charged_energy": 0.0,
                    "charged_from_pv": 0.0,
                    "charged_from_grid": 0.0,
                    "ratio": 0.0,
                    "charging_sessions": [],
                    "last_update": self._get_now_iso(),
                }
                return self.price_euro_per_wh

            # Calculate costs per event
            logger.debug(
                "[BATTERY-PRICE] Calculating total costs for %d events...",
                len(charging_events),
            )
            results = self._calculate_total_costs(
                charging_events, historical_data, lookback_hours, inventory_wh
            )
            logger.debug("[BATTERY-PRICE] Cost calculation complete")

            total_cost = results["total_cost"]
            total_energy_charged = results["total_energy_charged"]

            # Weighted average
            weighted_price = (
                total_cost / total_energy_charged
                if total_energy_charged > 0
                else self.price_euro_per_wh
            )

            # Store results for external reporting (ALWAYS)
            logger.debug("[BATTERY-PRICE] Storing analysis results...")
            self.last_analysis_results = {
                "stored_energy_price": round(weighted_price, 6),
                "duration_of_analysis": lookback_hours,
                "charged_energy": round(total_energy_charged, 1),
                "charged_from_pv": round(results["total_pv_energy"], 1),
                "charged_from_grid": round(results["total_grid_energy"], 1),
                "ratio": round(results["pv_ratio"], 1),
                "charging_sessions": results["sessions"],
                "last_update": self._get_now_iso(),
            }

            if total_energy_charged > 0:
                logger.info(
                    "[BATTERY-PRICE] Final Price %.4f€/kWh (Total Charged %.1fWh)",
                    weighted_price * 1000,
                    total_energy_charged,
                )
                return weighted_price

            logger.info("[BATTERY-PRICE] No energy charged in identified events")
            return self.price_euro_per_wh

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "[BATTERY-PRICE] Error in historical calculation: %s", e, exc_info=True
            )
            return None

    # pylint: disable=too-many-locals
    def _calculate_total_costs(
        self,
        charging_events: List[Dict],
        historical_data: Dict,
        lookback_hours: int,
        inventory_wh: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Calculate total cost and energy from all charging events."""
        total_cost = 0.0
        total_energy_charged = 0.0
        total_pv_energy = 0.0
        total_grid_energy = 0.0
        sessions = []

        now_tz = (
            datetime.now(self.timezone) if self.timezone else datetime.now(pytz.utc)
        )
        active_window_start = now_tz - timedelta(hours=lookback_hours)

        # First, calculate all sessions in the window
        all_sessions_data = []
        for i, event in enumerate(charging_events):
            # Skip events that end before our active window
            if event["end_time"] < active_window_start:
                continue

            event_totals = self._split_energy_sources(event, historical_data)
            energy_from_pv = event_totals["pv_to_battery_wh"]
            energy_from_grid = event_totals["grid_to_battery_wh"]
            battery_in_wh = event_totals["total_battery_wh"]

            # Skip sessions with no energy (e.g. single point sessions)
            if battery_in_wh <= 0.001:
                continue

            # Apply efficiency to the cost
            event_cost = event_totals["grid_cost_euro"] / self.charge_efficiency

            all_sessions_data.append(
                {
                    "start_time": event["start_time"],
                    "end_time": event["end_time"],
                    "charged_energy": battery_in_wh,
                    "charged_from_pv": energy_from_pv,
                    "charged_from_grid": energy_from_grid,
                    "cost": event_cost,
                    "is_inventory": False,
                    "inventory_energy": 0.0,
                }
            )

        # Inventory approach: walk backwards from most recent session
        accumulated_inventory = 0.0

        # Sort sessions by end_time descending (most recent first)
        all_sessions_data.sort(key=lambda x: x["end_time"], reverse=True)

        for session in all_sessions_data:
            if inventory_wh is not None and accumulated_inventory < inventory_wh:
                remaining_needed = inventory_wh - accumulated_inventory
                session_energy = session["charged_energy"]

                session["is_inventory"] = True
                if session_energy <= remaining_needed:
                    # Full session is part of inventory
                    session["inventory_energy"] = session_energy
                    accumulated_inventory += session_energy
                else:
                    # Partial session is part of inventory
                    session["inventory_energy"] = remaining_needed
                    accumulated_inventory = inventory_wh

            # Final aggregation for the price (only use inventory if inventory_wh provided)
            if inventory_wh is None or session["is_inventory"]:
                # If inventory mode, we only use the inventory_energy part for the price
                energy_to_use = (
                    session["inventory_energy"]
                    if inventory_wh is not None
                    else session["charged_energy"]
                )
                ratio = energy_to_use / session["charged_energy"]

                total_cost += session["cost"] * ratio
                total_energy_charged += energy_to_use
                total_pv_energy += session["charged_from_pv"] * ratio
                total_grid_energy += session["charged_from_grid"] * ratio

        # Prepare sessions for output (sort back to chronological)
        all_sessions_data.sort(key=lambda x: x["start_time"])

        for session in all_sessions_data:
            sessions.append(
                {
                    "start_time": session["start_time"].isoformat(),
                    "end_time": session["end_time"].isoformat(),
                    "charged_energy": round(session["charged_energy"], 1),
                    "charged_from_pv": round(session["charged_from_pv"], 1),
                    "charged_from_grid": round(session["charged_from_grid"], 1),
                    "ratio": (
                        round(
                            session["charged_from_pv"]
                            / session["charged_energy"]
                            * 100,
                            1,
                        )
                        if session["charged_energy"] > 0
                        else 0
                    ),
                    "cost": round(session["cost"], 4),
                    "is_inventory": session["is_inventory"],
                    "inventory_energy": round(session["inventory_energy"], 1),
                }
            )

        pv_ratio = (
            (total_pv_energy / total_energy_charged * 100)
            if total_energy_charged > 0
            else 0
        )
        logger.info(
            "[BATTERY-PRICE] Summary: PV %.1fWh, Grid %.1fWh, Ratio PV %.1f%%, Cost %.4f€",
            total_pv_energy,
            total_grid_energy,
            pv_ratio,
            total_cost,
        )

        return {
            "total_cost": total_cost,
            "total_energy_charged": total_energy_charged,
            "total_pv_energy": total_pv_energy,
            "total_grid_energy": total_grid_energy,
            "pv_ratio": pv_ratio,
            "sessions": sessions,
        }

    def should_update_price(self) -> bool:
        """Check if it's time to update the price."""
        if not self.price_calculation_enabled:
            return False

        now = datetime.now(self.timezone) if self.timezone else datetime.now()
        if self.last_price_calculation is None:
            return True

        time_since_last = (now - self.last_price_calculation).total_seconds()
        return time_since_last >= self.price_update_interval

    def update_price_if_needed(self, inventory_wh: Optional[float] = None) -> bool:
        """Update price if the update interval has passed."""
        if not self.should_update_price():
            return False

        new_price = self.calculate_battery_price_from_history(inventory_wh=inventory_wh)
        if new_price is not None:
            self.price_euro_per_wh = new_price
            self.last_price_calculation = (
                datetime.now(self.timezone) if self.timezone else datetime.now()
            )
            return True

        return False

    def _fetch_historical_power_data(
        self, lookback_hours: int, keys: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """Fetch historical power data."""
        try:
            end_time = datetime.now(self.timezone) if self.timezone else datetime.now()
            start_time = end_time - timedelta(
                hours=lookback_hours + self.BUFFER_HOURS_LOOKBACK
            )

            if self.load_interface:
                return self._fetch_via_load_interface(start_time, end_time, keys)

            return self._fetch_via_direct_api(start_time, end_time, keys)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("[BATTERY-PRICE] Failed to fetch historical data: %s", e)
            return None

    def _fetch_via_load_interface(
        self, start_time: datetime, end_time: datetime, keys: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """Fetch data using LoadInterface with parallel sensor fetching."""
        try:
            all_sensors = [
                (self.battery_power_sensor, "battery_power"),
                (self.pv_power_sensor, "pv_power"),
                (self.grid_power_sensor, "grid_power"),
                (self.load_power_sensor, "load_power"),
                (self.price_sensor, "price_data"),
            ]

            sensors = all_sensors
            if keys:
                sensors = [s for s in all_sensors if s[1] in keys]

            # Parallel fetching with threading
            fetch_results = {}
            fetch_lock = threading.Lock()

            def fetch_sensor_data(sensor, key):
                """Thread worker to fetch data for a single sensor."""
                try:
                    sensor_data = self.load_interface.fetch_historical_energy_data(
                        entity_id=sensor, start_time=start_time, end_time=end_time
                    )
                    converted_data = self._convert_historical_data(sensor_data, key)
                    with fetch_lock:
                        fetch_results[key] = converted_data
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.warning("[BATTERY-PRICE] Failed to fetch %s: %s", key, e)
                    with fetch_lock:
                        fetch_results[key] = []

            # Create and start threads for parallel fetching
            threads = []
            logger.debug(
                "[BATTERY-PRICE] Starting parallel fetch of %d sensors for %.1fh lookback",
                len(sensors),
                (end_time - start_time).total_seconds() / 3600,
            )

            for sensor, key in sensors:
                thread = threading.Thread(
                    target=fetch_sensor_data,
                    args=(sensor, key),
                    daemon=False,  # Changed to False
                )
                threads.append(thread)
                thread.start()

            # Wait for all threads to complete with timeout
            for thread in threads:
                thread.join(timeout=120)  # 2 minute timeout per thread
                if thread.is_alive():
                    logger.warning(
                        "[BATTERY-PRICE] Thread timeout waiting for sensor fetch"
                    )

            logger.debug(
                "[BATTERY-PRICE] Parallel fetch completed, retrieved %d/%d sensors",
                sum(1 for v in fetch_results.values() if v),
                len(sensors),
            )

            return fetch_results

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("[BATTERY-PRICE] LoadInterface fetch failed: %s", e)
            return None

    def _convert_historical_data(self, sensor_data: List[Dict], key: str) -> List[Dict]:
        """Convert historical data format to internal format."""
        converted_data = []
        for entry in sensor_data:
            try:
                timestamp = datetime.fromisoformat(
                    entry["last_updated"].replace("Z", "+00:00")
                )
                # Handle potential units in state string (e.g. "10.5 W")
                state_val = entry.get("state")
                if state_val is None:
                    continue
                if isinstance(state_val, str):
                    state_val = state_val.split()[0]
                value = float(state_val)
                # Price conversion logic
                if key == "price_data":
                    if value > 1.0:  # Likely in ct/kWh
                        value = value / 100.0
                converted_data.append({"timestamp": timestamp, "value": value})
            except (ValueError, KeyError, IndexError):
                continue
        return converted_data

    def _fetch_via_direct_api(
        self, start_time: datetime, end_time: datetime, keys: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """Fetch data directly via API (fallback when LoadInterface is not available)."""
        # pylint: disable=unused-argument
        # Implementation for direct API fetch if LoadInterface is not available
        # For now, return empty dict as it's a fallback
        return {}

    def _localize_time(self, dt: datetime) -> str:
        """Convert UTC datetime to local timezone and format as string."""
        if dt.tzinfo is None:
            dt = pytz.utc.localize(dt)

        local_tz = self.timezone if self.timezone else pytz.timezone("Europe/Berlin")
        return dt.astimezone(local_tz).strftime("%Y-%m-%d %H:%M:%S")

    def _detect_battery_power_convention(self, historical_data: Dict) -> str:
        """Detect battery power convention from historical data by analyzing charging context."""
        if "battery_power" not in historical_data:
            return "positive_charging"  # default

        battery_data = historical_data["battery_power"]
        pv_data = historical_data.get("pv_power", [])
        grid_data = historical_data.get("grid_power", [])
        load_data = historical_data.get("load_power", [])

        if not battery_data:
            return "positive_charging"

        # OPTIMIZATION: Sample only recent data for convention detection (last 24h is enough)
        # This avoids O(n²) performance issue with 96h of data
        logger.debug(
            "[BATTERY-PRICE] Detecting battery power convention from recent data..."
        )

        # Take only the most recent 20% of data points (but at least 100 points)
        sample_size = max(100, len(battery_data) // 5)
        battery_sample = battery_data[-sample_size:]

        # Sort all data by timestamp for alignment
        battery_sample.sort(key=lambda x: x["timestamp"])
        pv_data.sort(key=lambda x: x["timestamp"])
        grid_data.sort(key=lambda x: x["timestamp"])
        load_data.sort(key=lambda x: x["timestamp"])

        # Get time range of sample
        if battery_sample:
            sample_start = battery_sample[0]["timestamp"]
            sample_end = battery_sample[-1]["timestamp"]

            # Filter other sensors to same time range to reduce search space
            pv_data_filtered = [
                p for p in pv_data if sample_start <= p["timestamp"] <= sample_end
            ]
            grid_data_filtered = [
                p for p in grid_data if sample_start <= p["timestamp"] <= sample_end
            ]
            load_data_filtered = [
                p for p in load_data if sample_start <= p["timestamp"] <= sample_end
            ]
        else:
            pv_data_filtered = pv_data
            grid_data_filtered = grid_data
            load_data_filtered = load_data

        # Counters for contextual charging events
        evcc_charging_count = 0  # negative battery power + energy available
        standard_charging_count = 0  # positive battery power + energy available

        threshold = self.charging_threshold_w

        for battery_point in battery_sample:
            battery_power = battery_point.get("value", 0)
            timestamp = battery_point["timestamp"]

            # Only consider significant battery power events
            if abs(battery_power) <= threshold:
                continue

            # Check if energy is available for charging at this timestamp
            grid_power = self._get_value_at_timestamp(grid_data_filtered, timestamp)
            pv_power = self._get_value_at_timestamp(pv_data_filtered, timestamp)
            load_power = self._get_value_at_timestamp(load_data_filtered, timestamp)

            # Determine if there's surplus energy available
            grid_importing = grid_power > threshold
            pv_surplus = pv_power > (load_power + threshold)

            energy_available = grid_importing or pv_surplus

            if energy_available:
                if battery_power < -threshold:
                    evcc_charging_count += 1
                elif battery_power > threshold:
                    standard_charging_count += 1

        # Determine convention based on contextual charging events
        total_contextual_events = evcc_charging_count + standard_charging_count

        logger.debug(
            "[BATTERY-PRICE] Convention detection: %d standard, %d EVCC events from %d samples",
            standard_charging_count,
            evcc_charging_count,
            len(battery_sample),
        )

        if total_contextual_events < 3:
            # Not enough contextual data, fall back to simple heuristic
            return self._fallback_convention_detection(battery_sample)
        elif evcc_charging_count > standard_charging_count:
            return "negative_charging"
        else:
            return "positive_charging"

    def _get_value_at_timestamp(
        self, data: List[Dict], target_timestamp: datetime
    ) -> float:
        """Get the sensor value closest to the target timestamp."""
        if not data:
            return 0.0

        # Find the closest timestamp
        closest_point = min(
            data, key=lambda x: abs((x["timestamp"] - target_timestamp).total_seconds())
        )
        time_diff = abs((closest_point["timestamp"] - target_timestamp).total_seconds())

        # Only use if within reasonable time window (5 minutes)
        if time_diff <= 300:
            return closest_point.get("value", 0.0)
        return 0.0

    def _fallback_convention_detection(self, battery_data: List[Dict]) -> str:
        """Fallback detection when contextual analysis has insufficient data."""
        # Simple heuristic: look at the most common sign of high-power events
        threshold = self.charging_threshold_w * 2
        positive_count = 0
        negative_count = 0

        for point in battery_data:
            power = abs(point.get("value", 0))
            if power > threshold:
                if point.get("value", 0) > 0:
                    positive_count += 1
                elif point.get("value", 0) < 0:
                    negative_count += 1

        return (
            "negative_charging"
            if negative_count > positive_count
            else "positive_charging"
        )

    def _identify_charging_periods(self, historical_data: Dict) -> List[Dict]:
        """Identify periods when battery was charging."""
        if not historical_data or "battery_power" not in historical_data:
            return []

        # Auto-detect convention if not already detected
        if self.battery_power_convention is None:
            self.battery_power_convention = self._detect_battery_power_convention(
                historical_data
            )
            logger.info(
                "[BATTERY-PRICE] Auto-detected battery power convention: %s",
                self.battery_power_convention,
            )

        charging_events: List[Dict[str, Any]] = []
        battery_data = historical_data["battery_power"]
        battery_data.sort(key=lambda x: x["timestamp"])

        threshold = self.charging_threshold_w
        current_event = None
        last_charging_time = None

        for point in battery_data:
            power = point.get("value", 0)
            timestamp = point.get("timestamp")

            # Normalize power to positive for charging
            if self.battery_power_convention == "negative_charging":
                normalized_power = -power
            else:
                normalized_power = power

            if normalized_power > threshold:
                if current_event is None:
                    current_event = {
                        "start_time": timestamp,
                        "end_time": timestamp,
                        "power_points": [point],
                    }
                else:
                    # Check for gap even if power is still above threshold
                    gap = (timestamp - last_charging_time).total_seconds()
                    if gap < self.MAX_GAP_SECONDS_IDENTIFY:
                        current_event["end_time"] = timestamp
                        current_event["power_points"].append(point)
                    else:
                        self._close_charging_event(
                            current_event, charging_events, threshold
                        )
                        current_event = {
                            "start_time": timestamp,
                            "end_time": timestamp,
                            "power_points": [point],
                        }
                last_charging_time = timestamp
            elif current_event is not None:
                gap = (timestamp - last_charging_time).total_seconds()
                if gap < self.MAX_GAP_SECONDS_IDENTIFY:
                    current_event["end_time"] = timestamp
                    current_event["power_points"].append(point)
                else:
                    self._close_charging_event(
                        current_event, charging_events, threshold
                    )
                    current_event = None
                    last_charging_time = None

        if current_event is not None:
            self._close_charging_event(current_event, charging_events, threshold)

        return charging_events

    def _close_charging_event(
        self, event: Dict, events_list: List[Dict], threshold: float
    ):
        """Trim and add a charging event to the list."""
        while len(event["power_points"]) > 0:
            last_point = event["power_points"][-1]
            power = last_point["value"]
            # Normalize power
            if self.battery_power_convention == "negative_charging":
                normalized_power = -power
            else:
                normalized_power = power
            if normalized_power <= threshold:
                event["power_points"].pop()
            else:
                break

        if event["power_points"]:
            event["end_time"] = event["power_points"][-1]["timestamp"]
            events_list.append(event)

    # pylint: disable=too-many-locals
    def _split_energy_sources(
        self, event: Dict, historical_data: Dict
    ) -> Dict[str, float]:
        """Split charging energy between PV and grid sources."""
        totals = {
            "pv_to_battery_wh": 0.0,
            "grid_to_battery_wh": 0.0,
            "total_battery_wh": 0.0,
            "total_pv_wh": 0.0,
            "total_grid_wh": 0.0,
            "total_load_wh": 0.0,
            "grid_cost_euro": 0.0,
        }

        power_points = event["power_points"]
        if len(power_points) < 2:
            return totals

        # Indices for stream alignment
        indices = {"pv": 0, "grid": 0, "load": 0, "price": 0}

        for i in range(len(power_points) - 1):
            p_start = power_points[i]
            p_end = power_points[i + 1]

            timestamp = p_start["timestamp"]
            delta_seconds = (p_end["timestamp"] - p_start["timestamp"]).total_seconds()

            # Cap delta to avoid huge jumps if data is missing within an event
            if delta_seconds > self.MAX_GAP_SECONDS_IDENTIFY:
                delta_seconds = self.DEFAULT_DELTA_SECONDS

            time_hours = delta_seconds / 3600.0

            # Align sensor streams to the start of the interval
            pv_power = self._get_aligned_value(
                historical_data.get("pv_power", []), timestamp, indices, "pv"
            )
            grid_power = self._get_aligned_value(
                historical_data.get("grid_power", []), timestamp, indices, "grid"
            )
            load_power = self._get_aligned_value(
                historical_data.get("load_power", []), timestamp, indices, "load"
            )
            current_price = self._get_aligned_value(
                historical_data.get("price_data", []),
                timestamp,
                indices,
                "price",
                fallback_func=self._get_fallback_price,
            )

            # Use average battery power for the interval, normalized to positive for charging
            raw_avg_power = (p_start["value"] + p_end["value"]) / 2.0
            if self.battery_power_convention == "negative_charging":
                avg_battery_power = -raw_avg_power
            else:
                avg_battery_power = raw_avg_power

            pv_to_bat, grid_to_bat = self._calculate_power_split(
                avg_battery_power, pv_power, grid_power, load_power
            )

            grid_energy_wh = grid_to_bat * time_hours
            totals["pv_to_battery_wh"] += pv_to_bat * time_hours
            totals["grid_to_battery_wh"] += grid_energy_wh
            totals["total_battery_wh"] += avg_battery_power * time_hours
            totals["total_pv_wh"] += pv_power * time_hours
            totals["total_grid_wh"] += grid_power * time_hours
            totals["total_load_wh"] += load_power * time_hours
            totals["grid_cost_euro"] += (grid_energy_wh / 1000.0) * current_price

        return totals

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def _get_aligned_value(
        self,
        data: List[Dict],
        timestamp: datetime,
        indices: Dict[str, int],
        key: str,
        fallback_func=None,
    ) -> float:
        """Find the sensor value closest to the given timestamp."""
        if not data:
            return fallback_func(timestamp) if fallback_func else 0.0

        idx = indices[key]
        while idx < len(data) - 1 and data[idx + 1]["timestamp"] <= timestamp:
            idx += 1
        indices[key] = idx
        return data[idx]["value"]

    def _calculate_power_split(
        self,
        battery_power: float,
        pv_power: float,
        grid_power: float,
        load_power: float,
    ) -> Tuple[float, float]:
        """Determine how battery charging power is split between PV and grid."""
        pv_for_load = min(pv_power, load_power)
        remaining_load = max(0, load_power - pv_for_load)
        grid_for_load = min(grid_power, remaining_load)
        pv_surplus = max(0, pv_power - pv_for_load)
        grid_surplus = max(0, grid_power - grid_for_load)

        pv_to_battery = min(battery_power, pv_surplus)
        remaining_battery = max(0, battery_power - pv_to_battery)

        grid_to_battery = 0.0
        if grid_surplus > self.grid_charge_threshold_w:
            grid_to_battery = min(remaining_battery, grid_surplus)
            remaining_battery = max(0, remaining_battery - grid_to_battery)

        if remaining_battery > 0:
            pv_to_battery += remaining_battery

        return pv_to_battery, grid_to_battery

    def _get_fallback_price(self, timestamp: datetime) -> float:
        """Get fallback price when historical data is not available."""
        hour = timestamp.hour
        if 22 <= hour or hour <= 6:  # Night
            return 0.15
        if 7 <= hour <= 13:  # Morning/day
            return 0.25
        return 0.35

    def get_current_price(self) -> float:
        """Get the current calculated battery price."""
        return self.price_euro_per_wh

    def get_analysis_results(self) -> Dict[str, Any]:
        """Get the results of the last historical analysis."""
        return self.last_analysis_results

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the price calculation."""
        return {
            "enabled": self.price_calculation_enabled,
            "current_price": self.price_euro_per_wh,
            "last_calculation": (
                self.last_price_calculation.isoformat()
                if self.last_price_calculation
                else None
            ),
            "next_update_in": self._seconds_until_next_update(),
        }

    def _fetch_missing_sensor_data(
        self, historical_data: Dict, charging_events: List[Dict]
    ):
        """Fetch missing sensor data for active time ranges."""
        if not charging_events:
            return

        ranges = []
        for event in charging_events:
            start = event["start_time"] - timedelta(minutes=5)
            end = event["end_time"] + timedelta(minutes=5)
            ranges.append((start, end))

        merged_ranges = self._merge_ranges(
            ranges, max_gap_minutes=self.MAX_GAP_MINUTES_MERGE
        )

        sensors = [
            (self.pv_power_sensor, "pv_power"),
            (self.grid_power_sensor, "grid_power"),
            (self.load_power_sensor, "load_power"),
            (self.price_sensor, "price_data"),
        ]

        for sensor_id, key in sensors:
            all_points = []
            for start, end in merged_ranges:
                points = self._fetch_single_sensor_range(sensor_id, key, start, end)
                all_points.extend(points)

            all_points.sort(key=lambda x: x["timestamp"])
            historical_data[key] = all_points

    def _merge_ranges(
        self, ranges: List[Tuple[datetime, datetime]], max_gap_minutes: int = 30
    ) -> List[Tuple[datetime, datetime]]:
        """Merge overlapping or nearby time ranges."""
        if not ranges:
            return []

        sorted_ranges = sorted(ranges, key=lambda x: x[0])
        merged = []
        current_start, current_end = sorted_ranges[0]

        for next_start, next_end in sorted_ranges[1:]:
            if next_start <= current_end + timedelta(minutes=max_gap_minutes):
                current_end = max(current_end, next_end)
            else:
                merged.append((current_start, current_end))
                current_start, current_end = next_start, next_end

        merged.append((current_start, current_end))
        return merged

    def _fetch_single_sensor_range(
        self, sensor_id: str, key: str, start_time: datetime, end_time: datetime
    ) -> List[Dict]:
        """Fetch a single sensor for a specific time range."""
        try:
            if self.load_interface:
                sensor_data = self.load_interface.fetch_historical_energy_data(
                    entity_id=sensor_id, start_time=start_time, end_time=end_time
                )
                return self._convert_historical_data(sensor_data, key)
            return []
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning("[BATTERY-PRICE] Failed to fetch %s for range: %s", key, e)
            return []

    def _seconds_until_next_update(self) -> int:
        """Get seconds until next price update."""
        if not self.last_price_calculation:
            return 0
        now = datetime.now(self.timezone) if self.timezone else datetime.now()
        elapsed = (now - self.last_price_calculation).total_seconds()
        return max(0, int(self.price_update_interval - elapsed))

    def _get_now_iso(self) -> str:
        """Get current time in ISO format with timezone."""
        now = datetime.now(self.timezone) if self.timezone else datetime.now()
        return now.isoformat()
