---
type: repo-doc
project: ludicrous
description: "Archived one-page fix guide for the tkinter app's hardcoded Windows backslashes in card_images.py — the three broken lines, their pathlib replacements, the os.path.join alternative, and how to verify."
tags: [troubleshooting, filesystem]
updated: 2025-12-02
---

# Quick Fix Guide - Cross-Platform Compatibility

## The Critical Bug

**File:** `card_images.py`

**Lines to fix:** 59, 78, 92

### Current Code (BROKEN on Linux/Mac)

```python
# Line ~59
filename = f"{game.card_image_path}\\{rank.lower()}_of_{suit.lower()}.png"

# Line ~78
filename = f"{game.card_image_path}\\card_back_{color}.png"

# Line ~92
filename = f"{game.card_image_path}\\card_table_background.jpg"
```

### Fixed Code (Works Everywhere)

```python
# Line ~59
filename = game.card_image_path / f"{rank.lower()}_of_{suit.lower()}.png"

# Line ~78
filename = game.card_image_path / f"card_back_{color}.png"

# Line ~92
filename = game.card_image_path / "card_table_background.jpg"
```

### Why This Works

- `game.card_image_path` is already a `Path` object (from `pathlib`)
- The `/` operator on `Path` objects automatically uses the correct separator
- Linux/Mac: `/` (forward slash)
- Windows: `\` (backslash) 
- `pathlib` handles this automatically!

### Alternative Fix (If You Prefer String Paths)

If you want to keep string paths, use `os.path.join()`:

```python
import os

# Line ~59
filename = os.path.join(str(game.card_image_path), f"{rank.lower()}_of_{suit.lower()}.png")
```

But the `Path` operator `/` is cleaner and more modern.

## Testing After Fix

```bash
# On Linux/Mac
python3 war_game_main.py

# On Windows
python war_game_main.py
```

You should no longer see:
```
Image not found: /home/jpluto/projects/.../cards\2_of_hearts.png
```

Instead, images will load correctly!

