# Dartsnut PixelDart & PixelBoard — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Local Home Assistant integration for **Dartsnut PixelDart** and **PixelBoard** Raspberry Pi devices ([`Dartsnut/dartsnut_rpi`](https://github.com/Dartsnut/dartsnut_rpi)).

Communicates 100% locally with the Raspberry Pi's built-in WebSocket server (`:9251/ws`) and MCP HTTP server (`:9252/mcp`) — no cloud account or Pi modifications required.

---

## Features & Entities

| Platform | Entity | Description |
|---|---|---|
| `light` | **Screen** | Turns the RGB LED matrix completely off (`(0, 0, 0)` pitch black across Widget, Menu, and In-Game modes) and restores the previous mode & brightness (`1–9`) when turned back on. Ideal for room occupancy and sleep automations. |
| `camera` | **Screen** | Live `128×160` RGB matrix framebuffer snapshot (`image/png`) directly from shared memory. Use `image-rendering: pixelated` on dashboards for crisp pixel-art previews. |
| `sensor` | **State** | Current UI mode (`Widget`, `In Game`, `Menu`, `Game Select`, `Settings`, or `Screen Off`). |
| `sensor` | **Now Playing** | Human-readable summary of what is currently on screen (e.g., `Page 1: NFL Scores (128x128) · Digital Rain` or `Game: Cricket`), with attributes for `top_widget`, `bottom_widget`, `page_number`, `page_mode`, and `running_game_id`. |
| `sensor` | **Wi-Fi Signal** | Wi-Fi RSSI in `dBm` (plus SSID, IP, and MAC attributes). |
| `binary_sensor` | **Cloud Sync** | Connectivity status for Dartsnut remote sync. |
| `select` | **Widget Page** | Choose `Rotate All Pages` or pin any configured widget page (`Page 1`, `Page 2`, etc.). |
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
2. Click the **⋮** menu (top right) and select **Custom repositories**.
3. Paste `https://github.com/Duffanator/ha_dartsnut` and select category **Integration**.
4. Click **Download** on **Dartsnut PixelDart**.
5. **Restart Home Assistant**.

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

* **`dartsnut.start_game`**: Launch any game on the board by its `game_id` (e.g., `01dartgame`, `cricket`, `aroundtheworld`, `pico8`).
