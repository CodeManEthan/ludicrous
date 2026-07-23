import random
from players import player_attr
from players import player_label_attr
from player_frames import place_player_frames
from player_frames import create_player_objects
from leaderboard_window import determine_leaderboard_placements
from debug_output import *
# Redefine print to do nothing
import builtins
#builtins.print = lambda *args, **kwargs: None


def populate_deck(game):
    debug_print_populate_deck(game)
    # Build the deck at start of game
    for _ in range(game.number_decks):
        for suit in ("Hearts", "Diamonds", "Clubs", "Spades"):
            for rank in range(2, 15):
                game.deck.append((rank, suit))

def shuffle_and_split_deck(game):
    debug_print_shuffle_and_split(game)
    # Shuffle deck
    random.shuffle(game.deck)

    # Calculate cards per player
    cards_per_player = len(game.deck) // game.number_players

    # Split cards evenly amongst players
    for i in range(1, game.number_players + 1):
        player_number = i
        start_index = i - 1
        end_index = i

        game.players_data[i]['deck'] = game.deck[start_index*cards_per_player:end_index*cards_per_player]

        # Print the cards in each player's deck
        debug_print_player_deck(game, player_number)

        # Set each player's score and score label
        player_attr(game, player_number, 'score', cards_per_player)
        player_score_label = player_label_attr(game, player_number, 'score')
        player_score_label.config(text=f"Cards: {cards_per_player}")
        debug_print_player_score(game, player_number, player_attr(game, player_number, 'score'))

def split_cards_for_draw(game):
    debug_print_split_cards_for_draw(game)
    # Calculate cards per player
    cards_per_player = len(game.table) // len(game.players_in_draw)

    i = 0
    start_index = i - 1
    end_index = i

    # Split cards amongst players in the draw.
    for player_number in game.players_in_draw:
        start_index += 1
        end_index += 1
        debug_print_draw_indexes(game, start_index, end_index)

        reserve_deck = player_attr(game, player_number, 'reserve_deck')

        reserve_deck.extend(game.table[start_index*cards_per_player:end_index*cards_per_player])
        debug_print_cards_assigned_to_reserve(game, player_number, cards_per_player, 
                                              game.table[start_index*cards_per_player:end_index*cards_per_player])

    # Determine if there are any outlier cards
    cards_assigned = cards_per_player*len(game.players_in_draw)
    outlier_cards = len(game.table) - cards_assigned
    debug_print_outlier_cards(game, outlier_cards)

    # If any cards remain on the table
    if not outlier_cards == 0:
        # Shuffle players in draw
        random.shuffle(game.players_in_draw)
        debug_print_players_in_draw_shuffled(game)

        # Determine table index for card
        table_index = (end_index*cards_per_player)

        # Assign remaining cards to players
        debug_print_assign_remaining_cards(game, cards_per_player, end_index)

        for player_number in game.players_in_draw:
            # Check if there are remaining cards
            if table_index < len(game.table):
                # Assign the current card to the player
                debug_print_assign_outlier_card(game, table_index, player_number)
                reserve_deck = player_attr(game, player_number, 'reserve_deck')
                reserve_deck.extend([game.table[table_index]])
                table_index += 1
            else:
                # If no more cards are left, break out of the loop
                break
        
        for player_number in game.players_in_draw:
            debug_print_player_reserve_deck(game, player_number)


def card_name(card):
    rank = (
        str(card[0]) if card[0] <= 10 else
        "Jack" if card[0] == 11 else
        "Queen" if card[0] == 12 else
        "King" if card[0] == 13 else
        "Ace"
    )
    suit = card[1]
    card_name = f"{rank} of {suit}"
    return card_name 

