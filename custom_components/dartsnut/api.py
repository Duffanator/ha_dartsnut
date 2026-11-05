"""API client for Dartsnut PixelDart (WebSocket :9251 and MCP :9252)."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any

import aiohttp

from homeassistant.exceptions import HomeAssistantError

from .const import (
    DEFAULT_MCP_PORT,
    DEFAULT_WS_PORT,
    SIDELOAD_APP_ID,
    SIDELOAD_SESSION_ID,
)

_LOGGER = logging.getLogger(__name__)


class DartsnutError(HomeAssistantError):
    """Base exception for Dartsnut API errors."""


def _build_sideload_helper_script(ws_port: int) -> str:
    """Build the sideload helper script without hardcoded install paths.

    Modes controlled via --params JSON:
    - mode == 'blackout': Validates /dev/shm/pdoshm, keeps the 128x160 black
      sideload canvas active by sending local WebSocket heartbeats every 8s.
    - mode == 'wake': Validates required paths, optionally spawns a detached
      watcher to pulse btn_home (pdoshm[0]=64) once init_widgets finishes so
      the board transitions from MenuState to WidgetState, and exits cleanly.
    - mode == 'apply_conf': Validates relative ../../../conf.json path, writes
      the updated pages config atomically, optionally transitions to WidgetState,
      and exits cleanly.
    """
    return f"""import argparse
import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import time

PDOSHM_PATH = "/dev/shm/pdoshm"
UI_STATE_PATH = "/tmp/dartsnut_ui_state.json"
CONF_REL_PATH = os.path.abspath(os.path.join(os.getcwd(), "..", "..", "..", "conf.json"))


def fail(msg: str) -> None:
    sys.stderr.write(f"DARTSNUT_ERROR: {{msg}}\\n")
    sys.stderr.flush()
    sys.exit(1)


def send_local_heartbeat(port: int, session_id: str) -> None:
    s = socket.create_connection(("127.0.0.1", port), timeout=5)
    try:
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        handshake = (
            f"GET /ws HTTP/1.1\\r\\n"
            f"Host: 127.0.0.1:{{port}}\\r\\n"
            f"Upgrade: websocket\\r\\n"
            f"Connection: Upgrade\\r\\n"
            f"Sec-WebSocket-Key: {{key}}\\r\\n"
            f"Sec-WebSocket-Version: 13\\r\\n\\r\\n"
        )
        s.sendall(handshake.encode("ascii"))
        buf = b""
        while b"\\r\\n\\r\\n" not in buf:
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
        payload = json.dumps({{
            "action": "sideload_heartbeat",
            "session_id": session_id,
            "req_id": 1,
        }}).encode("utf-8")
        mask = os.urandom(4)
        header = bytearray([0x81, 0x80 | len(payload)]) + mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        s.sendall(bytes(header) + masked)
        s.recv(4096)
    finally:
        s.close()


def spawn_widget_transition_watcher() -> None:
    if not os.path.exists(PDOSHM_PATH):
        fail(f"Required shared memory path does not exist: {{PDOSHM_PATH}}")
    py_bin = shutil.which("python3") or sys.executable
    if not py_bin or not os.path.exists(py_bin):
        fail("Could not locate python3 interpreter on device")

    parent_pid = os.getpid()
    child_code = f\"\"\"import json, mmap, os, time
while True:
    try:
        os.kill({{parent_pid}}, 0)
        time.sleep(0.05)
    except OSError:
        break
time.sleep(1.5)
if not os.path.exists({{PDOSHM_PATH!r}}):
    raise SystemExit(1)
