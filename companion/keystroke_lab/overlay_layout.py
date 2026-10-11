"""Shared left-column spacing for the companion's independent HUD windows."""

# The guide reserves a slot below itself for session stats and above the keyboard.
# Keep these values aligned with the stats panel dimensions without importing a UI
# module into edit_window (which would couple their startup paths).
STATS_SLOT_GAP = 8
BASE_STATS_HEIGHT = 150
BASE_UNIT = 30


def units(game_height, scale):
    keyboard = max(22, min(42, int(game_height / 54 * max(1.0, min(scale, 2.0)))))
    guide = max(22, min(42, int(game_height / 54 * 1.5)))
    return keyboard, guide


def stats_height(game_height, scale):
    keyboard, guide = units(game_height, scale)
    return round(BASE_STATS_HEIGHT * min(keyboard, guide) / BASE_UNIT)


def edit_guide_lift(game_height, scale, keyboard_rows=11):
    """Lift the guide enough to fit stats between it and the keyboard at this scale."""
    keyboard, guide = units(game_height, scale)
    return max(0, stats_height(game_height, scale) + STATS_SLOT_GAP + keyboard_rows * (keyboard - guide))