def calculate_number_of_cards_for_testing(game):
    debug_print_calculate_cards(game)

    correct_number_of_cards = len(game.deck)
    actual_number_of_cards = 0

    for player_number in game.players_in_game:
        deck = player_attr(game, player_number, 'deck')
        reserve_deck = player_attr(game, player_number, 'reserve_deck')
        player_number_of_cards = len(deck) + len(reserve_deck)
        debug_print_player_card_count(game, player_number, player_number_of_cards, actual_number_of_cards + player_number_of_cards)
        actual_number_of_cards += player_number_of_cards

    debug_print_card_totals(game, correct_number_of_cards, actual_number_of_cards)

def draw_card(game, player_number):
    debug_print_draw_card(game, player_number)

    player_deck = player_attr(game, player_number, 'deck')
    player_reserve_deck = player_attr(game, player_number, 'reserve_deck')

    if not player_deck:
        debug_print_player_deck_empty(game, player_number)
        if not player_reserve_deck:
            # Return None if active deck and reserve deck are empty
            return None
        # If only active deck is empty:
        # Shuffle reserve deck
        debug_print_shuffle_reserve_to_deck(game, player_number)
        random.shuffle(player_reserve_deck)
        # Add reserve deck to active deck
        player_deck.extend(player_reserve_deck)
        # clear reserve deck
        player_reserve_deck.clear()

    # Return player card
    player_card = player_deck.pop(0)
    return player_card

def draw_cards_for_tiebreaker(game):
    # Used for default tiebreaker and forfeit tiebreaker
    debug_print_draw_cards_for_tiebreaker(game)

    players_to_remove = [] # players with less than 4 cards

    for player_number in game.players_in_round:
        deck = player_attr(game, player_number, 'deck')
        reserve_deck = player_attr(game, player_number, 'reserve_deck')
        number_player_cards = len(deck) + len(reserve_deck)
        debug_print_player_card_count_for_tiebreaker(game, player_number, number_player_cards)

        if number_player_cards > 3:
            # Place 4 cards on the table 
            debug_print_player_tiebreaker_action(game, player_number, "places down three cards and plays the fourth:")
            for i in range(4):
                player_card = draw_card(game, player_number)
                assign_card_to_player(game, player_number, player_card)
                debug_print_player_card_placement(game, player_number, player_card)

            debug_print_player_tiebreaker_action(game, player_number, f"plays {player_card}")
            debug_print_player_tiebreaker_action(game, player_number, "plays tiebreaker")
            
        # If player does not have enough cards to play tiebreaker
        else:
            debug_print_player_tiebreaker_action(game, player_number, "does not have enough cards for tiebreaker.")
            # Place all of players cards on table.
            for i in range(number_player_cards):
                player_card = draw_card(game, player_number)
                assign_card_to_player(game, player_number, player_card)

            # Add player to removal list
            players_to_remove.append(player_number)  
  
    # Remove players from game who are ineligble to play tiebreaker
    debug_print_players_to_remove(game, players_to_remove)
    for player_number in players_to_remove:
        remove_player_from_game_in_tiebreaker(game, player_number)

    debug_print_cards_on_table(game)

def draw_cards_for_modified_tiebreaker(game):
    # Used for modified tiebreaker and modified forfeit tiebreaker
    debug_print_draw_card_modified_tiebreaker(game)
    for player_number in game.players_in_round:
        deck = player_attr(game, player_number, 'deck')
        reserve_deck = player_attr(game, player_number, 'reserve_deck')
        number_player_cards = len(deck) + len(reserve_deck)
        players_to_remove = [] # players with less than 4 cards

        # Place all of players cards on table.
        if number_player_cards > 0:
            for i in range(number_player_cards):
                player_card = draw_card(game, player_number)
                assign_card_to_player(game, player_number, player_card)
        else:
            # Add player to removal list
            players_to_remove.append(player_number)

    # Remove players from game who are ineligble to play tiebreaker 
    for player_number in players_to_remove:
        remove_player_from_game_in_tiebreaker(game, player_number)

def draw_card_for_players_in_round(game):
    debug_print_draw_cards_for_players(game)
    for player_number in game.players_in_round:
        player_card = draw_card(game, player_number)
        debug_print_player_draws_card(game, player_number, player_card)
        # Assign card to player
        assign_card_to_player(game, player_number, player_card)
    debug_print_cards_on_table(game)

        