fd = os.open({{PDOSHM_PATH!r}}, os.O_RDWR)
m = mmap.mmap(fd, 0)
for _ in range(30):
    try:
        with open({{UI_STATE_PATH!r}}, encoding="utf-8") as f:
            st = json.load(f).get("state")
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
    subprocess.Popen(
        [py_bin, "-c", child_code],
        start_new_session=True,
        close_fds=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--params", default="{{}}")
    args, _ = parser.parse_known_args()
    try:
        params = json.loads(args.params) if args.params else {{}}
    except Exception as exc:
        fail(f"Invalid JSON in --params: {{exc}}")

    mode = params.get("mode", "blackout")
    port = int(params.get("ws_port", {ws_port}))
    target_state = params.get("target_state", "widget")

    if mode == "blackout":
        if not os.path.exists(PDOSHM_PATH):
            fail(f"Required shared memory path does not exist: {{PDOSHM_PATH}}")
        print("READY", flush=True)
        while True:
            time.sleep(8)
            try:
                send_local_heartbeat(port, {SIDELOAD_SESSION_ID!r})
            except Exception:
                pass

    elif mode == "wake":
        if target_state == "widget":
            spawn_widget_transition_watcher()
        print("WAKE_OK", flush=True)
        sys.exit(0)

    elif mode == "apply_conf":
        conf_b64 = params.get("conf_b64", "")
        if not conf_b64:
            fail("Missing conf_b64 parameter for apply_conf")
        if not os.path.isfile(CONF_REL_PATH):
            fail(f"Expected configuration file not found at {{CONF_REL_PATH}}")
        try:
            raw_bytes = base64.b64decode(conf_b64)
            json.loads(raw_bytes.decode("utf-8"))
            tmp_path = CONF_REL_PATH + ".tmp"
            with open(tmp_path, "wb") as f:
                f.write(raw_bytes)
            os.replace(tmp_path, CONF_REL_PATH)
        except Exception as exc:
            fail(f"Failed to write conf.json at {{CONF_REL_PATH}}: {{exc}}")

        if target_state == "widget":
            spawn_widget_transition_watcher()
        print("APPLY_OK", flush=True)
        sys.exit(0)

    else:
        fail(f"Unknown helper mode: {{mode}}")


if __name__ == "__main__":
    main()
"""


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

    @staticmethod
    def _raise_for_sideload_errors(logs: list[dict[str, Any]], context: str) -> None:
        """Inspect sideload log entries and raise a clear DartsnutError if DARTSNUT_ERROR is present."""
        for entry in logs:
            if not isinstance(entry, dict):
                continue
            text = str(entry.get("text") or "").strip()
            if "DARTSNUT_ERROR:" in text:
                detail = text.split("DARTSNUT_ERROR:", 1)[1].strip()
                raise DartsnutError(f"{context}: {detail}")

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

    async def is_blackout_running(self) -> bool:
        """Check whether the ha_screen_off blackout sideload session is currently running."""
        resp = await self.ws_execute(
            "sideload_logs",
            session_id=SIDELOAD_SESSION_ID,
            timeout=8.0,
        )
        if resp.get("error"):
            return False
        return bool(resp.get("running"))

    async def sideload_heartbeat(self) -> None:
        """Send a heartbeat to the active blackout session."""
        await self.ws_execute(
            "sideload_heartbeat",
            session_id=SIDELOAD_SESSION_ID,
            timeout=8.0,
        )

    async def sideload_start_blackout(self) -> None:
        """Start the 128x160 black-canvas sideload session without modifying conf.json."""
        script = _build_sideload_helper_script(self._ws_port)
        b64_main = base64.b64encode(script.encode("utf-8")).decode("ascii")
        results = await self.ws_execute_batch(
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
                    "params": {
                        "mode": "blackout",
                        "ws_port": self._ws_port,
                    },
                },
            ],
            timeout=30.0,
        )
        start_resp = results[-1] if results else {}
        if start_resp.get("error"):
            raise DartsnutError(f"Failed to start screen blackout session: {start_resp['error']}")

        await asyncio.sleep(0.3)
        logs_resp = await self.ws_execute("sideload_logs", session_id=SIDELOAD_SESSION_ID)
        self._raise_for_sideload_errors(logs_resp.get("logs") or [], "Screen off failed")
        if not logs_resp.get("running"):
            raise DartsnutError("Screen blackout session exited unexpectedly on device")

    async def sideload_stop_blackout(self, target_state: str = "widget") -> None:
        """Stop an active blackout session and restore target_state ('widget' or 'menu')."""
        want_widget = target_state == "widget"
        if want_widget:
            resp = await self.ws_execute(
                "sideload_update_params",
                session_id=SIDELOAD_SESSION_ID,
                params={"mode": "wake", "target_state": "widget"},
                timeout=15.0,
            )
            if resp.get("error"):
                return
            await asyncio.sleep(0.3)
            logs_resp = await self.ws_execute("sideload_logs", session_id=SIDELOAD_SESSION_ID)
            self._raise_for_sideload_errors(logs_resp.get("logs") or [], "Screen wake failed")
            await asyncio.sleep(2.4)
        else:
            await self.ws_execute(
                "sideload_stop",
                session_id=SIDELOAD_SESSION_ID,
                timeout=10.0,
            )
            await asyncio.sleep(1.2)

    async def apply_conf_and_transition(
        self,
        conf_data: dict[str, Any],
        target_state: str = "widget",
    ) -> None:
        """Atomically write apps/conf.json on the main loop and transition to target_state."""
        script = _build_sideload_helper_script(self._ws_port)
        b64_main = base64.b64encode(script.encode("utf-8")).decode("ascii")
        conf_b64 = base64.b64encode(json.dumps(conf_data).encode("utf-8")).decode("ascii")
        want_widget = target_state == "widget"

        results = await self.ws_execute_batch(
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
                    "params": {
                        "mode": "apply_conf",
                        "conf_b64": conf_b64,
                        "target_state": target_state,
                    },
                },
            ],
            timeout=30.0,
        )
        start_resp = results[-1] if results else {}
        if start_resp.get("error"):
            raise DartsnutError(f"Failed to apply widget page configuration: {start_resp['error']}")

        await asyncio.sleep(0.3)
        logs_resp = await self.ws_execute("sideload_logs", session_id=SIDELOAD_SESSION_ID)
        self._raise_for_sideload_errors(
            logs_resp.get("logs") or [],
            "Applying widget page configuration failed",
        )
        if want_widget:
            await asyncio.sleep(2.4)
        else:
            await asyncio.sleep(1.0)
