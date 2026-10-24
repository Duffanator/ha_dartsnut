"""Camera platform for Dartsnut PixelDart live 128x160 LED matrix screen."""

from __future__ import annotations

from homeassistant.components.camera import Camera
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
    """Set up Dartsnut live screen camera."""
    coordinator: DartsnutCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DartsnutScreenCamera(coordinator)])


class DartsnutScreenCamera(CoordinatorEntity[DartsnutCoordinator], Camera):
    """Live 128x160 RGB matrix framebuffer camera."""

    _attr_has_entity_name = True
    _attr_name = "Screen"
    _attr_icon = "mdi:bullseye-arrow"
    _attr_frame_interval = 2.0

    def __init__(self, coordinator: DartsnutCoordinator) -> None:
        """Initialize the camera."""
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._attr_unique_id = f"{coordinator.unique_id_base}_screen_camera"
        self._attr_device_info = coordinator.ha_device_info
        self.content_type = "image/png"

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        return await self.coordinator.async_get_screen_image()
