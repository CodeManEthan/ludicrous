"""
Debug Output Module for War Card Game

This module centralizes all debug/test print statements from the main game logic.
All debug functions check game.is_terminal_active before printing.

Usage:
    from debug_output import debug_print, debug_print_players_data
    debug_print(game, "Some message")
    debug_print_players_data(game)
"""

# ============================================================================
# GENERAL DEBUG OUTPUT
# ============================================================================

def debug_print(game, message):
    """Print a simple debug message if terminal is active."""
    if game.is_terminal_active:
        print(message)


def debug_print_separator(game):
    """Print a blank line for spacing."""
    if game.is_terminal_active:
        print()


# ============================================================================
# PLAYER DATA DEBUG OUTPUT
# ============================================================================

def debug_print_players_data(game):
    """Print the entire players_data dictionary."""
    if game.is_terminal_active:
        print("\nPlayers Data Dictionary:")
        for key, value in game.players_data.items():
            print(f"{key}: {value}")


def debug_print_players_labels(game):
    """Print the entire players_labels dictionary."""
    if game.is_terminal_active:
        print("\nPlayers Labels Dictionary:")
        for key, value in game.players_labels.items():
            print(f"{key}: {value}")


def debug_print_player_name_assignment(game, player_number, player_name):
    """Print when a player name is assigned."""
    if game.is_terminal_active:
        print(f"Assigned name to {player_number}: {player_name}")


def debug_print_player_attributes(game, attribute):
    """Print a specific attribute for all players."""
    if game.is_terminal_active:
        print(f"Player : {attribute.capitalize()}")
        for player_key, player_data in game.players_data.items():
            print(f"{player_key}: {player_data[attribute]}")


def debug_print_number_of_players(game):
    """Print the total number of players."""
    if game.is_terminal_active:
        print(f"\nNumber of players: {game.number_players}")


# ============================================================================
# CARD IMAGE DEBUG OUTPUT
# ============================================================================

def debug_print_card_dimensions(game):
    """Print card width and height."""
    if game.is_terminal_active:
        print("Scaled Card Width: " + str(game.card_width))
        print("Scaled Card Height: " + str(game.card_height))


def debug_print_adjusted_card_dimensions(game):
    """Print adjusted card dimensions after horizontal fit."""
    if game.is_terminal_active:
        print("Adjusted Card Width: " + str(game.card_width))
        print("Adjusted Card Height: " + str(game.card_height))


def debug_print_card_images(game):
    """Print all loaded card images."""
    if game.is_terminal_active:
        for key, value in game.card_images.items():
            print(f"Card Name: {key}, Image Object: {value}")


def debug_print_card_back_images(game):
    """Print all loaded card back images."""
    if game.is_terminal_active:
        print()
        print("Card Back Images:")
        for key, value in game.card_back_images.items():
            print(f"Color: {key} -> Image: {value}")
        print()


def debug_print_card_not_found(game, filename):
    """Print when a card image file is not found."""
    if game.is_terminal_active:
        print(f"Image not found: {filename}")


# ============================================================================
# PLAYER FRAME DEBUG OUTPUT
# ============================================================================

def debug_print_player_frame_height(game):
    """Print the calculated player frame height."""
    if game.is_terminal_active:
        print("Player Frame Height: " + str(game.player_frame_height))


def debug_print_player_frame_creation(game, player_number):
    """Print confirmation when player frame and labels are created."""
    if game.is_terminal_active:
        print(f"Added labels for player_{player_number}:")
        print(f"  Frame: {game.players_labels[player_number]['frame']}")
        print(f"  Name Label: {game.players_labels[player_number]['name']}")
        print(f"  Card Label: {game.players_labels[player_number]['card']}")
        print(f"  Score Label: {game.players_labels[player_number]['score']}")
        print(f"  Wins Label: {game.players_labels[player_number]['wins']}")


def debug_print_place_player_frames_start(game):
    """Print when starting to place player frames."""
    if game.is_terminal_active:
        print("\nPlace Player Frames:")
        print("Remove player frames for players not in game:")
        print(f"Players Out Of Game:")
        print(game.players_out_game)


def debug_print_player_frame_destroyed(game, player_number):
    """Print when a player frame is destroyed."""
    if game.is_terminal_active:
        print(f"Player {player_number} frame destroyed.")


def debug_print_table_frame_dimensions(game, num_columns, num_rows, max_frames_per_row):
    """Print table frame and layout calculations."""
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


def debug_print_place_frames_in_table(game):
    """Print when starting to place frames in table."""
    if game.is_terminal_active:
        print("\nPlace card labels in table frame: ")