def assign_card_to_player(game, player_number, player_card):
    # Assign card to players data card attribute
    player_attr(game, player_number, 'card', player_card)
    # Assign card to player for players in round list
    rank, suit = player_card
    game.players_in_round[player_number] = (rank, suit)
    # Place card in table list
    game.table.append(player_card)


def remove_players_not_in_game(game):
    debug_print_remove_players_not_in_game(game)
    # Remove players not in game from players in game list using a static list
    for player_number in list(game.players_in_game):
        in_game = player_attr(game, player_number, 'in_game')
        debug_print_player_in_game_status(game, player_number, in_game)

        if not in_game:
            game.players_in_game.remove(player_number)
            game.players_out_game.append((player_number, False))
            game.number_players_in_game -= 1
            debug_print_player_removed_from_game(game, player_number)
            # Set players round out value
            round_out = game.number_rounds
            player_attr(game, player_number, 'round_out', round_out)
    debug_print_players_in_game_list(game)

def remove_players_not_in_round(game):
    debug_print_remove_players_not_in_round(game)
    # Create a list of players to be removed
    players_to_remove = []

    # Iterate over the dictionary and check if players should be removed
    for player_number in game.players_in_round:
        in_round = player_attr(game, player_number, 'in_round')
        debug_print_player_in_round_status(game, player_number, in_round)

        if not in_round:
            players_to_remove.append(player_number)  # Add player to removal list

    # Remove players after iteration is complete
    for player_number in players_to_remove:
        del game.players_in_round[player_number]
        game.number_players_in_round -= 1
        debug_print_player_removed_from_round(game, player_number)
    debug_print_players_in_round_dict(game)

def remove_player_from_game_in_tiebreaker(game, player_number):
    debug_print_remove_player_from_game_in_tiebreaker(game, player_number)

    # Set player's card to None
    player_attr(game, player_number, 'card', None)

    # Set player's in round and in game status to False
    player_attr(game, player_number, 'in_round', False)
    player_attr(game, player_number, 'in_game', False)

    # Remove player from players in round dictionary and players in game list
    del game.players_in_round[player_number]
    game.players_in_game.remove(player_number)
    game.players_out_game.append((player_number, False))

    # Subtract player from number players in game and number players in round
    game.number_players_in_game -= 1
    game.number_players_in_round -= 1
    debug_print_player_removed_from_game(game, player_number)

    # Set players round out value
    round_out = game.number_rounds
    player_attr(game, player_number, 'round_out', round_out)

    # Set player image to back of card
    debug_print_player_card_label_to_back(game, player_number)
    player_card_label = player_label_attr(game, player_number, 'card')
    player_card_label.config(image=game.card_back_images.get(game.deck_color.lower()))
    
    debug_print_players_in_round_dict(game)
    debug_print_players_in_game_list(game)
    debug_print_players_out_game(game)

def add_players_to_tiebreaker_list(game):
    debug_print_add_players_to_tiebreaker(game)
    for player_number in game.players_in_round:
        game.players_in_tiebreaker.append(player_number)

def add_players_in_draw_to_list(game):
    debug_print_add_players_in_draw_header(game)
    for player_number in game.players_in_round:
        game.players_in_draw.append(player_number)
        debug_print_add_players_to_draw(game, player_number)

def set_players_in_game(game):
    debug_print_populate_players_in_game(game)
    # Add player number to players in game list
    for i in range(1, game.number_players + 1):
        player_number = i
        game.players_in_game.append(player_number)
    # Set number players in game (int)
    game.number_players_in_game = game.number_players
    
