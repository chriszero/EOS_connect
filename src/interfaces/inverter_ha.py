"""
This module provides the InverterHA class for controlling Home Assistant entities
as an inverter/battery interface for EOS Connect.
"""

import logging
import requests
import time

logger = logging.getLogger("__main__").getChild("InverterHA")
logger.setLevel(logging.INFO)


class InverterHA:
    """
    Class for handling generic Home Assistant controlled Inverters/Batteries.
    Allows configuring specific service calls for different EOS states.
    """

    def __init__(self, config: dict):
        self.config = config
        self.url = config.get("url", "").rstrip("/")
        self.token = config.get("token", "")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        # Validate configuration
        if not self.url or not self.token:
            logger.error("[InverterHA] Missing URL or Token in configuration")

        # Load state configurations
        self.config_charge = config.get("charge_from_grid", [])
        self.config_avoid = config.get("avoid_discharge", [])
        self.config_discharge = config.get("discharge_allowed", [])

        # Default fallback values
        self.max_grid_charge_rate = config.get("max_grid_charge_rate", 5000)
        self.max_pv_charge_rate = config.get("max_pv_charge_rate", 5000)

        # Internal state tracking
        self.current_mode = None

        logger.info("[InverterHA] Initialized with URL: %s", self.url)

    def _call_service(self, service_call_config: dict, variables: dict = None):
        """
        Executes a single service call to Home Assistant.

        Args:
            service_call_config (dict): Configuration of the service call
                                        (service, entity_id, data/data_template).
            variables (dict): Variables to replace in data_template (e.g. {{ power }}).
        """
        domain_service = service_call_config.get("service")
        if not domain_service or "." not in domain_service:
            logger.error("[InverterHA] Invalid service format: %s", domain_service)
            return

        domain, service = domain_service.split(".", 1)
        endpoint = f"{self.url}/api/services/{domain}/{service}"

        # Prepare payload
        payload = {}
        if "entity_id" in service_call_config:
            payload["entity_id"] = service_call_config["entity_id"]

        # Handle data/data_template
        data_config = service_call_config.get("data_template", service_call_config.get("data", {}))

        # Process templates if variables provided
        final_data = {}
        if variables:
            for key, value in data_config.items():
                if isinstance(value, str) and "{{" in value and "}}" in value:
                    # Simple template replacement for now
                    # We only support {{ power }} for now as strictly defined variable
                    if "{{ power }}" in value and "power" in variables:
                         # Try to keep type if the template is JUST the variable
                        if value.strip() == "{{ power }}":
                             final_data[key] = variables["power"]
                        else:
                             final_data[key] = value.replace("{{ power }}", str(variables["power"]))
                    else:
                        final_data[key] = value
                else:
                    final_data[key] = value
        else:
            final_data = data_config

        payload.update(final_data)

        try:
            logger.debug("[InverterHA] Calling service %s with payload %s", domain_service, payload)
            response = requests.post(endpoint, headers=self.headers, json=payload, timeout=10)
            response.raise_for_status()
            logger.debug("[InverterHA] Service call successful")
        except requests.exceptions.RequestException as e:
            logger.error("[InverterHA] Failed to call service %s: %s", domain_service, e)

    def _execute_sequence(self, sequence_config, variables=None):
        """Executes a list of service calls."""
        if not sequence_config:
            logger.warning("[InverterHA] No configuration found for requested mode")
            return

        for step in sequence_config:
            self._call_service(step, variables)

    def set_mode_force_charge(self, power=None):
        """
        Sets the inverter to charge from grid.
        Args:
            power (int): Charge power in Watts. If None, uses max_grid_charge_rate.
        """
        if power is None:
            power = self.max_grid_charge_rate

        # Clamp power
        power = min(max(0, int(power)), self.max_grid_charge_rate)

        logger.info("[InverterHA] Setting mode: Force Charge (Power: %s W)", power)
        self._execute_sequence(self.config_charge, variables={"power": power})
        self.current_mode = "force_charge"

    def set_mode_avoid_discharge(self):
        """Sets the inverter to avoid discharge (passive/hold/charge-only)."""
        logger.info("[InverterHA] Setting mode: Avoid Discharge")
        self._execute_sequence(self.config_avoid)
        self.current_mode = "avoid_discharge"

    def set_mode_allow_discharge(self):
        """Sets the inverter to allow discharge (normal operation)."""
        logger.info("[InverterHA] Setting mode: Allow Discharge")
        self._execute_sequence(self.config_discharge)
        self.current_mode = "allow_discharge"

    def api_set_max_pv_charge_rate(self, power):
        """
        Sets the max PV charge rate.
        Note: Currently not explicitly supported in the generic config unless
        added to 'discharge_allowed' sequence or similar.
        For now, we log it.
        """
        # This is called by EOS connect for dynamic adjustment if supported.
        # If the user wants to support this, they can use {{ power }} in the discharge_allowed config?
        # But discharge_allowed usually doesn't take power argument in base_control call logic
        # (it calls set_mode_allow_discharge without args).
        # However, inverter_fronius.py has api_set_max_pv_charge_rate separately.

        # For this generic interface, we simply update the internal limit.
        self.max_pv_charge_rate = power
        logger.debug("[InverterHA] Updated max PV charge rate to %s (internal only)", power)

    def shutdown(self):
        """Cleanup."""
        pass
