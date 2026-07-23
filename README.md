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

### Option 1: Windows Installer

Windows users can skip the Python setup entirely — run the installer in the
`installers/` folder (`War Card Game Installer.exe`) and launch the game from
the Start menu.

### Option 2: Run from Source

#### Requirements

- Python 3.7 or higher, with tkinter
- [Pillow](https://pypi.org/project/Pillow/) (installed via `requirements.txt`)

**Linux users:** tkinter is not always installed by default. If you get a
"No module named 'tkinter'" error:

```bash
# Fedora/RHEL
sudo dnf install python3-tkinter

# Debian/Ubuntu
sudo apt install python3-tk

# Arch
sudo pacman -S tk
```

#### Setup

1. Clone or download this repository:

```bash
git clone https://github.com/yourusername/war-card-game.git
cd war-card-game
```

2. Create and activate a virtual environment (recommended):

```bash
python3 -m venv venv

# On Linux/macOS:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

> **Note (Fedora/RHEL):** If you skip the virtual environment and use the
> system Pillow package, the game may fail with
> `ImportError: cannot import name 'ImageTk'`. Either use the virtual
> environment as shown above, or install the system package that provides
> Pillow's tkinter support: `sudo dnf install python3-pillow-tk`.

## Usage

### Web Simulator (new)

Simulate entire games instantly, then play them back at any speed — scrub like
a video, watch wars unfold, and see card counts charted over time:

```bash
python3 server.py
```

Then open http://localhost:8000. Configure players (2-100), decks (1-100), and
an optional seed (same seed = same game, reproducible and shareable). Games too
long for card-by-card playback automatically show an aggregate view with the
card-count chart and elimination timeline. You can also import recordings saved
with `simulate.py --json`. No extra dependencies — standard library only.

### Running the Game (tkinter)

With your virtual environment activated:

```bash
python3 app.py
```

On Windows:

```bash
python app.py
```

Remember to activate the virtual environment (`source venv/bin/activate`)
each time you open a new terminal. Run `deactivate` when you're done.

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
war-card-game/
├── app.py                    # Entry point — run this to start the game
├── engine/                   # Headless game engine (no GUI) — see docs/ENGINE.md
├── server.py                 # Web simulator server (python3 server.py)
├── web/                      # Browser playback UI (HTML/CSS/JS, no build step)
├── simulate.py               # CLI: simulate full games without the GUI
├── tests/                    # Engine test suite
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
├── app.spec                  # PyInstaller build configuration
├── cards/                    # Card image assets
│   ├── *.png                 # 52 card images
│   ├── card_back_*.png       # Card backs (6 colors)
│   └── card_table_background.jpg
├── docs/                     # Documentation (architecture, UI guide, etc.)
├── installers/               # Prebuilt Windows installer
└── requirements.txt          # Python dependencies
```

## Development

### Headless Simulation Engine

The game logic lives in the standalone `engine/` package (no GUI dependency) —
this powers the CLI simulator and will drive the upcoming web frontend.
See [docs/ENGINE.md](docs/ENGINE.md) for the API and event format.

Simulate full games from the command line:

```bash
python3 simulate.py -p 100 -d 50 --seed 42     # 100 players, 50 decks, reproducible
python3 simulate.py -p 6 -d 3 --json game.json  # save a replayable recording
```

Run the engine test suite:

```bash
python3 -m unittest discover -v
```

### Debug Mode

Enable terminal output for debugging by editing the flags near the top of `app.py`:

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

## Building a Standalone Executable

The project includes a PyInstaller spec file for creating a standalone executable:

```bash
pip install pyinstaller
pyinstaller app.spec
```

This builds `app.py` into a single-file executable at `dist/app`
(`dist/app.exe` on Windows), with the card images bundled in.

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

---

**Note:** This was one of my first Python projects, created to learn GUI programming with Tkinter and game logic implementation.
