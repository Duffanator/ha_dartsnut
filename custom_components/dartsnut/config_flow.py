"""Config flow for Dartsnut PixelDart integration."""

from __future__ import annotations

import asyncio
import json
import logging
import socket
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DartsnutApiClient, DartsnutError
from .const import (
    CONF_MCP_PORT,
    CONF_WS_PORT,
    DEFAULT_HOST,
    DEFAULT_MCP_PORT,
    DEFAULT_NAME,
    DEFAULT_WS_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _discover_udp_host(timeout: float = 3.2) -> str | None:
    """Listen briefly for the Dartsnut UDP discovery broadcast on port 9252."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(timeout)
        sock.bind(("", DEFAULT_MCP_PORT))
        data, addr = sock.recvfrom(4096)
        payload = json.loads(data.decode("utf-8", errors="ignore"))
        ip = str(payload.get("ip") or "").strip()
        if ip and ip != "0.0.0.0":
            return ip
        return addr[0]
    except Exception:
        return None
    finally:
        try:
            sock.close()
        except Exception:
            pass


def _build_host_schema(
    host: str,
    ws_port: int = DEFAULT_WS_PORT,
    mcp_port: int = DEFAULT_MCP_PORT,
) -> vol.Schema:
    """Build schema for host and port configuration."""
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): str,
            vol.Optional(CONF_WS_PORT, default=ws_port): int,
            vol.Optional(CONF_MCP_PORT, default=mcp_port): int,
        }
    )


async def _async_validate_connection(
    hass: HomeAssistant,
    host: str,
    ws_port: int,
    mcp_port: int,
) -> dict[str, Any]:
    """Validate connectivity to the Dartsnut device and return device_info."""
    session = async_get_clientsession(hass)
    client = DartsnutApiClient(
        session=session,
        host=host,
        ws_port=ws_port,
        mcp_port=mcp_port,
    )
    info_resp = await client.ws_execute("get_device_info")
    await client.get_ui_state()
    return info_resp.get("device_info") or {}


class DartsnutConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dartsnut PixelDart."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> DartsnutOptionsFlow:
        """Return the options flow to allow editing host/ports from the Configure button."""
        return DartsnutOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            ws_port = int(user_input.get(CONF_WS_PORT, DEFAULT_WS_PORT))
            mcp_port = int(user_input.get(CONF_MCP_PORT, DEFAULT_MCP_PORT))

            try:
                device_info = await _async_validate_connection(
                    self.hass, host, ws_port, mcp_port
                )
            except DartsnutError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception in Dartsnut config flow")
                errors["base"] = "unknown"
            else:
                unique_id = str(
                    device_info.get("mac_address")
                    or device_info.get("id")
                    or host
                ).lower()
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                title = str(device_info.get("name") or DEFAULT_NAME)
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_HOST: host,
                        CONF_WS_PORT: ws_port,
                        CONF_MCP_PORT: mcp_port,
                    },
                )

        discovered_host = await asyncio.to_thread(_discover_udp_host)
        default_host = (
            user_input[CONF_HOST]
            if user_input and CONF_HOST in user_input
            else (discovered_host or DEFAULT_HOST)
        )
        default_ws = int((user_input or {}).get(CONF_WS_PORT, DEFAULT_WS_PORT))
        default_mcp = int((user_input or {}).get(CONF_MCP_PORT, DEFAULT_MCP_PORT))

        return self.async_show_form(
            step_id="user",
            data_schema=_build_host_schema(default_host, default_ws, default_mcp),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of host and ports."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            ws_port = int(user_input.get(CONF_WS_PORT, DEFAULT_WS_PORT))
            mcp_port = int(user_input.get(CONF_MCP_PORT, DEFAULT_MCP_PORT))

            try:
                await _async_validate_connection(
                    self.hass, host, ws_port, mcp_port
                )
            except DartsnutError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception in Dartsnut reconfigure flow")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_HOST: host,
                        CONF_WS_PORT: ws_port,
                        CONF_MCP_PORT: mcp_port,
                    },
                )

        current_host = str(
            (user_input or {}).get(CONF_HOST)
            or entry.data.get(CONF_HOST, DEFAULT_HOST)
        )
        current_ws = int(
            (user_input or {}).get(CONF_WS_PORT)
            or entry.data.get(CONF_WS_PORT, DEFAULT_WS_PORT)
        )
        current_mcp = int(
            (user_input or {}).get(CONF_MCP_PORT)
            or entry.data.get(CONF_MCP_PORT, DEFAULT_MCP_PORT)
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_host_schema(current_host, current_ws, current_mcp),
            errors=errors,
        )


class DartsnutOptionsFlow(OptionsFlow):
    """Handle options flow (Configure button) to update IP address or ports."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the Dartsnut connection settings."""
        entry = self.config_entry
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            ws_port = int(user_input.get(CONF_WS_PORT, DEFAULT_WS_PORT))
            mcp_port = int(user_input.get(CONF_MCP_PORT, DEFAULT_MCP_PORT))

            try:
                await _async_validate_connection(
                    self.hass, host, ws_port, mcp_port
                )
            except DartsnutError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception in Dartsnut options flow")
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        CONF_HOST: host,
                        CONF_WS_PORT: ws_port,
                        CONF_MCP_PORT: mcp_port,
                    },
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_create_entry(title="", data={})

        current_host = str(
            (user_input or {}).get(CONF_HOST)
            or entry.data.get(CONF_HOST, DEFAULT_HOST)
        )
        current_ws = int(
            (user_input or {}).get(CONF_WS_PORT)
            or entry.data.get(CONF_WS_PORT, DEFAULT_WS_PORT)
        )
        current_mcp = int(
            (user_input or {}).get(CONF_MCP_PORT)
            or entry.data.get(CONF_MCP_PORT, DEFAULT_MCP_PORT)
        )

        return self.async_show_form(
            step_id="init",
            data_schema=_build_host_schema(current_host, current_ws, current_mcp),
            errors=errors,
        )
