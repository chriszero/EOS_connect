"""
Unit tests for the BatteryPriceHandler class in src.interfaces.battery_price_handler.

This module contains tests for missing sensor data detection and power split calculations.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import pytest
import pytz
from src.interfaces.battery_price_handler import BatteryPriceHandler


@pytest.fixture
def battery_config():
    """Returns a configuration dictionary for BatteryPriceHandler."""
    return {
        "price_calculation_enabled": True,
        "price_update_interval": 900,
        "price_history_lookback_hours": 48,
        "battery_power_sensor": "sensor.battery_power",
        "pv_power_sensor": "sensor.pv_power",
        "grid_power_sensor": "sensor.grid_power",
        "load_power_sensor": "sensor.load_power",
        "price_sensor": "sensor.price",
        "charging_threshold_w": 50.0,
        "grid_charge_threshold_w": 100.0,
        "charge_efficiency": 0.93,
        "discharge_efficiency": 0.93,
    }


@pytest.fixture
def mock_load_interface():
    """Returns a mock LoadInterface."""
    return MagicMock()


def test_missing_grid_sensor_warning(battery_config, mock_load_interface, caplog):
    """
    Test that missing grid sensor data triggers a warning and energy is misattributed to PV.

    Scenario: Battery charging with PV=0, grid sensor missing, should warn user
    about potential misattribution.
    """
    # Create handler
    handler = BatteryPriceHandler(
        config=battery_config,
        load_interface=mock_load_interface,
        timezone=pytz.timezone("Europe/Berlin"),
    )

    # Create test event with charging
    now = datetime.now(pytz.UTC)
    event = {
        "start_time": now,
        "end_time": now + timedelta(hours=1),
        "power_points": [
            {"timestamp": now, "value": 3000.0},  # 3kW charging
            {"timestamp": now + timedelta(hours=1), "value": 3000.0},
        ],
    }

    # Historical data with missing grid sensor (simulating user's issue)
    historical_data = {
        "battery_power": [
            {"timestamp": now, "value": 3000.0},
            {"timestamp": now + timedelta(hours=1), "value": 3000.0},
        ],
        "pv_power": [
            {"timestamp": now, "value": 0.0},  # No PV production
            {"timestamp": now + timedelta(hours=1), "value": 0.0},
        ],
        "grid_power": [],  # Missing grid data - THIS IS THE BUG
        "load_power": [
            {"timestamp": now, "value": 500.0},
            {"timestamp": now + timedelta(hours=1), "value": 500.0},
        ],
        "price_data": [
            {"timestamp": now, "value": 0.25},
            {"timestamp": now + timedelta(hours=1), "value": 0.25},
        ],
    }

    # Call the split function
    with caplog.at_level("WARNING"):
        result = handler._split_energy_sources(event, historical_data)

    # Verify warning was logged
    assert any(
        "Missing sensor data" in record.message and "grid" in record.message
        for record in caplog.records
    ), "Expected warning about missing grid sensor data"

    assert any(
        "misattributed to PV" in record.message for record in caplog.records
    ), "Expected warning about misattribution to PV"

    # Verify that without grid data, energy is misattributed to PV
    # This is the bug we're documenting
    assert (
        result["pv_to_battery_wh"] > 0
    ), "Energy should be (incorrectly) attributed to PV"
    assert result["grid_to_battery_wh"] == 0, "No grid attribution without grid sensor"


def test_correct_attribution_with_all_sensors(battery_config, mock_load_interface):
    """
    Test that with all sensor data present, grid charging is correctly attributed.

    Scenario: Battery charging from grid (import), PV=0, all sensors present.
    """
    handler = BatteryPriceHandler(
        config=battery_config,
        load_interface=mock_load_interface,
        timezone=pytz.timezone("Europe/Berlin"),
    )

    now = datetime.now(pytz.UTC)
    event = {
        "start_time": now,
        "end_time": now + timedelta(hours=1),
        "power_points": [
            {"timestamp": now, "value": 3000.0},  # 3kW charging
            {"timestamp": now + timedelta(hours=1), "value": 3000.0},
        ],
    }

    # Complete historical data
    historical_data = {
        "battery_power": [
            {"timestamp": now, "value": 3000.0},
            {"timestamp": now + timedelta(hours=1), "value": 3000.0},
        ],
        "pv_power": [
            {"timestamp": now, "value": 0.0},  # No PV
            {"timestamp": now + timedelta(hours=1), "value": 0.0},
        ],
        "grid_power": [
            {"timestamp": now, "value": 3500.0},  # Grid import (+)
            {"timestamp": now + timedelta(hours=1), "value": 3500.0},
        ],
        "load_power": [
            {"timestamp": now, "value": 500.0},
            {"timestamp": now + timedelta(hours=1), "value": 500.0},
        ],
        "price_data": [
            {"timestamp": now, "value": 0.25},
            {"timestamp": now + timedelta(hours=1), "value": 0.25},
        ],
    }

    result = handler._split_energy_sources(event, historical_data)

    # With grid data present, grid charging should be correctly attributed
    assert result["grid_to_battery_wh"] > 0, "Grid charging should be detected"
    assert result["pv_to_battery_wh"] == 0, "No PV charging expected"


def test_power_split_calculation():
    """Test the power split calculation logic with standard sensor conventions."""
    handler = BatteryPriceHandler(
        config={
            "charging_threshold_w": 50.0,
            "grid_charge_threshold_w": 100.0,
            "charge_efficiency": 0.93,
        },
        load_interface=None,
        timezone=pytz.timezone("Europe/Berlin"),
    )

    # Test case: Grid import (positive), PV=0, Load=500W, Battery charging 3kW
    pv_to_bat, grid_to_bat = handler._calculate_power_split(
        battery_power=3000.0,
        pv_power=0.0,
        grid_power=3500.0,  # Import from grid
        load_power=500.0,
    )

    # Expected: grid_for_load=500, grid_surplus=3000, all 3kW to battery from grid
    assert grid_to_bat == 3000.0, "All battery charging should come from grid"
    assert pv_to_bat == 0.0, "No PV charging"


def test_power_split_with_pv_and_grid():
    """Test power split when both PV and grid contribute to battery charging."""
    handler = BatteryPriceHandler(
        config={
            "charging_threshold_w": 50.0,
            "grid_charge_threshold_w": 100.0,
            "charge_efficiency": 0.93,
        },
        load_interface=None,
        timezone=pytz.timezone("Europe/Berlin"),
    )

    # PV=2kW, Grid=2kW, Load=500W, Battery=3kW
    pv_to_bat, grid_to_bat = handler._calculate_power_split(
        battery_power=3000.0, pv_power=2000.0, grid_power=2000.0, load_power=500.0
    )

    # Expected:
    # - PV for load: 500W
    # - PV surplus: 1500W → to battery
    # - Grid for load: 0W (already covered by PV)
    # - Grid surplus: 2000W → to battery (1500W remaining capacity)
    assert pv_to_bat == 1500.0, "PV surplus should charge battery"
    assert grid_to_bat == 1500.0, "Grid should cover remaining battery charge"
