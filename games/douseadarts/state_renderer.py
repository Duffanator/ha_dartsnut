import math
import os
import time
from typing import Dict, Any
import pygame

from game_state import GameStateEnum, TurnEffectType
from game_modes import StandardMode

# Basement Arcade 2.0 Palette
NEON_PINK = (255, 43, 214)      # #ff2bd6 (Player 1)
NEON_CYAN = (0, 240, 255)       # #00f0ff (Player 2)
NEON_YELLOW = (255, 230, 0)     # #ffe600 (Marquee Gold)
NEON_GREEN = (57, 255, 20)      # #39ff14 (Laser Green)
BG_TOP = (52, 0, 96)            # #340060
BG_MID = (18, 0, 42)            # #12002a
BG_BOT = (5, 0, 13)             # #05000d

# 11x8 classic Space Invader bitmap (frame A and frame B)
INVADER_A = [
    "..1.....1..",
    "...1...1...",
    "..1111111..",
    ".11.111.11.",
    "11111111111",
    "1.1111111.1",
    "1.1.....1.1",
    "...11.11...",
]
INVADER_B = [
    "..1.....1..",
    "1..1...1..1",
    "1.1111111.1",
    "111.111.111",
    "11111111111",
    ".111111111.",
    "..1.....1..",
    ".1.......1.",
]


def _get_font(size: int) -> pygame.font.Font:
    try:
        matched = pygame.font.match_font("Micro5")
    except Exception:
        matched = None
    if matched:
        return pygame.font.Font(matched, size)
    try:
        font_path = os.path.join(os.path.dirname(__file__), "Micro5.ttf")
        if os.path.exists(font_path):
            return pygame.font.Font(font_path, size)
    except Exception:
        pass
    return pygame.font.Font(None, size)


def _draw_invader(surface: pygame.Surface, cx: int, top_y: int, color: tuple, frame: int = 0) -> None:
    pattern = INVADER_A if (frame % 2 == 0) else INVADER_B
    start_x = cx - 5
    for row_idx, row in enumerate(pattern):
        for col_idx, ch in enumerate(row):
            if ch == "1":
                surface.set_at((start_x + col_idx, top_y + row_idx), color)


