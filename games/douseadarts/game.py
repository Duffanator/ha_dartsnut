import os
import random
import time
from typing import Dict, List, Optional, Tuple
import numpy as np
import pygame

from dartboard import Dartboard, NEON_PINK, NEON_CYAN, NEON_YELLOW, NEON_GREEN
from game_modes import StandardMode
from scoreboard import Scoreboard
from game_state import GameState, GameStateEnum, TurnEffectType
from state_renderer import StateRenderer

from pydartsnut import Dartsnut

engine = Dartsnut()

AI_RATING_PROFILES: Dict[int, Dict[str, float]] = {
    1: {"accuracy": 0.28, "neighbor_miss": 0.44, "ring_miss": 0.18, "full_miss": 0.10},
    2: {"accuracy": 0.32, "neighbor_miss": 0.42, "ring_miss": 0.18, "full_miss": 0.08},
    3: {"accuracy": 0.36, "neighbor_miss": 0.40, "ring_miss": 0.18, "full_miss": 0.06},
    4: {"accuracy": 0.40, "neighbor_miss": 0.38, "ring_miss": 0.18, "full_miss": 0.04},
    5: {"accuracy": 0.44, "neighbor_miss": 0.36, "ring_miss": 0.17, "full_miss": 0.03},
    6: {"accuracy": 0.48, "neighbor_miss": 0.34, "ring_miss": 0.16, "full_miss": 0.02},
    7: {"accuracy": 0.52, "neighbor_miss": 0.32, "ring_miss": 0.14, "full_miss": 0.02},
    8: {"accuracy": 0.56, "neighbor_miss": 0.31, "ring_miss": 0.12, "full_miss": 0.01},
    9: {"accuracy": 0.60, "neighbor_miss": 0.30, "ring_miss": 0.09, "full_miss": 0.01},
    10: {"accuracy": 0.64, "neighbor_miss": 0.29, "ring_miss": 0.06, "full_miss": 0.01},
    11: {"accuracy": 0.68, "neighbor_miss": 0.27, "ring_miss": 0.04, "full_miss": 0.01},
    12: {"accuracy": 0.71, "neighbor_miss": 0.25, "ring_miss": 0.03, "full_miss": 0.01},
    13: {"accuracy": 0.75, "neighbor_miss": 0.22, "ring_miss": 0.02, "full_miss": 0.01},
    14: {"accuracy": 0.79, "neighbor_miss": 0.19, "ring_miss": 0.01, "full_miss": 0.01},
    15: {"accuracy": 0.83, "neighbor_miss": 0.15, "ring_miss": 0.01, "full_miss": 0.01},
    16: {"accuracy": 0.87, "neighbor_miss": 0.11, "ring_miss": 0.01, "full_miss": 0.01},
    17: {"accuracy": 0.90, "neighbor_miss": 0.08, "ring_miss": 0.01, "full_miss": 0.01},
    18: {"accuracy": 0.92, "neighbor_miss": 0.06, "ring_miss": 0.01, "full_miss": 0.01},
}


