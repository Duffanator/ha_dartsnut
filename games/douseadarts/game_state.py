from enum import Enum
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
from game_modes import GameMode, StandardMode

NEON_PINK = (255, 43, 214)   # Player 1
NEON_CYAN = (0, 240, 255)    # Player 2
NEON_YELLOW = (255, 230, 0)  # Gold
NEON_GREEN = (57, 255, 20)   # Green


class GameStateEnum(Enum):
    """Enumeration of all possible game states"""

    STARTUP = "startup"
    SETTINGS = "settings"
    MENU = "menu"
    PLAYING = "playing"
    PLAYER_SWITCH = "player_switch"
    BUST_CONTINUE = "bust_continue"
    GAME_OVER = "game_over"
    PAUSED = "paused"


class TurnEffectType(Enum):
    """Enumeration of different turn-end effects"""

    HAT_TRICK = "hat_trick"
    TON = "ton"
    HIGH_TON = "high_ton"
    LOW_TON = "low_ton"
    BUST = "bust"
    CLOSE_CALL = "close_call"
    PLAYER_READY = "player_ready"


@dataclass
class TurnEffectData:
    """Data structure for turn-end effect information"""

    effect_type: TurnEffectType
    player_id: int
    start_time: float
    duration: float = 1.2
    message: str = ""
    color: tuple = (255, 255, 255)

    def is_active(self, current_time: float) -> bool:
        return current_time - self.start_time < self.duration

    def get_progress(self, current_time: float) -> float:
        elapsed = current_time - self.start_time
        if elapsed < 0:
            return 0.0
        return min(elapsed / max(0.001, self.duration), 1.0)


@dataclass
class PlayerData:
    """Data structure for player information"""

    score: int
    hits: Dict[int, int]
    shots: List[int]
    double_in_satisfied: bool = False
    turn_start_score: int = 0


class TurnEffectsManager:
    """Manages turn-end effects and their lifecycle"""

    def __init__(self):
        self.active_effects: List[TurnEffectData] = []

    def add_effect(
        self,
        effect_type: TurnEffectType,
        player_id: int,
        start_time: float,
        message: str = "",
        color: tuple = (255, 255, 255),
        duration: float = 1.2,
    ) -> None:
        effect = TurnEffectData(
            effect_type=effect_type,
            player_id=player_id,
            start_time=start_time,
            message=message,
            color=color,
            duration=duration,
        )
        self.active_effects.append(effect)

    def update_effects(self, current_time: float) -> None:
        self.active_effects = [
            effect for effect in self.active_effects if effect.is_active(current_time)
        ]

    def get_active_effects(self) -> List[TurnEffectData]:
        return self.active_effects

    def clear_all_effects(self) -> None:
        self.active_effects.clear()


