"""API client for Dartsnut PixelDart (WebSocket :9251 and MCP :9252)."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any

import aiohttp

from .const import (
    DEFAULT_MCP_PORT,
    DEFAULT_WS_PORT,
    SIDELOAD_APP_ID,
    SIDELOAD_SESSION_ID,
)

_LOGGER = logging.getLogger(__name__)


class DartsnutError(Exception):
    """Base exception for Dartsnut API errors."""


class DartsnutApiClient:
    """Async client for Dartsnut local WebSocket and MCP HTTP servers."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        ws_port: int = DEFAULT_WS_PORT,
        mcp_port: int = DEFAULT_MCP_PORT,
    ) -> None:
        self._session = session
        self._host = host
        self._ws_port = ws_port
        self._mcp_port = mcp_port
        self._req_id = 0
        self._ws_lock = asyncio.Lock()

    @property
    def host(self) -> str:
        """Return device host/IP."""
        return self._host

    @property
    def ws_url(self) -> str:
        """Return WebSocket URL."""
        return f"ws://{self._host}:{self._ws_port}/ws"

    @property
    def mcp_url(self) -> str:
        """Return MCP HTTP URL."""
        return f"http://{self._host}:{self._mcp_port}/mcp"

    def _next_req_id(self) -> int:
        self._req_id = (self._req_id % 100000) + 1
        return self._req_id

    async def call_mcp_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        """Call a tool on the Dartsnut MCP HTTP server (:9252/mcp)."""
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_req_id(),
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments or {},
            },
        }
        try:
            async with self._session.post(
                self.mcp_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except Exception as err:
            raise DartsnutError(f"MCP call {name} failed: {err}") from err

        if "error" in data:
            raise DartsnutError(f"MCP error in {name}: {data['error']}")

        result = data.get("result") or {}
        if result.get("isError"):
            content = result.get("content") or []
            text = content[0].get("text", "Unknown error") if content else "Unknown error"
            raise DartsnutError(f"MCP tool {name} returned error: {text}")

        return result

    async def get_ui_state(self) -> dict[str, Any]:
        """Get UI and network state snapshot via MCP."""
        result = await self.call_mcp_tool("get_ui_state", timeout=8.0)
        structured = result.get("structuredContent")
        if isinstance(structured, dict):
            return structured
        content = result.get("content") or []
        if content and isinstance(content[0], dict) and content[0].get("text"):
            return json.loads(content[0]["text"])
        return {}

    async def capture_screen(self, surface: str = "full") -> bytes:
        """Capture the current 128x160 RGB matrix framebuffer as PNG bytes."""
        result = await self.call_mcp_tool(
            "capture_screen",
            {"surface": surface, "format": "png"},
            timeout=8.0,
        )
        for item in result.get("content") or []:
            if isinstance(item, dict) and item.get("type") == "image" and item.get("data"):
                return base64.b64decode(item["data"])
        raise DartsnutError("No image data in capture_screen response")

    async def check_firmware_update(self) -> dict[str, Any]:
        """Check for firmware updates via MCP."""
        result = await self.call_mcp_tool("check_firmware_update", timeout=20.0)
        return result.get("structuredContent") or {}

    async def perform_firmware_update(self) -> dict[str, Any]:
        """Perform firmware update via MCP."""
        result = await self.call_mcp_tool("perform_firmware_update", timeout=120.0)
        return result.get("structuredContent") or {}

    async def restart_main_service(self) -> dict[str, Any]:
        """Restart dartsnut_python.service via MCP."""
        result = await self.call_mcp_tool("restart_main_service", timeout=30.0)
        return result.get("structuredContent") or {}

    async def ws_execute_batch(
        self,
        commands: list[dict[str, Any]],
        timeout: float = 20.0,
    ) -> list[dict[str, Any]]:
        """Execute a sequence of WebSocket actions over a single connection."""
        async with self._ws_lock:
            try:
                async with self._session.ws_connect(
                    self.ws_url,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as ws:
                    responses: list[dict[str, Any]] = []
                    for cmd in commands:
                        req_id = self._next_req_id()
                        payload = {**cmd, "req_id": req_id}
                        await ws.send_json(payload)
                        if cmd.get("action") == "reboot":
                            responses.append({"action": "reboot", "message": "Success"})
                            break
                        while True:
                            msg = await ws.receive_json(timeout=timeout)
                            if msg.get("req_id") == req_id or "req_id" not in msg:
                                responses.append(msg)
                                break
                    return responses
            except Exception as err:
                raise DartsnutError(f"WebSocket communication failed: {err}") from err

    async def ws_execute(
        self,
        action: str,
        timeout: float = 20.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute a single WebSocket action."""
        results = await self.ws_execute_batch(
            [{"action": action, **kwargs}],
            timeout=timeout,
        )
        return results[0] if results else {}

    async def set_brightness(self, brightness: int) -> dict[str, Any]:
        """Set logical brightness level (0-9)."""
        return await self.ws_execute("set_brightness", brightness=int(brightness))

    async def set_volume(self, volume: int) -> dict[str, Any]:
        """Set speaker volume (0-100)."""
        return await self.ws_execute("set_volume", volume=int(volume))

    async def locate_device(self) -> dict[str, Any]:
        """Flash the locate graphic on the display."""
        return await self.ws_execute("locate_device")

    async def reload_conf(self) -> dict[str, Any]:
        """Reload widget/app configuration."""
        return await self.ws_execute("reload_conf")

    async def start_game(self, game_id: str) -> dict[str, Any]:
        """Launch a game by game_id."""
        return await self.ws_execute("start_game", game_id=str(game_id))

    async def reboot(self) -> dict[str, Any]:
        """Reboot the Raspberry Pi."""
        return await self.ws_execute("reboot", timeout=5.0)

    async def get_conf_json(self) -> dict[str, Any]:
        """Read full apps/conf.json without string truncation via get_file."""
        resp = await self.ws_execute("get_file", file_name="conf.json")
        b64_data = resp.get("file_data")
        if not b64_data:
            raise DartsnutError(f"Failed to read conf.json: {resp}")
        raw = base64.b64decode(b64_data).decode("utf-8")
        return json.loads(raw)

    async def apply_conf_and_transition(
        self,
        conf_data: dict[str, Any],
        target_state: str = "widget",
    ) -> None:
        """Atomically write apps/conf.json on the main loop and transition to target_state.

        Using a one-shot sideload suspends production (terminating any running game and
        widget subprocesses before touching conf.json), writes conf.json atomically, and
        lets the main display loop run init_widgets(ctx) without thread race conditions.
        If target_state == 'widget', a detached watcher pulses btn_home (pdoshm[0]=64)
        once init_widgets finishes so the board enters WidgetState automatically.
        """
        conf_b64 = base64.b64encode(json.dumps(conf_data).encode("utf-8")).decode("ascii")
        want_widget = target_state == "widget"

        script = f"""import base64, os, subprocess
conf_path = "/home/rpi/dartsnut_rpi/apps/conf.json"
tmp_path = conf_path + ".tmp"
with open(tmp_path, "wb") as f:
    f.write(base64.b64decode("{conf_b64}"))
os.replace(tmp_path, conf_path)
"""
        if want_widget:
            script += """
parent_pid = os.getpid()
child_code = f\"\"\"import json, mmap, os, time
while True:
    try:
        os.kill({parent_pid}, 0)
        time.sleep(0.05)
    except OSError:
        break
time.sleep(1.5)
fd = os.open("/dev/shm/pdoshm", os.O_RDWR)
m = mmap.mmap(fd, 0)
for _ in range(30):
    try:
        st = json.load(open("/tmp/dartsnut_ui_state.json")).get("state")
    except Exception:
        st = ""
    if st == "widget":
        break
    if st == "menu":
        end = time.monotonic() + 0.12
        while time.monotonic() < end:
            m[0] = 64
            time.sleep(0.001)
        m[0] = 0
        time.sleep(1.1)
    else:
        time.sleep(0.2)
m.close()
os.close(fd)
\"\"\"
subprocess.Popen(["/usr/bin/python3", "-c", child_code], start_new_session=True, close_fds=True)
"""
        b64_main = base64.b64encode(script.encode("utf-8")).decode("ascii")
        await self.ws_execute_batch(
            [
                {
                    "action": "sideload_upload",
                    "session_id": SIDELOAD_SESSION_ID,
                    "app_id": SIDELOAD_APP_ID,
                    "relative_path": "main.py",
                    "file_data": b64_main,
                },
                {
                    "action": "sideload_start",
                    "session_id": SIDELOAD_SESSION_ID,
                    "app_id": SIDELOAD_APP_ID,
                    "size": [128, 160],
                    "params": {},
                },
            ],
            timeout=30.0,
        )
        if want_widget:
            await asyncio.sleep(2.6)
        else:
            await asyncio.sleep(1.2)
