# Project Architecture Overview

## Module Breakdown

### Core Application Files

#### `war_game_main.py` - Entry Point
**Purpose:** Application initialization and startup orchestration

**Responsibilities:**
- Creates Main_Game instance
- Initializes display and window
- Loads card images
- Launches startup window
- Handles testing mode

**Flow:**
1. Create game object
2. Set modes (application/terminal/testing)
3. Create root window
4. Load card assets
5. Show startup GUI

---

#### `classes.py` - Data Model
**Purpose:** Central data structures

**Main Class: `Main_Game`**
Contains all game state:
- Window references (root, startup, rules, leaderboard)
- Configuration flags (terminal, application, automation)
- Game data structures:
  - `players_data` - Dict of player attributes
  - `players_labels` - Dict of UI label references
  - `deck` - All cards in play
  - `table` - Cards currently on table
  - `players_in_game` - Active player list
  - `players_in_round` - Players in current round
- Image storage (card_images, card_back_images)
- UI measurements (display size, card dimensions)

---

### GUI Modules

#### `war_game_gui.py` - Main Window
**Purpose:** Creates and configures the main game window

**Key Functions:**
- `create_war_game_gui()` - Initialize Tkinter window
- `setup_war_game_gui()` - Configure layout, buttons, frames

**Components Created:**
- Table frame (where cards are displayed)
- Control buttons (Play Round, Automation, Speed controls)
- Result label
- Menu bar (Rules, Leaderboard)

---

#### `war_start_window.py` - Startup Dialog
**Purpose:** Initial configuration before game starts

**Features:**
- Player count selection (2-20 players)
- Name selection method (default/random/custom)
- Start button to launch game

---

#### `name_entry_window.py` - Custom Names
**Purpose:** Allow players to enter custom names

---

#### `rules_window.py` - Rules Display
**Purpose:** Shows game rules in popup window

---

#### `leaderboard_window.py` - Score Display
**Purpose:** Shows current standings and scores

---

### Logic Modules

#### `war_game_logic.py` - Game Engine
**Purpose:** Core game logic and rules

**Major Functions:**
- `populate_deck()` - Create standard 52-card deck
- `shuffle_and_split_deck()` - Distribute cards to players
- `play_round()` - Execute one round of play
- `draw_cards_for_players()` - Each player draws a card
- `compare_cards()` - Determine round winner
- `handle_draw()` - War scenario (tied cards)
- `update_scores()` - Track wins and card counts
- `check_for_winner()` - End game condition
- `update_card_images()` - Refresh UI with current cards

**Game Flow:**
1. Draw cards for all players
2. Compare card ranks
3. If tie → War (players bet 3 cards, draw again)
4. Winner takes all cards on table
5. Update scores and UI
6. Check if game over

---

### Player Management

#### `players.py` - Player Data
**Purpose:** Initialize and manage player data structures

**Functions:**
- `create_player_instances()` - Set up player dictionaries
- `assign_default_player_names()` - "Player 1", "Player 2", etc.
- `assign_random_player_names()` - Random name selection
- `populate_players_in_game()` - Track active players
- `reset_players_in_round()` - Reset round participation
- `update_leaderboard_rank()` - Calculate player rankings

---

#### `player_frames.py` - Player UI
**Purpose:** Create and position player display areas

**Functions:**
- `create_player_objects()` - Create labels for name, card, score, wins
- `place_player_frames()` - Position frames in table
- `remove_frames_for_players_out_of_game()` - Hide eliminated players

**Layout Logic:**
- Calculates grid positions for N players
- Adjusts for eliminated players
- Responsive positioning based on player count

---

### Utility Modules

#### `card_images.py` - Asset Loading
**Purpose:** Load and scale card images

**Functions:**
- `find_card_image_path()` - Locate cards directory
- `load_card_face_images()` - Load all 52 card faces
- `load_card_back_images()` - Load card back designs
- `load_card_table_image()` - Load background

**Image Processing:**
- Scales images based on display size
- Stores as PhotoImage objects
- Handles multiple card back colors

---

#### `object_scaling.py` - Responsive Sizing
**Purpose:** Calculate UI element sizes for different displays

**Functions:**
- `get_scaled_object_size()` - Scale based on display dimensions
- `get_scaled_object_size_for_horizontal_fit()` - Fit N objects in width
- `get_adjusted_font_size()` - Scale text for readability

---

#### `window_position.py` - Window Management
**Purpose:** Position windows on screen

**Functions:**
- `center_window_to_display()` - Center a window

---

#### `window_scaling.py` - (If exists)
**Purpose:** Handle window resize events

---

#### `random_names.py` - Name Generator
**Purpose:** Provide random player names

Contains list of preset names for random assignment.

---

#### `debug.py` - Testing Tools
**Purpose:** Set up test scenarios

**Functions:**
- `set_values_for_testing()` - Configure test mode
- `set_values_2_for_testing()` - Alternative test setup

---

## Data Flow

```
war_game_main.py
    ↓
classes.Main_Game (game object)
    ↓
war_game_gui.py (create UI)
    ↓
card_images.py (load assets)
    ↓
war_start_window.py (config)
    ↓
players.py (setup players)
    ↓
player_frames.py (create UI elements)
    ↓
war_game_logic.py (game loop)
    ↓
(repeat rounds until winner)
```

## Key Design Patterns

### 1. **Central Game Object**
- All state stored in single `Main_Game` instance
- Passed to all functions
- Acts as global context

### 2. **Separation of Concerns**
- GUI creation separate from logic
- Data model separate from presentation
- Utilities are modular and reusable

### 3. **Dictionary-Based Player Management**
- Players stored as dictionaries keyed by player number
- Easy to add/remove players dynamically
- Flexible data structure

### 4. **Image Preloading**
- All card images loaded at startup
- Stored in dictionaries for O(1) access
- Avoids I/O during gameplay

## Potential Improvements

1. **Event-Driven Architecture**
   - Currently uses button callbacks
   - Could use event queue for better decoupling

2. **Model-View-Controller (MVC)**
   - Separate game state from UI more strictly
   - Make logic testable without GUI

3. **Configuration Management**
   - Externalize magic numbers
   - Use config file for game rules

4. **State Machine**
   - Explicit game states (SETUP, PLAYING, WAR, GAME_OVER)
   - Clearer state transitions
