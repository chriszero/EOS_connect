"""
This module provides the InverterHA class for controlling Home Assistant entities
as an inverter interface for EOS Connect.
"""

import logging
import requests
import json

logger = logging.getLogger("__main__").getChild("InverterHA")
logger.setLevel(logging.INFO)


class InverterHA:
    """
    Inverter interface for Home Assistant.
    Allows configuring a list of service calls for each operating mode.
    """

    def __init__(self, config: dict) -> None:
        self.url = config.get("url", "")
        self.token = config.get("token", "")
        self.config = config

        # Load service configurations
        self.force_charge_services = config.get("force_charge_services", [])
        self.avoid_discharge_services = config.get("avoid_discharge_services", [])
        self.discharge_allowed_services = config.get("discharge_allowed_services", [])
        self.max_pv_charge_rate_services = config.get("max_pv_charge_rate_services", [])

        # Internal state
        self.inverter_current_data = {
            "DEVICE_TEMPERATURE_AMBIENTEMEAN_F32": 0,
        }

        # Validate configuration
        if not self.url:
            logger.error("[InverterHA] URL not configured.")
        if not self.token:
            logger.warning("[InverterHA] Access token not configured.")

    def _call_services(self, services, value=None):
        """
        Executes a list of Home Assistant service calls.

        Args:
            services (list): List of service configuration dictionaries.
            value (int/float, optional): Dynamic value to inject into the service call.
        """
        if not services:
            logger.debug("[InverterHA] No services configured for this action.")
            return

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        for srv in services:
            service_name = srv.get("service")
            entity_id = srv.get("entity_id")
            data = srv.get("data", {}).copy() # Copy to avoid modifying the config
            value_key = srv.get("value_key")

            if not service_name:
                logger.warning("[InverterHA] Service name missing in configuration.")
                continue

            # If entity_id is provided at the top level, add it to data
            if entity_id:
                data["entity_id"] = entity_id

            # Inject dynamic value if configured
            if value_key and value is not None:
                data[value_key] = value

            domain, service = service_name.split(".", 1)
            api_url = f"{self.url}/api/services/{domain}/{service}"

            try:
                logger.debug("[InverterHA] Calling service %s with data %s", service_name, data)
                response = requests.post(api_url, headers=headers, json=data, timeout=10)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                logger.error("[InverterHA] Failed to call service %s: %s", service_name, e)

    def set_mode_force_charge(self, power):
        """
        Sets the inverter to charge from the grid.
        Executes configured services for 'force_charge'.
        Injects 'power' if 'value_key' is set in the config.
        """
        logger.info("[InverterHA] Setting mode: Force Charge (Power: %s W)", power)
        self._call_services(self.force_charge_services, value=power)

    def set_mode_avoid_discharge(self):
        """
        Sets the inverter to avoid discharge.
        Executes configured services for 'avoid_discharge'.
        """
        logger.info("[InverterHA] Setting mode: Avoid Discharge")
        self._call_services(self.avoid_discharge_services)

    def set_mode_allow_discharge(self):
        """
        Sets the inverter to allow discharge.
        Executes configured services for 'discharge_allowed'.
        """
        logger.info("[InverterHA] Setting mode: Discharge Allowed")
        self._call_services(self.discharge_allowed_services)

    def api_set_max_pv_charge_rate(self, power):
        """
        Sets the maximum PV charge rate.
        Executes configured services for 'max_pv_charge_rate'.
        Injects 'power' if 'value_key' is set in the config.
        """
        logger.info("[InverterHA] Setting Max PV Charge Rate: %s W", power)
        self._call_services(self.max_pv_charge_rate_services, value=power)

    def fetch_inverter_data(self):
        """
        Fetches inverter data. (Currently a placeholder)
        Can be extended to read sensors from HA if configured.
        """
        # Placeholder: Implement reading specific sensors if needed.
        # For now, just return default empty data to satisfy interface.
        return self.inverter_current_data

    def get_inverter_current_data(self):
        """Get the current inverter data."""
        return self.inverter_current_data

    def shutdown(self):
        """Clean up actions if needed."""
        pass
