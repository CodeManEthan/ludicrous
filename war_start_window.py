import tkinter as tk
from tkinter import ttk
from window_position import center_window
from name_entry_window import create_name_entry_gui
from players import create_player_instances
from players import assign_default_player_names
from war_game_logic import set_players_in_game
from war_game_logic import reset_players_in_round
from war_game_gui import setup_war_game_gui


def click_start_button(game):
    # create player instances
    create_player_instances

    # assign default names for players
    assign_default_player_names(game)

    # close start window & assign player names option window
    game.names_option_window.destroy()
    game.startup_window.destroy()

    # Setup war game GUI
    setup_war_game_gui(game)

def create_assign_player_names_option_window(game):
    if game.is_application_active:
        # Create names option window
        game.names_option_window = tk.Toplevel()
        game.names_option_window.title = "Game Settings"
        # Hide names option window
        game.names_option_window.withdraw()
        # Set window size
        game.names_option_window.geometry("300x200")
        # Center startup window relative to root window
        center_window(game.root, game.names_option_window, 300, 200)
        # Make startup window a child of root window
        game.names_option_window.transient(game.root)
        # Set focus to startup window
        game.names_option_window.focus_set()

        # Show names option window
        game.names_option_window.deiconify()

        # Create widgets
        question_label = ttk.Label(game.names_option_window, text="Would you like to assign.\nnames for your players?", justify="center", font=("Helvetica", 12, "bold"))
        yes_label = ttk.Label(game.names_option_window, text="Yes", justify="center", font=("Helvetica", 10, "bold"))
        no_label = ttk.Label(game.names_option_window, text="No", justify="center", font=("Helvetica", 10, "bold"))
        assign_names_button = ttk.Button(game.names_option_window, text="Assign", command=lambda: create_name_entry_gui(game))
        start_game_button = ttk.Button(game.names_option_window, text="Start Game", command=lambda: click_start_button(game))

        # Place widgets
        question_label.place(relx=0.5, rely=0.2, anchor="n")
        yes_label.place(relx=0.3, rely=0.5, anchor="n")
        assign_names_button.place(relx=0.3, rely=0.6, anchor="n")
        no_label.place(relx= 0.7, rely=0.5, anchor="n")
        start_game_button.place(relx=0.7, rely=0.6, anchor="n")
    

def click_continue_button(game, number_players_dropdown, number_decks_dropdown, deck_color_dropdown):
    game.number_players = int(number_players_dropdown.get())
    game.number_players_in_game = game.number_players
    game.number_players_in_round = game.number_players
    game.number_decks = int(number_decks_dropdown.get())
    game.deck_color = deck_color_dropdown.get()

    # Create player instances
    create_player_instances(game)

    # Add players to players in game list
    set_players_in_game(game)

    # Add players to players in round dictionary
    reset_players_in_round(game)

    # Open assign player names option window
    create_assign_player_names_option_window(game)


def click_quit_game_button(game):
    game.root.destroy()  # Destroy the parent window
    game.startup_window.destroy()  # Destroy the child window


def create_startup_window_gui(game):
    if game.is_application_active:
        # Create startup window
        game.startup_window = tk.Toplevel()
        game.startup_window.title = "Game Settings"
        # Hide startup window
        game.startup_window.withdraw()
        # Set size of startup window
        game.startup_window.geometry("400x300")
        # Center startup window relative to root window
        center_window(game.root, game.startup_window, 400, 300)
        # Make startup window a child of root window
        game.startup_window.transient(game.root)
        # Set focus to startup window
        game.startup_window.focus_set()
        # Show startup window
        game.startup_window.deiconify()

        # Close both parent and child when the child window is closed
        def close_both():
            game.root.destroy()  # Destroy the parent window
            game.startup_window.destroy()  # Destroy the child window

        # Bind the close event of the child window
        game.startup_window.protocol("WM_DELETE_WINDOW", close_both)

        # CREATE WIDGETS

        # Create number players label and dropdown
        # Create values for number players dropdown
        number_players_options = []

        for i in range(2, 101):
            number_players_options.append(i)

        number_players_dropdown = ttk.Combobox(game.startup_window, value=number_players_options, state="readonly", width=10)
        number_players_label = ttk.Label(game.startup_window, text="Players:", justify="center", font=("Helvetica", 12, "bold"))   
        number_players_dropdown.set("2")     

        # Create number decks label and dropdown
        number_decks_options = []

        for i in range(1, 1001):
            number_decks_options.append(i)

        number_decks_dropdown = ttk.Combobox(game.startup_window, value=number_decks_options, state="readonly", width=10)
        number_decks_label = ttk.Label(game.startup_window, text="Decks:", justify="center", font=("Helvetica", 12, "bold"))
        number_decks_dropdown.set("1")

        # Create deck color label and dropdown
        deck_color_options = ["Black", "Blue", "Green", "Orange", "Purple", "Red"]
        deck_color_dropdown = ttk.Combobox(game.startup_window, values=deck_color_options, state="readonly", width=10)
        deck_color_label = ttk.Label(game.startup_window, text="Deck.\nColor:", justify="center", font=("Helvetica", 12, "bold"))
        deck_color_dropdown.set("Red")

        # Create start button and quit button
        continue_button = ttk.Button(
            game.startup_window, text="Continue", 
            command=lambda: click_continue_button(game, number_players_dropdown, number_decks_dropdown, deck_color_dropdown)
        )
        quit_button = ttk.Button(game.startup_window, text="Quit", command=lambda: click_quit_game_button)

        # PLACE WIDGETS
        number_players_label.place(relx=0.25, rely=0.075, anchor="n")
        number_players_dropdown.place(relx=0.25, rely=0.2, anchor="center")
        number_decks_label.place(relx=0.5, rely=0.075, anchor="n")
        number_decks_dropdown.place(relx=0.5, rely=0.2, anchor="center")
        deck_color_label.place(relx=0.75, rely=0.025, anchor="n")
        deck_color_dropdown.place(relx=0.75, rely=0.2, anchor="center")
        quit_button.place(relx=0.4, rely=0.85, anchor="center")
        continue_button.place(relx=0.6, rely=0.85, anchor="center")
        
        # Function to adjust number_decks_dropdown
        def adjust_number_decks(event):
            selected_players = int(number_players_dropdown.get())
            if selected_players > 52:
                new_decks_options = [i for i in range(2, 1001)]
                current_deck_value = int(number_decks_dropdown.get())
                number_decks_dropdown["values"] = new_decks_options
                if current_deck_value == 1:
                    number_decks_dropdown.set("2")
            else:
                number_decks_dropdown["values"] = number_decks_options

        # Bind the adjustment function to number_players_dropdown
        number_players_dropdown.bind("<<ComboboxSelected>>", adjust_number_decks)