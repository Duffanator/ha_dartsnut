"""Light platform for Dartsnut PixelDart screen brightness and power."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
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
    """Set up Dartsnut screen light entity."""
    coordinator: DartsnutCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DartsnutScreenLight(coordinator)])


class DartsnutScreenLight(CoordinatorEntity[DartsnutCoordinator], LightEntity):
    """Representation of the Dartsnut RGB LED matrix screen as a dimmable light."""

    _attr_has_entity_name = True
    _attr_name = "Screen"
    _attr_icon = "mdi:led-strip-variant"
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, coordinator: DartsnutCoordinator) -> None:
        """Initialize the screen light."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id_base}_screen"
        self._attr_device_info = coordinator.ha_device_info

    @property
    def is_on(self) -> bool:
        """Return true if screen is on (not blanked)."""
        if not self.coordinator.data:
            return False
        return self.coordinator.data.screen_on

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the screen mapped from 0-9 to 0-255."""
        if not self.coordinator.data or not self.coordinator.data.screen_on:
            return None
        level = max(0, min(9, self.coordinator.data.brightness))
        return round((level + 1) * 255 / 10)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if not self.coordinator.data:
            return {}
        info = self.coordinator.data.device_info
        return {
            "brightness_level": (
                self.coordinator.data.brightness
                if self.coordinator.data.screen_on
                else 0
            ),
            "dim_window_enabled": bool(info.get("dim_window_enabled", False)),
            "dim_window_start": info.get("dim_window_start", ""),
            "dim_window_end": info.get("dim_window_end", ""),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the screen on or adjust brightness (1-9)."""
        if ATTR_BRIGHTNESS in kwargs:
            ha_brightness = int(kwargs[ATTR_BRIGHTNESS])
            level = max(1, min(9, round(ha_brightness * 9 / 255)))
        else:
            level = max(1, min(9, self.coordinator.last_nonzero_brightness or 9))

        await self.coordinator.async_turn_on_screen(level)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the screen completely off (blank 0,0,0 canvas)."""
        await self.coordinator.async_turn_off_screen()
