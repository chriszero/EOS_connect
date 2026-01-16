# EOS Energy Optimizer

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/chriszero/eos_energy_optimizer.svg)](https://github.com/chriszero/eos_energy_optimizer/releases)

Home Assistant Custom Integration for intelligent energy management and optimization using the [Akkudoktor EOS](https://github.com/Akkudoktor-EOS/EOS) (Energy Optimization System) backend.

## Features

- **Energy Optimization**: Periodically requests optimization decisions from an EOS or EVopt backend
- **Battery Management**: Monitors SOC, calculates usable energy, and controls charging/discharging
- **PV Forecasting**: Uses existing Home Assistant sensors from Solcast, Forecast.Solar, or Open-Meteo Solar
- **Dynamic Pricing**: Uses existing Home Assistant sensors from Tibber, ENTSO-E, Nordpool, EPEX Spot, or Awattar
- **Native HA Integration**: All data exposed as Home Assistant entities with full history support
- **Lovelace Dashboard**: Pre-built dashboard with ApexCharts for visualization
- **Control via Entities**: Use select, number, and button entities to control the system
- **Services**: Comprehensive services for automation integration
- **Events**: Fires events on control updates for custom automations

## Requirements

- Home Assistant 2024.1.0 or newer
- An EOS or EVopt optimization server running and accessible
- A PV forecast sensor (Solcast, Forecast.Solar, or Open-Meteo Solar integration)
- A price sensor (Tibber, ENTSO-E, Nordpool, EPEX Spot, or Awattar integration)
- Optional: HACS [apexcharts-card](https://github.com/RomRider/apexcharts-card) for the dashboard

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots menu and select "Custom repositories"
4. Add `https://github.com/chriszero/eos_energy_optimizer` with category "Integration"
5. Click "Install"
6. Restart Home Assistant

### Manual Installation

1. Download the latest release
2. Copy the `custom_components/eos_energy_optimizer` folder to your `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to Settings → Devices & Services
2. Click "Add Integration"
3. Search for "EOS Energy Optimizer"
4. Follow the setup wizard:
   - **EOS Server**: Configure your EOS/EVopt server connection (default: localhost:8503)
   - **Battery**: Set your battery capacity, power limits, and SOC sensor
   - **PV Forecast**: Select a PV forecast sensor from Solcast, Forecast.Solar, or Open-Meteo Solar
   - **Pricing**: Select a price sensor from Tibber, ENTSO-E, Nordpool, EPEX Spot, or Awattar
   - **Load**: Configure your household power consumption sensor

## Entities

### Sensors

| Entity | Description |
|--------|-------------|
| `sensor.eos_inverter_mode` | Current operating mode (Auto, Charge from Grid, etc.) |
| `sensor.eos_ac_charge_demand` | Grid charging power demand (W) |
| `sensor.eos_dc_charge_demand` | PV charging power demand (W) |
| `sensor.eos_battery_soc` | Current battery state of charge (%) |
| `sensor.eos_battery_usable_energy` | Usable battery energy (Wh) |
| `sensor.eos_optimization_cost` | Total optimization cost (€) |
| `sensor.eos_current_price` | Current electricity price (€/kWh) |
| `sensor.eos_current_pv_forecast` | Current hour PV forecast (Wh) |
| `sensor.eos_soc_forecast` | SOC forecast for current hour (%) |
| `sensor.eos_grid_import_forecast` | Grid import forecast (Wh) |
| `sensor.eos_grid_export_forecast` | Grid export forecast (Wh) |

### Binary Sensors

| Entity | Description |
|--------|-------------|
| `binary_sensor.eos_discharge_allowed` | Whether battery discharge is allowed |
| `binary_sensor.eos_override_active` | Whether a manual override is active |
| `binary_sensor.eos_charging_from_grid` | Whether charging from grid is active |
| `binary_sensor.eos_optimization_ok` | Optimization status |

### Controls

| Entity | Description |
|--------|-------------|
| `select.eos_inverter_mode_control` | Select the operating mode |
| `number.eos_min_soc` | Set minimum SOC limit |
| `number.eos_max_soc` | Set maximum SOC limit |
| `button.eos_refresh_optimization` | Trigger optimization manually |
| `button.eos_clear_override` | Clear active override |

## Services

### `eos_energy_optimizer.set_mode`

Set the inverter operating mode.

```yaml
service: eos_energy_optimizer.set_mode
data:
  mode: charge_from_grid  # auto, charge_from_grid, avoid_discharge, discharge_allowed
```

### `eos_energy_optimizer.set_override`

Set a temporary mode override.

```yaml
service: eos_energy_optimizer.set_override
data:
  mode: charge_from_grid
  duration_minutes: 60
  charge_power: 3000  # Optional, for charge_from_grid mode
```

### `eos_energy_optimizer.clear_override`

Clear the current override and return to automatic mode.

```yaml
service: eos_energy_optimizer.clear_override
```

### `eos_energy_optimizer.refresh_optimization`

Manually trigger an optimization request.

```yaml
service: eos_energy_optimizer.refresh_optimization
```

### `eos_energy_optimizer.set_soc_limits`

Set battery SOC limits.

```yaml
service: eos_energy_optimizer.set_soc_limits
data:
  min_soc: 10
  max_soc: 95
```

## Events

The integration fires `eos_energy_optimizer_control_update` events when the control state changes:

```yaml
event_type: eos_energy_optimizer_control_update
data:
  mode: 0  # Numeric mode value
  mode_name: CHARGE_FROM_GRID
  ac_charge_demand: 3000
  dc_charge_demand: 5000
  discharge_allowed: false
```

## Example Automations

### Charge from Grid when Price is Low

```yaml
automation:
  - alias: "EOS: Charge when cheap"
    trigger:
      - platform: numeric_state
        entity_id: sensor.eos_current_price
        below: 0.15
    action:
      - service: eos_energy_optimizer.set_override
        data:
          mode: charge_from_grid
          duration_minutes: 60
          charge_power: 5000
```

### Notify on Low Battery

```yaml
automation:
  - alias: "EOS: Low battery warning"
    trigger:
      - platform: numeric_state
        entity_id: sensor.eos_battery_soc
        below: 20
    action:
      - service: notify.mobile_app
        data:
          title: "Battery Low"
          message: "Battery SOC is {{ states('sensor.eos_battery_soc') }}%"
```

## Dashboard

A pre-built Lovelace dashboard is available in `lovelace/eos_dashboard.yaml`. It includes:

- **24-hour Energy Overview**: PV forecast, grid import, charging schedule, prices, and SOC
- **Battery Gauge**: Visual SOC with color-coded severity
- **Control Panel**: Mode selection, SOC limits, and action buttons
- **48-hour Price Chart**: Electricity prices visualization
- **Detailed Charts**: PV forecast, SOC forecast, grid import/export, charge demands

### Dashboard Installation

1. Install [apexcharts-card](https://github.com/RomRider/apexcharts-card) via HACS
2. Copy the content from `lovelace/eos_dashboard.yaml`
3. Create a new dashboard or add a view in an existing dashboard
4. Paste the YAML configuration
5. Adjust entity IDs if needed (default prefix: `eos_energy_optimizer`)

### Simple Dashboard Example

```yaml
type: entities
title: EOS Energy Optimizer
entities:
  - entity: sensor.eos_energy_optimizer_inverter_mode
  - entity: sensor.eos_energy_optimizer_battery_soc
  - entity: binary_sensor.eos_energy_optimizer_discharge_allowed
  - entity: sensor.eos_energy_optimizer_ac_charge_demand
  - entity: sensor.eos_energy_optimizer_current_price
  - entity: select.eos_energy_optimizer_inverter_mode_control
  - entity: button.eos_energy_optimizer_refresh_optimization
```

## Supported PV Forecast Sensors

The integration reads PV forecasts from existing Home Assistant sensors:

| Integration | Sensor Attributes |
|-------------|-------------------|
| **Solcast** | `DetailedForecast`, `detailedHourly` with `period_start`, `pv_estimate` |
| **Forecast.Solar** | `watt_hours` dict or `forecast` list |
| **Open-Meteo Solar** | `forecast` list with `period_start`, `power` |

## Supported Price Sensors

The integration reads electricity prices from existing Home Assistant sensors:

| Integration | Sensor Attributes |
|-------------|-------------------|
| **Tibber** | `prices` list with `from`/`startsAt`, `price`/`total` |
| **Nordpool** | `prices_today`, `prices_tomorrow` or `raw_today`, `raw_tomorrow` |
| **ENTSO-E** | `data` list with `time`, `price` (converts €/MWh to €/kWh) |
| **EPEX Spot** | Similar to Nordpool format |
| **Awattar** | Similar to Tibber format |

## Troubleshooting

### Cannot connect to EOS server
- Verify the server address and port (default: 8503 for EOS, 8504 for EVopt)
- Check that the EOS server is running: `http://your-server:8503/v1/health`
- Ensure network connectivity between HA and the EOS server

### Optimization failing or timing out
- EOS optimization can take 2-3 minutes - this is normal
- Check the Home Assistant logs for error details
- Verify your battery and PV configuration
- Ensure the load sensor is providing valid data
- Check that PV forecast and price sensors have data in their attributes

### No PV forecast data
- Ensure your PV forecast integration is set up correctly (Solcast, Forecast.Solar, etc.)
- Check that the sensor has forecast data in its attributes
- The integration looks for: `DetailedForecast`, `forecast`, `watt_hours` attributes

### No price data
- Ensure your price integration is set up correctly (Tibber, Nordpool, etc.)
- Check that the sensor has price data in its attributes
- For ENTSO-E: Prices in €/MWh are automatically converted to €/kWh

### Dashboard not working
- Install `apexcharts-card` from HACS
- Check that entity IDs match (use `eos_energy_optimizer_` prefix)
- Verify sensors have `forecast_48h` or `prices_48h` in their attributes

## License

MIT License - see LICENSE file for details.

## Credits

- Based on [EOS_connect](https://github.com/ohAnd/EOS_connect) addon
- Uses [Akkudoktor EOS](https://github.com/Akkudoktor-EOS/EOS) backend
- Documentation: [akkudoktor-eos.readthedocs.io](https://akkudoktor-eos.readthedocs.io/)
