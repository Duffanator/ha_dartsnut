"""Update platform for Dartsnut PixelDart firmware."""

from __future__ import annotations

from typing import Any

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
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
    """Set up Dartsnut firmware update entity."""
    coordinator: DartsnutCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DartsnutFirmwareUpdate(coordinator)])


class DartsnutFirmwareUpdate(CoordinatorEntity[DartsnutCoordinator], UpdateEntity):
    """Update entity for Dartsnut Raspberry Pi firmware."""

    _attr_has_entity_name = True
    _attr_name = "Firmware"
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = UpdateEntityFeature.INSTALL

    def __init__(self, coordinator: DartsnutCoordinator) -> None:
        """Initialize the firmware update entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id_base}_firmware"
        self._attr_device_info = coordinator.ha_device_info

    @property
    def installed_version(self) -> str | None:
        """Return installed firmware version."""
        if not self.coordinator.data:
            return None
        fw = self.coordinator.data.firmware_check
        return (
            fw.get("current_version")
            or self.coordinator.data.device_info.get("firmware_version")
        )

    @property
    def latest_version(self) -> str | None:
        """Return latest available firmware version."""
        if not self.coordinator.data:
            return None
        fw = self.coordinator.data.firmware_check
        return fw.get("latest_version") or self.installed_version

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install firmware update via MCP."""
        await self.coordinator.client.perform_firmware_update()
        self.coordinator._last_firmware_fetch = 0.0
        await self.coordinator.async_request_refresh()
