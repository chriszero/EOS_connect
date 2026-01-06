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
1. **Requirements**: A running instance of [Akkudoktor EOS](https://github.com/Akkudoktor-EOS/EOS) or EVopt.
2. **Installation**:
   - **Home Assistant**: Add repository `ohAnd/ha_addons` and install the EOS Connect add-on.
   - **Docker**: `docker-compose up -d`
3. **Configuration**: Edit `src/config.yaml` to point to your devices and optimization server.
4. **Access**: Open `http://localhost:8081` (or your HA IP) to view the dashboard.

## Project Scope
Please note that EOS Connect is an **integration and control platform**, not an optimizer. It collects system data and follows the strategies provided by external optimization backends:
- **Akkudoktor EOS** (Recommended) - [https://github.com/Akkudoktor-EOS/EOS](https://github.com/Akkudoktor-EOS/EOS)
- **EVopt** - [https://github.com/thecem/hassio-evopt](https://github.com/thecem/hassio-evopt)

## Support & Sponsoring
If you find this project useful and would like to support its development, please consider sponsoring:

[https://github.com/sponsors/ohAnd](https://github.com/sponsors/ohAnd)

## License
MIT License - see [LICENSE](LICENSE) for details.
