from classes import Main_Game
import tkinter as tk
from war_game_gui import create_war_game_gui
from war_game_gui import setup_war_game_gui
from card_images import find_card_image_path
from card_images import load_card_face_images
from card_images import load_card_back_images
from war_start_window import create_startup_window_gui
from debug import set_values_for_testing
from players import create_player_instances
from players import assign_default_player_names
from players import assign_random_player_names

# Create game class instance
game = Main_Game()

# Control terminal and application use (For Debugging)
game.is_application_active = True
game.is_terminal_active = False
game.is_testing = False

# Set values for testing
if game.is_testing:
    set_values_for_testing(game)

# Create War Game root window
create_war_game_gui(game)

# Hide window if not application active
if not game.is_application_active:
    game.root.withdraw()

# Construct path to card images folder
find_card_image_path(game)

# Store card face images and card back images in card images dictionary
load_card_face_images(game)
load_card_back_images(game)

# Create startup window GUI
if game.is_application_active:
    create_startup_window_gui(game)

# Close startup window if for testing
if game.is_testing:
    game.startup_window.destroy()

if game.is_testing:
    # Create player instances and store player names
    create_player_instances(game)
    if game.is_default_names:
        assign_default_player_names(game)
    else:
        assign_random_player_names(game)

# If for testing setup War Game GUI (Else: setup in war startup window)
if game.is_application_active and game.is_testing:
    setup_war_game_gui(game)

if game.is_application_active:
    # Start main event loop
    game.root.mainloop()