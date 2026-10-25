class GameMode:
    """Base class for different dart game modes"""

    def __init__(self):
        self.name = "Base Mode"
        self.target_score = 0

    def get_initial_scores(self):
        """Get initial scores for players"""
        return [self.target_score, self.target_score]

    def process_shot(self, score, player_scores, player):
        """Process a shot and return updated scores"""
        player_scores[player] -= score
        return player_scores

    def check_win_condition(self, player_scores, player):
        """Check if a player has won"""
        return player_scores[player] <= 0

    def get_display_text(self, player_scores, player):
        """Get text to display for current player"""
        return str(player_scores[player])


class StandardMode(GameMode):
    """Standard 501 game mode with configurable options"""

    def __init__(self):
        self.name = "501"

        # Available game variants
        self.available_variants = [301, 501, 701, 901, 1101, 1501]
        self.game_variant = 501
        self.target_score = self.game_variant

        # Available in options
        self.available_in_options = ["single", "double"]
        self.in_option = "single"

        # Available out options
        self.available_out_options = ["single", "double"]
        self.out_option = "single"

        # Available bull options
        self.available_bull_options = ["25/50", "50/50"]
        self.bull_option = "25/50"

    def set_game_variant(self, variant):
        """Set the game variant (301, 501, 701, etc.)"""
        if variant in self.available_variants:
            self.game_variant = variant
            self.target_score = variant
            self.name = str(variant)

    def set_in_option(self, option):
        """Set the in option (single/double)"""
        if option in self.available_in_options:
            self.in_option = option

    def set_out_option(self, option):
        """Set the out option (single/double)"""
        if option in self.available_out_options:
            self.out_option = option

    def set_bull_option(self, option):
        """Set the bull option (25/50 or 50/50)"""
        if option in self.available_bull_options:
            self.bull_option = option

    def check_win_condition(self, player_scores, player):
        """Check for exact finish (must hit exactly 0)"""
        return player_scores[player] == 0

    def process_shot(self, score, player_scores, player):
        """Process shot with bust rule (can't go below 0)"""
        new_score = player_scores[player] - score
        if new_score < 0:
            # Bust - score stays the same
            return player_scores
        player_scores[player] = new_score
        return player_scores