def reset_players_in_round(game):
    debug_print_reset_players_in_round(game)
    # Clear players in round dictionary
    game.players_in_round.clear()
    # Clear players in tiebreaker list
    game.players_in_tiebreaker.clear()
    
    for player_number in game.players_in_game:
        # Add player numbers to players in round and placeholder for player card
        game.players_in_round[player_number] = (None, None)
        # Reset in round status for each player to True
        player_attr(game, player_number, 'in_round', True)

    # Reset number players in round, round winner and tiebreaker type values
    game.number_players_in_round = game.number_players_in_game
    game.round_winner = 0
    game.tiebreaker_type = ""
    for player_number in game.players_in_round.keys():
        debug_print_player_in_round_reset(game, player_number)
        
def check_players_in_game(game):
    debug_print_check_players_in_game(game)
    for player_number in game.players_in_game:
        player_deck = player_attr(game, player_number, 'deck')
        player_reserve_deck = player_attr(game, player_number, 'reserve_deck')

        if len(player_deck) + len(player_reserve_deck) == 0:
            player_attr(game, player_number, 'in_game', False)
            debug_print_player_in_game_set_false(game, player_number)

def check_players_in_round(game):
    debug_print_check_players_in_round(game)
    # Remove players from round without a card rank equal to the highest card rank
    for player_number, (rank, _), in game.players_in_round.items():
        if not rank == game.highest_rank:
            player_attr(game, player_number, 'in_round', False)
            debug_print_player_in_round_set_false(game, player_number)
    

def get_highest_rank(game):
    debug_print_get_highest_rank(game)
    game.highest_rank = -1
    
    for _, (rank, _) in game.players_in_round.items():   
        # If the rank is 14, return immediately
        if rank == 14:
            game.highest_rank = rank
            debug_print_highest_rank(game, game.highest_rank)
            return
        
        # Otherwise, check if this player's rank is higher than the current highest
        if rank > game.highest_rank:
            game.highest_rank = rank

    debug_print_highest_rank(game, game.highest_rank)

def winner_takes_cards(game):
    debug_print_winner_takes_cards(game)
    player_reserve_deck = player_attr(game, game.round_winner, 'reserve_deck')
    # Place all cards from table into players reserve deck
    player_reserve_deck.extend(game.table)
    debug_print_winner_reserve_deck(game)
    # Clear the table
    game.table.clear()


def update_card_images(game):
    debug_print_update_card_images(game)
    for player_number in game.players_in_round:
        player_card = player_attr(game, player_number, 'card')
        player_card_label = player_label_attr(game, player_number, 'card')
        player_card_label.config(image=game.card_images[card_name(player_card)])
        debug_print_player_card_image_updated(game, player_number, player_card)

def update_card_images_for_draw(game):
    debug_print_update_card_images_for_draw(game)
    for player_number in game.players_in_round:
        # Set player image to back of card
        player_card_label = player_label_attr(game, player_number, 'card')
        player_card_label.config(image=game.card_back_images.get(game.deck_color.lower()))
        debug_print_player_card_to_back(game, player_number)

def update_result_label(game):
    debug_print_update_result_label(game)
    if game.is_tie_round:
        result = "War!"
    else:
        if game.tiebreaker_type == "Forfeit" or game.tiebreaker_type == "Modified Forfeit":
            player_name = player_attr(game, game.round_winner, 'name')
            result = player_name + " Wins By Forfeit!"
        elif game.tiebreaker_type == "Draw":
            result = "It's A Draw!"
        else:
            player_name = player_attr(game, game.round_winner, 'name')
            result = player_name + " Wins!"

    # Update result label
    game.result_label.config(text=result)
    debug_print_result_label_text(game, result)

