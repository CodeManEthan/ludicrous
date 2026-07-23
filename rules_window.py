import tkinter as tk
from tkinter import ttk
from window_position import center_window
from debug_output import debug_print_empty_function_call

def create_rules_window(game):
    if not game.automation_active:
        game.rules_window = tk.Toplevel()
        game.rules_window.title("Game Rules")

        # Hide the game rules window
        game.rules_window.withdraw()
        # Set size of startup window
        game.rules_window.geometry("800x600")
        # Center startup window relative to root window
        center_window(game.root, game.rules_window, 800, 600)
        # Make startup window a child of root window
        game.rules_window.transient(game.root)
        # Show startup window
        game.rules_window.deiconify()

        game.game_rules = """
War Card Game Rules:

1. Shuffle the Deck: At the start of the game, shuffle the deck.
2. Card Distribution: All players are assigned an equal number of cards. Any leftover cards are discarded.
3. Playing a Round: Each player draws the top card from their deck and places it on the table. 
    The player with the highest-ranked card wins the round.
4. Winning a Round: The round winner collects all cards from the table and places them into their reserve deck.
5. Using the Reserve Deck: When a player runs out of cards in their deck, they shuffle their reserve deck 
    and use it as their new deck.
6. Game End: The winner is the last player remaining with cards. The game ends when all but one player have 
    no cards left.
7. Tiebreaker Rules: If multiple players have the highest-ranked card, a tiebreaker is required. 
   
Tiebreaker Rules:
1. Each player involved in the tiebreaker draws three cards and places them on the table, then plays 
    the fourth card.
2. If multiple players still have the highest-ranked card after the tiebreaker, they compete in another tiebreaker.
3. If any player does not have enough cards to participate in the tiebreaker, they forfeit and place all of 
    their remaining cards on the table.
4. If only one player has enough cards to play the tiebreaker, that player is declared the winner.
5. If none of the players have enough cards to participate in the tiebreaker, all players place all of their 
    remaining cards on the table and play their final card.
6. If all players have zero cards to play a tiebreaker, all cards on the table are shuffled and distributed 
    equally among the players in the tie. Any leftover cards are given to players at random, with no player 
    receiving more than one extra card.
    """

        debug_print_empty_function_call(game)

        # Create the text widget to display the rules
        text_widget = tk.Text(game.rules_window, wrap=tk.WORD, height=20, width=70)
        
        # Pack the text widget into the window
        text_widget.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        # Insert the game rules into the text widget
        text_widget.insert(tk.END, game.game_rules)

        # Configure the tag for font to be applied to all text
        text_widget.tag_configure("all_text", font=("Helvetica", 12))

        # Apply the "all_text" tag to the entire text widget
        text_widget.tag_add("all_text", "1.0", "end")

        # Configure the tag for bold text
        text_widget.tag_configure("bold", font=("Helvetica", 12, "bold"))

        # Add tags to the text for the rule titles to make them bold
        text_widget.tag_add("bold", "2.0", "2.23")  # "War Card Game Rules:"
        text_widget.tag_add("bold", "4.0", "4.20")  # "1. Shuffle the Deck:"
        text_widget.tag_add("bold", "5.0", "5.21")  # "2. Card Distribution:"
        text_widget.tag_add("bold", "6.0", "6.19")  # "3. Playing a Round:"
        text_widget.tag_add("bold", "8.0", "8.19")  # "4. Winning a Round:"
        text_widget.tag_add("bold", "9.0", "9.26")  # "5. Using the Reserve Deck:"
        text_widget.tag_add("bold", "11.0", "11.12")   # "6. Game End:"
        text_widget.tag_add("bold", "13.0", "13.20")  # "7. Tiebreaker Rules:"
        text_widget.tag_add("bold", "15.0", "15.17")  # "Tiebreaker Rules:"
        text_widget.tag_add("bold", "16.0", "16.2")  # "1."
        text_widget.tag_add("bold", "18.0", "18.2")  # "2."
        text_widget.tag_add("bold", "19.0", "19.2")  # "3."
        text_widget.tag_add("bold", "21.0", "21.2")  # "4."
        text_widget.tag_add("bold", "22.0", "22.2")  # "5."
        text_widget.tag_add("bold", "24.0", "24.2")  # "6."


        # Disable editing so that it's just for display
        text_widget.config(state=tk.DISABLED)

        # Add a button to close the window
        close_button = ttk.Button(game.rules_window, text="Close", command=game.rules_window.destroy)
        close_button.pack(pady=10)

        # Start the Tkinter main loop for this window
        game.rules_window.mainloop()
