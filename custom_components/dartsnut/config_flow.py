"""Config flow for Dartsnut PixelDart integration."""

from __future__ import annotations

import asyncio
import json
import logging
import socket
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
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


class DartsnutConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dartsnut PixelDart."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            ws_port = int(user_input.get(CONF_WS_PORT, DEFAULT_WS_PORT))
            mcp_port = int(user_input.get(CONF_MCP_PORT, DEFAULT_MCP_PORT))

            session = async_get_clientsession(self.hass)
            client = DartsnutApiClient(
                session=session,
                host=host,
                ws_port=ws_port,
                mcp_port=mcp_port,
            )

            try:
                info_resp = await client.ws_execute("get_device_info")
                await client.get_ui_state()
                device_info = info_resp.get("device_info") or {}
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
        default_host = discovered_host or DEFAULT_HOST

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=default_host): str,
                vol.Optional(CONF_WS_PORT, default=DEFAULT_WS_PORT): int,
                vol.Optional(CONF_MCP_PORT, default=DEFAULT_MCP_PORT): int,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
