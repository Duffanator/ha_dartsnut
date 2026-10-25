import os
import pygame

DIRNAME = os.path.dirname(os.path.abspath(__file__))

# Basement Arcade 2.0 Palette
NEON_PINK = (255, 43, 214)      # #ff2bd6 (Player 1)
NEON_CYAN = (0, 240, 255)       # #00f0ff (Player 2)
NEON_YELLOW = (255, 230, 0)     # #ffe600 (Marquee Gold)
NEON_GREEN = (57, 255, 20)      # #39ff14 (Laser Green)
BG_DARK = (10, 0, 24)
BG_PANEL = (22, 4, 46)


class Scoreboard:
    """Renders the 64x32 Basement Arcade neon HUD scoreboard."""

    def __init__(self, width=64, height=32):
        self.width = width
        self.height = height
        self.surface = pygame.Surface((width, height), pygame.SRCALPHA)

    def draw(self, player, player_scores, shots):
        """Draw the arcade HUD scoreboard with current game state."""
        self.surface.fill((*BG_DARK, 255))

        p_color = NEON_PINK if player == 0 else NEON_CYAN
        opp_color = NEON_CYAN if player == 0 else NEON_PINK

        # Left shot panel backdrop
        pygame.draw.rect(self.surface, BG_PANEL, (1, 1, 21, 30))

        # Subtle CRT scanlines across the 64x32 HUD
        for y in range(1, 31, 2):
            pygame.draw.line(self.surface, (5, 0, 12), (1, y), (62, y))

        # Outer neon border in active player's color + gold corner pixels
        pygame.draw.rect(self.surface, p_color, (0, 0, 64, 32), 1)
        for cx, cy in ((0, 0), (63, 0), (0, 31), (63, 31)):
            self.surface.set_at((cx, cy), NEON_YELLOW)

        # Vertical neon divider between 3-dart column (x=0..21) and main score area (x=22..63)
        pygame.draw.line(self.surface, p_color, (22, 1), (22, 30), 1)

        # Horizontal divider between active player score (top) and opponent score (bottom)
        pygame.draw.line(self.surface, (65, 20, 110), (23, 20), (62, 20), 1)

        # Active player badge ("P1" or "P2") at top-left of right pane
        badge_font = _get_font(11)
        p_label = f"P{player + 1}"
        pygame.draw.rect(self.surface, p_color, (24, 2, 10, 8))
        p_surf = badge_font.render(p_label, False, (0, 0, 0))
        self.surface.blit(p_surf, p_surf.get_rect(center=(29, 6)))

        # Current player large score
        score_val = str(player_scores[player])
        score_font = _get_font(23 if len(score_val) <= 3 else 18)
        # Drop shadow
        shadow_surf = score_font.render(score_val, False, (40, 0, 70))
        self.surface.blit(shadow_surf, shadow_surf.get_rect( center=(49, 11)))
        # Main glowing digits
        main_col = NEON_YELLOW if player_scores[player] <= 100 else (255, 255, 255)
        text_surface = score_font.render(score_val, False, main_col)
        self.surface.blit(text_surface, text_surface.get_rect(center=(48, 10)))

        # Opponent label & score on bottom row (y=21..30)
        opp_idx = 1 - player
        opp_tag = badge_font.render(f"P{opp_idx + 1}", False, opp_color)
        self.surface.blit(opp_tag, opp_tag.get_rect(center=(29, 26)))

        opp_font = _get_font(15)
        opp_surface = opp_font.render(str(player_scores[opp_idx]), False, (205, 205, 225))
        self.surface.blit(opp_surface, opp_surface.get_rect(center=(49, 26)))

        # Draw the 3 dart slots in the left column (centers at x=11, y=6, 16, 26)
        slot_y = (6, 16, 26)
        shot_font = _get_font(14)
        for i in range(3):
            sy = slot_y[i]
            if i < len(shots):
                shot = shots[i]
                if shot >= 50:
                    scol = NEON_YELLOW
                elif shot >= 25:
                    scol = NEON_GREEN
                elif shot == 0:
                    scol = (150, 70, 90)
                else:
                    scol = (255, 255, 255)
                s_surf = shot_font.render(str(shot), False, scol)
                self.surface.blit(s_surf, s_surf.get_rect(center=(11, sy)))
            else:
                # Unthrown dart indicator pip
                pygame.draw.rect(self.surface, (*p_color, 180), (9, sy - 1, 4, 2))


def _get_font(size: int) -> pygame.font.Font:
    """Load Micro5.ttf or a matching system font; fall back to default."""
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