def debug_print_player_frame_placement(game, player_number, relx_value, rely_value):
    """Print player frame placement details."""
    if game.is_terminal_active:
        print(f"Player {player_number}")
        print(f"Placed frame for {player_number}:")
        print(f"  Frame Object: {game.players_labels[player_number]['frame']}")
        print(f"  Relative X Position: {relx_value}")
        print(f"  Relative Y Position: {rely_value}")


def debug_print_all_frames_placed(game):
    """Print confirmation that all frames are placed."""
    if game.is_terminal_active:
        print("\nAll player frames have been placed.")


# ============================================================================
# GAME LOGIC DEBUG OUTPUT
# ============================================================================

def debug_print_populate_deck(game):
    """Print deck population details."""
    if game.is_terminal_active:
        print("\nPopulate Deck:")
        for item in game.deck:
            print(item)


def debug_print_shuffle_and_split(game):
    """Print when shuffling and splitting deck."""
    if game.is_terminal_active:
        print("\nShuffle And Split Deck:")


def debug_print_player_deck(game, player_number):
    """Print a player's deck contents."""
    if game.is_terminal_active:
        print(f"Player {player_number}'s deck: {game.players_data[player_number]['deck']}")


def debug_print_player_score(game, player_number, score):
    """Print a player's score."""
    if game.is_terminal_active:
        print(f"Player {player_number} Score: {score}")


def debug_print_split_cards_for_draw(game):
    """Print details when splitting cards for a draw."""
    if game.is_terminal_active:
        print("\nSplit Cards For Draw:")
        print(f"Cards On Table: {len(game.table)}")
        print("Cards On Table:")
        print(game.table)
        print(f"Cards Per Player: {len(game.table) // len(game.players_in_draw)}")
        print("Players In Draw:")
        print(game.players_in_draw)


def debug_print_draw_indexes(game, start_index, end_index):
    """Print start and end indexes for draw card distribution."""
    if game.is_terminal_active:
        print(f"\nStart Index: {start_index}")
        print(f"End_Index: {end_index}")


def debug_print_cards_assigned_to_reserve(game, player_number, cards_per_player, cards):
    """Print when cards are assigned to a player's reserve deck."""
    if game.is_terminal_active:
        print(f"{cards_per_player} cards assigned to Player {player_number} reserve deck.")
        print(f"Cards Assigned To Player {player_number}:")
        print(cards)


def debug_print_outlier_cards(game, outlier_cards):
    """Print information about outlier cards."""
    if game.is_terminal_active:
        print(f"\nOutlier cards: {outlier_cards}")
        if outlier_cards != 0:
            print("Outlier cards still on table.")
            print("Shuffle players in draw.")


def debug_print_players_in_draw_shuffled(game):
    """Print players in draw list after shuffling."""
    if game.is_terminal_active:
        print("Players In Draw:")
        print(game.players_in_draw)


def debug_print_assign_remaining_cards(game, cards_per_player, end_index):
    """Print when assigning remaining cards."""
    if game.is_terminal_active:
        print("Assign remaining cards to players.")
        print(f"Table Index = {end_index} x {cards_per_player}")


def debug_print_assign_outlier_card(game, table_index, player_number):
    """Print when assigning an outlier card to a player."""
    if game.is_terminal_active:
        print(f"\nTable Index: {table_index}")
        print(f"Assign {game.table[table_index]} to Player {player_number}")


def debug_print_player_reserve_deck(game, player_number):
    """Print a player's reserve deck."""
    if game.is_terminal_active:
        reserve_deck = game.players_data[player_number]['reserve_deck']
        print(f"Player {player_number} Reserve Deck:")
        print(reserve_deck)


def debug_print_calculate_cards(game):
    """Print card calculation for testing."""
    if game.is_terminal_active:
        print("\nCalculate Cards:")


def debug_print_player_card_count(game, player_number, count, total):
    """Print individual player card count."""
    if game.is_terminal_active:
        print(f"Player {player_number} Number Of Cards: {count}")
        print(f"Actual Number Of Cards: {total}")


def debug_print_card_totals(game, correct, actual):
    """Print total card counts."""
    if game.is_terminal_active:
        print(f"\nCorrect Number Of Cards: {correct}")
        print(f"Actual Number Of Cards: {actual}")


def debug_print_draw_card(game, player_number):
    """Print when drawing a card for a player."""
    if game.is_terminal_active:
        print(f"\nDraw Card For Player {player_number}:")


def debug_print_player_deck_empty(game, player_number):
    """Print when a player's deck is empty."""
    if game.is_terminal_active:
        print(f"Player {player_number} deck is empty.")


