import random
from players import player_attr
from players import player_label_attr
from player_frames import place_player_frames
from player_frames import create_player_objects
from leaderboard_window import determine_leaderboard_placements
# Redefine print to do nothing
import builtins
#builtins.print = lambda *args, **kwargs: None


def populate_deck(game):
    print("\nPopulate Deck:")
    # Build the deck at start of game
    for _ in range(game.number_decks):
        for suit in ("Hearts", "Diamonds", "Clubs", "Spades"):
            for rank in range(2, 15):
                game.deck.append((rank, suit))
    for item in game.deck:
        print(item)

def shuffle_and_split_deck(game):
    print("\nShuffle And Split Deck:")
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
        print(f"Player {i}'s deck: {game.players_data[i]['deck']}")

        # Set each player's score and score label
        player_attr(game, player_number, 'score', cards_per_player)
        player_score_label = player_label_attr(game, player_number, 'score')
        player_score_label.config(text=f"Cards: {cards_per_player}")
        print(f"Player {player_number} Score: {player_attr(game, player_number, 'score')}")

def split_cards_for_draw(game):
    print("\nSplit Cards For Draw:")
    # Calculate cards per player
    cards_per_player = len(game.table) // len(game.players_in_draw)
    print(f"Cards On Table: {len(game.table)}")
    print("Cards On Table:")
    print(game.table)
    print(f"Cards Per Player: {cards_per_player}")
    print("Players In Draw:")
    print(game.players_in_draw)

    i = 0
    start_index = i - 1
    end_index = i

    # Split cards amongst players in the draw.
    for player_number in game.players_in_draw:
        start_index += 1
        end_index += 1
        print(f"\nStart Index: {start_index}")
        print(f"End_Index: {end_index}")

        reserve_deck = player_attr(game, player_number, 'reserve_deck')

        reserve_deck.extend(game.table[start_index*cards_per_player:end_index*cards_per_player])
        print(f"{cards_per_player} cards assigned to Player {player_number} reserve deck.")
        print(f"Cards Assigned To Player {player_number}:")
        print(game.table[start_index*cards_per_player:end_index*cards_per_player])

    # Determine if there are any outlier cards
    cards_assigned = cards_per_player*len(game.players_in_draw)
    outlier_cards = len(game.table) - cards_assigned
    print(f"\nOutlier cards: {outlier_cards}")

    # If any cards remain on the table
    if not outlier_cards == 0:
        print("Outlier cards still on table.")
        # Shuffle players in draw
        print("Shuffle players in draw.")
        random.shuffle(game.players_in_draw)
        print("Players In Draw:")
        print(game.players_in_draw)

        # Determine table index for card
        table_index = (end_index*cards_per_player)

        # Assign remaining cards to players
        print("Assign remaining cards to players.")
        print(f"Table Index = {end_index} x {cards_per_player}")

        for player_number in game.players_in_draw:
            # Check if there are remaining cards
            if table_index < len(game.table):
                # Assign the current card to the player
                print(f"\nTable Index: {table_index}")
                reserve_deck = player_attr(game, player_number, 'reserve_deck')
                print(f"Assign {game.table[table_index]} to Player {player_number}")
                reserve_deck.extend([game.table[table_index]])
                table_index += 1
            else:
                # If no more cards are left, break out of the loop
                break
        
        for player_number in game.players_in_draw:
            reserve_deck = player_attr(game, player_number, 'reserve_deck')
            print(f"Player {player_number} Resere Deck:")
            print(reserve_deck)


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
    print("\nCalculate Cards:")

    correct_number_of_cards = len(game.deck)
    actual_number_of_cards = 0

    for player_number in game.players_in_game:
        deck = player_attr(game, player_number, 'deck')
        reserve_deck = player_attr(game, player_number, 'reserve_deck')
        player_number_of_cards = len(deck) + len(reserve_deck)
        print(f"Player {player_number} Number Of Cards: {player_number_of_cards}")
        actual_number_of_cards += player_number_of_cards
        print(f"Actual Number Of Cards: {actual_number_of_cards}")

    print(f"\nCorrect Number Of Cards: {correct_number_of_cards}")
    print(f"Actual Number Of Cards: {actual_number_of_cards}")

