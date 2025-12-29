
import sys
from unittest.mock import MagicMock, patch

# Mock homeassistant module
sys.modules["homeassistant"] = MagicMock()
sys.modules["homeassistant.config_entries"] = MagicMock()
sys.modules["homeassistant.const"] = MagicMock()
sys.modules["homeassistant.core"] = MagicMock()
sys.modules["homeassistant.helpers"] = MagicMock()
sys.modules["homeassistant.helpers.selector"] = MagicMock()
sys.modules["homeassistant.helpers.config_validation"] = MagicMock()
sys.modules["homeassistant.helpers.update_coordinator"] = MagicMock()
sys.modules["homeassistant.helpers.entity_platform"] = MagicMock()
sys.modules["homeassistant.components"] = MagicMock()
sys.modules["homeassistant.components.sensor"] = MagicMock()
sys.modules["homeassistant.components.recorder"] = MagicMock()
sys.modules["homeassistant.util"] = MagicMock()
sys.modules["homeassistant.data_entry_flow"] = MagicMock()

# Import the custom component
import custom_components.eos_connect.const
import custom_components.eos_connect.config_flow
import custom_components.eos_connect.coordinator
import custom_components.eos_connect.sensor
import custom_components.eos_connect

print("Imports successful")
