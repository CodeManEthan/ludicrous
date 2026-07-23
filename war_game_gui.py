import tkinter as tk
from tkinter import ttk
from window_position import center_window_to_display
from object_scaling import get_adjusted_font_size
from player_frames import create_player_objects
from player_frames import place_player_frames
from war_game_logic import play_round
from war_game_logic import populate_deck
from war_game_logic import shuffle_and_split_deck
from war_game_logic import toggle_automation
from war_game_logic import increase_speed
from war_game_logic import decrease_speed
from rules_window import create_rules_window
from leaderboard_window import create_leaderboard_window
from debug import set_values_2_for_testing
from debug_output import debug_print_gui_setup_complete



def create_war_game_gui(game):
    # Create the Tkinter root window
    game.root = tk.Tk()
    game.root.title("War Card Game")
    # Hide root window
    game.root.withdraw()

    # Get screen width and height
    game.display_width = game.root.winfo_screenwidth()
    game.display_height = game.root.winfo_screenheight() - 80

    # Set window size to default size and center to display
    center_window_to_display(game.root, game.display_width, (game.display_height))

    # Show root window
    game.root.deiconify()

    # Focus root window
    game.root.focus_set()

    # Option to exit full-screen mode
    def exit_fullscreen(event):
        game.root.attributes("-fullscreen", False)

    game.root.bind("<Escape>", exit_fullscreen)

    # Get font sizes adjusted for display size
    game.result_label_font_size = get_adjusted_font_size(game.display_width, game.display_height, 16)
    game.name_label_font_size = get_adjusted_font_size(game.display_width, game.display_height, 11)
    game.score_label_font_size = get_adjusted_font_size(game.display_width, game.display_height, 8)
    game.play_button_font_size = get_adjusted_font_size(game.display_width, game.display_height, 10)


def setup_war_game_gui(game):
    # Focus root window
    game.root.focus_set()

    # Adjust result label font size based on number of rows needed for players
    if game.number_players < 20:
        game.result_label_font_size = get_adjusted_font_size(game.display_width, game.display_height, 20)

    # Calculate dynamic positions for result label and play button
    result_label_rely = 40 / game.display_height  # Adjust to keep relative distance from the top
    if game.number_players > 20:
        play_button_rely = 70 / game.display_height  # Adjust based on result label position
    else:
        play_button_rely = 100 / game.display_height  # Adjust based on result label position

    # Create and place result label and play round button
    game.result_label = tk.Label(game.root, text="Welcome to War!", font=("Helvetica", game.result_label_font_size))
    game.play_button = ttk.Button(game.root, text="Play Round!", command=lambda: play_round(game))


    # Create or modify the style for the button
    style = ttk.Style()

    # Generate a unique style name for this button if needed
    button_style_name = "PlayButton.TButton"

    # Configure the new style to adjust only the font size
    style.configure(button_style_name, font=("TkDefaultFont", game.play_button_font_size))
    
    if game.number_players < 20:
        game.play_button['padding'] = (10, 5)

        # Determine font size for play button relative to window size
        game.play_button_font_size = get_adjusted_font_size(game.display_width, game.display_height, 12)

        # Apply the custom style to the play button
        game.play_button.configure(style=button_style_name)

    game.result_label.place(relx=0.5, rely=result_label_rely, anchor="center")
    game.play_button.place(relx=0.5, rely=play_button_rely, anchor="center")

    # Create and place the rules button
    game.rules_button = ttk.Button(game.root, text="Game Rules", command= lambda: create_rules_window(game))
    game.rules_button.place(relx=0.95, rely=result_label_rely, anchor="center")
    game.rules_button.configure(style=button_style_name)

    # Create and place the automate button
    game.automation_button = ttk.Button(game.root, text="Automate", command=lambda: toggle_automation(game))
    game.automation_button.place(relx=0.9, rely=result_label_rely, anchor="center")
    game.automation_button.configure(style=button_style_name)

    # Create faster automation and slower automation buttons
    game.faster_button = ttk.Button(game.root, text="Faster", command=lambda: increase_speed(game))
    game.slower_button = ttk.Button(game.root, text="Slower", command=lambda: decrease_speed(game))
    game.slower_button.place(relx=0.88, rely=result_label_rely + 0.03, anchor="center")
    game.faster_button.place(relx=0.92, rely=result_label_rely + 0.03, anchor="center")

    # Create and place round counter lable
    game.round_counter_label = tk.Label(game.root, text="Rounds: 0", font="Helvetica, 12")
    game.round_counter_label.place(relx=0.7, rely=result_label_rely, anchor="center")

    # Create and place leaderboard button
    game.leaderboard_button = ttk.Button(game.root, text="Leaderboard", command=lambda: create_leaderboard_window(game))
    game.leaderboard_button.place(relx=0.85, rely=result_label_rely, anchor="center")
    game.leaderboard_button.configure(style=button_style_name)

    debug_print_gui_setup_complete(game)

    # If for testing then add players to players in game list and players in round dictionary
    if game.is_application_active and game.is_testing:
        set_values_2_for_testing(game)
    
    # Dynamically create player name, card, and score labels
    create_player_objects(game)

    # Dynamically place player name, card, and score labels
    place_player_frames(game)

    # Populate deck
    populate_deck(game)

    # Shuffle and split deck evenly amongst players
    shuffle_and_split_deck(game)