def update_player_scores(game):
    debug_print_update_player_scores(game)
    for player_number in game.players_in_game:
        # Get player deck, reserve deck and score label
        player_deck = player_attr(game, player_number, 'deck')
        player_reserve_deck = player_attr(game, player_number, 'reserve_deck')
        player_score_label = player_label_attr(game, player_number, 'score')
        debug_print_player_deck_and_reserve(game, player_number)

        # Calculate player score
        player_score = len(player_deck) + len(player_reserve_deck)
        debug_print_player_score_calculation(game, player_number, len(player_deck), len(player_reserve_deck))
        # Update player score
        player_attr(game, player_number, 'score', player_score)
        debug_print_player_score_value(game, player_number, player_score)
        
        # Determine score label text
        if game.tiebreaker_type == "Forefeit" and player_score < 4:
            score_text = "Not Enough Cards!"
            debug_print_player_not_enough_cards(game, player_number)

        elif game.tiebreaker_type in ["Forfeit", "Modified Forfeit"] and player_score == 0:
            score_text = "Not Enough Cards!"
            debug_print_player_not_enough_cards(game, player_number)
        else:
            score_text = f"Cards: {player_score}"

        # Update player score label
        player_score_label.config(text=score_text)
        debug_print_player_score_label_updated(game, player_number, score_text)

    # Update scores for any players not in game who are in a tiebreaker
    debug_print_update_remaining_scores(game)
    for player_number in game.players_in_tiebreaker:
        # Determine if player has been taken out of the game yet.
        for player_number_2, taken_out in game.players_out_game:
            if player_number_2 == player_number and not taken_out:
                score_text = "Not Enough Cards!"
                score_label = player_label_attr(game, player_number, 'score')
                score_label.config(text=score_text)
                debug_print_player_score_label_updated(game, player_number, score_text)
        
def update_round_counter(game):
    game.number_rounds += 1
    game.round_counter_label.config(text=f"Round: {game.number_rounds:,}")

def update_player_wins_for_winner(game):
    debug_print_update_player_wins(game)
    player_wins = player_attr(game, game.round_winner, 'wins')
    player_win_label = player_label_attr(game, game.round_winner, 'wins')
    player_wins += 1
    player_attr(game, game.round_winner, 'wins', player_wins)
    player_win_label.config(text=f"Wins: {player_wins}")
    debug_print_player_wins_updated(game, game.round_winner, player_wins)

def update_play_button_for_tiebreaker(game):
    debug_print_update_play_button_tiebreaker(game)
    game.play_button.config(text="Play Tiebreaker!", command=lambda:play_tiebreaker(game))

def reset_play_button_to_default(game):
    debug_print_reset_play_button(game)
    game.play_button.config(text="Play Round!", command=lambda: play_round(game))

def determine_tiebreaker_type(game):
    debug_print_determine_tiebreaker_type(game)

    # Tiebreaker Types:
        # Default - At least two players have 4 cards
        # Forfeit - Only one player has 4 cards 
        # Modified - At least two players have at least 1 card and less than 4 cards
        # Modified Forfeit - Only one player has at least 1 card and less than 4 cards
        # Draw - All players have zero cards
    
    game.tiebreaker_type = ""
    players_with_4_cards = 0
    players_with_1_card = 0

    # Iterate through all players in tiebreaker
    for player_number in game.players_in_round:
        player_deck = player_attr(game, player_number, 'deck')
        reserve_player_deck = player_attr(game, player_number, 'reserve_deck')
        number_player_cards = len(player_deck) + len(reserve_player_deck)

        # Check if player has more than zero cards and more than three cards
        if number_player_cards > 0:
            players_with_1_card += 1
        if number_player_cards > 3:
            players_with_4_cards += 1
        
        # Check if default tiebreaker
        if players_with_4_cards > 1:
            game.tiebreaker_type = "Default"
            debug_print_tiebreaker_type(game, "Default")
            return
    
    debug_print_players_with_cards(game, players_with_4_cards, players_with_1_card)

    # Check if forfeit tiebreaker
    if players_with_4_cards == 1:
        game.tiebreaker_type = "Forfeit"
        debug_print_tiebreaker_type(game, "Forfeit")
        return

    # Check if modified tiebreaker
    if players_with_1_card > 1:
        game.tiebreaker_type = "Modified"
        debug_print_tiebreaker_type(game, "Modified")
        return

    # Check if modified forfeit tiebreaker
    if players_with_1_card == 1:
        game.tiebreaker_type = "Modified Forfeit"
        debug_print_tiebreaker_type(game, "Modified Forfeit")
        return

    # Check if draw tiebreaker
    if players_with_1_card == 0:
        debug_print_tiebreaker_type(game, "Draw")
        game.tiebreaker_type = "Draw"
        game.is_tie_round = False