def debug_print_shuffle_reserve_to_deck(game, player_number):
    """Print when shuffling reserve deck to main deck."""
    if game.is_terminal_active:
        reserve_deck = game.players_data[player_number]['reserve_deck']
        player_deck = game.players_data[player_number]['deck']
        print(f"Player {player_number} Reserve Deck:")
        print(reserve_deck)
        print("Shuffle reserve deck and make it the players deck.")
        print(f"Player {player_number} Deck:")
        print(player_deck)


def debug_print_draw_cards_for_tiebreaker(game):
    """Print when drawing cards for tiebreaker."""
    if game.is_terminal_active:
        print("\nDraw Cards For Tiebreaker:")


def debug_print_player_card_count_for_tiebreaker(game, player_number, count):
    """Print player's card count for tiebreaker."""
    if game.is_terminal_active:
        print(f"Number of cards for Player {player_number}: {count}")


def debug_print_player_tiebreaker_action(game, player_number, action):
    """Print player's action in tiebreaker."""
    if game.is_terminal_active:
        print(f"Player {player_number} {action}")


def debug_print_player_card_placement(game, player_number, card):
    """Print when a player places a card."""
    if game.is_terminal_active:
        print(f"Player {player_number} places down {card}")


def debug_print_players_to_remove(game, players_list):
    """Print list of players to be removed."""
    if game.is_terminal_active:
        print("Players To Remove:")
        print(players_list)


def debug_print_cards_on_table(game):
    """Print all cards currently on the table."""
    if game.is_terminal_active:
        print("Cards on table:")
        print(game.table)


def debug_print_draw_card_modified_tiebreaker(game):
    """Print when drawing cards for modified tiebreaker."""
    if game.is_terminal_active:
        print("\nDraw Card For Modified Tiebreaker")


def debug_print_draw_cards_for_players(game):
    """Print when drawing cards for all players in round."""
    if game.is_terminal_active:
        print("\nDraw Cards For Players:")


def debug_print_player_draws_card(game, player_number, card):
    """Print when a specific player draws a card."""
    if game.is_terminal_active:
        print(f"Player {player_number} draws {card}")


def debug_print_remove_players_not_in_game(game):
    """Print when removing players not in game."""
    if game.is_terminal_active:
        print("\nRemove Players Not In Game:")
        print("Players In Game:")
        print(game.players_in_game)


def debug_print_player_in_game_status(game, player_number, status):
    """Print a player's in-game status."""
    if game.is_terminal_active:
        print(f"Player {player_number} in game status: {status}")


def debug_print_player_removed_from_game(game, player_number):
    """Print when a player is removed from the game."""
    if game.is_terminal_active:
        print(f"Player {player_number} removed from game.")


def debug_print_players_in_game_list(game):
    """Print the current players in game list."""
    if game.is_terminal_active:
        print("Players In Game:")
        print(game.players_in_game)


def debug_print_remove_players_not_in_round(game):
    """Print when removing players not in round."""
    if game.is_terminal_active:
        print("\nRemove Players Not In Round:")


def debug_print_player_in_round_status(game, player_number, status):
    """Print a player's in-round status."""
    if game.is_terminal_active:
        print(f"Player {player_number} in round status: {status}")


def debug_print_player_removed_from_round(game, player_number):
    """Print when a player is removed from the round."""
    if game.is_terminal_active:
        print(f"Player {player_number} removed from round.")


def debug_print_players_in_round_dict(game):
    """Print the current players in round dictionary."""
    if game.is_terminal_active:
        print("Players In Round:")
        print(game.players_in_round)


def debug_print_remove_player_from_game_in_tiebreaker(game, player_number):
    """Print when removing a player from game during tiebreaker."""
    if game.is_terminal_active:
        print("Remove players from game who are ineligible to play tiebreaker:")
        print(f"Player {player_number} exits game")


def debug_print_player_card_label_to_back(game, player_number):
    """Print when setting player's card label to back."""
    if game.is_terminal_active:
        print(f"Player {player_number} card label set to card back.")


def debug_print_players_out_game(game):
    """Print the players out of game list."""
    if game.is_terminal_active:
        print("Players Out Game:")
        print(game.players_out_game)


def debug_print_add_players_to_tiebreaker(game):
    """Print when adding players to tiebreaker list."""
    if game.is_terminal_active:
        print("\nAdd Players In Tiebreaker To List")


def debug_print_add_players_to_draw(game, player_number):
    """Print when adding a player to draw list."""
    if game.is_terminal_active:
        print(f"Player {player_number} added to players in draw list.")


def debug_print_add_players_in_draw_header(game):
    """Print header for adding players to draw."""
    if game.is_terminal_active:
        print("Add Players In Draw To List:")


