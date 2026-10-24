"""Constants for the Dartsnut PixelDart integration."""

from homeassistant.const import Platform

DOMAIN = "dartsnut"

CONF_HOST = "host"
CONF_WS_PORT = "ws_port"
CONF_MCP_PORT = "mcp_port"

DEFAULT_NAME = "Dartsnut"
DEFAULT_HOST = "dartsnut"
DEFAULT_WS_PORT = 9251
DEFAULT_MCP_PORT = 9252

PLATFORMS: list[Platform] = [
    Platform.LIGHT,
    Platform.CAMERA,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.BUTTON,
    Platform.UPDATE,
]

OPTION_ROTATE_ALL = "Rotate All Pages"
OPTION_GAME_NONE = "None"

SCREEN_OFF_PAGE_UUID = "00000000-0000-4000-8000-000000000000"
SIDELOAD_SESSION_ID = "ha_screen_off"
SIDELOAD_APP_ID = "blackout"

STATE_LABELS: dict[str, str] = {
    "widget": "Widget",
    "in_game": "In Game",
    "menu": "Menu",
    "game_select": "Game Select",
    "settings": "Settings",
}

WIDGET_FRIENDLY_NAMES: dict[str, str] = {
    "nflscores_128_128": "NFL Scores (128x128)",
    "nflscores": "NFL Scores",
    "digitalrain": "Digital Rain",
    "pet": "Pet",
    "daystoxmas": "Days to Xmas",
    "tetris": "Tetris",
    "dvdlogo": "DVD Logo",
    "chessstream": "Chess Live Stream",
    "sunrisesunset": "Sunrise & Sunset",
    "fishtank": "Fish Tank",
    "factory_tool": "Factory Tool",
    "01dartgame": "01 Dart Game",
    "12draw": "12 Draw",
    "aroundtheworld": "Around the World",
    "beerpong": "Beer Pong",
    "colorbuster": "Color Buster",
    "cricket": "Cricket",
    "cubecrush": "Cube Crush",
    "flipdarts": "Flip Darts",
    "minigolf": "Mini Golf",
    "pico8": "PICO-8",
    "savingthehostage": "Saving the Hostage",
    "splashgame": "Splash Game",
    "tictactoe": "Tic Tac Toe",
    "toydarts": "Toy Darts",
}