def determine_winner(game):
    debug_print_determine_winner(game)

    # If round is a draw
    if game.tiebreaker_type == "Draw":
        debug_print_round_is_draw(game)

        add_players_in_draw_to_list(game)
        split_cards_for_draw(game)
        update_card_images_for_draw(game)
        update_result_label(game)
        game.is_tie_round = False
        return

    # Iterate through all player cards to determine highest card (Stop if Ace found)
    get_highest_rank(game)

    # Iterate through all player cards to determine all players with highest card (for tiebreaker)
    check_players_in_round(game)

    # Remove players not in round from players in round dictionary
    remove_players_not_in_round(game)

    # If only one player in round
    if game.number_players_in_round == 1:
        # Declare winner as the only player remaining in the round
        if game.players_in_round:
            game.round_winner = next(iter(game.players_in_round))
        else:
            game.round_winner = None
        game.is_tie_round = False
        debug_print_round_winner(game, game.round_winner)

    # If more than one players have the highest card
    elif game.number_players_in_round > 1:
        game.is_tie_round = True
        game.had_tie_round = True
        debug_print_tie_round(game)

# Function to start automating the clicks
def start_automating_clicks(game):
    debug_print_start_automating(game)
    if not game.automation_active:
        game.automation_active = True
        click_play_button_periodically(game)
        game.automation_button.config(text="Stop")

# Function to stop automating the clicks
def stop_automating_clicks(game):
    debug_print_stop_automating(game)
    game.automation_active = False
    game.automation_button.config(text="Automate")

# Function that simulates the click on the play_button every second
def click_play_button_periodically(game):
    debug_print_click_play_button_periodically(game)
    if game.is_game_over:
        game.automation_active = False

    if game.automation_active:
        game.play_button.invoke()
        game.root.after(game.automation_speed, lambda: click_play_button_periodically(game))

# Function to handle automate button click
def toggle_automation(game):
    debug_print_toggle_automation(game)
    if game.automation_active:
        stop_automating_clicks(game)  # Stop automation if it's currently active
    else:
        start_automating_clicks(game)  # Start automation if it's not active

def increase_speed(game):
    game.is_faster = True
    adjust_speed(game)

def decrease_speed(game):
    game.is_faster = False
    adjust_speed(game)

def adjust_speed(game):
    if game.is_faster:
        if not game.automation_speed <= 100:
            game.automation_speed -= 100
        elif not game.automation_speed <= 10:
            game.automation_speed -= 10
        elif not game.automation_speed == 1:
            game.automation_speed -= 1
    elif not game.is_faster:
        if not game.automation_speed == 10000:
            game.automation_speed += 100
        

def play_tiebreaker(game):
    debug_print_play_tiebreaker(game)

    # Add players in tiebreaker to players in tiebreaker list
    add_players_to_tiebreaker_list(game)

    # Update player frames
    place_player_frames(game)

    # Determine tiebreaker type
    determine_tiebreaker_type(game)

    # Draw cards for tiebreaker
    if game.tiebreaker_type == "Default" or game.tiebreaker_type == "Forfeit":
        draw_cards_for_tiebreaker(game)
    elif game.tiebreaker_type == "Modified" or game.tiebreaker_type == "Modified Forfeit":
        draw_cards_for_modified_tiebreaker(game)
    elif game.tiebreaker_type == "Draw":
        update_card_images_for_draw(game)

    if not game.tiebreaker_type == "Draw":
        # Update player cards
        update_card_images(game)

    # Determine winner(s)
    determine_winner(game)

    if not game.players_in_round:
        debug_print_no_players_in_tiebreaker(game)

    # If tie:
    if game.is_tie_round:
        debug_print_continue_tiebreaker(game)

        # Update scores for players in tiebreaker
        update_player_scores(game)

        # Remove all players without the highest card from players in round list
        check_players_in_round(game)
        remove_players_not_in_round(game)

        # Continue tiebreaker by clicking play button
    else:
        debug_print_end_tiebreaker(game)
        # Update result label
        update_result_label(game)

        # End the round
        end_round(game)