def debug_print_populate_players_in_game(game):
    """Print when populating players in game list."""
    if game.is_terminal_active:
        print("\nPopulate Players In Game List")
        print("Players in game list:")
        print(game.players_in_game)


def debug_print_reset_players_in_round(game):
    """Print when resetting players in round."""
    if game.is_terminal_active:
        print("\nReset Players In Round:")


def debug_print_player_in_round_reset(game, player_number):
    """Print when a player is added back to round."""
    if game.is_terminal_active:
        print(f"Player {player_number} in round.")


def debug_print_check_players_in_game(game):
    """Print when checking players in game status."""
    if game.is_terminal_active:
        print("\nCheck Players In Game Status:")


def debug_print_player_in_game_set_false(game, player_number):
    """Print when player's in-game status is set to false."""
    if game.is_terminal_active:
        print(f"Player {player_number} in game status set to False")


def debug_print_check_players_in_round(game):
    """Print when checking players in round status."""
    if game.is_terminal_active:
        print("\nCheck Players In Round Status:")


def debug_print_player_in_round_set_false(game, player_number):
    """Print when player's in-round status is set to false."""
    if game.is_terminal_active:
        print(f"Player {player_number} in round status set to false.")


def debug_print_get_highest_rank(game):
    """Print when getting highest rank."""
    if game.is_terminal_active:
        print("\nGet Highest Rank:")
        print("Player cards in players in game dictionary:")
        for player_number, player_card in game.players_in_round.items():
            print(f"Player {player_number}: {player_card}")


def debug_print_highest_rank(game, rank):
    """Print the highest rank found."""
    if game.is_terminal_active:
        print(f"\nHighest rank: {rank}")


def debug_print_winner_takes_cards(game):
    """Print when winner takes cards."""
    if game.is_terminal_active:
        print("\nWinner Takes Cards:")
        print(f"Round winner: Player {game.round_winner}")
        print("Cards assigned to winners reserve deck:")
        print(game.table)


def debug_print_winner_reserve_deck(game):
    """Print the winner's reserve deck after taking cards."""
    if game.is_terminal_active:
        reserve_deck = game.players_data[game.round_winner]['reserve_deck']
        print(f"Player {game.round_winner} Reserve Deck:")
        print(reserve_deck)


def debug_print_update_card_images(game):
    """Print when updating card images."""
    if game.is_terminal_active:
        print("\nUpdate Card Images:")


def debug_print_player_card_image_updated(game, player_number, card):
    """Print when a player's card image is updated."""
    if game.is_terminal_active:
        print(f"Player {player_number} card image updated to {card}.")


def debug_print_update_card_images_for_draw(game):
    """Print when updating card images for draw."""
    if game.is_terminal_active:
        print("\nUpdate Card Images For Draw:")


def debug_print_player_card_to_back(game, player_number):
    """Print when player's card is set to back."""
    if game.is_terminal_active:
        print(f"Player {player_number} card label updated to back of card.")


def debug_print_update_result_label(game):
    """Print when updating result label."""
    if game.is_terminal_active:
        print("\nUpdate Result Label:")
        print(f"Tiebreaker Type: {game.tiebreaker_type}")
        print(f"Is Tie Round: {game.is_tie_round}")


def debug_print_result_label_text(game, text):
    """Print the result label text."""
    if game.is_terminal_active:
        print(f"Result label update: {text}")


def debug_print_update_player_scores(game):
    """Print when updating player scores."""
    if game.is_terminal_active:
        print("\nUpdate Player Scores:")
        print(f"Tiebreaker Type: {game.tiebreaker_type}")
        print("Players In Game:")
        print(game.players_in_game)


def debug_print_player_deck_and_reserve(game, player_number):
    """Print a player's deck and reserve deck."""
    if game.is_terminal_active:
        print(f"\nPlayer {player_number} Deck:")
        print(game.players_data[player_number]['deck'])
        print(f"Player {player_number} Reserve Deck:")
        print(game.players_data[player_number]['reserve_deck'])


def debug_print_player_score_calculation(game, player_number, deck_len, reserve_len):
    """Print player score calculation."""
    if game.is_terminal_active:
        print(f"Player {player_number} Score = {deck_len} + {reserve_len}")


def debug_print_player_score_value(game, player_number, score):
    """Print a player's score value."""
    if game.is_terminal_active:
        print(f"Player {player_number} Score: {score}")


def debug_print_player_not_enough_cards(game, player_number):
    """Print when a player doesn't have enough cards."""
    if game.is_terminal_active:
        print(f"Player {player_number} does not have enough cards.")


