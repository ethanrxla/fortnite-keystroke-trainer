"""Every Fortnite action a keybind profile should cover, with a category and Fortnite's default key.

The overlay and the analysis treat a press as a mistake only if the key is not bound to *any* of these actions
(or learned as a habit), so movement, sprint, hotbar and the rest never show up as accidents. Players override the
defaults through `python -m keystroke_lab binds` (writes companion/keybinds.json). Several actions may share one key.

Categories: move, combat, build, edit, ui.
"""

# (action id, prompt shown while calibrating, category, default key in pynput naming)
ACTIONS = [
    ("forward", "move FORWARD", "move", "w"),
    ("left", "move LEFT", "move", "a"),
    ("back", "move BACK", "move", "s"),
    ("right", "move RIGHT", "move", "d"),
    ("sprint", "SPRINT", "move", "shift"),
    ("jump", "JUMP", "move", "space"),
    ("crouch", "CROUCH / slide", "move", "ctrl_l"),
    ("fire", "FIRE", "combat", "mouse_left"),
    ("aim", "AIM down sights", "combat", "mouse_right"),
    ("reload", "RELOAD", "combat", "r"),
    ("pickaxe", "PICKAXE slot", "combat", "f1"),
    ("slot1", "weapon slot 1", "combat", "1"),
    ("slot2", "weapon slot 2", "combat", "2"),
    ("slot3", "weapon slot 3", "combat", "3"),
    ("slot4", "weapon slot 4", "combat", "4"),
    ("slot5", "weapon slot 5", "combat", "5"),
    ("wall", "WALL (build)", "build", "q"),
    ("floor", "FLOOR (build)", "build", "f2"),
    ("ramp", "RAMP / stairs (build)", "build", "f3"),
    ("cone", "ROOF / cone (build)", "build", "f4"),
    ("trap", "TRAP slot", "build", "f5"),
    ("material", "SWITCH MATERIAL", "build", "z"),
    ("rotate", "ROTATE piece", "build", "r"),
    ("repair", "REPAIR build", "build", "b"),
    ("edit", "EDIT", "edit", "g"),
    ("edit_confirm", "EDIT CONFIRM", "edit", "mouse_left"),
    ("reset", "EDIT RESET", "edit", "f"),
    ("use", "USE / interact", "ui", "e"),
    ("map", "MAP", "ui", "m"),
    ("inventory", "INVENTORY / bag", "ui", "tab"),
    ("chat", "CHAT", "ui", "enter"),
    ("push_to_talk", "PUSH TO TALK", "ui", "t"),
    ("emote", "EMOTE wheel", "ui", "b"),
    ("ping", "PING", "ui", "mouse_middle"),
]
# Older profiles and drills.json use this name for "the key of your first gun slot".
LEGACY_ALIASES = {"swap_weapon": "slot1"}

CATEGORIES = ["move", "combat", "build", "edit", "ui"]
DEFAULTS = {a: k for a, _, _, k in ACTIONS}
PROMPTS = {a: p for a, p, _, _ in ACTIONS}
CATEGORY_OF = {a: c for a, _, c, _ in ACTIONS}


def actions_in(categories):
    """Action ids in catalogue order for the given categories (all when None)."""
    wanted = set(categories) if categories else set(CATEGORIES)
    return [a for a, _, c, _ in ACTIONS if c in wanted]