def end_game(game):
    debug_print_end_game(game)
    # Update game over boolean
    game.is_game_over = True

    # Determine game winner
    game.game_winner = game.players_in_game[0]
    debug_print_game_winner(game, game.game_winner)

    # Update result label
    player_name = player_attr(game, game.game_winner, 'name')
    game.result_label.config(text=f"{player_name} Wins The Game!")

    # Update play button
    game.play_button.config(text="Game Over!", command=None)

def end_round(game):
    debug_print_end_round(game)
    
    if not game.tiebreaker_type == "Draw":
        # Place all cards on the table into winning players' reserve deck
        winner_takes_cards(game)

    # Update scores for players
    update_player_scores(game)
    
    if not game.tiebreaker_type == "Draw":
        # Update wins and wins label for winning player
        update_player_wins_for_winner(game)

    # Check if any players have zero cards and remove them from players in game list
    check_players_in_game(game)
    remove_players_not_in_game(game)

    # Update leaderboard
    determine_leaderboard_placements(game)

    # If only one player is active in game
    if game.number_players_in_game == 1:
        # Declare game winner
        # Call end game function
        end_game(game)
    else:
        # Reset play button to default
        reset_play_button_to_default(game)
        calculate_number_of_cards_for_testing(game)

def reset_game(game):
    # Reset player attributes
    for i in range(1, game.number_players + 1):
        player_number = i
        player_attr(game, player_number, 'deck', None)
        player_attr(game, player_number, 'reserve_deck', None)
        player_attr(game, player_number, 'card', None)
        player_attr(game, player_number, 'score', 0)
        player_attr(game, player_number, 'wins', 0)
        player_attr(game, player_number, 'in_round', True)
        player_attr(game, player_number, 'in_game', True)
        player_label_attr(game, player_number, 'name', None)
        player_label_attr(game, player_number, 'card', None)
        player_label_attr(game, player_number, 'score', None)
        player_label_attr(game, player_number, 'wins', None)
        player_label_attr(game, player_number, 'frame', None)

    # Add players to game
    set_players_in_game(game)

    # Add players to round
    reset_players_in_round(game)

    # Shuffle and split deck
    shuffle_and_split_deck

    # Reset play button to default
    reset_play_button_to_default(game)

    # Update result label
    game.result_label.config(text="Welcome To War!")

    # Delete table frame
    game.table_frame.destroy()

    # Create player frames
    create_player_objects(game)

    # Place player frames
    place_player_frames(game)

def play_round(game):
    debug_print_start_new_round(game)
    # Clear the result label
    game.result_label.config(text="")
    game.root.update()

    # Update round counter
    update_round_counter(game)

    # Add all players in game list to players in round dictionary
    reset_players_in_round(game)

    # If last round had tie then update scores for all players in game
    #if game.had_tie_round:
    #    update_player_scores
    #    game.had_tie_round = False

    # Update player frames
    place_player_frames(game)

    # Draw cards for each player in players in round dictionary and place player cards in table list
    draw_card_for_players_in_round(game)

    # Update player card images
    update_card_images(game)

    # Determine winner(s)
    determine_winner(game)

    # Update result label
    update_result_label(game)

    # Highlight winning card(s)

    # If tie:
    if game.is_tie_round:
        # Update player scores
        update_player_scores(game) 

        # Update play button config for tiebreaker
        update_play_button_for_tiebreaker(game)
    else:
        # Else: End the round
        end_round(game)
