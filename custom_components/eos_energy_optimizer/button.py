"""Button platform for EOS Energy Optimizer."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EOSDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class EOSButtonEntityDescription(ButtonEntityDescription):
    """Describes EOS button entity."""

    press_fn: Callable[[EOSDataUpdateCoordinator], Awaitable[None]]


async def _refresh_optimization(coordinator: EOSDataUpdateCoordinator) -> None:
    """Refresh optimization."""
    await coordinator.api_client.async_run_optimization()
    await coordinator.async_request_refresh()


async def _clear_override(coordinator: EOSDataUpdateCoordinator) -> None:
    """Clear override."""
    await coordinator.api_client.async_clear_override()
    await coordinator.async_request_refresh()


BUTTON_DESCRIPTIONS: tuple[EOSButtonEntityDescription, ...] = (
    EOSButtonEntityDescription(
        key="refresh_optimization",
        translation_key="refresh_optimization",
        name="Refresh Optimization",
        icon="mdi:refresh",
        press_fn=_refresh_optimization,
    ),
    EOSButtonEntityDescription(
        key="clear_override",
        translation_key="clear_override",
        name="Clear Override",
        icon="mdi:close-circle",
        press_fn=_clear_override,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EOS button entities from a config entry."""
    coordinator: EOSDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        EOSButton(coordinator, description)
        for description in BUTTON_DESCRIPTIONS
    ]

    async_add_entities(entities)


class EOSButton(CoordinatorEntity[EOSDataUpdateCoordinator], ButtonEntity):
    """Representation of an EOS button entity."""

    entity_description: EOSButtonEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EOSDataUpdateCoordinator,
        description: EOSButtonEntityDescription,
    ) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.entity_description.press_fn(self.coordinator)
