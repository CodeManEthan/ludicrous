class Main_Game:
    def __init__(self):
        self.root = None
        self.startup_window = None
        self.names_option_window = None
        self.name_entry_window = None
        self.rules_window = None
        self.leaderboard_window = None

        self.is_terminal_active = False
        self.is_application_active = False
        self.is_testing = False
        self.is_default_names = True
        self.automation_active = False
        self.is_faster = True
        self.is_game_over = False

        self.random_names = []
        self.players_data = {} # Dictionary containing all player attributes
        self.players_labels = {} # Dictionary containing all player labels

        self.display_width = 0
        self.display_height = 0
        
        self.deck = [] # List containing all cards (tuple) (rank, suit)
        self.table = [] # List containing all cards on the table (tuple) (rank, suit)
        self.players_in_game = [] # List containing all players in game (int) (Player Number)
        self.players_out_game = [] # List containing all players with zero cards (int) (Player Number)
        self.players_in_round = {} # Dictionary containing all players (int) and their player card (tuple) (rank, suit)
        self.players_in_draw = []
        self.players_in_tiebreaker = []
        self.number_players = 0 # Total number of players (int)
        self.number_decks = 0 # Total number of decks (int)
        self.number_players_in_game = 0 # Total number of players in game (int)
        self.number_players_in_round = 0 # Total number of players in round (int)
        self.highest_rank = 0 # Highest card rank in a game round (int)
        self.tiebreaker_type = "" # String represents the type of tiebreaker being played.

        self.round_winner = 0 # Round winning player's player number (int)
        self.game_winner = [] # Game winning player's player number (int)
        self.is_tie_round = False # Boolean tells if round is a tie
        self.had_tie_round = False # Boolean tells if a round had a tie
        self.is_tie_game = False # Boolean tells if game is a tie

        self.card_images = {}
        self.card_back_images = {}
        self.card_table_image = []
        self.card_image_path = ""
        self.deck_color = ""

        self.game_rules = """"""
        self.automation_speed = 1000
        self.number_rounds = 0

        self.card_width = 100
        self.card_height = 140
        self.table_frame_width = 0
        self.table_frame_height = 0
        self.player_frame_width = 0
        self.player_frame_height = 0
        self.name_label_height = 0
        self.score_label_height = 0
        self.top_height = 0

        self.result_label = None
        self.play_button = None
        self.table_frame = None
        self.reset_button = None
        self.start_button = None
        self.rules_button = None
        self.automation_button = None
        self.faster_button = None
        self.slower_button = None
        self.round_counter_label = None
        self.leaderboard_button = None

        self.result_label_font_size = 0
        self.name_label_font_size = 0
        self.score_label_font_size = 0
        self.play_button_font_size = 10
