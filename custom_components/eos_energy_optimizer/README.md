# EOS Energy Optimizer

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/chriszero/eos_energy_optimizer.svg)](https://github.com/chriszero/eos_energy_optimizer/releases)

Home Assistant Custom Integration for intelligent energy management and optimization using the EOS (Energy Optimization System) backend.

## Features

- **Energy Optimization**: Periodically requests optimization decisions from an EOS or EVopt backend
- **Battery Management**: Monitors SOC, calculates usable energy, and controls charging/discharging
- **PV Forecasting**: Integrates with Akkudoktor, Open-Meteo, and Forecast.Solar for solar production forecasts
- **Dynamic Pricing**: Supports Tibber, Akkudoktor, and fixed pricing for electricity costs
- **Native HA Integration**: All data exposed as Home Assistant entities with full history support
- **Control via Entities**: Use select, number, and button entities to control the system
- **Services**: Comprehensive services for automation integration
- **Events**: Fires events on control updates for custom automations

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
   - **EOS Server**: Configure your EOS/EVopt server connection
   - **Battery**: Set your battery capacity, power limits, and SOC sensor
   - **PV System**: Configure your solar panels for forecasting
   - **Pricing**: Set up your electricity price source
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

## Dashboard Example

```yaml
type: entities
title: EOS Energy Optimizer
entities:
  - entity: sensor.eos_inverter_mode
  - entity: sensor.eos_battery_soc
  - entity: binary_sensor.eos_discharge_allowed
  - entity: sensor.eos_ac_charge_demand
  - entity: sensor.eos_current_price
  - entity: select.eos_inverter_mode_control
  - entity: button.eos_refresh_optimization
```

## Requirements

- Home Assistant 2024.1.0 or newer
- An EOS or EVopt optimization server running and accessible
- Optional: Tibber account for dynamic pricing

## Troubleshooting

### Cannot connect to EOS server
- Verify the server address and port
- Check that the EOS server is running
- Ensure network connectivity between HA and the EOS server

### Optimization failing
- Check the Home Assistant logs for error details
- Verify your battery and PV configuration
- Ensure the load sensor is providing valid data

## License

MIT License - see LICENSE file for details.

## Credits

Based on [EOS_connect](https://github.com/chriszero/EOS_connect) addon.
