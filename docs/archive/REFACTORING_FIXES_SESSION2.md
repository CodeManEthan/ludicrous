---
type: repo-doc
project: ludicrous
description: "Archived line-by-line record of session 2 of the debug refactor: every debug_print call missing the `game` parameter, listed per file with old and new call signatures, plus the verification performed."
tags: [build-report, architecture, troubleshooting]
updated: 2025-12-02
---

# Refactoring Fixes - Session 2

## Date: December 2, 2024

## Summary
Fixed missing `game` parameter in debug function calls throughout the codebase. The previous refactoring session created the debug_output.py module with functions that require the `game` parameter, but some function calls were missing this parameter.

## Files Fixed

### 1. war_game_gui.py
**Issue:** `debug_print_gui_setup_complete()` called without `game` parameter
**Fix:** Changed to `debug_print_gui_setup_complete(game)`
**Line:** 119

### 2. rules_window.py
**Issue:** `debug_print_empty_function_call()` called without `game` parameter
**Fix:** Changed to `debug_print_empty_function_call(game)`
**Line:** 50

### 3. leaderboard_window.py
**Issue:** `debug_print_empty_function_call()` called without `game` parameter
**Fix:** Changed to `debug_print_empty_function_call(game)`
**Line:** 46

### 4. war_game_logic.py
**Issues Fixed (13 total):**

1. **Line 453:** `debug_print_player_score_label_updated(player_number, score_text)`
   - Fixed to: `debug_print_player_score_label_updated(game, player_number, score_text)`
   - Applied to 2 occurrences

2. **Line 456:** `debug_print_update_remaining_scores()`
   - Fixed to: `debug_print_update_remaining_scores(game)`

3. **Line 477:** `debug_print_player_wins_updated(game.round_winner, player_wins)`
   - Fixed to: `debug_print_player_wins_updated(game, game.round_winner, player_wins)`

4. **Line 480:** `debug_print_update_play_button_tiebreaker()`
   - Fixed to: `debug_print_update_play_button_tiebreaker(game)`

5. **Line 484:** `debug_print_reset_play_button()`
   - Fixed to: `debug_print_reset_play_button(game)`

6. **Line 550:** `debug_print_round_is_draw()`
   - Fixed to: `debug_print_round_is_draw(game)`

7. **Line 582:** `debug_print_tie_round()`
   - Fixed to: `debug_print_tie_round(game)`

8. **Line 586:** `debug_print_start_automating()`
   - Fixed to: `debug_print_start_automating(game)`

9. **Line 594:** `debug_print_stop_automating()`
   - Fixed to: `debug_print_stop_automating(game)`

10. **Line 600:** `debug_print_click_play_button_periodically()`
    - Fixed to: `debug_print_click_play_button_periodically(game)`

11. **Line 665:** `debug_print_no_players_in_tiebreaker()`
    - Fixed to: `debug_print_no_players_in_tiebreaker(game)`

12. **Line 669:** `debug_print_continue_tiebreaker()`
    - Fixed to: `debug_print_continue_tiebreaker(game)`

13. **Line 680:** `debug_print_end_tiebreaker()`
    - Fixed to: `debug_print_end_tiebreaker(game)`

14. **Line 776:** `debug_print_start_new_round()`
    - Fixed to: `debug_print_start_new_round(game)`

## Verification

### Code Quality Checks Performed:
1. ✅ Searched for remaining `debug_print.*\(\)` calls without parameters - Found and fixed all occurrences
2. ✅ Verified no raw `print()` statements remain in main game files:
   - war_game_*.py files: Clean
   - player*.py files: Clean
   - card*.py files: Clean
   - object_scaling.py: Clean

### Testing Status:
- Application structure verified
- All debug function calls now properly pass the `game` parameter
- Ready for testing with actual GUI launch

## Next Steps:
1. Launch the game with GUI to test functionality
2. Verify debug output appears when `is_terminal_active = True`
3. Verify no debug output when `is_terminal_active = False`
4. Test all game features to ensure nothing was broken

## Notes:
- All fixes maintain consistency with the debug_output.py module design
- No changes to game logic - only parameter fixes to debug calls
- The refactoring maintains the centralized debug architecture
