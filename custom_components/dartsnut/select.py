"""Select platform for Dartsnut PixelDart widget page and game launch control."""

from __future__ import annotations

import copy

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, OPTION_GAME_NONE, OPTION_ROTATE_ALL, SCREEN_OFF_PAGE_UUID
from .coordinator import DartsnutCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dartsnut select entities."""
    coordinator: DartsnutCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            DartsnutWidgetPageSelect(coordinator),
            DartsnutGameSelect(coordinator),
        ]
    )


class DartsnutWidgetPageSelect(CoordinatorEntity[DartsnutCoordinator], SelectEntity):
    """Select entity to rotate all widget pages or pin a specific widget page."""

    _attr_has_entity_name = True
    _attr_name = "Widget Page"
    _attr_icon = "mdi:view-carousel"

    def __init__(self, coordinator: DartsnutCoordinator) -> None:
        """Initialize the widget page selector."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id_base}_widget_page"
        self._attr_device_info = coordinator.ha_device_info

    @property
    def options(self) -> list[str]:
        """Return available page options."""
        page_map = self.coordinator.get_page_options_map()
        return [OPTION_ROTATE_ALL, *page_map.keys()]

    @property
    def current_option(self) -> str | None:
        """Return currently selected option."""
        return self.coordinator.get_current_page_option()

    async def async_select_option(self, option: str) -> None:
        """Select a widget page or enable rotation across all pages."""
        conf = await self.coordinator.client.get_conf_json()
        raw_pages = copy.deepcopy(conf.get("pages") or [])
        if not raw_pages:
            return

        page_map = self.coordinator.get_page_options_map()
        target_uuid = page_map.get(option)

        new_pages = []
        enabled_uuids = []
        for page in raw_pages:
            if not isinstance(page, dict):
                continue
            puuid = str(page.get("uuid") or "")
            if not puuid or puuid in ("0", SCREEN_OFF_PAGE_UUID):
                continue
            if option == OPTION_ROTATE_ALL or not target_uuid:
                page["enabled"] = True
            else:
                page["enabled"] = puuid == target_uuid
            if page["enabled"]:
                enabled_uuids.append(puuid)
            new_pages.append(page)

        self.coordinator.saved_enabled_page_uuids = enabled_uuids
        conf["pages"] = new_pages
        await self.coordinator.client.apply_conf_and_transition(conf, target_state="widget")
        await self.coordinator.async_refresh_apps_and_pages()


class DartsnutGameSelect(CoordinatorEntity[DartsnutCoordinator], SelectEntity):
    """Select entity to launch an installed game on the Dartsnut board."""

    _attr_has_entity_name = True
    _attr_name = "Launch Game"
    _attr_icon = "mdi:gamepad-variant"

    def __init__(self, coordinator: DartsnutCoordinator) -> None:
        """Initialize the game launcher select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id_base}_launch_game"
        self._attr_device_info = coordinator.ha_device_info

    @property
    def options(self) -> list[str]:
        """Return available games."""
        games_map = self.coordinator.get_games_map()
        opts = [OPTION_GAME_NONE, *sorted(games_map.keys())]
        curr = self.current_option
        if curr and curr not in opts:
            opts.append(curr)
        return opts

    @property
    def current_option(self) -> str | None:
        """Return currently running game or None."""
        if not self.coordinator.data:
            return OPTION_GAME_NONE
        running_gid = str(
            self.coordinator.data.ui_state.get("running_game_id")
            or (
                self.coordinator.data.ui_state.get("game_id")
                if self.coordinator.data.ui_state.get("state") == "in_game"
                else ""
            )
            or ""
        ).strip()
        if not running_gid:
            return OPTION_GAME_NONE
        for name, gid in self.coordinator.get_games_map().items():
            if gid == running_gid:
                return name
        return running_gid

    async def async_select_option(self, option: str) -> None:
        """Launch the selected game or exit back to menu/widgets."""
        if option == OPTION_GAME_NONE:
            if self.current_option != OPTION_GAME_NONE:
                await self.coordinator.client.restart_main_service()
                await self.coordinator.async_request_refresh()
            return

        games_map = self.coordinator.get_games_map()
        game_id = games_map.get(option, option)
        await self.coordinator.client.start_game(game_id)
        await self.coordinator.async_request_refresh()
