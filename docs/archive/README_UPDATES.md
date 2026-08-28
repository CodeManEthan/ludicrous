---
type: repo-doc
project: ludicrous
description: "Archived change log of one editing pass over the tkinter app's README: player count raised to 100, multi-deck support documented, Linux tkinter install notes, and revised known issues."
tags: [build-report, simulation]
updated: 2025-12-02
---

# README.md Updates - Change Log

## Changes Made

### 1. Updated Player Count
- **Old:** "Play against 1-19 computer opponents"
- **New:** "Play with up to 100 players"
- **Old:** "2-20 Player Support"
- **New:** "2-100 Player Support"

### 2. Added Multiple Deck Feature
- **New Feature Listed:** "Multiple Deck Support - Use 1-100 decks (52 cards each) in a single game"

### 3. Enhanced Requirements Section
Added tkinter installation instructions for Linux users:
```markdown
**Linux users:** If you get a "No module named 'tkinter'" error, install it via:
# Fedora/RHEL
sudo dnf install python3-tkinter

# Debian/Ubuntu  
sudo apt install python3-tk

# Arch
sudo pacman -S tk
```

### 4. Updated How to Play Instructions
Added step for deck selection:
```markdown
3. Select number of decks to use (1-100)
   - More decks = longer games with more cards in play
   - Recommended: 1 deck per 2 players
```

### 5. Added Multiple Deck Rules Explanation
New section explaining how identical cards work with multiple decks:
```markdown
**Multiple Decks:**
When using multiple decks, identical cards are treated as equal rank. 
If two players play the same card (e.g., both play Ace of Spades from 
different decks), they go to War just like any other tie.
```

### 6. Updated Known Issues
- **Old:** "Large player counts (15+) may have small card images"
- **New:** "Very large player counts (50+) may have small card images"
- **Added:** "With many players, the UI may require scrolling or a larger display"

## Summary

The README now accurately reflects that your game supports:
- ✅ 2-100 players (not just 2-20)
- ✅ 1-100 decks (previously not mentioned)
- ✅ Linux tkinter installation guidance
- ✅ Better explanation of how multiple decks work
- ✅ Updated UI constraints for very large games

The documentation is now complete and accurate! 🎉
