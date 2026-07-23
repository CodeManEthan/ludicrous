import tkinter as tk
from tkinter import ttk
from tkinter import font
import math
from object_scaling import get_scaled_object_height_for_vertical_fit
from object_scaling import get_frame_size_for_objects_fit
from object_scaling import get_distance_from_object_to_window_top
from players import player_label_attr
from players import player_attr
from debug_output import (
    debug_print_number_of_players,
    debug_print_player_frame_height,
    debug_print_player_frame_creation,
    debug_print_players_labels,
    debug_print_place_player_frames_start,
    debug_print_player_frame_destroyed,
    debug_print_table_frame_dimensions,
    debug_print_place_frames_in_table,
    debug_print_player_frame_placement,
    debug_print_all_frames_placed
)

# Create player labels, place labels in player frame and store all in player labels dictionary
def create_player_objects(game):
    debug_print_number_of_players(game)

    # Ensure that all pending layout updates are processed
    game.root.update_idletasks()

    # Calculate distance from the bottom of the play button to the top of the window
    game.top_height = get_distance_from_object_to_window_top(game.root, game.play_button)
    game.top_height += 10 # Add spacing

    # Create frame to hold labels
    game.table_frame = tk.Frame(game.root) #borderwidth=2, relief="solid")

    # Create a style object
    name_style = ttk.Style()
    score_style = ttk.Style()
    name_style.configure("Custom1.TLabel", font=("Helvetica", game.name_label_font_size, "bold"), justify="center")
    score_style.configure("Custom2.TLabel", font=("Helvetica", game.score_label_font_size), justify="center")

    # Get the name label height and score label height
    name_label_font = font.Font(family="Helvetica", size=game.name_label_font_size)
    score_label_font = font.Font(family="Helvetica", size=game.score_label_font_size)

    game.name_label_height = name_label_font.metrics("linespace")
    game.score_label_height = score_label_font.metrics("linespace")

    # Set the player frame width
    game.player_frame_width = game.card_width
    # Calculate the player frame height based on fitting 5 rows of cards with extra spacing for result label and play button
    player_frame_height = game.card_height + game.name_label_height + (game.score_label_height*2) + 35
    game.player_frame_height = get_scaled_object_height_for_vertical_fit(5, player_frame_height, 10, game.top_height, game.display_height)
    # Adjust the player frame height to include name label, score label and win label.

    debug_print_player_frame_height(game)

    for i in range(1, game.number_players + 1):
        # Create player frame and labels
        player_frame = tk.Frame(game.table_frame, width=game.player_frame_width, height=game.player_frame_height) #borderwidth=2, relief="solid")
        player_name_label = ttk.Label(player_frame, text=game.players_data[i]['name'], style="Custom1.TLabel")
        player_card_label = ttk.Label(player_frame, image=game.card_back_images.get(game.deck_color.lower()))
        player_score_label = ttk.Label(player_frame, text="Cards:", style="Custom2.TLabel")
        player_wins_label = ttk.Label(player_frame, text="Wins: 0", style="Custom2.TLabel")
        
        # Add labels to the players labels dictionary
        game.players_labels[i]['frame'] = player_frame
        game.players_labels[i]['name'] = player_name_label
        game.players_labels[i]['card'] = player_card_label
        game.players_labels[i]['score'] = player_score_label
        game.players_labels[i]['wins'] = player_wins_label

        # Place player labels inside player frame
        player_name_label.place(relx=0.5, rely=0.05, anchor="center")
        player_card_label.place(relx=0.5, rely=0.47, anchor="center")
        player_score_label.place(relx=0.5, rely=0.87, anchor="center")
        player_wins_label.place(relx=0.5, rely=0.95, anchor="center")

        # Print confirmation for each player
        debug_print_player_frame_creation(game, i)
    
    # Make root window fullscreen
    game.root.attributes('-fullscreen', True)

    # Print the entire players_labels dictionary for verification
    debug_print_players_labels(game)

def place_player_frames(game):
    debug_print_place_player_frames_start(game)

    # Set index int for players out game list
    i = -1

    # Remove player frames for players not in game
    for player_number, taken_out in game.players_out_game:
        i += 1

        if not taken_out:
            game.players_out_game[i] = (player_number, True)
            player_frame = player_label_attr(game, player_number, 'frame')
            if player_frame.winfo_ismapped():
                player_frame.destroy()
                debug_print_player_frame_destroyed(game, player_number)

    # Remove player frames for players not in round
    for player_number in game.players_in_game:
        in_round = player_attr(game, player_number, 'in_round')
        if not in_round:
            player_frame = player_label_attr(game, player_number, 'frame')
            if player_frame.winfo_ismapped():
                player_frame.place_forget()


    # Constants for player frame dimensions and spacing
    spacing = 5  # Space between frames

    # Set max frames per row
    if game.number_players_in_round > 75:
        max_frames_per_row = 20
    elif game.number_players_in_round > 50:
        max_frames_per_row = 15
    elif game.number_players_in_round > 25:
        max_frames_per_row = 10
    else:
        max_frames_per_row = 5

    # Calculate number of rows
    num_rows = math.ceil(game.number_players_in_round / max_frames_per_row)

    # Calculate number of columns
    if game.number_players_in_round < 5:
        num_columns = game.number_players_in_round
    else:
        num_columns = max_frames_per_row

    # Calculate width and height for table frame
    game.table_frame_width, game.table_frame_height = get_frame_size_for_objects_fit(num_columns, num_rows, game.player_frame_height, game.player_frame_width, spacing, 20)

    debug_print_table_frame_dimensions(game, num_columns, num_rows, max_frames_per_row)
        

    # Adjust table frame width and height
    game.table_frame.config(width=game.table_frame_width, height=game.table_frame_height)

    # Determine table frame rely
    if num_rows == 5:
        table_rely = 0.53
    else:
        table_rely = 0.5

    # Place table frame in center of window
    game.table_frame.place(relx=0.5, rely=table_rely, anchor="center")

    # Set integer for number of label
    i = -1

    debug_print_place_frames_in_table(game)
    # Place card labels in table frame dynamically
    for player_number in game.players_in_round: 
        # Incease number of label by one for each iteration
        i += 1

        # Calculate row and column positions
        row = i // max_frames_per_row
        col = i % max_frames_per_row

        # Calculate the number of players in the current row
        players_in_current_row = (
            max_frames_per_row
            if row < num_rows - 1
            else game.number_players_in_round % max_frames_per_row or max_frames_per_row
        )

        # Calculate offset to center frames in the current row
        total_row_width = players_in_current_row * (game.player_frame_width + spacing) - spacing
        row_offset = (game.table_frame_width - total_row_width) / 2

        # Calculate relative x and y positions for the player frame
        relx_value = (row_offset + col * (game.player_frame_width + spacing) + game.player_frame_width / 2) / game.table_frame_width
        rely_value = (row + 0.5) / num_rows

        # Retrieve player frame
        player_frame = player_label_attr(game, player_number, 'frame')
        # Place player frame
        player_frame.place(relx=relx_value, rely=rely_value, anchor="center")

        # Debugging output
        debug_print_player_frame_placement(game, player_number, relx_value, rely_value)

    # Print confirmation if all labels were placed
    debug_print_all_frames_placed(game)
