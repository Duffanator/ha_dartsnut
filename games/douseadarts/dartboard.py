import math
import os
import random
import pygame

# Basement Arcade 2.0 Palette
NEON_PINK = (255, 43, 214)      # #ff2bd6 (Player 1 / Triple-Double Ring A)
NEON_CYAN = (0, 240, 255)       # #00f0ff (Player 2 / Triple-Double Ring B)
NEON_YELLOW = (255, 230, 0)     # #ffe600 (Marquee Gold / Inner Bull)
NEON_GREEN = (57, 255, 20)      # #39ff14 (Laser Green / Outer Bull)
DARK_VIOLET = (46, 14, 84)      # Light single wedge (Arcade cabinet violet)
DEEP_OBSIDIAN = (12, 3, 26)     # Dark single wedge (Deep CRT purple-black)
BG_CABINET = (6, 0, 14)         # Outer corner background

TEXT_CORNER = [
    (80, -1),
    (97, 107),
    (62, 117),
    (111, 22),
    (43, -1),
    (121, 56),
    (26, 107),
    (4, 76),
    (12, 22),
    (118, 76),
    (123, 76),
    (0, 57),
    (4, 57),
    (21, 7),
    (26, 7),
    (118, 38),
    (123, 38),
    (0, 38),
    (5, 38),
    (111, 93),
    (116, 93),
    (8, 93),
    (13, 93),
    (77, 115),
    (82, 115),
    (96, 7),
    (101, 7),
    (41, 115),
    (46, 115),
    (59, -3),
    (65, -3),
]


