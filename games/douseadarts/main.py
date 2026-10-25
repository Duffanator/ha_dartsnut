import sys
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(base_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from game import DartGame
from game_modes import StandardMode


def main() -> None:
    """Launch Dousea Darts in x01 mode (default 501)."""
    game = DartGame(initial_game_mode=StandardMode())
    game.run()


if __name__ == "__main__":
    main()
