# Dartsnut PixelDart & PixelBoard — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)

Local Home Assistant integration for **Dartsnut PixelDart** and **PixelBoard** Raspberry Pi devices ([`Dartsnut/dartsnut_rpi`](https://github.com/Dartsnut/dartsnut_rpi)).

Communicates 100% locally with the Raspberry Pi's built-in WebSocket server (`:9251/ws`) and MCP HTTP server (`:9252/mcp`) — no cloud account or manual Pi modifications required.

---

## Features & Entities

| Platform | Entity | Description |
|---|---|---|
| `light` | **Screen** | Turns the RGB LED matrix completely off (`(0, 0, 0)` pitch black across Widget, Menu, and In-Game modes without modifying `conf.json`) and restores the previous mode & brightness (`1–9`) when turned back on. Ideal for room occupancy and sleep automations. |
| `camera` | **Screen** | Live `128×160` RGB matrix framebuffer snapshot (`image/png`) directly from shared memory. Use `image-rendering: pixelated` on dashboards for crisp pixel-art previews. |
| `sensor` | **State** | Current UI mode (`Widget`, `In Game`, `Menu`, `Game Select`, `Settings`, or `Screen Off`). |
| `sensor` | **Now Playing** | Human-readable summary of what is currently on screen (e.g., `Page 1: NFL Scores (128x128) · Digital Rain` or `Game: Cricket`), with attributes for `top_widget`, `bottom_widget`, `page_number`, `page_mode`, and `running_game_id`. |
| `sensor` | **Wi-Fi Signal** | Wi-Fi RSSI in `dBm` (plus SSID, IP, and MAC attributes). |
| `binary_sensor` | **Cloud Sync** | Connectivity status for Dartsnut remote sync. |
| `select` | **Widget Page** | Choose `Rotate All Pages` or pin any configured widget page (`Page 1`, `Page 2`, etc.). Previous multi-page state is persisted in Home Assistant storage. |
| `select` | **Launch Game** | Lists all installed games on the board and launches the selected game immediately (or selects `None` to exit back to widgets/menu). |
| `number` | **Volume** | Speaker volume (`0–100%`). |
| `number` | **Brightness Level** | Logical brightness level (`0–9`). |
| `button` | **Locate Device** | Flashes the identify graphic on the LED matrix. |
| `button` | **Reload Widgets** | Soft-reloads the widget configuration. |
| `button` | **Restart Service** | Restarts `dartsnut_python.service` (also exits any running game). |
| `button` | **Reboot Pi** | Reboots the Dartsnut Raspberry Pi. |
| `update` | **Firmware** | Checks and installs Dartsnut firmware updates from the `release` branch. |

---

## Installation

### Via HACS (Recommended)
1. Open **HACS** in Home Assistant.
2. Search for **Dartsnut PixelDart** and click **Download**.
3. **Restart Home Assistant**.

<details>
<summary><b>Installing as a Custom Repository (if not yet visible in your HACS catalog)</b></summary>

1. Open **HACS** in Home Assistant.
2. Click the **⋮** menu (top right) and select **Custom repositories**.
3. Paste `https://github.com/Duffanator/ha_dartsnut` and select category **Integration**.
4. Click **Download** on **Dartsnut PixelDart** and **Restart Home Assistant**.
</details>

### Manual Installation
1. Copy the `custom_components/dartsnut` folder into your Home Assistant `/config/custom_components/` directory.
2. **Restart Home Assistant**.

---

## Configuration

1. Go to **Settings → Devices & Services → + Add Integration**.
2. Search for **Dartsnut PixelDart**.
3. The config flow listens briefly for your board's UDP discovery broadcast on port `9252` to auto-fill its IP address, or you can enter your board's IP/hostname (`dartsnut`) manually.
4. Click **Submit**.

---

## Actions (Services)

* **`dartsnut.start_game`**: Launch any game on a targeted Dartsnut board (`device_id`, `entity_id`, or `area_id`) by its `game_id` (e.g., `01dartgame`, `cricket`, `aroundtheworld`, `pico8`).

---

## How Screen Blanking & Page Switching Work (On-Device Technical Details)

On Dartsnut hardware, logical brightness level `0` maps to `10%` PWM brightness (`rpi-rgb-led-matrix` only accepts `1..100%` PWM brightness), and the WebSocket API does not expose a native screen-off or UI-mode transition command. To provide true `0%` black screen control and conflict-free page pinning without modifying firmware files on the Pi, the integration uses the board's built-in local **Sideload API** (`sideload_upload` / `sideload_start` / `sideload_update_params` / `sideload_stop` on WebSocket `:9251/ws`):

1. **Screen Off (`light.turn_off`)**:
   * Starts an exclusive `128×160` black-canvas sideload session (`session_id: ha_screen_off`, staged under `apps/.sideload/ha_screen_off/blackout/main.py`) and sets brightness to `0`.
   * While active, the board's `SideloadSessionManager` suspends running widget/game subprocesses and renders a `(0, 0, 0)` black frame at 30 FPS **without modifying `apps/conf.json`**. The staged script sends a local WebSocket heartbeat (`127.0.0.1:9251`) every 8 seconds so the screen remains blanked even across Home Assistant restarts.
2. **Screen On (`light.turn_on`) & State Recovery**:
   * Stops the `ha_screen_off` sideload session (which causes the board's main loop to reload the unchanged `apps/conf.json` on `MenuState`).
   * If the board was in `Widget` mode prior to turning off (persisted in Home Assistant's `.storage/dartsnut.<entry_id>`), a short-lived helper process checks `/tmp/dartsnut_ui_state.json` and pulses bit `64` (`btn_home`) in `/dev/shm/pdoshm` so `MenuState` transitions back into `WidgetState` automatically. If a game was running prior to turning off, `start_game` is called to resume that game.
3. **Widget Page Selection (`select.select_option`)**:
   * When pinning a single page or restoring rotation, the helper writes `../../../conf.json` (resolved relative to the sideload working directory `apps/.sideload/<session_id>/<app_id>`) atomically while widget subprocesses are suspended, avoiding WebSocket thread race conditions in `WidgetState.update`.
   * If `/dev/shm/pdoshm`, `python3`, or the relative `conf.json` path is missing on the device, the helper exits with a non-zero status and reports the error in `sideload_logs`, which Home Assistant raises as a `HomeAssistantError`.