def draw_card(game, player_number):
    print(f"\nDraw Card For Player {player_number}:")

    player_deck = player_attr(game, player_number, 'deck')
    player_reserve_deck = player_attr(game, player_number, 'reserve_deck')

    if not player_deck:
        print(f"Player {player_number} deck is empty.")
        if not player_reserve_deck:
            # Return None if active deck and reserve deck are empty
            return None
        # If only active deck is empty:
        # Shuffle reserve deck
        print(f"Player {player_number} Reserve Deck:")
        print(player_reserve_deck)
        print("Shuffle reserve deck and make it the players deck.")
        random.shuffle(player_reserve_deck)
        # Add reserve deck to active deck
        player_deck.extend(player_reserve_deck)
        print(f"Player {player_number} Deck:")
        print(player_deck)
        # clear reserve deck
        player_reserve_deck.clear()

    # Return player card
    player_card = player_deck.pop(0)
    return player_card

def draw_cards_for_tiebreaker(game):
    # Used for default tiebreaker and forfeit tiebreaker
    print("\nDraw Cards For Tiebreaker:")

    players_to_remove = [] # players with less than 4 cards

    for player_number in game.players_in_round:
        deck = player_attr(game, player_number, 'deck')
        reserve_deck = player_attr(game, player_number, 'reserve_deck')
        number_player_cards = len(deck) + len(reserve_deck)
        print(f"Number of cards for Player {player_number}: {number_player_cards}")

        if number_player_cards > 3:
            # Place 4 cards on the table 
            print("Player places down three cards and plays the fourth:")
            for i in range(4):
                player_card = draw_card(game, player_number)
                assign_card_to_player(game, player_number, player_card)
                print(f"Player {player_number} places down {player_card}")

            print(f"Player {player_number} plays {player_card}")
            print(f"Player {player_number} plays tiebreaker")
            
        # If player does not have enough cards to play tiebreaker
        else:
            print(f"Player {player_number} does not have enough cards for tiebreaker.")
            # Place all of players cards on table.
            for i in range(number_player_cards):
                player_card = draw_card(game, player_number)
                assign_card_to_player(game, player_number, player_card)

            # Add player to removal list
            players_to_remove.append(player_number)  
  
    # Remove players from game who are ineligble to play tiebreaker
    print("Players To Remove:")
    print(players_to_remove)
    for player_number in players_to_remove:
        remove_player_from_game_in_tiebreaker(game, player_number)

    print("Cards on table:")
    print(game.table)

def draw_cards_for_modified_tiebreaker(game):
    # Used for modified tiebreaker and modified forfeit tiebreaker
    print("\nDraw Card For Modified Tiebreaker")
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
    print("\nDraw Cards For Players:")
    for player_number in game.players_in_round:
        player_card = draw_card(game, player_number)
        print(f"Player {player_number} draws {player_card}")
        # Assign card to player
        assign_card_to_player(game, player_number, player_card)
    print("Cards on table:")
    print(game.table)

        
def assign_card_to_player(game, player_number, player_card):
    # Assign card to players data card attribute
    player_attr(game, player_number, 'card', player_card)
    # Assign card to player for players in round list
    rank, suit = player_card
    game.players_in_round[player_number] = (rank, suit)
    # Place card in table list
    game.table.append(player_card)


def remove_players_not_in_game(game):
    print("\nRemove Players Not In Game:")
    print("Players In Game:")
    print(game.players_in_game)
    # Remove players not in game from players in game list using a static list
    for player_number in list(game.players_in_game):
        in_game = player_attr(game, player_number, 'in_game')
        print(f"Player {player_number} in game status: {in_game}")

        if not in_game:
            game.players_in_game.remove(player_number)
            game.players_out_game.append((player_number, False))
            game.number_players_in_game -= 1
            print(f"Player {player_number} removed from game.")
            # Set players round out value
            round_out = game.number_rounds
            player_attr(game, player_number, 'round_out', round_out)
    print("Players In Game:")
    print(game.players_in_game)

