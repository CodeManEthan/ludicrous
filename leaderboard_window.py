import tkinter as tk
from tkinter import ttk
from players import player_attr
from window_position import center_window
from debug_output import debug_print_empty_function_call


def determine_leaderboard_placements(game):
    # Create a list of players with their attributes
    players = []
    for player_number in range(1, game.number_players + 1):
        player_data = {
            "player_number": player_number,
            "name": player_attr(game, player_number, "name"),
            "score": player_attr(game, player_number, "score"),
            "wins": player_attr(game, player_number, "wins"),
            "in_game": player_attr(game, player_number, "in_game"),
            "round_out": player_attr(game, player_number, "round_out"),
        }
        players.append(player_data)

    # Define the sort key
    def sort_key(player):
        if player["in_game"]:
            # Players in game: prioritize score (descending), then player_number (ascending)
            return (0, -player["score"], -player["wins"], player["player_number"])
        else:
            # Players out of game: prioritize round_out (descending), wins (descending), then player_number (ascending)
            return (1, -player["round_out"], -player["wins"], player["player_number"])

    # Sort players using the defined sort key
    players.sort(key=sort_key)

    # Assign leaderboard ranks
    for rank, player in enumerate(players, start=1):
        player_number = player["player_number"]
        # Update the player's leaderboard rank
        player_attr(game, player_number, "leaderboard_rank", rank)


def click_close_button(game):
    game.leaderboard_window.destroy() 
    game.root.focus_set()       

def create_leaderboard_window(game):
    debug_print_empty_function_call(game)
    if not game.automation_active:
        game.leaderboard_window = tk.Toplevel()
        game.leaderboard_window.title("Leaderboard")
        game.leaderboard_window.geometry("1700x1000")

        # Hide leaderboard window
        game.leaderboard_window.withdraw()
        # Center leaderboard window relative to root window
        center_window(game.root, game.leaderboard_window, 1700, 1000)
        # Make leaderboard window a child of root window
        game.leaderboard_window.transient(game.root)
        # Set focus to leaderboard window
        game.leaderboard_window.focus_set()
        # Show leaderboard window
        game.leaderboard_window.deiconify()

        # Create and place title label
        title_label = tk.Label(game.leaderboard_window, text="Leaderboard", justify="center", font=("Helvetica", 20, "bold"))
        title_label.place(relx=0.5, rely=0.05, width=300, height=30, anchor="center")  # Centered title

        # Create and place close button
        close_button = ttk.Button(game.leaderboard_window, text="Close", command=lambda: click_close_button(game))
        close_button.place(relx=0.5, rely=0.93, anchor="center")
        
        # Create or modify the style for the button
        style = ttk.Style()

        # Generate a unique style name for this button if needed
        button_style_name = "CloseButton.TButton"

        # Configure the new style to adjust only the font size
        style.configure(button_style_name, font=("TkDefaultFont", 12))

        # Apply the custom style to the play button
        close_button.configure(style=button_style_name)

        # Create and place header labels
        if game.number_players > 75:
            num_full_columns = 4
        elif game.number_players > 50:
            num_full_columns = 3
        elif game.number_players > 25:
            num_full_columns = 2
        else:
            num_full_columns = 1

        # Create and place headers
        for i in range(num_full_columns):
            relx_value = 0.14 + (0.24*i)

            # Title frame
            title_frame = tk.Frame(game.leaderboard_window, width=400, height=30, borderwidth=2, relief="solid", bg="white")
            title_frame.place(relx=relx_value, rely=0.1, anchor="center")  # Place the frame in the window


            # Rank label
            rank_label = tk.Label(title_frame, text="Rank", font=("Helvetica", 12, "bold"), justify="center", bg="white")
            rank_label.place(relx=0.1, rely=0.5, anchor="center")

            # Name label
            name_label = tk.Label(title_frame, text="Name", font=("Helvetica", 12, "bold"), justify="center", bg="white")
            name_label.place(relx=0.3, rely=0.5, anchor="center")

            # Wins label
            wins_label = tk.Label(title_frame, text="Wins", font=("Helvetica", 12, "bold"), justify="center", bg="white")
            wins_label.place(relx=0.55, rely=0.5, anchor="center")

            # Rounds label
            rounds_label = tk.Label(title_frame, text="Rounds", font=("Helvetica", 12, "bold"), justify="center", bg="white" )
            rounds_label.place(relx=0.85, rely=0.5, anchor="center")

        

        # Create and place labels
        relx_increment = 0
        rely_value = 0.1
        rely_increment = 0.030

        for i in range(game.number_players):
            rank = i + 1

            for player_number in range(1, game.number_players + 1):
                if player_attr(game, player_number, "leaderboard_rank") == rank:
                    name = player_attr(game, player_number, "name")
                    wins = player_attr(game, player_number, "wins")
                    in_game = player_attr(game, player_number, 'in_game')
                    round_out = player_attr(game, player_number, 'round_out')
                    break

            # Determine background color based on `in_game`
            bg_color = "lightcoral" if not in_game else "white"  # Light red if `in_game` is False, otherwise white

            if i == 25 or i == 50 or i == 75:
                relx_increment += 1

            relx_value = 0.14 + (0.24*relx_increment)

            if i == 25 or i ==50 or i == 75:
                rely_value = 0.1

            rely_value += rely_increment
            
            # Title frame
            label_frame = tk.Frame(game.leaderboard_window, width=400, height=30, borderwidth=2, relief="solid", bg=bg_color)
            label_frame.place(relx=relx_value, rely=rely_value, anchor="center")  # Place the frame in the window

            # Rank label
            rank_label = tk.Label(label_frame, text=f"{rank}", font=("Helvetica", 11, "bold"), justify="center", bg=bg_color)
            rank_label.place(relx=0.1, rely=0.5, anchor="center")

            # Name label
            name_label = tk.Label(label_frame, text=f"{name}", font=("Helvetica", 11), justify="left", bg=bg_color)
            name_label.place(relx=0.3, rely=0.5, anchor="center")

            # Wins label
            wins_label = tk.Label(label_frame, text=f"{wins:,}", font=("Helvetica", 11), justify="center", bg=bg_color)
            wins_label.place(relx=0.55, rely=0.5, anchor="center")

            # Rounds label
            if round_out == 0:
                rounds = game.number_rounds
            else:
                rounds = round_out

            rounds_label = tk.Label(label_frame, text=f"{rounds:,}", font=("Helvetica", 11), justify="center", bg=bg_color)
            rounds_label.place(relx=0.85, rely=0.5, anchor="center")

        game.leaderboard_window.mainloop()
