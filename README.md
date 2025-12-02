# War Card Game V3

A graphical implementation of the classic War card game built with Python and Tkinter. Play with up to 100 players using multiple decks for epic card battles!

## Features

- **2-100 Player Support** - Play with any number of players from 2 to 100
- **Multiple Deck Support** - Use 1-100 decks (52 cards each) in a single game
- **Automated Gameplay** - Watch the computer play out rounds automatically
- **Customizable Names** - Choose default, random, or custom player names
- **Speed Controls** - Adjust game speed from slow to instant
- **Leaderboard** - Track scores and wins in real-time
- **Game Rules** - Built-in rules reference
- **Cross-Platform** - Works on Windows, Linux, and macOS

## Screenshots

*(Add screenshots here)*

## Installation

### Requirements

- Python 3.7 or higher (includes tkinter on Windows/macOS)
- Pillow (PIL) library

**Linux users:** If you get a "No module named 'tkinter'" error, install it via:
```bash
# Fedora/RHEL
sudo dnf install python3-tkinter

# Debian/Ubuntu  
sudo apt install python3-tk

# Arch
sudo pacman -S tk
```

### Setup

1. Clone or download this repository:
```bash
git clone https://github.com/yourusername/war-card-game.git
cd war-card-game/War_Card_Game_V3
```

2. **(Recommended)** Create a virtual environment:
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

**Note:** When using a virtual environment, you'll need to activate it each time before running the game. To deactivate when done, simply run `deactivate`.

## Usage

### Running the Game

```bash
python3 war_game_main.py
```

On Windows:
```bash
python war_game_main.py
```

### How to Play

1. Launch the application
2. Select number of players (2-100)
3. Select number of decks to use (1-100)
   - More decks = longer games with more cards in play
   - Recommended: 1 deck per 2 players
4. Choose naming method:
   - **Default**: Player 1, Player 2, etc.
   - **Random**: Random names from preset list
   - **Custom**: Enter your own names
5. Click "Start Game"
6. Click "Play Round" to play each round, or enable automation

### Controls

- **Play Round** - Execute one round of the game
- **Automation** - Toggle automatic round playing
- **Speed Up** - Increase automation speed
- **Slow Down** - Decrease automation speed
- **Rules** - View game rules
- **Leaderboard** - View current standings

## Game Rules

War is a simple card game:

1. The deck is shuffled and dealt evenly to all players
2. Each round, all players flip their top card
3. The player with the highest card wins all cards played that round
4. If there's a tie, those players go to "War":
   - Each tied player places 3 cards face down
   - Then draws another card face up
   - Highest card wins all cards
5. The game continues until one player has all the cards

**Card Rankings:**
- 2 (lowest) through 10
- Jack (11)
- Queen (12)
- King (13)
- Ace (14, highest)

**Multiple Decks:**
When using multiple decks, identical cards are treated as equal rank. If two players play the same card (e.g., both play Ace of Spades from different decks), they go to War just like any other tie.

## Project Structure

```
War_Card_Game_V3/
├── war_game_main.py          # Entry point
├── classes.py                # Game data model
├── war_game_gui.py           # Main window GUI
├── war_game_logic.py         # Game logic and rules
├── card_images.py            # Image loading
├── player_frames.py          # Player UI components
├── players.py                # Player management
├── war_start_window.py       # Startup dialog
├── name_entry_window.py      # Name entry dialog
├── leaderboard_window.py     # Leaderboard display
├── rules_window.py           # Rules display
├── random_names.py           # Random name generator
├── object_scaling.py         # UI scaling utilities
├── window_position.py        # Window positioning
├── debug.py                  # Testing utilities
├── cards/                    # Card image assets
│   ├── *.png                # 52 card images
│   ├── card_back_*.png      # Card backs (6 colors)
│   └── card_table_background.jpg
├── docs/                     # Documentation
│   ├── ARCHITECTURE.md
│   ├── QUICK_FIX_PATH_BUG.md
│   ├── UI_LAYOUT_GUIDE.md
│   └── ANALYSIS_AND_RECOMMENDATIONS.md
└── requirements.txt          # Python dependencies
```

## Development

### Debug Mode

Enable terminal output for debugging:

Edit `war_game_main.py`:
```python
game.is_terminal_active = True  # Show debug output
game.is_testing = True          # Use test values
```

### Testing

The project includes a `debug.py` module with preset test configurations:

```python
from debug import set_values_for_testing
set_values_for_testing(game)
```

## Building Standalone Executable

The project includes a PyInstaller spec file for creating standalone executables:

```bash
pyinstaller war_game_main.spec
```

The executable will be created in `dist/war_game_main/`.

## Known Issues

- Window resize doesn't dynamically adjust card sizes (planned for future update)
- Very large player counts (50+) may have small card images on low-resolution displays
- With many players, the UI may require scrolling or a larger display

## Future Enhancements

- [ ] Dynamic card resizing on window resize
- [ ] Save/load game state
- [ ] Statistics tracking across sessions
- [ ] Sound effects
- [ ] Animations for card movements
- [ ] Network multiplayer support
- [ ] Configuration file for game settings

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

### Guidelines

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is open source and available under the MIT License.

## Credits

- Card images: [Source/Attribution]
- Developed as a learning project

## Contact

Ethan - [Your contact info if you want to share]

Project Link: [https://github.com/yourusername/war-card-game](https://github.com/yourusername/war-card-game)

---

**Note:** This was one of my first Python projects, created to learn GUI programming with Tkinter and game logic implementation.