def remove_players_not_in_round(game):
    print("\nRemove Players Not In Round:")
    # Create a list of players to be removed
    players_to_remove = []

    # Iterate over the dictionary and check if players should be removed
    for player_number in game.players_in_round:
        in_round = player_attr(game, player_number, 'in_round')
        print(f"Player {player_number} in round status: {in_round}")

        if not in_round:
            players_to_remove.append(player_number)  # Add player to removal list

    # Remove players after iteration is complete
    for player_number in players_to_remove:
        del game.players_in_round[player_number]
        game.number_players_in_round -= 1
        print(f"Player {player_number} removed from round.")
    print("Players In Round:")
    print(game.players_in_round) 

def remove_player_from_game_in_tiebreaker(game, player_number):
    print("Remove players from game who are ineligible to play tiebreaker:")

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
    print(f"Player {player_number} exits game")

    # Set players round out value
    round_out = game.number_rounds
    player_attr(game, player_number, 'round_out', round_out)

    # Set player image to back of card
    print(f"Player {player_number} card label set to card back.")
    player_card_label = player_label_attr(game, player_number, 'card')
    player_card_label.config(image=game.card_back_images.get(game.deck_color.lower()))
    
    print("Players In Round:")
    print(game.players_in_round)
    print("Players In Game:")
    print(game.players_in_game)
    print("Players Out Game:")
    print(game.players_out_game)

def add_players_to_tiebreaker_list(game):
    print("\nAdd Players In Tiebreaker To List")
    for player_number in game.players_in_round:
        game.players_in_tiebreaker.append(player_number)

def add_players_in_draw_to_list(game):
    print("Add Players In Draw To List:")
    for player_number in game.players_in_round:
        game.players_in_draw.append(player_number)
        print(f"Player {player_number} added to players in draw list.")

def set_players_in_game(game):
    print("\nPopulate Players In Game List")
    # Add player number to players in game list
    for i in range(1, game.number_players + 1):
        player_number = i
        game.players_in_game.append(player_number)
    # Set number players in game (int)
    game.number_players_in_game = game.number_players
    print("Players in game list:")
    print(game.players_in_game)
    
def reset_players_in_round(game):
    print("\nReset Players In Round:")
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
        print(f"Player {player_number} in round.")
        
def check_players_in_game(game):
    print("\nCheck Players In Game Status:")
    for player_number in game.players_in_game:
        player_deck = player_attr(game, player_number, 'deck')
        player_reserve_deck = player_attr(game, player_number, 'reserve_deck')

        if len(player_deck) + len(player_reserve_deck) == 0:
            player_attr(game, player_number, 'in_game', False)
            print(f"Player {player_number} in game status set to False")

def check_players_in_round(game):
    print("\nCheck Players In Round Status:")
    # Remove players from round without a card rank equal to the highest card rank
    for player_number, (rank, _), in game.players_in_round.items():
        if not rank == game.highest_rank:
            player_attr(game, player_number, 'in_round', False)
            print(f"Player {player_number} in round status set to false.")
    

def get_highest_rank(game):
    print("\nGet Highest Rank:")
    print("Player cards in players in game dictionary:")
    for player_number, player_card in game.players_in_round.items():
        print(f"Player {player_number}: {player_card}")
    game.highest_rank = -1
    
    for _, (rank, _) in game.players_in_round.items():   
        # If the rank is 14, return immediately
        if rank == 14:
            game.highest_rank = rank
            print(f"\nHighest rank: {game.highest_rank}")
            return
        
        # Otherwise, check if this player's rank is higher than the current highest
        if rank > game.highest_rank:
            game.highest_rank = rank

    print(f"\nHighest rank: {game.highest_rank}")

