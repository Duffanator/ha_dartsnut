"""Sensor platform for Dartsnut PixelDart."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STATE_LABELS
from .coordinator import DartsnutCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dartsnut sensors."""
    coordinator: DartsnutCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            DartsnutStateSensor(coordinator),
            DartsnutNowPlayingSensor(coordinator),
            DartsnutWifiSignalSensor(coordinator),
        ]
    )


class DartsnutStateSensor(CoordinatorEntity[DartsnutCoordinator], SensorEntity):
    """Sensor reporting the current UI state of the Dartsnut board."""

    _attr_has_entity_name = True
    _attr_name = "State"
    _attr_icon = "mdi:bullseye-arrow"

    def __init__(self, coordinator: DartsnutCoordinator) -> None:
        """Initialize the state sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id_base}_state"
        self._attr_device_info = coordinator.ha_device_info

    @property
    def native_value(self) -> str:
        """Return the current state."""
        if not self.coordinator.data:
            return "Unknown"
        if not self.coordinator.data.screen_on:
            return "Screen Off"
        raw = str(self.coordinator.data.ui_state.get("state") or "unknown")
        return STATE_LABELS.get(raw, raw.title())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        _, attrs = self.coordinator.get_now_playing_summary()
        return attrs


class DartsnutNowPlayingSensor(CoordinatorEntity[DartsnutCoordinator], SensorEntity):
    """Sensor reporting what is currently displayed or playing on the board."""

    _attr_has_entity_name = True
    _attr_name = "Now Playing"
    _attr_icon = "mdi:television-play"

    def __init__(self, coordinator: DartsnutCoordinator) -> None:
        """Initialize the now playing sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id_base}_now_playing"
        self._attr_device_info = coordinator.ha_device_info

    @property
    def native_value(self) -> str:
        """Return human-readable summary of current display content."""
        summary, _ = self.coordinator.get_now_playing_summary()
        return summary

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes about the active page/widgets/game."""
        _, attrs = self.coordinator.get_now_playing_summary()
        return attrs


class DartsnutWifiSignalSensor(CoordinatorEntity[DartsnutCoordinator], SensorEntity):
    """Sensor reporting Wi-Fi RSSI in dBm."""

    _attr_has_entity_name = True
    _attr_name = "Wi-Fi Signal"
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: DartsnutCoordinator) -> None:
        """Initialize the Wi-Fi signal sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id_base}_wifi_signal"
        self._attr_device_info = coordinator.ha_device_info

    @property
    def native_value(self) -> int | None:
        """Return RSSI in dBm."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.rssi

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return network details."""
        if not self.coordinator.data:
            return {}
        net = self.coordinator.data.ui_state.get("network") or {}
        info = self.coordinator.data.device_info
        return {
            "ssid": net.get("ssid") or info.get("ssid") or "",
            "ip_address": net.get("ip_address") or self.coordinator.client.host,
            "mac_address": info.get("mac_address") or info.get("id") or "",
        }