def _draw_chase_border(surface: pygame.Surface, rect: tuple, ticks: int, primary: tuple, secondary: tuple) -> None:
    """Draw an animated Basement Arcade chasing marquee bulb border."""
    x0, y0, w, h = rect
    pygame.draw.rect(surface, primary, (x0, y0, w, h), 1)
    pygame.draw.rect(surface, (45, 10, 75), (x0 + 2, y0 + 2, w - 4, h - 4), 1)

    step = 8
    phase = (ticks // 90) % step
    for idx, bx in enumerate(range(x0 + 2 + phase, x0 + w - 2, step)):
        c = NEON_YELLOW if idx % 2 == 0 else secondary
        pygame.draw.rect(surface, c, (bx, y0, 2, 2))
        pygame.draw.rect(surface, c, (x0 + w - 2 - (bx - x0), y0 + h - 2, 2, 2))
    for idx, by in enumerate(range(y0 + 2 + phase, y0 + h - 2, step)):
        c = secondary if idx % 2 == 0 else NEON_YELLOW
        pygame.draw.rect(surface, c, (x0, by, 2, 2))
        pygame.draw.rect(surface, c, (x0 + w - 2, y0 + h - 2 - (by - y0), 2, 2))


def _draw_text_with_shadow(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    center: tuple,
    color: tuple,
    shadow_color: tuple = (0, 0, 0),
    offset: tuple = (1, 1),
) -> None:
    s_surf = font.render(text, False, shadow_color)
    surface.blit(s_surf, s_surf.get_rect(center=(center[0] + offset[0], center[1] + offset[1])))
    t_surf = font.render(text, False, color)
    surface.blit(t_surf, t_surf.get_rect(center=center))


class StateRenderer:
    """Renders Basement Arcade themed game states and turn animations."""

    def __init__(self, screen: pygame.Surface, dartboard_surface: pygame.Surface):
        self.screen = screen
        self.dartboard_surface = dartboard_surface
        self.menu_surface = pygame.Surface((128, 128), pygame.SRCALPHA)
        self.small_font = _get_font(12)
        self.font = _get_font(14)
        self.mode_font = _get_font(16)
        self.title_font = _get_font(22)
        self.huge_font = _get_font(26)

    def render_state(self, game_info: Dict[str, Any]) -> None:
        current_state = game_info["current_state"]

        if current_state == GameStateEnum.STARTUP:
            self._render_startup(game_info)
        elif current_state == GameStateEnum.SETTINGS:
            self._render_settings(game_info)
        elif current_state == GameStateEnum.GAME_OVER:
            self._render_game_over(game_info)
        elif current_state == GameStateEnum.PLAYER_SWITCH:
            self._render_player_switch(game_info)
        elif current_state == GameStateEnum.BUST_CONTINUE:
            self._render_bust_continue(game_info)
        elif current_state == GameStateEnum.PAUSED:
            self._render_paused()
        elif current_state == GameStateEnum.PLAYING:
            self._render_playing_state(game_info)

        self._render_turn_effects(game_info)

    def _draw_arcade_backdrop(self, target: pygame.Surface, height: int = 128) -> None:
        """Draw the Basement Arcade radial/vertical purple gradient + CRT scanlines."""
        for y in range(height):
            t = y / max(1, height - 1)
            if t < 0.45:
                k = t / 0.45
                r = int(BG_TOP[0] * (1 - k) + BG_MID[0] * k)
                g = int(BG_TOP[1] * (1 - k) + BG_MID[1] * k)
                b = int(BG_TOP[2] * (1 - k) + BG_MID[2] * k)
            else:
                k = (t - 0.45) / 0.55
                r = int(BG_MID[0] * (1 - k) + BG_BOT[0] * k)
                g = int(BG_MID[1] * (1 - k) + BG_BOT[1] * k)
                b = int(BG_MID[2] * (1 - k) + BG_BOT[2] * k)
            pygame.draw.line(target, (r, g, b), (0, y), (127, y))

        for y in range(0, height, 3):
            pygame.draw.line(target, (3, 0, 8), (0, y), (127, y))

    def _render_startup(self, game_info: Dict[str, Any]) -> None:
        """Render the Dousea Darts Basement Arcade attract screen + secondary marquee."""
        target = self.menu_surface
        ticks = pygame.time.get_ticks()

        self._draw_arcade_backdrop(target, 128)

        # Twinkling arcade starfield
        for i in range(14):
            sx = (i * 29 + 11) % 116 + 6
            sy = (i * 19 + 7) % 112 + 8
            if ((ticks // 220) + i) % 4 == 0:
                target.set_at((sx, sy), NEON_CYAN if i % 2 == 0 else NEON_PINK)

        # Chasing bulb frame matching Basement Arcade 2.0
        _draw_chase_border(target, (0, 0, 128, 128), ticks, NEON_PINK, NEON_CYAN)

        # Animated pixel Space Invaders at top
        inv_frame = (ticks // 400) % 2
        _draw_invader(target, 64, 8, NEON_GREEN, inv_frame)
        _draw_invader(target, 24, 9, NEON_CYAN, inv_frame + 1)
        _draw_invader(target, 104, 9, NEON_CYAN, inv_frame + 1)

        # Neon flicker effect
        flicker_slot = (ticks // 120) % 50
        is_dim = flicker_slot in (10, 12, 27)
        title_pink = (150, 20, 125) if is_dim else NEON_PINK
        title_cyan = (0, 140, 160) if is_dim else NEON_CYAN

        _draw_text_with_shadow(
            target, self.huge_font, "DOUSEA", (64, 29), title_pink, (60, 0, 50), (2, 2)
        )
        _draw_text_with_shadow(
            target, self.title_font, "DARTS", (64, 47), title_cyan, (0, 55, 75), (2, 2)
        )

        # Neon divider with diamond center
        pygame.draw.line(target, NEON_PINK, (14, 59), (58, 59), 1)
        pygame.draw.line(target, NEON_CYAN, (70, 59), (114, 59), 1)
        pygame.draw.rect(target, NEON_YELLOW, (63, 58, 3, 3))

        # Active mode pill box
        game_mode = game_info.get("game_mode")
        game_state = game_info.get("game_state")
        mode_name = str(getattr(game_mode, "name", "501")).upper()
        out_opt = str(getattr(game_mode, "out_option", "single")).upper()
        ai_lvl = getattr(game_state, "ai_level", 0) if game_state else 0
        opp_tag = f"VS CPU AI (LVL {ai_lvl})" if ai_lvl > 0 else "P1 VS P2"

        pygame.draw.rect(target, (24, 4, 52), (14, 64, 100, 24))
        pygame.draw.rect(target, NEON_CYAN, (14, 64, 100, 24), 1)
        _draw_text_with_shadow(
            target,
            self.mode_font,
            f"{mode_name} · {out_opt} OUT",
            (64, 71),
            NEON_YELLOW,
            (0, 0, 0),
        )
        _draw_text_with_shadow(
            target,
            self.small_font,
            opp_tag,
            (64, 81),
            NEON_GREEN,
            (0, 0, 0),
        )

        # Blinking "INSERT COIN / A = START" prompt
        if (ticks // 450) % 2 == 0:
            _draw_text_with_shadow(
                target,
                self.font,
                "A = START GAME",
                (64, 99),
                NEON_YELLOW,
                (50, 35, 0),
            )
        else:
            _draw_text_with_shadow(
                target,
                self.font,
                "INSERT COIN",
                (64, 99),
                NEON_PINK,
                (50, 0, 40),
            )

        if isinstance(game_mode, StandardMode):
            _draw_text_with_shadow(
                target,
                self.small_font,
                "B = ARCADE OPTIONS",
                (64, 114),
                (200, 230, 255),
                (0, 0, 0),
            )

        self.screen.blit(target, (0, 0))

        # Secondary 64x32 display marquee during attract mode
        sec = pygame.Surface((64, 32))
        sec.fill((10, 0, 24))
        for y in range(0, 32, 2):
            pygame.draw.line(sec, (4, 0, 10), (0, y), (63, y))
        pygame.draw.rect(sec, NEON_PINK, (0, 0, 64, 32), 1)
        pygame.draw.rect(sec, NEON_CYAN, (2, 2, 60, 28), 1)
        _draw_text_with_shadow(sec, self.font, "BASEMENT", (32, 10), NEON_PINK, (0, 0, 0))
        _draw_text_with_shadow(sec, self.font, "ARCADE", (32, 22), NEON_CYAN, (0, 0, 0))
        self.screen.blit(sec, (0, 128))

    def _render_settings(self, game_info: Dict[str, Any]) -> None:
        """Render the Basement Arcade themed settings menu."""
        target = self.menu_surface
        ticks = pygame.time.get_ticks()

        self._draw_arcade_backdrop(target, 128)
        _draw_chase_border(target, (0, 0, 128, 128), ticks, NEON_CYAN, NEON_PINK)

        _draw_text_with_shadow(
            target, self.title_font, "ARCADE SETUP", (64, 15), NEON_CYAN, (0, 60, 80), (1, 1)
        )
        pygame.draw.line(target, NEON_PINK, (14, 27), (114, 27), 1)

        game_mode = game_info.get("game_mode")
        if isinstance(game_mode, StandardMode):
            self._render_501_settings(target, game_mode, game_info)

        self.screen.blit(target, (0, 0))

        # Secondary 64x32 helper instructions
        sec = pygame.Surface((64, 32))
        sec.fill((10, 0, 24))
        pygame.draw.rect(sec, NEON_CYAN, (0, 0, 64, 32), 1)
        _draw_text_with_shadow(sec, self.small_font, "UP/DN: SELECT", (32, 8), NEON_YELLOW, (0, 0, 0))
        _draw_text_with_shadow(sec, self.small_font, "L/R: CHANGE", (32, 17), NEON_CYAN, (0, 0, 0))
        _draw_text_with_shadow(sec, self.small_font, "A: SAVE/BACK", (32, 26), NEON_GREEN, (0, 0, 0))
        self.screen.blit(sec, (0, 128))

    def _render_501_settings(self, target, game_mode, game_info):
        game_state = game_info.get("game_state")
        selected_option = getattr(game_state, "settings_selected_option", 0) if game_state else 0

        bgm_status = "ON" if (game_state and getattr(game_state, "bgm_enabled", True)) else "OFF"
        sfx_status = "ON" if (game_state and getattr(game_state, "sfx_enabled", True)) else "OFF"
        ai_level = getattr(game_state, "ai_level", 0) if game_state else 0
        ai_status = "OFF" if ai_level == 0 else f"LVL {ai_level}"

        options = [
            ("GAME", game_mode.available_variants, game_mode.game_variant),
            ("IN", game_mode.available_in_options, game_mode.in_option.upper()),
            ("OUT", game_mode.available_out_options, game_mode.out_option.upper()),
            ("BULL", game_mode.available_bull_options, game_mode.bull_option),
            ("BGM", ["ON", "OFF"], bgm_status),
            ("SFX", ["ON", "OFF"], sfx_status),
            ("AI BOT", ["OFF"] + [str(i) for i in range(1, 19)], ai_status),
        ]

        for i, (option_name, _values, current_value) in enumerate(options):
            y_pos = 32 + i * 13
            if i == selected_option:
                pygame.draw.rect(target, (48, 8, 86), (8, y_pos, 112, 12), 0)
                pygame.draw.rect(target, NEON_PINK, (8, y_pos, 112, 12), 1)
                name_color = NEON_YELLOW
                val_color = NEON_CYAN
            else:
                name_color = (190, 175, 215)
                val_color = (235, 235, 245)

            option_surface = self.font.render(f"{option_name}:", False, name_color)
            option_rect = option_surface.get_rect(left=13, centery=y_pos + 6)
            target.blit(option_surface, option_rect)

            value_surface = self.font.render(str(current_value), False, val_color)
            value_rect = value_surface.get_rect(right=110, centery=y_pos + 6)
            target.blit(value_surface, value_rect)

            if i == selected_option:
                l_surf = self.font.render("<", False, NEON_YELLOW)
                target.blit(l_surf, l_surf.get_rect(right=value_rect.left - 3, centery=y_pos + 6))
                r_surf = self.font.render(">", False, NEON_YELLOW)
                target.blit(r_surf, r_surf.get_rect(left=value_rect.right + 3, centery=y_pos + 6))

    def _render_playing_state(self, game_info: Dict[str, Any]) -> None:
        """Render end-of-turn prompt when current player has thrown all 3 darts and hit animations settled."""
        current_player = game_info["current_player"]
        current_player_data = game_info["players"][current_player]

        if len(current_player_data.shots) >= 3:
            # Wait until any active celebration effect or dart-hit floating popup finishes
            turn_effects = game_info.get("turn_effects")
            if turn_effects and turn_effects.get_active_effects():
                return
            if game_info.get("animations_busy"):
                return

            ticks = pygame.time.get_ticks()
            next_player = 1 - current_player
            next_color = NEON_PINK if next_player == 0 else NEON_CYAN
            turn_total = sum(current_player_data.shots)

            overlay = pygame.Surface((128, 128), pygame.SRCALPHA)
            overlay.fill((6, 0, 16, 135))
            self.screen.blit(overlay, (0, 0))

            # Retro arcade card box in center
            box = (12, 42, 104, 44)
            pygame.draw.rect(self.screen, (16, 2, 36), box)
            pygame.draw.rect(self.screen, next_color, box, 2)
            pygame.draw.rect(self.screen, NEON_YELLOW, (14, 44, 100, 40), 1)

            _draw_text_with_shadow(
                self.screen,
                self.mode_font,
                f"TURN TOTAL: +{turn_total}",
                (64, 54),
                NEON_YELLOW,
                (0, 0, 0),
            )

            if (ticks // 350) % 2 == 0:
                prompt = f"PRESS A -> P{next_player + 1}"
                p_col = next_color
            else:
                prompt = "REMOVE DARTS"
                p_col = (255, 255, 255)
            _draw_text_with_shadow(
                self.screen,
                self.font,
                prompt,
                (64, 72),
                p_col,
                (0, 0, 0),
            )

    def _render_bust_continue(self, game_info: Dict[str, Any]) -> None:
        ticks = pygame.time.get_ticks()
        current_player = game_info["current_player"]
        next_player = 1 - current_player
        next_color = NEON_PINK if next_player == 0 else NEON_CYAN

        overlay = pygame.Surface((128, 128), pygame.SRCALPHA)
        overlay.fill((20, 0, 10, 140))
        self.screen.blit(overlay, (0, 0))

        box = (12, 42, 104, 44)
        pygame.draw.rect(self.screen, (28, 0, 18), box)
        pygame.draw.rect(self.screen, (255, 40, 80), box, 2)

        _draw_text_with_shadow(
            self.screen, self.mode_font, "BUST! NO SCORE", (64, 54), (255, 60, 90), (0, 0, 0)
        )
        if (ticks // 350) % 2 == 0:
            _draw_text_with_shadow(
                self.screen, self.font, f"PRESS A -> P{next_player + 1}", (64, 72), next_color, (0, 0, 0)
            )
        else:
            _draw_text_with_shadow(
                self.screen, self.font, "REMOVE DARTS", (64, 72), NEON_YELLOW, (0, 0, 0)
            )

    def _render_player_switch(self, game_info: Dict[str, Any]) -> None:
        current_player = game_info["current_player"]
        p_col = NEON_PINK if current_player == 0 else NEON_CYAN
        _draw_text_with_shadow(
            self.screen, self.title_font, f"PLAYER {current_player + 1}", (64, 64), p_col, (0, 0, 0)
        )

    def _render_paused(self) -> None:
        overlay = pygame.Surface((128, 128), pygame.SRCALPHA)
        overlay.fill((8, 0, 20, 160))
        self.screen.blit(overlay, (0, 0))
        _draw_text_with_shadow(
            self.screen, self.title_font, "PAUSED", (64, 64), NEON_YELLOW, (0, 0, 0)
        )

    def _render_game_over(self, game_info: Dict[str, Any]) -> None:
        """Render a full-screen Basement Arcade victory celebration."""
        winner = game_info["winner"]
        if winner is None:
            return

        base_color = NEON_PINK if winner == 0 else NEON_CYAN
        accent_color = NEON_YELLOW
        cx, cy = 64, 64
        ticks = pygame.time.get_ticks()
        t = ticks / 1000.0

        effect = pygame.Surface((128, 160), pygame.SRCALPHA)
        effect.fill((10, 0, 24, 215))

        ray_count = 14
        angle0 = (ticks * 0.1) * math.pi / 180.0
        for i in range(ray_count):
            a = angle0 + (2 * math.pi * i / ray_count)
            col = (*base_color, 85) if i % 2 == 0 else (*NEON_YELLOW, 55)
            r_outer = 110
            r_inner = 8
            width_angle = math.radians(6)
            pts = [
                (cx + int(r_outer * math.cos(a)), cy + int(r_outer * math.sin(a))),
                (cx + int(r_inner * math.cos(a + width_angle)), cy + int(r_inner * math.sin(a + width_angle))),
                (cx + int(r_inner * math.cos(a - width_angle)), cy + int(r_inner * math.sin(a - width_angle))),
            ]
            pygame.draw.polygon(effect, col, pts)

        for j in range(3):
            phase = (t * 0.85 + j * 0.33) % 1.0
            radius = int(10 + phase * 90)
            alpha = max(0, int(190 * (1 - phase)))
            pygame.draw.circle(effect, (*base_color, alpha), (cx, cy), radius, 2)

        self.screen.blit(effect, (0, 0))
        _draw_chase_border(self.screen, (0, 0, 128, 128), ticks, base_color, accent_color)

        pygame.draw.rect(self.screen, (18, 2, 40), (10, 32, 108, 64))
        pygame.draw.rect(self.screen, base_color, (10, 32, 108, 64), 2)
        _draw_invader(self.screen, 64, 37, NEON_GREEN, (ticks // 300) % 2)

        _draw_text_with_shadow(
            self.screen, self.title_font, "VICTORY!", (64, 56), NEON_YELLOW, (0, 0, 0), (2, 2)
        )
        _draw_text_with_shadow(
            self.screen, self.huge_font, f"PLAYER {winner + 1} WINS", (64, 78), base_color, (0, 0, 0), (2, 2)
        )

        sec = pygame.Surface((64, 32))
        sec.fill((12, 0, 28))
        pygame.draw.rect(sec, base_color, (0, 0, 64, 32), 1)
        _draw_text_with_shadow(sec, self.font, f"P{winner + 1} CHAMP!", (32, 10), NEON_YELLOW, (0, 0, 0))
        if (ticks // 400) % 2 == 0:
            _draw_text_with_shadow(sec, self.small_font, "B = REMATCH", (32, 23), NEON_GREEN, (0, 0, 0))
        self.screen.blit(sec, (0, 128))

    def _render_turn_effects(self, game_info: Dict[str, Any]) -> None:
        turn_effects = game_info.get("turn_effects")
        if not turn_effects:
            return

        current_time = time.time()
        turn_effects.update_effects(current_time)
        active_effects = turn_effects.get_active_effects()
        if not active_effects:
            return

        for effect in active_effects:
            self._render_single_turn_effect(effect, current_time, game_info)

    def _render_single_turn_effect(self, effect, current_time: float, game_info: Dict[str, Any]) -> None:
        progress = effect.get_progress(current_time)
        effect_surface = pygame.Surface((128, 128), pygame.SRCALPHA)

        if effect.effect_type == TurnEffectType.PLAYER_READY:
            self._render_player_ready_effect(effect_surface, progress, effect.color, effect.player_id, game_info)
        elif effect.effect_type == TurnEffectType.HAT_TRICK:
            self._render_arcade_achievement(effect_surface, progress, NEON_YELLOW, "HAT TRICK!", "3X BULLSEYE")
        elif effect.effect_type == TurnEffectType.TON:
            self._render_arcade_achievement(effect_surface, progress, NEON_PINK, "MAXIMUM 180!", "TRIPLE TON")
        elif effect.effect_type == TurnEffectType.HIGH_TON:
            self._render_arcade_achievement(effect_surface, progress, NEON_GREEN, "HIGH TON!", effect.message)
        elif effect.effect_type == TurnEffectType.LOW_TON:
            self._render_arcade_achievement(effect_surface, progress, NEON_CYAN, "LOW TON!", effect.message)
        elif effect.effect_type == TurnEffectType.BUST:
            self._render_bust_effect(effect_surface, progress)
        elif effect.effect_type == TurnEffectType.CLOSE_CALL:
            self._render_close_call_effect(effect_surface, progress, effect.message)

        self.screen.blit(effect_surface, (0, 0))

    def _render_player_ready_effect(
        self,
        surface: pygame.Surface,
        progress: float,
        color: tuple,
        player_id: int,
        game_info: Dict[str, Any],
    ) -> None:
        """Retro Arcade CRT laser curtain wipe + 'READY PLAYER X' turn-switch animation."""
        ticks = pygame.time.get_ticks()
        players = game_info.get("players") or []
        p_score = players[player_id].score if player_id < len(players) else 501
        game_state = game_info.get("game_state")
        is_ai = bool(game_state and game_state.is_ai_enabled() and player_id == game_state.ai_player_index)
        p_title = f"CPU AI (L{game_state.ai_level})" if is_ai else f"PLAYER {player_id + 1}"

        # Phase 1 (0..0.75): Full arcade turn banner with animated CRT laser borders
        # Phase 2 (0.75..1.0): CRT laser curtains retract toward center to reveal the dartboard
        if progress < 0.75:
            open_ratio = 1.0
        else:
            open_ratio = max(0.0, 1.0 - (progress - 0.75) / 0.25)

        band_half = int(42 * open_ratio)
        if band_half > 2:
            top_y = 64 - band_half
            height = band_half * 2
            pygame.draw.rect(surface, (12, 0, 28, 238), (0, top_y, 128, height))
            for sy in range(top_y, top_y + height, 3):
                pygame.draw.line(surface, (0, 0, 0, 125), (0, sy), (127, sy))

            # Top and bottom glowing laser scanbeams + chasing dots
            pygame.draw.line(surface, (*color, 255), (0, top_y), (127, top_y), 2)
            pygame.draw.line(surface, (*NEON_YELLOW, 255), (0, top_y + height - 1), (127, top_y + height - 1), 2)
            for bx in range(4 + ((ticks // 60) % 8), 124, 8):
                pygame.draw.rect(surface, (*NEON_YELLOW, 255), (bx, top_y, 3, 2))
                pygame.draw.rect(surface, (*color, 255), (124 - bx, top_y + height - 2, 3, 2))

            if open_ratio > 0.65:
                _draw_invader(surface, 18, top_y + 8, color, (ticks // 150) % 2)
                _draw_invader(surface, 110, top_y + 8, color, (ticks // 150) % 2)

                _draw_text_with_shadow(
                    surface,
                    self.small_font,
                    "GET READY",
                    (64, top_y + 12),
                    NEON_YELLOW,
                    (0, 0, 0),
                )
                _draw_text_with_shadow(
                    surface,
                    self.huge_font,
                    p_title,
                    (64, top_y + 34),
                    color,
                    (0, 0, 0),
                    (2, 2),
                )

                sub_text = f"CHECKOUT: {p_score}!" if p_score <= 170 else f"SCORE: {p_score}"
                sub_col = NEON_GREEN if p_score <= 170 else (255, 255, 255)
                _draw_text_with_shadow(
                    surface,
                    self.mode_font,
                    sub_text,
                    (64, top_y + 58),
                    sub_col,
                    (0, 0, 0),
                )

        # Also animate the 64x32 bottom scoreboard during the turn switch
        secondary_surface = pygame.Surface((64, 32), pygame.SRCALPHA)
        secondary_surface.fill((12, 0, 28, 245))
        pygame.draw.rect(secondary_surface, color, (0, 0, 64, 32), 2)
        _draw_text_with_shadow(
            secondary_surface, self.mode_font, p_title, (32, 10), color, (0, 0, 0)
        )
        _draw_text_with_shadow(
            secondary_surface, self.font, "THROW 3!", (32, 23), NEON_YELLOW, (0, 0, 0)
        )
        self.screen.blit(secondary_surface, (0, 128))

    def _render_arcade_achievement(
        self,
        surface: pygame.Surface,
        progress: float,
        color: tuple,
        headline: str,
        subline: str,
    ) -> None:
        """Render retro arcade celebration for TON / HIGH TON / LOW TON / HAT TRICK."""
        pulse = 0.5 + 0.5 * math.sin(progress * math.pi * 6)
        bg_alpha = int(110 * pulse * (1 - progress * 0.4))
        pygame.draw.rect(surface, (*color, bg_alpha), (0, 0, 128, 128))

        for i in range(4):
            ring_p = (progress + i * 0.25) % 1.0
            radius = int(12 + ring_p * 70)
            alpha = int(180 * (1 - ring_p))
            pygame.draw.circle(surface, (*color, alpha), (64, 64), radius, 2)

        if progress < 0.85:
            bounce = int(math.sin(progress * math.pi * 6) * 3)
            pygame.draw.rect(surface, (12, 0, 28, 225), (8, 40 + bounce, 112, 46))
            pygame.draw.rect(surface, color, (8, 40 + bounce, 112, 46), 2)
            _draw_text_with_shadow(
                surface, self.huge_font, headline, (64, 55 + bounce), NEON_YELLOW, (0, 0, 0), (2, 2)
            )
            _draw_text_with_shadow(
                surface, self.mode_font, subline.upper(), (64, 74 + bounce), color, (0, 0, 0)
            )

    def _render_bust_effect(self, surface: pygame.Surface, progress: float) -> None:
        color = (255, 40, 80)
        pulse = 0.5 + 0.5 * math.sin(progress * math.pi * 8)
        bg_alpha = int(130 * pulse * (1 - progress * 0.3))
        pygame.draw.rect(surface, (*color, bg_alpha), (0, 0, 128, 128))

        shake_x = int(math.sin(progress * math.pi * 20) * 3)
        if progress < 0.88:
            pygame.draw.rect(surface, (24, 0, 12, 230), (14 + shake_x, 44, 100, 40))
            pygame.draw.rect(surface, color, (14 + shake_x, 44, 100, 40), 2)
            _draw_text_with_shadow(
                surface, self.huge_font, "BUST!", (64 + shake_x, 64), NEON_YELLOW, (0, 0, 0), (2, 2)
            )

    def _render_close_call_effect(self, surface: pygame.Surface, progress: float, message: str) -> None:
        if progress < 0.8:
            pygame.draw.rect(surface, (14, 0, 30, 210), (14, 48, 100, 32))
            pygame.draw.rect(surface, NEON_GREEN, (14, 48, 100, 32), 1)
            _draw_text_with_shadow(
                surface, self.mode_font, message.upper(), (64, 64), NEON_GREEN, (0, 0, 0)
            )