class GameState:
    """Main game state manager that handles all game logic and state transitions"""

    def __init__(self, initial_game_mode: Optional[GameMode] = None):
        self.current_state = GameStateEnum.STARTUP
        self.previous_state = None

        self.current_player = 0  # 0 = Neon Pink (P1), 1 = Electric Cyan (P2)
        self.game_mode: GameMode = initial_game_mode or StandardMode()
        self.players: List[PlayerData] = []
        self.game_won = False
        self.winner: Optional[int] = None

        self.turn_effects = TurnEffectsManager()

        self.settings_selected_option = 0
        self.settings_selected_value = 0

        self.bgm_enabled = True
        self.sfx_enabled = True

        self.ai_level = 0
        self.ai_player_index = 1

        self.bust_restore_to_start_of_turn = True

        self._initialize_players()

    def _initialize_players(self):
        initial_scores = self.game_mode.get_initial_scores()
        self.players = []
        for i in range(2):
            player_data = PlayerData(score=initial_scores[i], hits={}, shots=[])
            self.players.append(player_data)

    def change_state(self, new_state: GameStateEnum) -> None:
        if new_state == self.current_state:
            return

        self.previous_state = self.current_state
        self.current_state = new_state

        if new_state == GameStateEnum.STARTUP:
            self._on_enter_startup()
        elif new_state == GameStateEnum.SETTINGS:
            self._on_enter_settings()
        elif new_state == GameStateEnum.PLAYING:
            self._on_enter_playing()
        elif new_state == GameStateEnum.GAME_OVER:
            self._on_enter_game_over()
        elif new_state == GameStateEnum.PLAYER_SWITCH:
            self._on_enter_player_switch()
        elif new_state == GameStateEnum.BUST_CONTINUE:
            self._on_enter_bust_continue()

    def _on_enter_startup(self) -> None:
        pass

    def _on_enter_settings(self) -> None:
        self.settings_selected_option = 0
        self._update_settings_selected_value()

    def _on_enter_playing(self) -> None:
        current_player = self.players[self.current_player]
        current_player.turn_start_score = current_player.score

        import time

        current_time = time.time()
        player_colors = {0: NEON_PINK, 1: NEON_CYAN}
        player_color = player_colors[self.current_player]

        active_effects = self.turn_effects.get_active_effects()
        has_ready_effect = any(
            e.effect_type == TurnEffectType.PLAYER_READY
            and e.player_id == self.current_player
            for e in active_effects
        )

        if not has_ready_effect:
            self.turn_effects.add_effect(
                TurnEffectType.PLAYER_READY,
                self.current_player,
                current_time,
                f"Player {self.current_player + 1} Ready",
                player_color,
                duration=1.35,
            )

    def _on_enter_game_over(self) -> None:
        self.game_won = True
        self.winner = self.current_player

    def _on_enter_player_switch(self) -> None:
        self.players[self.current_player].shots.clear()
        self.current_player = 1 - self.current_player
        self.change_state(GameStateEnum.PLAYING)

    def _on_enter_bust_continue(self) -> None:
        pass

    def process_shot(self, score: int, x: int, y: int) -> Tuple[bool, Optional[str]]:
        if self.current_state != GameStateEnum.PLAYING:
            return False, None

        if score < 0:
            return False, None

        current_player = self.players[self.current_player]
        if len(current_player.shots) >= 3:
            return False, None

        self.players[self.current_player].shots.append(score)

        try:
            sound_name = self._process_standard_shot(score)

            if self._check_win_condition():
                self.change_state(GameStateEnum.GAME_OVER)
                return True, sound_name

            return True, sound_name
        except Exception:
            return False, None

    def _process_standard_shot(self, score: int) -> Optional[str]:
        player = self.players[self.current_player]
        old_score = player.score

        new_score = old_score - score
        if new_score < 0:
            if self.bust_restore_to_start_of_turn:
                turn_start_score = old_score + sum(player.shots[:-1])
                player.score = turn_start_score
            else:
                player.score = old_score
            if player.shots:
                player.shots[-1] = 0
            while len(player.shots) < 3:
                player.shots.append(0)
            import time

            self.turn_effects.add_effect(
                TurnEffectType.BUST,
                self.current_player,
                time.time(),
                "BUST!",
                (255, 40, 80),
                duration=1.2,
            )
            return "bust"
        else:
            player.score = new_score
            return None

    def _check_win_condition(self) -> bool:
        return self._check_standard_win()

    def _check_standard_win(self) -> bool:
        return self.players[self.current_player].score == 0

    def switch_game_mode(self) -> None:
        pass

    def switch_game_mode_in_settings(self) -> None:
        pass

    def reset_game(self) -> None:
        self.current_player = 0
        self.game_won = False
        self.winner = None
        self.turn_effects.clear_all_effects()
        self._initialize_players()
        self.change_state(GameStateEnum.STARTUP)

    def start_game(self) -> None:
        if self.current_state == GameStateEnum.STARTUP:
            self.change_state(GameStateEnum.PLAYING)

    def show_settings(self) -> None:
        if self.current_state == GameStateEnum.STARTUP and isinstance(
            self.game_mode, StandardMode
        ):
            self.change_state(GameStateEnum.SETTINGS)

    def back_to_startup(self) -> None:
        if self.current_state == GameStateEnum.SETTINGS:
            self.change_state(GameStateEnum.STARTUP)

    def toggle_bgm(self) -> None:
        self.bgm_enabled = not self.bgm_enabled

    def navigate_settings_up(self) -> None:
        if self.current_state == GameStateEnum.SETTINGS:
            if self.settings_selected_option > 0:
                self.settings_selected_option -= 1
                self._update_settings_selected_value()

    def navigate_settings_down(self) -> None:
        if self.current_state == GameStateEnum.SETTINGS:
            if self.settings_selected_option < 6:
                self.settings_selected_option += 1
                self._update_settings_selected_value()

    def navigate_settings_left(self) -> None:
        if self.current_state == GameStateEnum.SETTINGS:
            current_values = self._get_current_option_values()
            if len(current_values) > 1:
                if self.settings_selected_value == 0:
                    self.settings_selected_value = len(current_values) - 1
                else:
                    self.settings_selected_value -= 1
                self._apply_settings_change()

    def navigate_settings_right(self) -> None:
        if self.current_state == GameStateEnum.SETTINGS:
            current_values = self._get_current_option_values()
            if len(current_values) > 1:
                if self.settings_selected_value == len(current_values) - 1:
                    self.settings_selected_value = 0
                else:
                    self.settings_selected_value += 1
                self._apply_settings_change()

    def _update_settings_selected_value(self) -> None:
        if isinstance(self.game_mode, StandardMode):
            if self.settings_selected_option == 0:
                try:
                    self.settings_selected_value = (
                        self.game_mode.available_variants.index(
                            self.game_mode.game_variant
                        )
                    )
                except ValueError:
                    self.settings_selected_value = 0
            elif self.settings_selected_option == 1:
                try:
                    self.settings_selected_value = (
                        self.game_mode.available_in_options.index(
                            self.game_mode.in_option
                        )
                    )
                except ValueError:
                    self.settings_selected_value = 0
            elif self.settings_selected_option == 2:
                try:
                    self.settings_selected_value = (
                        self.game_mode.available_out_options.index(
                            self.game_mode.out_option
                        )
                    )
                except ValueError:
                    self.settings_selected_value = 0
            elif self.settings_selected_option == 3:
                try:
                    self.settings_selected_value = (
                        self.game_mode.available_bull_options.index(
                            self.game_mode.bull_option
                        )
                    )
                except ValueError:
                    self.settings_selected_value = 0
            elif self.settings_selected_option == 4:
                self.settings_selected_value = 0 if self.bgm_enabled else 1
            elif self.settings_selected_option == 5:
                self.settings_selected_value = 0 if self.sfx_enabled else 1
            elif self.settings_selected_option == 6:
                self.settings_selected_value = self.ai_level

    def _get_current_option_values(self) -> List:
        if isinstance(self.game_mode, StandardMode):
            if self.settings_selected_option == 0:
                return self.game_mode.available_variants
            elif self.settings_selected_option == 1:
                return self.game_mode.available_in_options
            elif self.settings_selected_option == 2:
                return self.game_mode.available_out_options
            elif self.settings_selected_option == 3:
                return self.game_mode.available_bull_options
            elif self.settings_selected_option in (4, 5):
                return ["ON", "OFF"]
            elif self.settings_selected_option == 6:
                return ["OFF"] + [str(i) for i in range(1, 19)]
        return []

    def _apply_settings_change(self) -> None:
        if isinstance(self.game_mode, StandardMode):
            current_values = self._get_current_option_values()
            if self.settings_selected_value < len(current_values):
                new_value = current_values[self.settings_selected_value]

                if self.settings_selected_option == 0:
                    self.game_mode.set_game_variant(new_value)
                    self._initialize_players()
                elif self.settings_selected_option == 1:
                    self.game_mode.set_in_option(new_value)
                elif self.settings_selected_option == 2:
                    self.game_mode.set_out_option(new_value)
                elif self.settings_selected_option == 3:
                    self.game_mode.set_bull_option(new_value)
                elif self.settings_selected_option == 4:
                    self.bgm_enabled = new_value == "ON"
                elif self.settings_selected_option == 5:
                    self.sfx_enabled = new_value == "ON"
                elif self.settings_selected_option == 6:
                    self.ai_level = 0 if new_value == "OFF" else int(new_value)

    def is_ai_enabled(self) -> bool:
        return self.ai_level > 0

    def is_ai_turn(self) -> bool:
        return (
            self.current_state == GameStateEnum.PLAYING
            and isinstance(self.game_mode, StandardMode)
            and self.is_ai_enabled()
            and self.current_player == self.ai_player_index
        )

    def switch_player(self) -> None:
        if self.current_state == GameStateEnum.PLAYING and not self.game_won:
            self.change_state(GameStateEnum.PLAYER_SWITCH)

    def get_current_player_data(self) -> PlayerData:
        return self.players[self.current_player]

    def get_opponent_data(self) -> PlayerData:
        return self.players[1 - self.current_player]

    def _check_turn_end_effects(self, delay_seconds: float = 0.0) -> Optional[str]:
        import time

        current_time = time.time() + delay_seconds
        current_player = self.players[self.current_player]
        shots = current_player.shots

        if len(shots) < 3:
            return None

        active_effects = self.turn_effects.get_active_effects()
        bust_effects = [
            effect
            for effect in active_effects
            if effect.effect_type == TurnEffectType.BUST
        ]
        if bust_effects:
            return None

        turn_total = sum(shots)
        sound_name: Optional[str] = None

        def has_active(effect_type: TurnEffectType, player_id: int) -> bool:
            return any(
                e.effect_type == effect_type and e.player_id == player_id
                for e in active_effects
            )

        if turn_total == 180 and not has_active(
            TurnEffectType.TON, self.current_player
        ):
            self.turn_effects.add_effect(
                TurnEffectType.TON,
                self.current_player,
                current_time,
                f"MAX 180!",
                NEON_PINK,
                duration=1.4,
            )
            sound_name = "ton"
        elif (
            len(shots) == 3
            and all(shot in [25, 50] for shot in shots)
            and turn_total not in [150, 180]
            and not has_active(TurnEffectType.HAT_TRICK, self.current_player)
        ):
            self.turn_effects.add_effect(
                TurnEffectType.HAT_TRICK,
                self.current_player,
                current_time,
                "HAT TRICK!",
                NEON_YELLOW,
                duration=1.4,
            )
            sound_name = "hattrick"
        elif 150 <= turn_total <= 179 and not has_active(
            TurnEffectType.HIGH_TON, self.current_player
        ):
            self.turn_effects.add_effect(
                TurnEffectType.HIGH_TON,
                self.current_player,
                current_time,
                f"HIGH TON {turn_total}!",
                NEON_GREEN,
                duration=1.3,
            )
            sound_name = "highton"
        elif 100 <= turn_total <= 149 and not has_active(
            TurnEffectType.LOW_TON, self.current_player
        ):
            self.turn_effects.add_effect(
                TurnEffectType.LOW_TON,
                self.current_player,
                current_time,
                f"LOW TON {turn_total}!",
                NEON_CYAN,
                duration=1.2,
            )
            sound_name = "lowton"

        if 0 < current_player.score <= 20:
            if not has_active(TurnEffectType.CLOSE_CALL, self.current_player):
                self.turn_effects.add_effect(
                    TurnEffectType.CLOSE_CALL,
                    self.current_player,
                    current_time,
                    f"{current_player.score} TO WIN!",
                    NEON_YELLOW,
                    duration=1.1,
                )

        return sound_name

    def get_game_info(self) -> Dict[str, Any]:
        return {
            "current_player": self.current_player,
            "game_mode": self.game_mode,
            "players": self.players,
            "game_won": self.game_won,
            "winner": self.winner,
            "current_state": self.current_state,
            "turn_effects": self.turn_effects,
        }
