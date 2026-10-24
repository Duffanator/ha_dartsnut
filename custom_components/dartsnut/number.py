"""Number platform for Dartsnut PixelDart volume and brightness level."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
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
    """Set up Dartsnut number entities."""
    coordinator: DartsnutCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            DartsnutVolumeNumber(coordinator),
            DartsnutBrightnessNumber(coordinator),
        ]
    )


class DartsnutVolumeNumber(CoordinatorEntity[DartsnutCoordinator], NumberEntity):
    """Number entity for speaker volume (0-100%)."""

    _attr_has_entity_name = True
    _attr_name = "Volume"
    _attr_icon = "mdi:volume-high"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 5
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: DartsnutCoordinator) -> None:
        """Initialize the volume control."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id_base}_volume"
        self._attr_device_info = coordinator.ha_device_info

    @property
    def native_value(self) -> float | None:
        """Return current volume."""
        if not self.coordinator.data:
            return None
        return float(self.coordinator.data.volume)

    async def async_set_native_value(self, value: float) -> None:
        """Set new volume level."""
        vol_int = max(0, min(100, int(round(value))))
        await self.coordinator.client.set_volume(vol_int)
        if self.coordinator.data:
            self.coordinator.data.volume = vol_int
            self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class DartsnutBrightnessNumber(CoordinatorEntity[DartsnutCoordinator], NumberEntity):
    """Number entity for raw logical brightness level (0-9)."""

    _attr_has_entity_name = True
    _attr_name = "Brightness Level"
    _attr_icon = "mdi:brightness-6"
    _attr_native_min_value = 0
    _attr_native_max_value = 9
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: DartsnutCoordinator) -> None:
        """Initialize the brightness level number entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id_base}_brightness_level"
        self._attr_device_info = coordinator.ha_device_info

    @property
    def native_value(self) -> float | None:
        """Return current logical brightness (0-9)."""
        if not self.coordinator.data:
            return None
        return float(self.coordinator.data.brightness)

    async def async_set_native_value(self, value: float) -> None:
        """Set logical brightness (0-9)."""
        lvl = max(0, min(9, int(round(value))))
        if lvl > 0:
            self.coordinator.last_nonzero_brightness = lvl
            if self.coordinator.data and not self.coordinator.data.screen_on:
                await self.coordinator.async_turn_on_screen(lvl)
                return
        await self.coordinator.client.set_brightness(lvl)
        if self.coordinator.data:
            self.coordinator.data.brightness = lvl
            self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