def debug_print_player_score_label_updated(game, player_number, text):
    """Print when a player's score label is updated."""
    if game.is_terminal_active:
        print(f"Player {player_number} score label updated to {text}.")


def debug_print_update_remaining_scores(game):
    """Print header for updating remaining player scores."""
    if game.is_terminal_active:
        print("Update Score Labels For Any Remaining Players:")


def debug_print_update_player_wins(game):
    """Print when updating player wins."""
    if game.is_terminal_active:
        print("\nUpdate Player Wins For Winner:")


def debug_print_player_wins_updated(game, player_number, wins):
    """Print when a player's wins are updated."""
    if game.is_terminal_active:
        print(f"Player {player_number} wins updated to {wins}.")


def debug_print_update_play_button_tiebreaker(game):
    """Print when updating play button for tiebreaker."""
    if game.is_terminal_active:
        print("\nUpdate Play Button For Tiebreaker.")


def debug_print_reset_play_button(game):
    """Print when resetting play button to default."""
    if game.is_terminal_active:
        print("\nReset Play Button To Default.")


def debug_print_determine_tiebreaker_type(game):
    """Print when determining tiebreaker type."""
    if game.is_terminal_active:
        print("\nDetermine Tiebreaker Type:")
        print("Players in tiebreaker:")
        print(game.players_in_round)


def debug_print_players_with_cards(game, players_4, players_1):
    """Print count of players with different card amounts."""
    if game.is_terminal_active:
        print(f"Players with at least 4 cards: {players_4}")
        print(f"Players with at least 1 card: {players_1}")


def debug_print_tiebreaker_type(game, tiebreaker_type):
    """Print the determined tiebreaker type."""
    if game.is_terminal_active:
        print(f"{tiebreaker_type} Tiebreaker")


def debug_print_determine_winner(game):
    """Print when determining winner."""
    if game.is_terminal_active:
        print("\nDetermine Winner:")


def debug_print_round_is_draw(game):
    """Print when round is a draw."""
    if game.is_terminal_active:
        print("Round is a draw.")


def debug_print_round_winner(game, winner):
    """Print the round winner."""
    if game.is_terminal_active:
        print(f"Round Winner: Player {winner}")


def debug_print_tie_round(game):
    """Print when there's a tie round."""
    if game.is_terminal_active:
        print("Tie Round")


def debug_print_no_players_in_tiebreaker(game):
    """Print when no players are left in tiebreaker."""
    if game.is_terminal_active:
        print("No players left for the tiebreaker.")


def debug_print_continue_tiebreaker(game):
    """Print when continuing tiebreaker."""
    if game.is_terminal_active:
        print("Continue tiebreaker.")


def debug_print_end_tiebreaker(game):
    """Print when ending tiebreaker."""
    if game.is_terminal_active:
        print("End tiebreaker.")


def debug_print_start_automating(game):
    """Print when starting automation."""
    if game.is_terminal_active:
        print("\nStart Automating")


def debug_print_stop_automating(game):
    """Print when stopping automation."""
    if game.is_terminal_active:
        print("\nStop Automating")


def debug_print_click_play_button_periodically(game):
    """Print when clicking play button periodically."""
    if game.is_terminal_active:
        print("\nClick Play Button Periodically:")
        print("Automation Operation Invoked")


def debug_print_toggle_automation(game):
    """Print when toggling automation."""
    if game.is_terminal_active:
        print("\nToggle Automation")
        print(f"Automation Active: {game.automation_active}")


def debug_print_play_tiebreaker(game):
    """Print when playing tiebreaker."""
    if game.is_terminal_active:
        print("\nPlay Tiebreaker:")


def debug_print_end_game(game):
    """Print when ending game."""
    if game.is_terminal_active:
        print("\nEnd Game.")


def debug_print_game_winner(game, winner):
    """Print the game winner."""
    if game.is_terminal_active:
        print(f"Game Winner: Player {winner}")


def debug_print_end_round(game):
    """Print when ending round."""
    if game.is_terminal_active:
        print("\nEnd Round Procedure:")


def debug_print_start_new_round(game):
    """Print when starting a new round."""
    if game.is_terminal_active:
        print("START NEW ROUND")


# ============================================================================
# GUI DEBUG OUTPUT
# ============================================================================

def debug_print_gui_setup_complete(game):
    """Print when GUI setup is complete."""
    if game.is_terminal_active:
        print("Created & placed result label & play button in root window.")


# ============================================================================
# MISCELLANEOUS DEBUG OUTPUT
# ============================================================================

def debug_print_empty_function_call(game):
    """Print a blank line (used for empty print() calls)."""
    if game.is_terminal_active:
        print()
