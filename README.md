# EOS Connect

## Overview
EOS Connect is an open-source integration and control platform for intelligent energy management. It acts as the orchestration layer between your energy hardware (inverters, batteries, PV forecasts) and external optimization engines.

## Detailed Documentation
For complete guides, tutorials, and configuration references, please visit our official documentation:

### [https://ohAnd.github.io/EOS_connect/](https://ohAnd.github.io/EOS_connect/)

All technical details and advanced setup instructions are maintained there.

## Key Features
- **Automated Optimization**: Bridges hardware with Akkudoktor EOS or EVopt backends.
- **Battery Management**: Intelligent charge/discharge control with SOC-based power curves and temperature protection.
- **Solar Forecasting**: Built-in support for Akkudoktor, Solcast, OpenMeteo, and Forecast.Solar.
- **Dynamic Pricing**: Integration with Tibber, smartenergy.at, and Stromligning.dk for cost-aware energy use.
- **Home Integration**: Native compatibility with Home Assistant, OpenHAB, EVCC, and MQTT.
- **Live Dashboard**: Real-time monitoring and manual override controls via a responsive web interface.

## Quick Start
1. **Requirements**: A running instance of [Akkudoktor EOS](https://github.com/Akkudoktor-EOS/EOS) or [EVopt](https://github.com/thecem/hassio-evopt).
2. **Installation**:
   - **Home Assistant**: Add repository `ohAnd/ha_addons` and install the EOS Connect add-on.
   - **Docker**: `docker-compose up -d`
3. **Configuration**: Edit `src/config.yaml` to point to your devices and optimization server.
4. **Access**: Open `http://localhost:8081` (or your HA IP) to view the dashboard.

## Configuration
The behavior of EOS Connect is defined in the `config.yaml` file. A default configuration will be created automatically on the first start if it does not exist.

### Full Configuration Reference
For complete documentation of all parameters, including solar forecasting, electricity prices, inverter controls, and advanced options, visit:

**[https://ohAnd.github.io/EOS_connect/user-guide/configuration.html](https://ohAnd.github.io/EOS_connect/user-guide/configuration.html)**

### Minimal Configuration Example
```yaml
# Load configuration
load:
  source: default  # Uses a static load profile

# EOS server configuration
eos:
  source: eos_server
  server: 192.168.1.94  # Replace with your EOS/EVopt server IP
  port: 8503
  time_frame: 3600 # EOS server supports 3600 only (hourly); EVopt supports 3600 or 900 (15-minute)

# Electricity price configuration
price:
  source: default  # Uses Akkudoktor price API

# Battery configuration
battery:
  source: default
  capacity_wh: 10000
  max_charge_power_w: 5000
  charge_efficiency: 0.9
  discharge_efficiency: 0.9

# PV forecast configuration
pv_forecast_source:
  source: akkudoktor

pv_forecast:
  - name: myPV
    lat: 52.5200
    lon: 13.4050
    azimuth: 180
    tilt: 25

# Inverter configuration
inverter:
  type: default  # Options: fronius_gen24, fronius_gen24_legacy, evcc, default

# EVCC configuration (optional)
evcc:
  url: ""  # Set to your EVCC URL if used, e.g., http://evcc:7070

# MQTT configuration (optional)
mqtt:
  enabled: false

# General settings
refresh_time: 3  # Optimization refresh interval in minutes
time_zone: Europe/Berlin
eos_connect_web_port: 8081
log_level: info
request_timeout: 10
```

## Project Scope
Please note that EOS Connect is an **integration and control platform**, not an optimizer. It collects system data and follows the strategies provided by external optimization backends:
- **Akkudoktor EOS** (Recommended) - [https://github.com/Akkudoktor-EOS/EOS](https://github.com/Akkudoktor-EOS/EOS)
- **EVopt** - [https://github.com/thecem/hassio-evopt](https://github.com/thecem/hassio-evopt)

## Support & Sponsoring
If you find this project useful and would like to support its development, please consider sponsoring:

[https://github.com/sponsors/ohAnd](https://github.com/sponsors/ohAnd)

## License
MIT License - see [LICENSE](LICENSE) for details.
