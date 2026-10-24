"""Button platform for Dartsnut PixelDart actions."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DartsnutCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dartsnut button entities."""
    coordinator: DartsnutCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            DartsnutLocateButton(coordinator),
            DartsnutReloadWidgetsButton(coordinator),
            DartsnutRestartServiceButton(coordinator),
            DartsnutRebootButton(coordinator),
        ]
    )


class DartsnutLocateButton(CoordinatorEntity[DartsnutCoordinator], ButtonEntity):
    """Button to flash the identify graphic on the Dartsnut board."""

    _attr_has_entity_name = True
    _attr_name = "Locate Device"
    _attr_icon = "mdi:crosshairs-gps"

    def __init__(self, coordinator: DartsnutCoordinator) -> None:
        """Initialize the locate button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id_base}_locate"
        self._attr_device_info = coordinator.ha_device_info

    async def async_press(self) -> None:
        """Flash locate image on display."""
        await self.coordinator.client.locate_device()


class DartsnutReloadWidgetsButton(CoordinatorEntity[DartsnutCoordinator], ButtonEntity):
    """Button to reload widgets configuration."""

    _attr_has_entity_name = True
    _attr_name = "Reload Widgets"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: DartsnutCoordinator) -> None:
        """Initialize the reload widgets button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id_base}_reload_widgets"
        self._attr_device_info = coordinator.ha_device_info

    async def async_press(self) -> None:
        """Reload widgets configuration."""
        await self.coordinator.client.reload_conf()
        await self.coordinator.async_refresh_apps_and_pages()


class DartsnutRestartServiceButton(CoordinatorEntity[DartsnutCoordinator], ButtonEntity):
    """Button to restart dartsnut_python.service (also exits any running game)."""

    _attr_has_entity_name = True
    _attr_name = "Restart Service"
    _attr_icon = "mdi:restart"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: DartsnutCoordinator) -> None:
        """Initialize the restart service button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id_base}_restart_service"
        self._attr_device_info = coordinator.ha_device_info

    async def async_press(self) -> None:
        """Restart the main Dartsnut Python service."""
        await self.coordinator.client.restart_main_service()
        await self.coordinator.async_request_refresh()


class DartsnutRebootButton(CoordinatorEntity[DartsnutCoordinator], ButtonEntity):
    """Button to reboot the Dartsnut Raspberry Pi."""

    _attr_has_entity_name = True
    _attr_name = "Reboot Pi"
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: DartsnutCoordinator) -> None:
        """Initialize the reboot button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id_base}_reboot"
        self._attr_device_info = coordinator.ha_device_info

    async def async_press(self) -> None:
        """Reboot the Raspberry Pi."""
        await self.coordinator.client.reboot()
