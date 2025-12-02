from PIL import Image, ImageTk
from pathlib import Path
from object_scaling import get_scaled_object_size
from object_scaling import get_scaled_object_size_for_horizontal_fit

"""
Card Images:
- Width: 500
- Height:

Card Back Images:
- Width: 686
- Height: 976

"""
    

def print_card_images(game):
    for key, value in game.card_images.items():
        # The key is a string like "Ace of Spades"
        print(f"Card Name: {key}, Image Object: {value}") 

def print_card_back_images(game):
    print()
    print("Card Back Images:")
    for key, value in game.card_back_images.items():
        print(f"Color: {key} -> Image: {value}")     
    print()


def find_card_image_path(game):
    # Get the directory of the current script
    script_dir = Path(__file__).parent

    # Construct the path to the images folder
    game.card_image_path = script_dir / 'cards'

# load each card face images into card images dictionary
# Use (rank, suit) as the key for each image
def load_card_face_images(game):
    # Get width and height of card images based on display size
    card_width, card_height = get_scaled_object_size(game.display_width, game.display_height, 100, 140)
    print("Scaled Card Width: " + str(card_width))
    print("Scaled Card Height: " + str(card_height))
    # Get width and height of card images based on fitting 20 cards in a row
    game.card_width, game.card_height = get_scaled_object_size_for_horizontal_fit(20, card_width, card_height, 5, 20, game.display_width)
    print("Adjusted Card Width: " + str(game.card_width))
    print("Adjusted Card Height: " + str(game.card_height))

    # Define all possible suits and ranks
    suits = ["Hearts", "Diamonds", "Clubs", "Spades"]
    ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "Jack", "Queen", "King", "Ace"]
    
    # Clear card images dictionary
    game.card_images.clear()

    for suit in suits:
        for rank in ranks:
            # Construct file path for card image
            filename = game.card_image_path / f"{rank.lower()}_of_{suit.lower()}.png"
            # Constuct the card name
            card_name = f"{rank} of {suit}"
            try:
                # Open image
                img = Image.open(filename)
                # Resize image
                img = img.resize((game.card_width, game.card_height), Image.Resampling.LANCZOS)
                # store resized image in card images dictionary
                game.card_images[card_name] = ImageTk.PhotoImage(img)
            except FileNotFoundError:
                print(f"Image not found: {filename}")
    # Print card images dictionary
    if game.is_terminal_active:
        print_card_images(game)

def load_card_back_images(game):
    colors = ["black", "blue", "green", "orange", "purple", "red"]

    game.card_back_images.clear()

    for color in colors:
        filename = game.card_image_path / f"card_back_{color}.png"
        try:
            img = Image.open(filename)
            img = img.resize((game.card_width, game.card_height), Image.Resampling.LANCZOS)
            game.card_back_images[color] = ImageTk.PhotoImage(img)
        except FileNotFoundError:
            print(f"Image not found: {filename}")
    # Print card back images dictionary
    if game.is_terminal_active:
        print_card_back_images(game)                

def load_card_table_image(game):
    filename = game.card_image_path / f"card_table_background.jpg"
    img = Image.open(filename)
    #img = img.resize(game.display_width, game.display_height), Image.Resampling.LANCZOS
    game.card_table_image = ImageTk.PhotoImage(img)
        