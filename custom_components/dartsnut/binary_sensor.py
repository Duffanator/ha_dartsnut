"""Binary sensor platform for Dartsnut PixelDart."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
    """Set up Dartsnut binary sensors."""
    coordinator: DartsnutCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DartsnutCloudConnectedBinarySensor(coordinator)])


class DartsnutCloudConnectedBinarySensor(
    CoordinatorEntity[DartsnutCoordinator], BinarySensorEntity
):
    """Binary sensor indicating whether Dartsnut cloud sync is connected."""

    _attr_has_entity_name = True
    _attr_name = "Cloud Sync"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: DartsnutCoordinator) -> None:
        """Initialize the cloud sync binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id_base}_cloud_connected"
        self._attr_device_info = coordinator.ha_device_info

    @property
    def is_on(self) -> bool:
        """Return true if connected to Dartsnut remote sync."""
        if not self.coordinator.data:
            return False
        return bool(
            self.coordinator.data.device_info.get("supabase_connected")
            or self.coordinator.data.device_info.get("remote_connected")
        )
