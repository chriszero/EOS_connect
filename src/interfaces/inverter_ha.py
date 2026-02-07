"""
This module provides the InverterHA class for controlling Home Assistant entities
as an inverter/battery interface for EOS Connect.

Note: This class is prepared for BaseInverter compatibility (PR #170).
Once BaseInverter is merged, change to `class InverterHA(BaseInverter)`,
call `super().__init__(config)`, and register in InverterFactory.
"""

import logging
import requests

logger = logging.getLogger("__main__").getChild("InverterHA")
logger.setLevel(logging.INFO)


class InverterHA:
    """
    Class for handling generic Home Assistant controlled Inverters/Batteries.
    Allows configuring specific service calls for different EOS states.
    """

    supports_extended_monitoring_default = False

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

        # BaseInverter-compatible attributes
        self.address = self.url
        self.is_authenticated = False
        self.inverter_type = self.__class__.__name__

        # Internal state tracking
        self.current_mode = None

        logger.info("[InverterHA] Initialized with URL: %s", self.url)

    def _call_service(self, service_call_config: dict, variables: dict = None) -> bool:
        """
        Executes a single service call to Home Assistant.

        Args:
            service_call_config (dict): Configuration of the service call
                                        (service, entity_id, data/data_template).
            variables (dict): Variables to replace in data_template (e.g. {{ power }}).

        Returns:
            bool: True if the service call succeeded, False otherwise.
        """
        domain_service = service_call_config.get("service")
        if not domain_service or "." not in domain_service:
            logger.error("[InverterHA] Invalid service format: %s", domain_service)
            return False

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
            return True
        except requests.exceptions.RequestException as e:
            logger.error("[InverterHA] Failed to call service %s: %s", domain_service, e)
            return False

    def _execute_sequence(self, sequence_config, variables=None) -> bool:
        """Executes a list of service calls.

        Returns:
            bool: True if all steps succeeded, False otherwise.
        """
        if not sequence_config:
            logger.warning("[InverterHA] No configuration found for requested mode")
            return False

        success = True
        for step in sequence_config:
            if not self._call_service(step, variables):
                success = False
        return success

    def set_mode_force_charge(self, charge_power_w=None) -> bool:
        """
        Sets the inverter to charge from grid.
        Args:
            charge_power_w (int): Charge power in Watts. If None, uses max_grid_charge_rate.
        Returns:
            bool: True if the mode was set successfully, False otherwise.
        """
        if charge_power_w is None:
            charge_power_w = self.max_grid_charge_rate

        # Clamp power
        charge_power_w = min(max(0, int(charge_power_w)), self.max_grid_charge_rate)

        logger.info("[InverterHA] Setting mode: Force Charge (Power: %s W)", charge_power_w)
        result = self._execute_sequence(self.config_charge, variables={"power": charge_power_w})
        self.current_mode = "force_charge"
        return result

    def set_mode_avoid_discharge(self) -> bool:
        """Sets the inverter to avoid discharge (passive/hold/charge-only).

        Returns:
            bool: True if the mode was set successfully, False otherwise.
        """
        logger.info("[InverterHA] Setting mode: Avoid Discharge")
        result = self._execute_sequence(self.config_avoid)
        self.current_mode = "avoid_discharge"
        return result

    def set_mode_allow_discharge(self) -> bool:
        """Sets the inverter to allow discharge (normal operation).

        Returns:
            bool: True if the mode was set successfully, False otherwise.
        """
        logger.info("[InverterHA] Setting mode: Allow Discharge")
        result = self._execute_sequence(self.config_discharge)
        self.current_mode = "allow_discharge"
        return result

    def api_set_max_pv_charge_rate(self, max_pv_charge_rate: int):
        """
        Sets the max PV charge rate.
        Note: Currently not explicitly supported in the generic config unless
        added to 'discharge_allowed' sequence or similar.
        For now, we log it.
        """
        self.max_pv_charge_rate = max_pv_charge_rate
        logger.debug("[InverterHA] Updated max PV charge rate to %s (internal only)", max_pv_charge_rate)

    # --- BaseInverter-compatible stubs (PR #170) ---

    def initialize(self):
        """Initialize the inverter connection. HA uses stateless REST, no persistent connect."""
        self.is_authenticated = True

    def authenticate(self) -> bool:
        """Authenticate with the inverter. Bearer token is set at init, no auth flow needed."""
        return True

    def connect_inverter(self) -> bool:
        """Connect to the inverter. Stateless HTTP, always succeeds."""
        return True

    def disconnect_inverter(self) -> bool:
        """Disconnect from the inverter. Stateless HTTP, always succeeds."""
        return True

    def set_battery_mode(self, mode: str) -> bool:
        """Dispatch battery mode changes to the appropriate sequence.

        Args:
            mode (str): One of 'force_charge', 'avoid_discharge', 'allow_discharge'.

        Returns:
            bool: True if the mode was set successfully, False otherwise.
        """
        if mode == "force_charge":
            return self.set_mode_force_charge()
        elif mode == "avoid_discharge":
            return self.set_mode_avoid_discharge()
        elif mode == "allow_discharge":
            return self.set_mode_allow_discharge()
        else:
            logger.error("[InverterHA] Unknown battery mode: %s", mode)
            return False

    def set_allow_grid_charging(self, value: bool):
        """Enable or disable grid charging.

        Args:
            value (bool): If True, execute the charge sequence.
        """
        if value:
            self._execute_sequence(self.config_charge)

    def get_battery_info(self) -> dict:
        """Return battery information. HA does not provide direct battery data via this interface."""
        return {}

    def fetch_inverter_data(self) -> dict:
        """Return inverter data. HA does not provide direct inverter data via this interface."""
        return {}

    def shutdown(self):
        """Cleanup and shutdown the inverter interface."""
        logger.info("[InverterHA] Shutting down inverter interface")
