# EOS Connect - Home Assistant Custom Component

Integration to connect Home Assistant with the Akkudoktor EOS optimization server.

## Installation via HACS

1.  Add this repository to HACS as a Custom Repository (Integration).
2.  Install "EOS Connect".
3.  Restart Home Assistant.

## Configuration

1.  Go to **Settings** -> **Devices & Services** -> **Add Integration**.
2.  Search for "EOS Connect".
3.  **Step 1: Connection & System**:
    *   **EOS URL**: IP address of your running `eos_server` container (e.g., `192.168.1.5`).
    *   **EOS Port**: Port of the server (default `8503`).
    *   **Battery Capacity**: Total capacity in Wh.
    *   **Max Charge/Discharge Rate**: Max power in Watts.
4.  **Step 2: Sensor Mappings**:
    *   **SoC Sensor**: Your battery's State of Charge sensor (%).
    *   **Load Sensor**: Your house load/consumption sensor (W or kW). History is used for prediction.
    *   **PV Forecast**: A sensor containing forecast data (e.g., from Solar Forecast integration).
5.  **Step 3: Control Mappings**:
    *   **Charge Limit Entity**: A `number` entity to set the grid charge limit (Watts).
    *   **Discharge Limit Entity**: A `number` entity to set the discharge limit (Watts).
    *   **Mode Entity**: A `select` to force "Charge" or "Hold".
    *   **EV Connected Entity** (Optional): A binary sensor to tell if the car is plugged in.

## Visualization (ApexCharts)

You can visualize the EOS plan using the **ApexCharts Card** (available in HACS).
Here is an example configuration using the `sensor.eos_connect_plan_data` sensor:

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: EOS Optimization Plan
  show_states: true
  colorize_states: true
graph_span: 48h
span:
  start: minute
series:
  - entity: sensor.eos_connect_plan_data
    name: PV Forecast
    data_generator: |
      return entity.attributes.time.map((t, i) => {
        return [new Date(t).getTime(), entity.attributes.pv_forecast[i]];
      });
    type: area
    color: yellow
    opacity: 0.3

  - entity: sensor.eos_connect_plan_data
    name: Price
    data_generator: |
      return entity.attributes.time.map((t, i) => {
        return [new Date(t).getTime(), entity.attributes.price_forecast[i] * 1000]; // Convert to EUR/MWh or similar if needed
      });
    type: line
    color: blue
    y_axis_id: price

  - entity: sensor.eos_connect_plan_data
    name: Planned Charge
    data_generator: |
      return entity.attributes.time.map((t, i) => {
        return [new Date(t).getTime(), entity.attributes.plan_ac_charge[i] * 100]; // %
      });
    type: column
    color: green
    group_by:
      func: avg
      duration: 1h

yaxis:
  - id: default
    decimals: 0
  - id: price
    opposite: true
    decimals: 2
```

## How it works

The integration polls the EOS Server every 15 minutes. It gathers history from your Load sensor and forecast from your PV sensor, sends it to EOS, and applies the resulting strategy to your mapped control entities.
