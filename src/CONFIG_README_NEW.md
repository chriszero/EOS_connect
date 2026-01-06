# EOS Connect Configuration

The behavior of EOS Connect is defined in the `config.yaml` file.

## Full Configuration Reference
For a complete list of all parameters, including solar forecasting, electricity prices, and inverter controls, please refer to the official documentation:

### [https://ohAnd.github.io/EOS_connect/user-guide/configuration.html](https://ohAnd.github.io/EOS_connect/user-guide/configuration.html)

The online guide contains detailed descriptions of valid values, units, and examples for every setting.

## Minimal Possible Configuration
The following example shows a minimal configuration setup. A default `config.yaml` will be created automatically on the first start if it does not exist.

```yaml
# Load configuration
load:
  source: default  # Uses a static load profile

# EOS server configuration
eos:
  source: eos_server
  server: 192.168.1.94  # Replace with your EOS/EVopt server IP
  port: 8503
  time_frame: 3600 # 3600 for hourly, 900 for 15-minute intervals

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
```

## Support & Sponsoring
If you find this project useful and would like to support its development, please consider sponsoring:

[https://github.com/sponsors/ohAnd](https://github.com/sponsors/ohAnd)