def winner_takes_cards(game):
    print("\nWinner Takes Cards:")
    print(f"Round winner: Player {game.round_winner}")
    print("Cards assigned to winners reserve deck:")
    print(game.table)
    player_reserve_deck = player_attr(game, game.round_winner, 'reserve_deck')
    # Place all cards from table into players reserve deck
    player_reserve_deck.extend(game.table)
    print(f"Player {game.round_winner} Reserve Deck:")
    print(player_reserve_deck)
    # Clear the table
    game.table.clear()


def update_card_images(game):
    print("\nUpdate Card Images:")
    for player_number in game.players_in_round:
        player_card = player_attr(game, player_number, 'card')
        player_card_label = player_label_attr(game, player_number, 'card')
        player_card_label.config(image=game.card_images[card_name(player_card)])
        print(f"Player {player_number} card image updated to {player_card}.")

def update_card_images_for_draw(game):
    print("\nUpdate Card Images For Draw:")
    for player_number in game.players_in_round:
        # Set player image to back of card
        player_card_label = player_label_attr(game, player_number, 'card')
        player_card_label.config(image=game.card_back_images.get(game.deck_color.lower()))
        print(f"Player {player_number} card label updated to back of card.")

def update_result_label(game):
    print("\nUpdate Result Label:")
    print(f"Tiebreaker Type: {game.tiebreaker_type}")
    print(f"Is Tie Round: {game.is_tie_round}")
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
    print(f"Result label update: {result}")

def update_player_scores(game):
    print("\nUpdate Player Scores:")
    print(f"Tiebreaker Type: {game.tiebreaker_type}")
    print("Players In Game:")
    print(game.players_in_game)
    for player_number in game.players_in_game:
        # Get player deck, reserve deck and score label
        player_deck = player_attr(game, player_number, 'deck')
        player_reserve_deck = player_attr(game, player_number, 'reserve_deck')
        player_score_label = player_label_attr(game, player_number, 'score')
        print(f"\nPlayer {player_number} Deck:")
        print(player_deck)
        print(f"Player {player_number} Reserve Deck:")
        print(player_reserve_deck)

        # Calculate player score
        player_score = len(player_deck) + len(player_reserve_deck)
        print(f"Player {player_number} Score = {len(player_deck)} + {len(player_reserve_deck)}")
        # Update player score
        player_attr(game, player_number, 'score', player_score)
        print(f"Player {player_number} Score: {player_score}")
        
        # Determine score label text
        if game.tiebreaker_type == "Forefeit" and player_score < 4:
            score_text = "Not Enough Cards!"
            print(f"Player {player_number} does not have enough cards.")

        elif game.tiebreaker_type in ["Forfeit", "Modified Forfeit"] and player_score == 0:
            score_text = "Not Enough Cards!"
            print(f"Player {player_number} does not have enough cards.")
        else:
            score_text = f"Cards: {player_score}"

        # Update player score label
        player_score_label.config(text=score_text)
        print(f"Player {player_number} score label updated to {score_text}.")

    # Update scores for any players not in game who are in a tiebreaker
    print("Update Score Labels For Any Remaining Players:")
    for player_number in game.players_in_tiebreaker:
        # Determine if player has been taken out of the game yet.
        for player_number_2, taken_out in game.players_out_game:
            if player_number_2 == player_number and not taken_out:
                score_text = "Not Enough Cards!"
                score_label = player_label_attr(game, player_number, 'score')
                score_label.config(text=score_text)
                print(f"Player {player_number} score label updated to {score_text}")
        
def update_round_counter(game):
    game.number_rounds += 1
    game.round_counter_label.config(text=f"Round: {game.number_rounds:,}")

def update_player_wins_for_winner(game):
    print("\nUpdate Player Wins For Winner:")
    player_wins = player_attr(game, game.round_winner, 'wins')
    player_win_label = player_label_attr(game, game.round_winner, 'wins')
    player_wins += 1
    player_attr(game, game.round_winner, 'wins', player_wins)
    player_win_label.config(text=f"Wins: {player_wins}")
    print(f"Player {game.round_winner} wins updated to {player_wins}.")

