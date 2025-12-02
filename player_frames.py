import tkinter as tk
from tkinter import ttk
from tkinter import font
import math
from object_scaling import get_scaled_object_height_for_vertical_fit
from object_scaling import get_frame_size_for_objects_fit
from object_scaling import get_distance_from_object_to_window_top
from players import player_label_attr
from players import player_attr

# Create player labels, place labels in player frame and store all in player labels dictionary
def create_player_objects(game):
    if game.is_terminal_active:
        print(f"\nNumber of players: {game.number_players}")

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

    print("Player Frame Height: " + str(game.player_frame_height))

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
        if game.is_terminal_active:
            print(f"Added labels for player_{i}:")
            print(f"  Frame: {game.players_labels[i]['frame']}")
            print(f"  Name Label: {game.players_labels[i]['name']}")
            print(f"  Card Label: {game.players_labels[i]['card']}")
            print(f"  Score Label: {game.players_labels[i]['score']}")
            print(f"  Wins Label: {game.players_labels[i]['wins']}")
    
    # Make root window fullscreen
    game.root.attributes('-fullscreen', True)

    # Print the entire players_labels dictionary for verification
    if game.is_terminal_active:
        print("\nUpdated Players Labels Dictionary:")
        for player, labels in game.players_labels.items():
            print(f"{player}: {labels}")

def place_player_frames(game):
    print("\nPlace Player Frames:")
    print("Remove player frames for players not in game:")
    print(f"Players Out Of Game:")
    print(game.players_out_game)

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
                print(f"Player {player_number} frame destroyed.")

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

    if game.is_terminal_active:
        print("\nTable Frame Width: " + str(game.table_frame_width))
        print("Table Frame Height: " + str(game.table_frame_height))
        print("Player Frame Width: " + str(game.player_frame_width))
        print("Player Frame Height: " + str(game.player_frame_height))
        print("Number players in round: " + str(game.number_players_in_round))
        print("Number players in game: " + str(game.number_players_in_game))
        print("Number Columns: " + str(num_columns))
        print("Number Rows: " + str(num_rows))
        print("Max frames per row: " + str(max_frames_per_row))
        print(f"Number Players In Round Divided By Max Frames Per Row: {math.ceil(game.number_players_in_round / max_frames_per_row)}")
        

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

    print("\nPlace card labels in table frame: ")
    # Place card labels in table frame dynamically
    for player_number in game.players_in_round: 
        print(f"Player {player_number}")
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
        if game.is_terminal_active:
            print(f"Placed frame for {player_number}:")
            print(f"  Frame Object: {game.players_labels[player_number]['frame']}")
            print(f"  Relative X Position: {relx_value}")
            print(f"  Relative Y Position: {rely_value}")

    # Print confirmation if all labels were placed
    if game.is_terminal_active:
        print("\nAll player frames have been placed.")