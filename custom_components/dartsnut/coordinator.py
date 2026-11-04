"""DataUpdateCoordinator for the Dartsnut PixelDart integration."""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass, field
from datetime import timedelta
import json
import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DartsnutApiClient, DartsnutError
from .const import (
    DOMAIN,
    OPTION_ROTATE_ALL,
    SIDELOAD_SESSION_ID,
    STATE_LABELS,
    WIDGET_FRIENDLY_NAMES,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)
APPS_REFRESH_INTERVAL = 60.0
FIRMWARE_REFRESH_INTERVAL = 1800.0
STORAGE_VERSION = 1


@dataclass
class DartsnutData:
    """Snapshot of Dartsnut device state."""

    device_info: dict[str, Any] = field(default_factory=dict)
    ui_state: dict[str, Any] = field(default_factory=dict)
    rssi: int | None = None
    brightness: int = 9
    screen_on: bool = True
    volume: int = 40
    apps: list[dict[str, Any]] = field(default_factory=list)
    pages: list[dict[str, Any]] = field(default_factory=list)
    conf_raw: dict[str, Any] = field(default_factory=dict)
    firmware_check: dict[str, Any] = field(default_factory=dict)


class DartsnutCoordinator(DataUpdateCoordinator[DartsnutData]):
    """Coordinator to manage polling Dartsnut local APIs."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: DartsnutApiClient,
        entry_id: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.entry_id = entry_id
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}"
        )
        self._store_loaded: bool = False

        self.last_nonzero_brightness: int = 9
        self.saved_enabled_page_uuids: list[str] = []
        self._state_before_off: str = "widget"
        self._game_before_off: str = ""
        self._blackout_active: bool = False

        self._last_apps_fetch: float = 0.0
        self._last_firmware_fetch: float = 0.0
        self._cached_apps: list[dict[str, Any]] = []
        self._cached_pages: list[dict[str, Any]] = []
        self._cached_conf_raw: dict[str, Any] = {}
        self._cached_firmware: dict[str, Any] = {}

        self._last_screen_png: bytes | None = None
        self._last_screen_at: float = 0.0

    async def async_load_store(self) -> None:
        """Load persisted state from Home Assistant storage."""
        if self._store_loaded:
            return
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            try:
                lvl = int(stored.get("last_nonzero_brightness", 9))
                if 1 <= lvl <= 9:
                    self.last_nonzero_brightness = lvl
            except (TypeError, ValueError):
                pass
            saved_uuids = stored.get("saved_enabled_page_uuids")
            if isinstance(saved_uuids, list) and all(isinstance(x, str) for x in saved_uuids):
                self.saved_enabled_page_uuids = [x for x in saved_uuids if x]
            state_before = stored.get("state_before_off")
            if isinstance(state_before, str) and state_before:
                self._state_before_off = state_before
            game_before = stored.get("game_before_off")
            if isinstance(game_before, str):
                self._game_before_off = game_before
        self._store_loaded = True

    async def async_save_store(self) -> None:
        """Persist state to Home Assistant storage."""
        await self._store.async_save(
            {
                "last_nonzero_brightness": self.last_nonzero_brightness,
                "saved_enabled_page_uuids": self.saved_enabled_page_uuids,
                "state_before_off": self._state_before_off,
                "game_before_off": self._game_before_off,
            }
        )

    @property
    def device_name(self) -> str:
        """Return the device friendly name."""
        if self.data and self.data.device_info.get("name"):
            return str(self.data.device_info["name"])
        return "DouseaDart"

    @property
    def unique_id_base(self) -> str:
        """Return unique identifier for the device."""
        if self.data:
            mac = self.data.device_info.get("mac_address") or self.data.device_info.get("id")
            if mac:
                return str(mac).lower()
        return self.entry_id

    @property
    def ha_device_info(self) -> DeviceInfo:
        """Return Home Assistant DeviceInfo."""
        info = self.data.device_info if self.data else {}
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id_base)},
            name=self.device_name,
            manufacturer="Dartsnut",
            model=info.get("model") or "PixelDart",
            hw_version=info.get("hardware_version"),
            sw_version=info.get("firmware_version") or self._cached_firmware.get("current_version"),
            configuration_url=f"http://{self.client.host}:{self.client._mcp_port}/mcp",
        )

    def get_user_pages(self) -> list[dict[str, Any]]:
        """Return user-configured widget pages (excluding synthetic default page 0)."""
        pages = self.data.pages if self.data else self._cached_pages
        return [
            p
            for p in pages
            if isinstance(p, dict)
            and p.get("uuid")
            and p.get("uuid") != "0"
        ]

    def get_widget_friendly_name(self, widget_id: str) -> str:
        """Resolve a human-readable name for a widget or game ID."""
        if not widget_id:
            return ""
        for page in self._cached_pages:
            for w in page.get("widgets") or []:
                if isinstance(w, dict) and w.get("id") == widget_id and w.get("widget_name"):
                    return str(w["widget_name"])
        for app in self._cached_apps:
            if app.get("id") == widget_id and app.get("name") and app.get("name") != widget_id:
                return str(app["name"])
        return WIDGET_FRIENDLY_NAMES.get(widget_id, widget_id)

    def get_page_option_label(self, idx: int, page: dict[str, Any]) -> str:
        """Build a clean dropdown label for a widget page."""
        title = str(page.get("title") or f"Page {idx + 1}").strip()
        widget_names: list[str] = []
        for w in page.get("widgets") or []:
            if isinstance(w, dict):
                wname = w.get("widget_name") or self.get_widget_friendly_name(str(w.get("id") or ""))
                if wname:
                    widget_names.append(str(wname))
        if widget_names:
            return f"{title}: {' + '.join(widget_names)}"
        return title

    def get_page_options_map(self) -> dict[str, str]:
        """Return mapping of option label -> page UUID for real user pages."""
        mapping: dict[str, str] = {}
        for idx, page in enumerate(self.get_user_pages()):
            uuid = str(page.get("uuid") or "")
            label = self.get_page_option_label(idx, page)
            mapping[label] = uuid
        return mapping

    def get_current_page_option(self) -> str:
        """Return currently selected widget page mode option."""
        user_pages = self.get_user_pages()
        enabled_pages = [p for p in user_pages if p.get("enabled", True)]
        if len(enabled_pages) == 1:
            target_uuid = enabled_pages[0].get("uuid")
            for idx, p in enumerate(user_pages):
                if p.get("uuid") == target_uuid:
                    return self.get_page_option_label(idx, p)
        return OPTION_ROTATE_ALL

    def get_games_map(self) -> dict[str, str]:
        """Return mapping of game display name -> game_id for installed games."""
        apps = self.data.apps if self.data else self._cached_apps
        games: dict[str, str] = {}
        for app in apps:
            if app.get("type") == "game" and app.get("id"):
                gid = str(app["id"])
                name = str(app.get("name") or gid)
                games[name] = gid
        return games

    def get_now_playing_summary(self) -> tuple[str, dict[str, Any]]:
        """Compute the Now Playing state string and extra attributes."""
        if not self.data:
            return "Unknown", {}

        raw_state = str(self.data.ui_state.get("state") or "unknown")
        running_game = str(
            self.data.ui_state.get("running_game_id")
            or (
                self.data.ui_state.get("game_id")
                if raw_state == "in_game"
                else ""
            )
            or ""
        ).strip()
        page_index = self.data.ui_state.get("page_index")
        page_title = str(self.data.ui_state.get("page_title") or "").strip()
        page_uuid = str(self.data.ui_state.get("page_uuid") or "").strip()
        widget_ids = self.data.ui_state.get("widget_ids") or []
        widget_names = [self.get_widget_friendly_name(str(wid)) for wid in widget_ids if wid]

        user_pages = self.get_user_pages()
        if not page_title and page_uuid:
            for idx, p in enumerate(user_pages):
                if p.get("uuid") == page_uuid:
                    page_title = str(p.get("title") or f"Page {idx + 1}")
                    break

        top_widget = widget_names[0] if len(widget_names) >= 1 else ""
        bottom_widget = widget_names[1] if len(widget_names) >= 2 else ""

        enabled_pages = [p for p in user_pages if p.get("enabled", True)]

        attrs: dict[str, Any] = {
            "mode": "Screen Off" if not self.data.screen_on else STATE_LABELS.get(raw_state, raw_state.title()),
            "raw_state": raw_state,
            "screen_on": self.data.screen_on,
            "brightness_level": 0 if not self.data.screen_on else self.data.brightness,
            "page_number": (int(page_index) + 1) if isinstance(page_index, int) else None,
            "page_title": page_title,
            "page_uuid": page_uuid,
            "widget_ids": widget_ids,
            "widgets": widget_names,
            "top_widget": top_widget,
            "bottom_widget": bottom_widget,
            "running_game_id": running_game,
            "total_pages": len(user_pages),
            "enabled_pages": len(enabled_pages),
            "page_mode": self.get_current_page_option(),
        }

        if not self.data.screen_on:
            return "Screen Off", attrs

        if raw_state == "in_game" or running_game:
            game_name = self.get_widget_friendly_name(running_game) if running_game else "Game"
            attrs["running_game_name"] = game_name
            return f"Game: {game_name}", attrs

        if raw_state == "widget":
            if widget_names:
                prefix = f"{page_title}: " if page_title else ""
                return f"{prefix}{' · '.join(widget_names)}", attrs
            return page_title or "Widgets", attrs

        if raw_state == "game_select":
            return "Selecting Game", attrs

        if raw_state == "menu":
            return "Main Menu", attrs

        if raw_state == "settings":
            return "Settings", attrs

        return STATE_LABELS.get(raw_state, "Idle"), attrs

    async def async_turn_off_screen(self) -> None:
        """Blank the LED matrix to 100% black via sideload without modifying conf.json."""
        await self.async_load_store()
        if self.data and self.data.brightness > 0:
            self.last_nonzero_brightness = self.data.brightness

        if not self._blackout_active:
            try:
                live_ui = await self.client.get_ui_state()
            except DartsnutError:
                live_ui = self.data.ui_state if self.data else {}

            raw_state = str(live_ui.get("state") or "widget")
            self._state_before_off = raw_state
            self._game_before_off = (
                str(live_ui.get("running_game_id") or live_ui.get("game_id") or "").strip()
                if raw_state == "in_game"
                else ""
            )
            await self.async_save_store()

        await self.client.set_brightness(0)
        await self.client.sideload_start_blackout()
        self._blackout_active = True
        await self.async_request_refresh()

    async def async_turn_on_screen(self, brightness_level: int | None = None) -> None:
        """Restore the LED matrix from the blackout session and restore prior mode."""
        await self.async_load_store()
        level = max(1, min(9, brightness_level or self.last_nonzero_brightness or 9))
        self.last_nonzero_brightness = level
        await self.async_save_store()

        restore_state = (
            "menu"
            if self._state_before_off in ("menu", "game_select", "settings")
            else "widget"
        )
        await self.client.sideload_stop_blackout(target_state=restore_state)
        self._blackout_active = False
        await self.client.set_brightness(level)

        if self._state_before_off == "in_game" and self._game_before_off:
            try:
                await self.client.start_game(self._game_before_off)
            except DartsnutError as err:
                _LOGGER.warning(
                    "Could not relaunch game %s after screen on: %s",
                    self._game_before_off,
                    err,
                )

        self._last_apps_fetch = 0.0
        await self.async_request_refresh()

    async def async_get_screen_image(self) -> bytes | None:
        """Fetch or return cached 128x160 PNG screen capture."""
        now = time.monotonic()
        if self._last_screen_png and (now - self._last_screen_at) < 2.0:
            return self._last_screen_png
        try:
            png_bytes = await self.client.capture_screen("full")
            self._last_screen_png = png_bytes
            self._last_screen_at = now
            return png_bytes
        except DartsnutError as err:
            _LOGGER.debug("Screen capture failed, using cached frame if available: %s", err)
            return self._last_screen_png

    async def async_refresh_apps_and_pages(self) -> None:
        """Force an immediate refresh of apps/conf.json and list_apps."""
        self._last_apps_fetch = 0.0
        await self.async_request_refresh()

    async def _async_update_data(self) -> DartsnutData:
        """Fetch latest state from Dartsnut MCP (:9252) and WebSocket (:9251)."""
        await self.async_load_store()

        now = time.monotonic()
        need_apps = (now - self._last_apps_fetch) >= APPS_REFRESH_INTERVAL or not self._cached_pages
        need_fw = (now - self._last_firmware_fetch) >= FIRMWARE_REFRESH_INTERVAL or not self._cached_firmware

        ws_cmds: list[dict[str, Any]] = [
            {"action": "get_device_info"},
            {"action": "get_wifi_rssi"},
            {"action": "sideload_logs", "session_id": SIDELOAD_SESSION_ID},
        ]
        if need_apps:
            ws_cmds.append({"action": "list_apps"})
            ws_cmds.append({"action": "get_file", "file_name": "conf.json"})

        try:
            ui_state, ws_results = await self._gather_core(ws_cmds)
        except DartsnutError as err:
            raise UpdateFailed(str(err)) from err

        device_info: dict[str, Any] = {}
        rssi: int | None = None
        sideload_running: bool = False

        for msg in ws_results:
            action = msg.get("action")
            if action == "get_device_info":
                device_info = msg.get("device_info") or {}
            elif action == "get_wifi_rssi":
                try:
                    rssi = int(msg.get("rssi"))
                except (TypeError, ValueError):
                    rssi = None
            elif action == "sideload_logs":
                sideload_running = bool(msg.get("running"))
            elif action == "list_apps" and "apps" in msg:
                parsed_apps: list[dict[str, Any]] = []
                for item in msg.get("apps") or []:
                    try:
                        manifest = json.loads(
                            base64.b64decode(item.get("conf", "")).decode("utf-8")
                        )
                        if isinstance(manifest, dict):
                            parsed_apps.append(manifest)
                    except Exception:
                        continue
                self._cached_apps = parsed_apps
                self._last_apps_fetch = now
            elif action == "get_file" and msg.get("file_name") == "conf.json" and msg.get("file_data"):
                try:
                    raw_conf = json.loads(
                        base64.b64decode(msg["file_data"]).decode("utf-8")
                    )
                    if isinstance(raw_conf, dict):
                        self._cached_conf_raw = raw_conf
                        pages = raw_conf.get("pages")
                        if isinstance(pages, list):
                            self._cached_pages = pages
                            enabled_real = [
                                str(p.get("uuid"))
                                for p in pages
                                if isinstance(p, dict)
                                and p.get("uuid") not in (None, "", "0")
                                and p.get("enabled", True)
                            ]
                            if len(enabled_real) > 1 and enabled_real != self.saved_enabled_page_uuids:
                                self.saved_enabled_page_uuids = enabled_real
                                await self.async_save_store()
                except Exception as err:
                    _LOGGER.debug("Failed to parse conf.json: %s", err)

        self._blackout_active = sideload_running
        if sideload_running:
            try:
                await self.client.sideload_heartbeat()
            except DartsnutError:
                pass

        if need_fw:
            try:
                self._cached_firmware = await self.client.check_firmware_update()
                self._last_firmware_fetch = now
            except DartsnutError as err:
                _LOGGER.debug("Firmware check skipped: %s", err)

        try:
            brightness = int(device_info.get("brightness", 9))
        except (TypeError, ValueError):
            brightness = 9
        if brightness > 0 and brightness != self.last_nonzero_brightness:
            self.last_nonzero_brightness = brightness
            await self.async_save_store()

        try:
            volume = int(device_info.get("volume", 40))
        except (TypeError, ValueError):
            volume = 40

        screen_on = not sideload_running

        return DartsnutData(
            device_info=device_info,
            ui_state=ui_state,
            rssi=rssi,
            brightness=brightness,
            screen_on=screen_on,
            volume=volume,
            apps=list(self._cached_apps),
            pages=list(self._cached_pages),
            conf_raw=dict(self._cached_conf_raw),
            firmware_check=dict(self._cached_firmware),
        )

    async def _gather_core(
        self, ws_cmds: list[dict[str, Any]]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Fetch MCP get_ui_state and WebSocket batch concurrently."""
        ui_task = self.client.get_ui_state()
        ws_task = self.client.ws_execute_batch(ws_cmds)
        ui_state, ws_results = await asyncio.gather(ui_task, ws_task)
        return ui_state, ws_results