def update_play_button_for_tiebreaker(game):
    print("\nUpdate Play Button For Tiebreaker.")
    game.play_button.config(text="Play Tiebreaker!", command=lambda:play_tiebreaker(game))

def reset_play_button_to_default(game):
    print("\nReset Play Button To Default.")
    game.play_button.config(text="Play Round!", command=lambda: play_round(game))

def determine_tiebreaker_type(game):
    print("\nDetermine Tiebreaker Type:")
    print("Players in tiebreaker:")
    print(game.players_in_round)

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
            print("Default Tiebreaker")
            return
    
    print(f"Players with at least 4 cards: {players_with_4_cards}")
    print(f"Players with at least 1 card: {players_with_1_card}")

    # Check if forfeit tiebreaker
    if players_with_4_cards == 1:
        game.tiebreaker_type = "Forfeit"
        print("Forfeit Tiebreaker")
        return

    # Check if modified tiebreaker
    if players_with_1_card > 1:
        game.tiebreaker_type = "Modified"
        print("Modified Tiebreaker")
        return

    # Check if modified forfeit tiebreaker
    if players_with_1_card == 1:
        game.tiebreaker_type = "Modified Forfeit"
        print("Modified Forfeit Tiebreaker")
        return

    # Check if draw tiebreaker
    if players_with_1_card == 0:
        print("Draw Tiebreaker")
        game.tiebreaker_type = "Draw"
        game.is_tie_round = False

def determine_winner(game):
    print("\nDetermine Winner:")

    # If round is a draw
    if game.tiebreaker_type == "Draw":
        print("Round is a draw.")

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
        print(f"Round Winner: Player {game.round_winner}")

    # If more than one players have the highest card
    elif game.number_players_in_round > 1:
        game.is_tie_round = True
        game.had_tie_round = True
        print("Tie Round")

# Function to start automating the clicks
def start_automating_clicks(game):
    print("\nStart Automating")
    if not game.automation_active:
        game.automation_active = True
        click_play_button_periodically(game)
        game.automation_button.config(text="Stop")

# Function to stop automating the clicks
def stop_automating_clicks(game):
    print("\nStop Automating")
    game.automation_active = False
    game.automation_button.config(text="Automate")

# Function that simulates the click on the play_button every second
def click_play_button_periodically(game):
    print("\nClick Play Button Periodically:")
    if game.is_game_over:
        game.automation_active = False

    if game.automation_active:
        game.play_button.invoke()
        game.root.after(game.automation_speed, lambda: click_play_button_periodically(game))
        print("Automation Operation Invoked")

# Function to handle automate button click
def toggle_automation(game):
    print("\nToggle Automation")
    print(f"Automation Active: {game.automation_active}")
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
    print("\nPlay Tiebreaker:")

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
        print("No players left for the tiebreaker.")

    # If tie:
    if game.is_tie_round:
        print("Continue tiebreaker.")

        # Update scores for players in tiebreaker
        update_player_scores(game)

        # Remove all players without the highest card from players in round list
        check_players_in_round(game)
        remove_players_not_in_round(game)

        # Continue tiebreaker by clicking play button
    else:
        print("End tiebreaker.")
        # Update result label
        update_result_label(game)

        # End the round
        end_round(game)

def end_game(game):
    print("/nEnd Game.")
    # Update game over boolean
    game.is_game_over = True

    # Determine game winner
    game.game_winner = game.players_in_game[0]
    print(f"Game Winner: Player {game.game_winner}")

    # Update result label
    player_name = player_attr(game, game.game_winner, 'name')
    game.result_label.config(text=f"{player_name} Wins The Game!")

    # Update play button
    game.play_button.config(text="Game Over!", command=None)

def end_round(game):
    print("\nEnd Round Procedure:")
    
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
    print("START NEW ROUND")
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