class DartGame:
    """Main game class for Dousea Darts (Basement Arcade Edition)."""

    def __init__(self, initial_game_mode=None):
        pygame.init()
        self._audio_ready = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self._audio_ready = True
        except Exception:
            self._audio_ready = False

        self.WIDTH, self.HEIGHT = 128, 128
        self.screen = pygame.display.set_mode((128, 160), pygame.SRCALPHA)
        self.clock = pygame.time.Clock()
        self.FPS = 60

        self.sfx = {}
        self.played_victory_sound = False
        self._init_audio_assets()

        self.dartboard = Dartboard()
        self.scoreboard = Scoreboard()
        self.state_renderer = StateRenderer(self.screen, self.dartboard.surface)

        self.game_state = GameState(initial_game_mode=initial_game_mode)

        self.ai_min_throw_delay_frames = 180
        self.ai_max_throw_delay_frames = 240
        self.ai_pre_throw_delay_frames = 90
        self.ai_auto_continue_delay_frames = 90
        self.ai_next_throw_frame = 0
        self.ai_turn_started = False
        self.ai_turn_ready_frame = 0
        self.ai_auto_continue_frame = -1
        self.frame_count = 0

        self.floating_texts = []

        self.big_hit_active = False
        self.big_hit_timer = 0
        self.big_hit_duration = 80
        self.big_hit_center = (64, 64)
        self.big_hit_particles = []

        self.update_frame_buffer()

    def switch_game_mode(self):
        self.game_state.switch_game_mode()
        self.dartboard.clear_highlight()
        self._update_scoreboard()

    def reset_game(self):
        self.game_state.reset_game()
        self.dartboard.clear_highlight()
        self._update_scoreboard()

    def _update_scoreboard(self):
        game_info = self.game_state.get_game_info()
        self.scoreboard.draw(
            game_info["current_player"],
            [p.score for p in game_info["players"]],
            game_info["players"][game_info["current_player"]].shots,
        )

    def update_frame_buffer(self):
        self.screen.fill((0, 0, 0))

        if self.game_state.current_state == GameStateEnum.GAME_OVER:
            if not self.played_victory_sound:
                self._play_sfx("victory")
                try:
                    pygame.mixer.music.fadeout(500)
                except Exception:
                    pass
                self.played_victory_sound = True
        else:
            self.played_victory_sound = False

        if self.game_state.current_state in [
            GameStateEnum.STARTUP,
            GameStateEnum.SETTINGS,
        ]:
            game_info = self.game_state.get_game_info()
            game_info["game_state"] = self.game_state
            self.state_renderer.render_state(game_info)
            pygame.display.flip()
            engine.update_frame_buffer(
                bytearray(pygame.image.tobytes(self.screen, "RGB"))
            )
            return

        self.dartboard.update_retro_effect()
        self.dartboard.update_shake()
        self._update_floating_texts()
        self._update_big_hit_animation()

        shake_offset = self.dartboard.get_shake_offset()
        self.screen.blit(self.dartboard.surface, shake_offset)
        self.screen.blit(self.scoreboard.surface, (0, 128))

        self.dartboard.draw_retro_effect(self.screen, offset=shake_offset)

        animations_busy = bool(
            self.dartboard.retro_effect_active
            or self.big_hit_active
            or self.floating_texts
        )

        current_player = self.game_state.current_player
        current_player_data = self.game_state.get_current_player_data()
        if len(current_player_data.shots) >= 3 and not animations_busy:
            next_player = 1 - current_player
            highlight_color = NEON_PINK if next_player == 0 else NEON_CYAN
            self.dartboard.draw_rotary_highlight(
                self.screen, highlight_color, offset=shake_offset
            )

        self.dartboard.draw_rotary_once(self.screen, offset=shake_offset)

        self._draw_big_hit_animation()
        self._draw_floating_texts()

        game_info = self.game_state.get_game_info()
        game_info["game_state"] = self.game_state
        game_info["animations_busy"] = animations_busy
        self.state_renderer.render_state(game_info)

        pygame.display.flip()
        engine.update_frame_buffer(
            bytearray(pygame.image.tobytes(self.screen, "RGB"))
        )

    def _sector_index_to_score(self, sector_index: int, bull_option: str = "25/50") -> int:
        if sector_index == 0:
            return 50
        if sector_index == 1:
            return 50 if bull_option == "50/50" else 25
        if sector_index < 2:
            return 0
        main_sector = (sector_index - 2) // 4
        part = (sector_index - 2) % 4
        base = self.dartboard.SCORES[main_sector]
        if part == 1:
            return base * 3
        if part == 3:
            return base * 2
        return base

    def _score_to_sector_index(self, score: int) -> Optional[int]:
        bull_option = getattr(self.game_state.game_mode, "bull_option", "25/50")
        candidates: List[int] = []
        for sector_index in range(len(self.dartboard.sectors)):
            if self._sector_index_to_score(sector_index, bull_option) == score:
                candidates.append(sector_index)
        if not candidates:
            return None
        return random.choice(candidates)

    def _score_to_hit_xy(self, score: int) -> Optional[Tuple[int, int]]:
        sector_index = self._score_to_sector_index(score)
        if sector_index is None:
            return None
        sector_pixels = self.dartboard.sectors[sector_index]
        if not sector_pixels:
            return None
        return random.choice(sector_pixels)

    def _choose_ai_target_score(self, ai_level: int) -> int:
        player = self.game_state.get_current_player_data()
        remaining = player.score
        darts_left = max(0, 3 - len(player.shots))
        game_mode = self.game_state.game_mode
        double_in = getattr(game_mode, "in_option", "single") == "double"
        double_out = getattr(game_mode, "out_option", "single") == "double"
        opened = getattr(player, "double_in_satisfied", False)

        if double_in and not opened:
            return random.choice([40, 32, 24, 20, 16])

        if double_out:
            if remaining == 50:
                return 50
            if 2 <= remaining <= 40 and remaining % 2 == 0:
                return remaining

        if ai_level >= 12 and darts_left > 1:
            preferred = [60, 57, 54, 51, 50, 45, 40, 38, 36, 34, 32]
            for hit in preferred:
                leave = remaining - hit
                if leave < 2:
                    continue
                if double_out:
                    if leave == 50 or (2 <= leave <= 40 and leave % 2 == 0):
                        return hit
                    if leave == 1:
                        continue
                return hit

        if 7 <= ai_level <= 11:
            if remaining >= 61:
                return 60
            if remaining >= 41:
                return random.choice([45, 40, 38, 36])

        if remaining > 60:
            return random.choice([60, 20, 20, 5, 1])
        return max(1, min(remaining, random.choice([20, 16, 12, 8, 4, remaining])))

    def _neighbor_score_same_ring(self, score: int) -> int:
        if score in (25, 50):
            return 25 if score == 50 else random.choice([1, 5, 20])
        if score <= 0:
            return 0

        multiplier = 1
        if score % 3 == 0 and (score // 3) in self.dartboard.SCORES:
            multiplier = 3
            base = score // 3
        elif score % 2 == 0 and (score // 2) in self.dartboard.SCORES:
            multiplier = 2
            base = score // 2
        else:
            base = score

        if base not in self.dartboard.SCORES:
            return 0
        idx = self.dartboard.SCORES.index(base)
        neighbor_idx = (idx + random.choice([-1, 1])) % len(self.dartboard.SCORES)
        return self.dartboard.SCORES[neighbor_idx] * multiplier

    def _ring_miss_same_sector(self, score: int) -> int:
        if score == 50:
            return 25
        if score == 25:
            return random.choice([0, 50, 1, 5, 20])
        if score <= 0:
            return 0
        if score % 3 == 0 and (score // 3) in self.dartboard.SCORES:
            return score // 3
        if score % 2 == 0 and (score // 2) in self.dartboard.SCORES:
            return score // 2
        return random.choice([0, self._neighbor_score_same_ring(score)])

    def _sample_ai_actual_score(self, intended_score: int, ai_level: int) -> int:
        profile = AI_RATING_PROFILES.get(ai_level, AI_RATING_PROFILES[1])
        roll = random.random()
        if roll < profile["accuracy"]:
            return intended_score
        roll -= profile["accuracy"]
        if roll < profile["neighbor_miss"]:
            return self._neighbor_score_same_ring(intended_score)
        roll -= profile["neighbor_miss"]
        if roll < profile["ring_miss"]:
            return self._ring_miss_same_sector(intended_score)
        return 0

    def _get_ai_hit_xy(self) -> Optional[Tuple[int, int]]:
        ai_level = max(1, min(18, int(getattr(self.game_state, "ai_level", 1))))
        intended = self._choose_ai_target_score(ai_level)
        actual = self._sample_ai_actual_score(intended, ai_level)
        if actual <= 0:
            return (-1, -1)
        hit_xy = self._score_to_hit_xy(actual)
        if hit_xy is None:
            return (-1, -1)
        return hit_xy

    def _reset_ai_pacing(self) -> None:
        self.ai_next_throw_frame = self.frame_count + self._get_ai_throw_delay_frames()
        self.ai_turn_started = False
        self.ai_turn_ready_frame = 0
        self.ai_auto_continue_frame = -1

    def _get_ai_throw_delay_frames(self) -> int:
        ai_level = max(1, min(18, int(getattr(self.game_state, "ai_level", 1))))
        ratio = (ai_level - 1) / 17.0
        delay = self.ai_max_throw_delay_frames - (
            self.ai_max_throw_delay_frames - self.ai_min_throw_delay_frames
        ) * ratio
        return int(round(delay))

    def handle_ai_turn(self):
        if not self.game_state.is_ai_turn():
            self.ai_turn_started = False
            self.ai_auto_continue_frame = -1
            return
        current_player_data = self.game_state.get_current_player_data()
        if len(current_player_data.shots) >= 3:
            return
        if not self.ai_turn_started:
            self.ai_turn_started = True
            self.ai_turn_ready_frame = self.frame_count + self.ai_pre_throw_delay_frames
            self.ai_next_throw_frame = self.ai_turn_ready_frame
            return
        if self.frame_count < self.ai_turn_ready_frame:
            return
        if self.frame_count < self.ai_next_throw_frame:
            return
        ai_hit = self._get_ai_hit_xy()
        if ai_hit is None:
            return
        self._process_single_hit(ai_hit[0], ai_hit[1], dart_index=None)
        self.ai_next_throw_frame = self.frame_count + self._get_ai_throw_delay_frames()

    def _perform_player_continue_switch(self) -> None:
        self._play_sfx("button")
        self.game_state.turn_effects.clear_all_effects()
        self.game_state.switch_player()
        self._reset_ai_pacing()
        self.dartboard.clear_highlight()
        self._update_scoreboard()

    def _handle_ai_auto_continue(self) -> bool:
        if self.game_state.current_state != GameStateEnum.PLAYING:
            self.ai_auto_continue_frame = -1
            return False
        if not self.game_state.is_ai_turn():
            self.ai_auto_continue_frame = -1
            return False
        current_player_data = self.game_state.get_current_player_data()
        if len(current_player_data.shots) < 3:
            self.ai_auto_continue_frame = -1
            return False
        if self.ai_auto_continue_frame < 0:
            self.ai_auto_continue_frame = (
                self.frame_count + self.ai_auto_continue_delay_frames
            )
            return True
        if self.frame_count < self.ai_auto_continue_frame:
            return True
        self._perform_player_continue_switch()
        self.ai_auto_continue_frame = -1
        return True

    def handle_dart_hits(self):
        hits = engine.get_dart_hits()
        current_state = self.game_state.current_state

        if current_state != GameStateEnum.PLAYING:
            return
        for dart_index, x, y in hits:
            keep_processing = self._process_single_hit(x, y, dart_index=dart_index)
            if not keep_processing:
                return

    def _process_single_hit(self, x: int, y: int, dart_index=None) -> bool:
        if self.game_state.current_state != GameStateEnum.PLAYING:
            return False

        current_player = self.game_state.current_player
        current_color = NEON_PINK if current_player == 0 else NEON_CYAN

        if not (0 <= x < 128 and 0 <= y < 128):
            self.dartboard.trigger_shake()
            current_player_data = self.game_state.get_current_player_data()
            current_player_data.shots.append(0)
            self._play_sfx("miss")
            self._update_scoreboard()
            return False

        score = self.dartboard.get_score(x, y, self.game_state.game_mode)

        if score <= 0:
            self.dartboard.trigger_shake()
            current_player_data = self.game_state.get_current_player_data()
            current_player_data.shots.append(0)
            self._play_sfx("miss")
            self._update_scoreboard()
            return False

        sector_index = self.dartboard.get_sector_index(x, y)
        if sector_index >= 0:
            self.dartboard.highlight_sector(sector_index)

        self.dartboard.trigger_retro_effect(x, y, player_color=current_color)

        # Enforce Double-In per player
        if isinstance(self.game_state.game_mode, StandardMode) and (
            getattr(self.game_state.game_mode, "in_option", "single") == "double"
        ):
            current_player_data = self.game_state.get_current_player_data()
            if not getattr(current_player_data, "double_in_satisfied", False):
                is_double_hit = (sector_index == 0) or (
                    sector_index >= 2 and ((sector_index - 2) % 4) == 3
                )
                if not is_double_hit:
                    current_player_data.shots.append(0)
                    self.dartboard.trigger_shake()
                    self._play_sfx("miss")
                    self._update_scoreboard()
                    return False
                current_player_data.double_in_satisfied = True

        # Enforce Double-Out and proper bust behavior
        if isinstance(self.game_state.game_mode, StandardMode) and (
            getattr(self.game_state.game_mode, "out_option", "single") == "double"
        ):
            current_player_data = self.game_state.get_current_player_data()
            remaining_before = current_player_data.score
            turn_start_score = remaining_before + sum(current_player_data.shots)
            would_new_score = remaining_before - score

            is_double_hit = (sector_index == 0) or (
                sector_index >= 2 and ((sector_index - 2) % 4) == 3
            )

            if (
                would_new_score < 0
                or would_new_score == 1
                or (would_new_score == 0 and not is_double_hit)
            ):
                if self.game_state.bust_restore_to_start_of_turn:
                    current_player_data.score = turn_start_score
                else:
                    current_player_data.score = remaining_before

                current_player_data.shots.append(0)
                while len(current_player_data.shots) < 3:
                    current_player_data.shots.append(0)

                self.game_state.turn_effects.add_effect(
                    TurnEffectType.BUST,
                    self.game_state.current_player,
                    time.time(),
                    "BUST!",
                    (255, 40, 80),
                    duration=1.2,
                )
                self._play_sfx("bust")
                self._update_scoreboard()
                self._check_bust_auto_switch()
                return False

        success, shot_sound = self.game_state.process_shot(score, x, y)
        if success:
            if shot_sound:
                self._play_sfx(shot_sound)
            self._play_sfx("hit")
            self._update_scoreboard()
            self.dartboard.trigger_rotary_once(current_color)
            current_player_data = self.game_state.get_current_player_data()
            shot_index = max(0, len(current_player_data.shots) - 1)
            hit_label = self.dartboard.get_hit_label(x, y, self.game_state.game_mode)
            self._create_floating_score_text(score, hit_label, x, y, shot_index, current_color)
            if score >= 50 or sector_index in (0, 1):
                self._play_sfx("highscore")
                self._trigger_big_hit_animation(x, y)

            if len(current_player_data.shots) >= 3:
                if self.big_hit_active:
                    delay_seconds = self.big_hit_timer / 60.0
                    sound_name = self.game_state._check_turn_end_effects(delay_seconds)
                else:
                    sound_name = self.game_state._check_turn_end_effects()
                if sound_name:
                    self._play_sfx(sound_name)

            self._check_bust_auto_switch()
        return True

    def _create_floating_score_text(
        self,
        score: int,
        hit_label: str,
        hit_x: int,
        hit_y: int,
        shot_index: int,
        player_color: tuple,
    ) -> None:
        slot = max(0, min(2, shot_index))
        scoreboard_slot_positions = {0: (11, 6), 1: (11, 16), 2: (11, 26)}
        target_local = scoreboard_slot_positions.get(slot, (11, 26))
        target_screen_pos = (target_local[0], 128 + target_local[1])

        shake_offset = self.dartboard.get_shake_offset()
        start_screen_pos = (
            max(22, min(106, int(hit_x + shake_offset[0]))),
            max(14, min(114, int(hit_y + shake_offset[1]))),
        )

        hold_frames = 22
        move_frames = 44

        if score >= 50:
            font_size = 24
            col = NEON_YELLOW
        elif hit_label.startswith(("T-", "D-", "BULL")):
            font_size = 20
            col = NEON_GREEN
        else:
            font_size = 20
            col = player_color

        self.floating_texts.append(
            {
                "text": hit_label,
                "score_str": str(score),
                "start": start_screen_pos,
                "end": target_screen_pos,
                "hold": hold_frames,
                "move": move_frames,
                "age": 0,
                "color": col,
                "font_size": font_size,
                "shake0": (shake_offset[0], shake_offset[1]),
            }
        )

    def _get_font(self, size: int) -> pygame.font.Font:
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

    def _update_floating_texts(self) -> None:
        if not self.floating_texts:
            return
        remaining = []
        for entry in self.floating_texts:
            entry["age"] += 1
            total = entry["hold"] + entry["move"]
            if entry["age"] <= total:
                remaining.append(entry)
        self.floating_texts = remaining

    def _draw_floating_texts(self) -> None:
        if not self.floating_texts:
            return

        for entry in self.floating_texts:
            age = entry["age"]
            hold = entry["hold"]
            move = entry["move"]
            start_x, start_y = entry["start"]
            end_x, end_y = entry["end"]

            if age <= hold:
                cur_shake = self.dartboard.get_shake_offset()
                ox0, oy0 = entry.get("shake0", (0, 0))
                dx, dy = cur_shake[0] - ox0, cur_shake[1] - oy0
                x, y = start_x + dx, start_y + dy
                display_str = entry["text"]
                fsize = entry["font_size"]
            else:
                t = min(1.0, (age - hold) / max(1, move))
                ease = 3 * t * t - 2 * t * t * t
                x = int(round(start_x + (end_x - start_x) * ease))
                y = int(round(start_y + (end_y - start_y) * ease))
                display_str = entry["score_str"] if t > 0.45 else entry["text"]
                fsize = max(14, int(entry["font_size"] * (1.0 - 0.3 * t)))

            alpha = (
                255
                if age <= hold
                else int(255 * (1 - 0.65 * min(1.0, (age - hold) / max(1, move))))
            )

            font = self._get_font(fsize)
            shadow_surf = font.render(display_str, False, (0, 0, 0))
            text_surface = font.render(display_str, False, entry["color"])
            if alpha < 255:
                shadow_surf.set_alpha(alpha)
                text_surface.set_alpha(alpha)
            self.screen.blit(shadow_surf, shadow_surf.get_rect(center=(x + 1, y + 1)))
            self.screen.blit(text_surface, text_surface.get_rect(center=(x, y)))

    def _trigger_big_hit_animation(self, hit_x: int, hit_y: int) -> None:
        self.big_hit_active = True
        self.big_hit_timer = self.big_hit_duration
        shake_offset = self.dartboard.get_shake_offset()
        self.big_hit_center = (
            int(hit_x + shake_offset[0]),
            int(hit_y + shake_offset[1]),
        )
        self.big_hit_particles = []
        self._spawn_big_hit_particles(count=55)

    def _spawn_big_hit_particles(self, count: int = 50) -> None:
        palette = [
            NEON_PINK,
            NEON_CYAN,
            NEON_YELLOW,
            NEON_GREEN,
            (255, 255, 255),
        ]
        cx, cy = self.big_hit_center
        for _ in range(count):
            angle = random.uniform(0, 2 * np.pi)
            speed = random.uniform(1.2, 2.9)
            vx = speed * np.cos(angle)
            vy = speed * np.sin(angle) - random.uniform(0.0, 1.2)
            size = random.randint(1, 3)
            color = random.choice(palette)
            life = random.randint(36, 78)
            self.big_hit_particles.append(
                {
                    "x": float(cx),
                    "y": float(cy),
                    "vx": float(vx),
                    "vy": float(vy),
                    "size": size,
                    "color": color,
                    "life": life,
                    "age": 0,
                }
            )

    def _update_big_hit_animation(self) -> None:
        if not self.big_hit_active:
            return
        self.big_hit_timer -= 1
        remaining_particles = []
        for p in self.big_hit_particles:
            p["age"] += 1
            if p["age"] >= p["life"]:
                continue
            p["vy"] += 0.06
            p["vx"] *= 0.995
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            remaining_particles.append(p)
        self.big_hit_particles = remaining_particles

        if self.big_hit_timer <= 0 and not self.big_hit_particles:
            self.big_hit_active = False

    def _draw_big_hit_animation(self) -> None:
        if not self.big_hit_active:
            return

        effect = pygame.Surface((self.WIDTH, self.HEIGHT), pygame.SRCALPHA)
        t = 1.0 - (self.big_hit_timer / max(1, self.big_hit_duration))
        flash_alpha = int(max(0, 150 * (1 - t)))
        if flash_alpha > 0:
            effect.fill((*NEON_PINK, flash_alpha // 2))

        cx, cy = self.big_hit_center
        ring_progress = 1.0 - (self.big_hit_timer / max(1, self.big_hit_duration))
        ring_cols = (NEON_YELLOW, NEON_PINK, NEON_CYAN)
        for i in range(3):
            rp = (ring_progress + i * 0.14) % 1.0
            radius = int(8 + rp * 96)
            alpha = int(max(0, 175 * (1 - rp)))
            if alpha > 0:
                pygame.draw.circle(effect, (*ring_cols[i], alpha), (cx, cy), radius, 2)

        for p in self.big_hit_particles:
            pa = 1.0 - (p["age"] / p["life"])
            a = int(max(0, min(255, 255 * pa)))
            color = (*p["color"][:3], a)
            rect = pygame.Rect(
                int(p["x"]) - p["size"],
                int(p["y"]) - p["size"],
                p["size"] * 2,
                p["size"] * 2,
            )
            pygame.draw.rect(effect, color, rect)

        self.screen.blit(effect, (0, 0))

    def handle_buttons(self):
        button_events = engine.get_button_events()

        if self.game_state.current_state == GameStateEnum.STARTUP:
            if button_events.get("btn_a"):
                self._play_sfx("start")
                if getattr(self.game_state, "bgm_enabled", True):
                    self._start_bgm()
                self.game_state.start_game()
                self._reset_ai_pacing()
                self.dartboard.clear_highlight()
                self._update_scoreboard()
                return
            elif button_events.get("btn_b"):
                if isinstance(self.game_state.game_mode, StandardMode):
                    self._play_sfx("button")
                    self.game_state.show_settings()
                else:
                    self._play_sfx("button")
                return

        if self.game_state.current_state == GameStateEnum.SETTINGS:
            if button_events.get("btn_a"):
                self._play_sfx("button")
                self.game_state.back_to_startup()
                return
            elif button_events.get("btn_up"):
                self._play_sfx("button")
                self.game_state.navigate_settings_up()
                return
            elif button_events.get("btn_down"):
                self._play_sfx("button")
                self.game_state.navigate_settings_down()
                return
            elif button_events.get("btn_left"):
                self._play_sfx("button")
                self.game_state.navigate_settings_left()
                if getattr(self.game_state, "bgm_enabled", True):
                    self._start_bgm()
                else:
                    self._stop_bgm()
                return
            elif button_events.get("btn_right"):
                self._play_sfx("button")
                self.game_state.navigate_settings_right()
                if getattr(self.game_state, "bgm_enabled", True):
                    self._start_bgm()
                else:
                    self._stop_bgm()
                return

        if self.game_state.current_state == GameStateEnum.BUST_CONTINUE:
            if button_events.get("btn_a"):
                self._play_sfx("button")
                self.game_state.turn_effects.clear_all_effects()
                self.game_state.change_state(GameStateEnum.PLAYER_SWITCH)
                self._reset_ai_pacing()
                self.dartboard.clear_highlight()
                self._update_scoreboard()
                return

        if self._handle_ai_auto_continue():
            return

        if button_events.get("btn_a"):
            current_player_data = self.game_state.get_current_player_data()
            if len(current_player_data.shots) >= 3:
                self._perform_player_continue_switch()

        if button_events.get("btn_b"):
            self._play_sfx("button")
            self.reset_game()
            self._reset_ai_pacing()
            if getattr(self.game_state, "bgm_enabled", True):
                self._start_bgm()

    def handle_events(self):
        for event in pygame.event.get([pygame.QUIT]):
            if event.type == pygame.QUIT:
                return False
        return True

    def run(self):
        if self.game_state.current_state != GameStateEnum.STARTUP:
            self._update_scoreboard()
        self.update_frame_buffer()

        running = True
        while running:
            self.frame_count += 1
            running = self.handle_events()
            self.handle_dart_hits()
            self.handle_ai_turn()
            self.handle_buttons()
            self._check_bust_auto_switch()
            self.clock.tick(self.FPS)
            self.update_frame_buffer()

        pygame.quit()

    def _init_audio_assets(self) -> None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        sound_dir = os.path.join(base_dir, "sound")
        if not self._audio_ready or not os.path.isdir(sound_dir):
            return

        def load(name: str, filename: str):
            path = os.path.join(sound_dir, filename)
            if os.path.exists(path):
                try:
                    self.sfx[name] = pygame.mixer.Sound(path)
                except Exception:
                    pass

        load("button", "button.mp3")
        load("start", "start.mp3")
        load("hit", "hit.mp3")
        load("miss", "miss.mp3")
        load("victory", "victory.mp3")
        load("highscore", "hightscore.mp3")
        load("bust", "bust.mp3")
        load("hattrick", "hattrick.mp3")
        load("highton", "highton.mp3")
        load("lowton", "lowton.mp3")
        load("ton", "ton.mp3")

        bgm_path = os.path.join(sound_dir, "bgm.mp3")
        try:
            if os.path.exists(bgm_path):
                pygame.mixer.music.load(bgm_path)
                pygame.mixer.music.set_volume(0.35)
                pygame.mixer.music.play(-1)
        except Exception:
            pass

    def _start_bgm(self) -> None:
        if not self._audio_ready:
            return
        try:
            if not pygame.mixer.music.get_busy():
                pygame.mixer.music.play(-1)
        except Exception:
            pass

    def _stop_bgm(self) -> None:
        if not self._audio_ready:
            return
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass

    def _play_sfx(self, name: str) -> None:
        if not self._audio_ready:
            return
        if hasattr(self, "game_state") and not getattr(
            self.game_state, "sfx_enabled", True
        ):
            return
        s = self.sfx.get(name)
        if s is None:
            return
        try:
            s.set_volume(0.7)
            s.play()
        except Exception:
            pass

    def _check_bust_auto_switch(self) -> None:
        current_time = time.time()
        active_effects = self.game_state.turn_effects.get_active_effects()
        bust_effects = [
            effect
            for effect in active_effects
            if effect.effect_type == TurnEffectType.BUST
        ]

        if bust_effects:
            for effect in bust_effects:
                if not effect.is_active(current_time):
                    self.game_state.turn_effects.clear_all_effects()
                    self.dartboard.clear_highlight()
                    self.game_state.change_state(GameStateEnum.BUST_CONTINUE)
                    self._update_scoreboard()
                    return