class Dartboard:
    """Handles the neon Basement Arcade dartboard rendering, sectors, and hit animations."""

    def __init__(self, width=128, height=128):
        self.width = width
        self.height = height
        self.center = (width // 2, height // 2)
        self.surface = pygame.Surface((width, height), pygame.SRCALPHA)
        self.animate_surface = pygame.Surface((width, height), pygame.SRCALPHA)
        self.sectors = []
        self.scores = [[0 for _ in range(width)] for _ in range(height)]
        self.highlighted_sector = -1

        # Retro arcade hit effect properties
        self.retro_effect_active = False
        self.retro_effect_timer = 0
        self.retro_effect_duration = 52  # ~0.87s at 60fps
        self.retro_flash_intensity = 0
        self.retro_ripple_center = None
        self.retro_ripple_radius = 0
        self.retro_hit_color = NEON_PINK
        self.retro_sparks = []

        # Shake effect properties (for out-of-board / miss hits)
        self.shake_active = False
        self.shake_timer = 0
        self.shake_duration = 20
        self.shake_magnitude = 4
        self._shake_offset = (0, 0)

        # One-shot rotary highlight effect (for valid hits)
        self.rotary_once_active = False
        self.rotary_once_color = NEON_PINK
        self.rotary_once_start_ms = 0
        self.rotary_once_duration_ms = 750
        self.rotary_arc_span_rad = math.radians(30)

        # Dartboard geometry (calibrated to hardware sensor matrix)
        self.radius_double_bull = 3
        self.radius_single_bull = 7
        self.radius_inner_triple = 25
        self.radius_outer_triple = 31
        self.radius_inner_double = 50
        self.radius_outer_double = 56

        self.SCORES = [
            6, 10, 15, 2, 17, 3, 19, 7, 16, 8,
            11, 14, 9, 12, 5, 20, 1, 18, 4, 13,
        ]
        # [0]=Ring A (Neon Pink), [1]=Ring B (Neon Cyan), [2]=Light Single (Violet), [3]=Dark Single (Obsidian)
        self.SECTOR_COLORS = [NEON_PINK, NEON_CYAN, DARK_VIOLET, DEEP_OBSIDIAN]
        self.BULL_DOUBLE_COLOR = NEON_YELLOW
        self.BULL_SINGLE_COLOR = NEON_GREEN

        self._init_sectors()
        self._redraw_with_highlight()

    def _load_font(self, size=15):
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

    def _init_sectors(self):
        """Initialize dartboard sectors and scoring map."""
        self.text_positions = TEXT_CORNER

        # Double bull (50 points)
        self.sectors.append([])
        for x in range(
            self.center[0] - self.radius_double_bull,
            self.center[0] + self.radius_double_bull + 1,
        ):
            for y in range(
                self.center[1] - self.radius_double_bull,
                self.center[1] + self.radius_double_bull + 1,
            ):
                if (
                    math.sqrt((x - self.center[0]) ** 2 + (y - self.center[1]) ** 2)
                    < self.radius_double_bull
                ):
                    self.sectors[0].append((x, y))
                    self.surface.set_at((x, y), self.BULL_DOUBLE_COLOR)
                    self.scores[x][y] = 50

        # Single bull (25 points)
        self.sectors.append([])
        for x in range(
            self.center[0] - self.radius_single_bull,
            self.center[0] + self.radius_single_bull + 1,
        ):
            for y in range(
                self.center[1] - self.radius_single_bull,
                self.center[1] + self.radius_single_bull + 1,
            ):
                distance = math.sqrt(
                    (x - self.center[0]) ** 2 + (y - self.center[1]) ** 2
                )
                if self.radius_double_bull <= distance < self.radius_single_bull:
                    self.sectors[1].append((x, y))
                    self.surface.set_at((x, y), self.BULL_SINGLE_COLOR)
                    self.scores[x][y] = 25

        # Main dartboard sectors (20 sectors, 18° each)
        for i in range(20):
            start_angle = math.radians(i * 18 - 9)
            end_angle = math.radians((i + 1) * 18 - 9)
            sector_pixels = []

            for x in range(
                self.center[0] - self.radius_outer_double,
                self.center[0] + self.radius_outer_double + 1,
            ):
                for y in range(
                    self.center[1] - self.radius_outer_double,
                    self.center[1] + self.radius_outer_double + 1,
                ):
                    distance = math.sqrt(
                        (x - self.center[0]) ** 2 + (y - self.center[1]) ** 2
                    )
                    if self.radius_single_bull <= distance < self.radius_outer_double:
                        angle = math.atan2(y - self.center[1], x - self.center[0])
                        if i == 0:
                            if start_angle <= angle < end_angle:
                                sector_pixels.append((x, y))
                        else:
                            if angle < 0:
                                angle += 2 * math.pi
                            if start_angle <= angle < end_angle:
                                sector_pixels.append((x, y))

            # Divide sector into 4 parts (inner single, triple, outer single, double)
            small_sectors = [[], [], [], []]
            for x, y in sector_pixels:
                distance = math.sqrt(
                    (x - self.center[0]) ** 2 + (y - self.center[1]) ** 2
                )

                if self.radius_single_bull <= distance < self.radius_inner_triple:
                    small_sectors[0].append((x, y))
                    self.scores[x][y] = self.SCORES[i]
                elif self.radius_inner_triple <= distance < self.radius_outer_triple:
                    small_sectors[1].append((x, y))
                    self.scores[x][y] = self.SCORES[i] * 3
                elif self.radius_outer_triple <= distance < self.radius_inner_double:
                    small_sectors[2].append((x, y))
                    self.scores[x][y] = self.SCORES[i]
                elif self.radius_inner_double <= distance < self.radius_outer_double:
                    small_sectors[3].append((x, y))
                    self.scores[x][y] = self.SCORES[i] * 2

            for small_sector in small_sectors:
                self.sectors.append(small_sector)

    def highlight_sector(self, sector_index):
        """Highlight a specific sector with a bright arcade overlay."""
        self.highlighted_sector = sector_index
        self._redraw_with_highlight()

    def clear_highlight(self):
        """Clear the current highlight."""
        self.highlighted_sector = -1
        self._redraw_with_highlight()

    def _redraw_with_highlight(self):
        """Redraw the neon arcade dartboard with current highlight."""
        self.surface.fill((*BG_CABINET, 255))

        # Subtle outer neon halo ring around the board perimeter
        pygame.draw.circle(self.surface, (55, 10, 85), self.center, self.radius_outer_double + 1, 1)

        # Draw sector numbers around the board
        self._draw_sector_numbers()

        # Redraw all sectors
        for i, sector in enumerate(self.sectors):
            highlight_color = None
            if i == self.highlighted_sector:
                highlight_color = (*NEON_YELLOW, 185)

            base_color = self._get_original_sector_color(i)
            for x, y in sector:
                if highlight_color:
                    blended_color = self._blend_colors(base_color, highlight_color)
                    self.surface.set_at((x, y), blended_color)
                else:
                    self.surface.set_at((x, y), base_color)

    def _get_original_sector_color(self, sector_index):
        """Get the neon arcade color for a sector."""
        if sector_index == 0:
            return self.BULL_DOUBLE_COLOR
        elif sector_index == 1:
            return self.BULL_SINGLE_COLOR
        else:
            main_sector = (sector_index - 2) // 4
            part = (sector_index - 2) % 4

            if part == 1 or part == 3:  # Triple or double ring
                return self.SECTOR_COLORS[0] if main_sector % 2 == 1 else self.SECTOR_COLORS[1]
            else:  # Single areas
                return self.SECTOR_COLORS[2] if main_sector % 2 == 1 else self.SECTOR_COLORS[3]

    def _blend_colors(self, color1, color2):
        if len(color1) == 3:
            color1 = (*color1, 255)
        if len(color2) == 3:
            color2 = (*color2, 255)
        alpha = color2[3] / 255.0
        return tuple(
            int(color1[i] * (1 - alpha) + color2[i] * alpha) for i in range(3)
        )

    def _draw_sector_numbers(self):
        """Draw sector numbers in crisp neon colors."""
        font = self._load_font(15)
        self.text_positions = TEXT_CORNER
        for i in range(20):
            num = i + 1
            if num == 20:
                col = NEON_YELLOW
            elif num % 2 == 0:
                col = NEON_CYAN
            else:
                col = (255, 180, 242)

            if i < 9:
                text_surface = font.render(str(num), False, col)
                self.surface.blit(text_surface, TEXT_CORNER[i])
            else:
                text_surface_tens = font.render(str(num // 10), False, col)
                self.surface.blit(text_surface_tens, TEXT_CORNER[i * 2 - 9])
                text_surface_units = font.render(str(num % 10), False, col)
                self.surface.blit(text_surface_units, TEXT_CORNER[i * 2 - 8])

    def get_score(self, x, y, game_mode=None):
        """Get the score for a given position."""
        if 0 <= x < self.width and 0 <= y < self.height:
            base_score = self.scores[x][y]
            if base_score == 25 and game_mode and hasattr(game_mode, "bull_option"):
                if game_mode.bull_option == "50/50":
                    return 50
            return base_score
        return 0

    def get_hit_label(self, x, y, game_mode=None) -> str:
        """Return an arcade callout label for a hit at (x, y), e.g. 'T-60!', 'D-40!', 'BULL!', '+20'."""
        score = self.get_score(x, y, game_mode)
        if score <= 0:
            return "MISS"
        sec = self.get_sector_index(x, y)
        if sec == 0:
            return "DBULL 50!"
        if sec == 1:
            return f"BULL {score}!"
        if sec >= 2:
            part = (sec - 2) % 4
            if part == 1:
                return f"T-{score}!"
            if part == 3:
                return f"D-{score}!"
        return f"+{score}"

    def get_sector_index(self, x, y):
        """Get the sector index for a given position."""
        for i, sector in enumerate(self.sectors):
            if (x, y) in sector:
                return i
        return -1

    def clear_animation(self):
        self.animate_surface.fill((0, 0, 0, 0))

    def trigger_retro_effect(self, x=None, y=None, player_color=None):
        """Trigger the retro arcade impact effect when a dart lands."""
        self.retro_effect_active = True
        self.retro_effect_timer = self.retro_effect_duration
        self.retro_flash_intensity = 255
        if player_color is not None:
            self.retro_hit_color = player_color

        if (
            isinstance(x, int)
            and isinstance(y, int)
            and 0 <= x < self.width
            and 0 <= y < self.height
        ):
            self.retro_ripple_center = (x, y)
        else:
            self.retro_ripple_center = (self.width // 2, self.height // 2)
        self.retro_ripple_radius = 1

        # Spawn 8-bit square arcade sparks from the impact point
        cx, cy = self.retro_ripple_center
        spark_palette = [NEON_PINK, NEON_CYAN, NEON_YELLOW, NEON_GREEN, (255, 255, 255)]
        self.retro_sparks = []
        for _ in range(22):
            ang = random.uniform(0, 2 * math.pi)
            spd = random.uniform(0.8, 2.6)
            self.retro_sparks.append(
                {
                    "x": float(cx),
                    "y": float(cy),
                    "vx": math.cos(ang) * spd,
                    "vy": math.sin(ang) * spd - 0.3,
                    "color": random.choice(spark_palette),
                    "life": random.randint(18, 42),
                    "age": 0,
                    "size": random.choice([1, 2, 2]),
                }
            )

    def update_retro_effect(self):
        """Update the retro arcade impact animation."""
        if not self.retro_effect_active:
            return

        if self.retro_flash_intensity > 0:
            self.retro_flash_intensity = max(0, self.retro_flash_intensity - 12)

        if self.retro_ripple_center:
            self.retro_ripple_radius += 2

        alive_sparks = []
        for s in self.retro_sparks:
            s["age"] += 1
            if s["age"] < s["life"]:
                s["x"] += s["vx"]
                s["y"] += s["vy"]
                s["vy"] += 0.05  # arcade gravity
                alive_sparks.append(s)
        self.retro_sparks = alive_sparks

        self.retro_effect_timer -= 1
        if self.retro_effect_timer <= 0:
            self.retro_effect_active = False
            self.retro_ripple_center = None
            self.retro_ripple_radius = 0
            self.retro_sparks = []

    def update_shake(self):
        if not self.shake_active:
            self._shake_offset = (0, 0)
            return

        remaining_ratio = self.shake_timer / max(1, self.shake_duration)
        amplitude = self.shake_magnitude * remaining_ratio
        phase = self.shake_timer
        offset_x = int(round(amplitude * math.sin(phase * 0.9)))
        offset_y = int(round(amplitude * math.cos(phase * 1.3)))
        self._shake_offset = (offset_x, offset_y)

        self.shake_timer -= 1
        if self.shake_timer <= 0:
            self.shake_active = False
            self._shake_offset = (0, 0)

    def trigger_shake(self, magnitude=None, duration=None):
        if magnitude is not None:
            self.shake_magnitude = magnitude
        if duration is not None:
            self.shake_duration = duration
        self.shake_active = True
        self.shake_timer = self.shake_duration
        self._shake_offset = (0, 0)

    def get_shake_offset(self):
        return self._shake_offset

    def draw_retro_effect(self, target_surface, offset=(0, 0)):
        """Draw the retro arcade impact overlay (crosshair, dual shockwaves, 8-bit sparks, sector pulse)."""
        if not self.retro_effect_active:
            return

        effect_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        progress = 1.0 - (self.retro_effect_timer / max(1, self.retro_effect_duration))

        # 1) Neon flash on impact
        if self.retro_flash_intensity > 0:
            flash_alpha = int(self.retro_flash_intensity * 0.25)
            flash_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            flash_surface.fill((*self.retro_hit_color, flash_alpha))
            effect_surface.blit(flash_surface, (0, 0))

        # 2) Pulsing neon glow on the hit sector
        if 0 <= self.highlighted_sector < len(self.sectors):
            pulse = 0.5 + 0.5 * math.sin(self.retro_effect_timer * 0.6)
            sec_alpha = int(190 * (1.0 - progress * 0.7) * pulse)
            sec_col = NEON_YELLOW if (self.retro_effect_timer // 3) % 2 == 0 else self.retro_hit_color
            for sx, sy in self.sectors[self.highlighted_sector]:
                effect_surface.set_at((sx, sy), (*sec_col, sec_alpha))

        # 3) CRT scanlines
        scanline_alpha = int(55 * (1.0 - progress))
        for y in range(0, self.height, 3):
            pygame.draw.line(effect_surface, (0, 0, 0, scanline_alpha), (0, y), (self.width, y))

        # 4) Dual concentric neon shockwave rings + 8-bit target reticle at impact point
        if self.retro_ripple_center:
            cx, cy = self.retro_ripple_center
            r1 = self.retro_ripple_radius
            if r1 < 95:
                a1 = int(200 * (1.0 - r1 / 95.0))
                pygame.draw.circle(effect_surface, (*NEON_YELLOW, a1), (cx, cy), r1, 2)
            r2 = max(1, r1 - 10)
            if r2 < 85:
                a2 = int(180 * (1.0 - r2 / 85.0))
                pygame.draw.circle(effect_surface, (*self.retro_hit_color, a2), (cx, cy), r2, 1)

            # 8-bit arcade target crosshair reticle (snaps in and blinks)
            if progress < 0.75:
                ret_alpha = int(255 * (1.0 - progress / 0.75))
                ret_col = NEON_YELLOW if (self.retro_effect_timer // 2) % 2 == 0 else (255, 255, 255)
                box_r = max(4, int(12 * (1.0 - min(1.0, progress * 2.2))))
                pygame.draw.rect(
                    effect_surface,
                    (*ret_col, ret_alpha),
                    (cx - box_r, cy - box_r, box_r * 2 + 1, box_r * 2 + 1),
                    1,
                )
                # Crosshair arms
                pygame.draw.line(effect_surface, (*NEON_CYAN, ret_alpha), (cx - box_r - 3, cy), (cx - 2, cy), 1)
                pygame.draw.line(effect_surface, (*NEON_CYAN, ret_alpha), (cx + 2, cy), (cx + box_r + 3, cy), 1)
                pygame.draw.line(effect_surface, (*NEON_CYAN, ret_alpha), (cx, cy - box_r - 3), (cx, cy - 2), 1)
                pygame.draw.line(effect_surface, (*NEON_CYAN, ret_alpha), (cx, cy + 2), (cx, cy + box_r + 3), 1)

        # 5) 8-bit pixel sparks
        for s in self.retro_sparks:
            sx, sy = int(s["x"]), int(s["y"])
            if 0 <= sx < self.width and 0 <= sy < self.height:
                sa = int(255 * (1.0 - s["age"] / max(1, s["life"])))
                pygame.draw.rect(
                    effect_surface,
                    (*s["color"], sa),
                    (sx, sy, s["size"], s["size"]),
                )

        try:
            ox, oy = int(offset[0]), int(offset[1])
        except (TypeError, ValueError, IndexError):
            ox, oy = 0, 0
        target_surface.blit(effect_surface, (ox, oy))

    def draw_rotary_highlight(
        self, target_surface: pygame.Surface, color, offset=(0, 0)
    ) -> None:
        """Draw a dual-beam arcade radar sweep over the board when waiting for next player."""
        try:
            ox, oy = int(offset[0]), int(offset[1])
        except (TypeError, ValueError, IndexError):
            ox, oy = 0, 0

        ticks = pygame.time.get_ticks()
        base_angle = (ticks * 0.0045) % (2 * math.pi) - math.pi / 2
        arc_span = math.radians(26)
        outer_radius = self.radius_outer_double
        cx, cy = self.center

        surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        for beam_offset, alpha in ((0.0, 130), (math.pi, 75)):
            center_angle = base_angle + beam_offset
            start_angle = center_angle - arc_span / 2
            end_angle = center_angle + arc_span / 2
            segments = 24
            step = (end_angle - start_angle) / segments
            points = [(cx, cy)]
            for i in range(segments + 1):
                a = start_angle + i * step
                x = cx + int(round(outer_radius * math.cos(a)))
                y = cy + int(round(outer_radius * math.sin(a)))
                points.append((x, y))
            pygame.draw.polygon(surf, (*color[:3], alpha), points)

        # Pulsing outer arcade ring in next player's color
        pulse_a = int(120 + 90 * math.sin(ticks * 0.01))
        pygame.draw.circle(surf, (*color[:3], pulse_a), (cx, cy), outer_radius, 2)
        target_surface.blit(surf, (ox, oy))

    def trigger_rotary_once(self, color: tuple) -> None:
        """Start a one-rotation neon radar sweep using the provided RGB color."""
        self.rotary_once_active = True
        self.rotary_once_color = color
        self.rotary_once_start_ms = pygame.time.get_ticks()

    def draw_rotary_once(self, target_surface: pygame.Surface, offset=(0, 0)) -> None:
        if not self.rotary_once_active:
            return

        try:
            ox, oy = int(offset[0]), int(offset[1])
        except (TypeError, ValueError, IndexError):
            ox, oy = 0, 0

        now = pygame.time.get_ticks()
        elapsed = now - self.rotary_once_start_ms
        progress = elapsed / max(1, self.rotary_once_duration_ms)
        if progress >= 1.0:
            self.rotary_once_active = False
            return

        center_angle = progress * 2 * math.pi - math.pi / 2
        arc_span = self.rotary_arc_span_rad
        start_angle = center_angle - arc_span / 2
        end_angle = center_angle + arc_span / 2
        outer_radius = self.radius_outer_double
        cx, cy = self.center

        segments = 24
        step = (end_angle - start_angle) / segments
        points = [(cx, cy)]
        for i in range(segments + 1):
            a = start_angle + i * step
            x = cx + int(round(outer_radius * math.cos(a)))
            y = cy + int(round(outer_radius * math.sin(a)))
            points.append((x, y))

        surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        alpha = int(145 * (1.0 - progress * 0.4))
        pygame.draw.polygon(surf, (*self.rotary_once_color[:3], alpha), points)
        target_surface.blit(surf, (ox, oy))
