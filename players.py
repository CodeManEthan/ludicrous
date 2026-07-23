import random
import tkinter as tk
from random_names import random_300_first_names
from debug_output import (
    debug_print_separator,
    debug_print_players_data,
    debug_print_players_labels,
    debug_print_player_name_assignment,
    debug_print_player_attributes
)

# Function to create player instances with dynamic decks
def create_player_instances(game):
    for i in range(1, game.number_players + 1):
        player_key = i  # This will be the key, e.g., '1'
        # Initialize the player's data (e.g., name, deck, reserve_deck)
        game.players_data[player_key] = {
            'name': "",  # Initially empty name, can be filled later
            'deck': [],  # Empty deck to start
            'reserve_deck': [],  # Empty reserve_deck to start
            'card': (), # Empty Tuple for player card
            'score': 0,  # score to track player score
            'wins': 0,  # wins to track player wins
            'in_round': True, # Tells if player is active in the round
            'in_game' : True, # Tells if player is active in the game
            'round_out': 0, # Tells which round the player was taken out of the game
            'leaderboard_rank': 0,   
        }
        game.players_labels[player_key] = {
            'name': None,
            'card': None,
            'score': None,
            'wins': None,
            'frame': None,
        }

    debug_print_separator(game)
    debug_print_players_data(game)
    debug_print_players_labels(game)
    debug_print_separator(game)

# Get or assign player attribute
def player_attr(game, player_number, attribute, value=None):
    if value is not None:
        # Set the value if provided
        game.players_data[player_number][attribute] = value
    return game.players_data[player_number][attribute]

# Get or assign player attribute
def player_label_attr(game, player_number, attribute, value=None):
    if value is not None:
        # Set the value if provided
        game.players_labels[player_number][attribute] = value
    return game.players_labels[player_number][attribute]

# Assign default names (Player 1, Player 2, etc.)
def assign_default_player_names(game):
    debug_print_separator(game)

    for i in range(1, game.number_players + 1):
        player_number = i
        player_name = f"Player {i}"

        # Assign default player name
        player_attr(game, player_number, 'name', player_name)

        # Assign players place in the leaderboard
        player_attr(game, player_number, 'leaderboard_rank', player_number)

        # Print each player's key and assigned name
        debug_print_player_name_assignment(game, player_number, player_name)
    
    # Print the updated players_data dictionary for verification
    debug_print_players_data(game)
    debug_print_separator(game)

def assign_random_player_names(game):
    debug_print_separator(game)

    game.random_names = random_300_first_names()
    random.shuffle(game.random_names)

    for i in range(1, game.number_players + 1):
        player_number = i
        player_name = game.random_names[i - 1]
        
        # Assign random player name
        player_attr(game, player_number, 'name', player_name)

        # Assign players place in the leaderboard
        player_attr(game, player_number, 'leaderboard_rank', player_number)
        
        # Print each player's key and assigned name
        debug_print_player_name_assignment(game, player_number, player_name)

    # Print the updated players_data dictionary for verification
    debug_print_players_data(game)
    debug_print_separator(game)

# Generate random names for players
def generate_random_names(game, names):
    # Get a shuffled list of names
    random.shuffle(names)
    
    # Iterate through player entries and assign names
    for i in range(1, game.number_players + 1):
        if game.is_application_active:
            # Get the corresponding entry widget dynamically
            entry = getattr(game.name_entry_window, f"player_{i}_entry", None)
            if entry:
                # Assign a name from the shuffled list
                entry.delete(0, tk.END)  # Clear any existing text
                entry.insert(0, names[i - 1])  # Insert the name

# Retrieves names from entry widgets and assigns them to the respective players in players_data.
def assign_names_from_entries(game):    
    for i in range(1, game.number_players + 1):
        # Get the corresponding entry widget dynamically
        entry = getattr(game.name_entry_window, f"player_{i}_entry", None)
        if entry:
            # Retrieve the text from the entry widget
            player_name = entry.get().strip()  # Strip any extra whitespace

            if not player_name:
                player_name = f"Player {i}"
            
            # Assign the name to the respective player in players_data
            player_number = i
            player_attr(game, player_number, 'name', player_name)

            # Assign players place in the leaderboard
            player_attr(game, player_number, 'leaderboard_rank', player_number)

            # Print each player's key and assigned name
            debug_print_player_name_assignment(game, player_number, player_name)

        # Print the updated players_data dictionary for verification
        debug_print_players_data(game)
        debug_print_separator(game)


# Example of accessing the deck for player 1
# game.players_data["player_1"]['deck'] = [(1, "Hearts"), (8, "Spades")]
# game.players_data["player_1"]['reserve_deck'] = [(10, "Clubs")]

# Now you can access the deck for player 1 dynamically
# print(game.players_data["player_1"]['deck'])  # Output: [(1, "Hearts"), (8, "Spades")]
# print(game.players_data["player_1"]['reserve_deck'])  # Output: [(10, "Clubs")]


def print_player_attributes(game, attribute):
    debug_print_player_attributes(game, attribute)
