import tkinter as tk
from tkinter import ttk
from players import create_player_instances
from window_position import center_window
from random_names import random_300_first_names
from players import generate_random_names
from players import assign_names_from_entries
from war_game_gui import setup_war_game_gui



def click_go_back(game):
    game.name_entry_window.destroy()

def click_start_button(game):
    # Create instances for players
    create_player_instances(game)

    # Assign player names from entries
    assign_names_from_entries(game)

    # Setup War Game GUI
    setup_war_game_gui(game)

    # Close startup window, names option window and name entry window
    game.name_entry_window.destroy()
    game.names_option_window.destroy()
    game.startup_window.destroy()

def create_widgets(game, window):
    rely_value = 0.09
    # Set x start position
    if game.number_players <= 10:
        relx_value = 0.5
    elif game.number_players <= 20:
        relx_value = 0.27
    elif game.number_players <= 30:
        relx_value = 0.2
    elif game.number_players <= 60:
        relx_value = 0.1
    elif game.number_players <= 70:
        relx_value = 0.075
    elif game.number_players <= 80:
        relx_value = 0.06
    elif game.number_players <= 90:
        relx_value = 0.05
    elif game.number_players <= 100:
        relx_value = 0.045

    # Set value to increment x by
    if game.number_players <= 10:
        relx_increment = 0
    elif game.number_players <= 20:
        relx_increment = 0.4
    elif game.number_players <= 30:
        relx_increment = 0.3
    elif game.number_players <= 40:
        relx_increment = 0.22
    elif game.number_players <=50:
        relx_increment = 0.18
    elif game.number_players <=60:
        relx_increment = 0.16
    elif game.number_players <= 70:
        relx_increment = 0.14
    elif game.number_players <= 80:
        relx_increment = 0.12
    elif game.number_players <= 90:
        relx_increment = 0.11
    elif game.number_players <= 100:
        relx_increment = 0.1

    # Create labels and entries
    for i in range(1, game.number_players + 1):
        # Create label with player number
        player_label = ttk.Label(window, text=f"Player: {i}:", font=("Helvetica", 8, "bold"), justify="right")
        player_label.place(relx=relx_value, rely=rely_value, anchor="e")

        # Create entry for the player
        player_entry= ttk.Entry(window, width=10)
        player_entry.place(relx=relx_value, rely=rely_value, anchor="w")

        # Store references to the player labels and entries with dynamic names
        setattr(window, f"player_{i}_label", player_label)
        setattr(window, f"player_{i}_entry", player_entry)

        # Increment the rely value for the next player
        rely_value += 0.07

        # Increment relx value for next column (multiples of 10)
        if game.number_players > 10:
            if i % 10 == 0:
                rely_value = 0.09
                relx_value += relx_increment

    # Create and place frame to hold buttons and info label
    frame = ttk.Frame(game.name_entry_window, width=300, height=60)
    frame.place(relx=0.5, rely=0.9, anchor="center")

    # Create buttons and info label
    start_game_button = ttk.Button(frame, text="Start Game", command=lambda: click_start_button(game))
    generate_names_button = ttk.Button(frame, text="Generate Names", command=lambda: generate_random_names(game, game.random_names))
    go_back_button = ttk.Button(frame, text="Go Back", command=lambda: click_go_back(game))
    info_label = ttk.Label(frame, text="Blank names will auto-generate.")

    # Place buttons and info label into frame
    go_back_button.place(relx=0.2, rely=0.4, anchor="center")
    generate_names_button.place(relx=0.5, rely=0.4, anchor="center")
    start_game_button.place(relx=0.8, rely=0.4, anchor="center")
    info_label.place(relx=0.5, rely=0.8, anchor="center")

def create_name_entry_gui(game):
    if game.is_application_active:
        # Create name entry window
        game.name_entry_window = tk.Toplevel()
        game.name_entry_window.title = "Assign Player Names"
        # Hide name entry window
        game.name_entry_window.withdraw()

        # Determine window width size based on number of players
        if game.number_players > 20:
            if game.number_players <= 70:
                width = (((game.number_players + 9) // 10) * 100) + 200
            else:
                width = (((game.number_players + 9) // 10) * 100) + 300
        else:
            width = 400

        height = 400
        game.name_entry_window.geometry(f"{width}x{height}")

        # Center startup window relative to root window
        center_window(game.root, game.name_entry_window, width, height)
        # Make startup window a child of root window
        game.name_entry_window.transient(game.root)
        # Set focus to startup window
        game.name_entry_window.focus_set()
        # Show name entry window
        game.name_entry_window.deiconify()

        # Retrieve list of random names
        game.random_names = random_300_first_names()

        # Create and place player labels and entries dynamically
        create_widgets(game, game.name_entry_window)