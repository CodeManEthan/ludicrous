import tkinter as tk
from window_position import center_window_to_display
from war_game_logic import set_players_in_game
from war_game_logic import reset_players_in_round


def set_values_for_testing(game):
    game.number_players = 26
    game.number_active_players = game.number_players
    game.number_players_in_game = game.number_players
    game.number_players_in_round = game.number_players
    game.number_decks = 1
    game.deck_color = "Red"
    game.is_default_names = True
    
def set_values_2_for_testing(game):
    set_players_in_game(game)
    reset_players_in_round(game)

def create_war_game_gui_for_testing(game):
    game.root = tk.Tk()
    game.root.title("War Card Game")
    # Hide root window
    game.root.withdraw()

    # Get screen width and height
    game.root.screen_width = game.root.winfo_screenwidth()
    game.root.screen_height = game.root.winfo_screenheight()

    # Set window size to default size and center to display
    center_window_to_display(game.root, 800, 600)

    # Show root window
    game.root.deiconify()

    # Option to exit full-screen mode
    def exit_fullscreen(event):
        game.root.attributes("-fullscreen", False)

    game.root.bind("<Escape>", exit_fullscreen)