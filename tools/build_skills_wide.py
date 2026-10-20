"""Skills Test wide mode: bot spawners spread over the whole aim plate, additive (KT15_SkillsWide_* only).

    python tools/build_skills_wide.py [--dry-run]
    python tools/build_skills_tiles.py       # the WIDE tile and its light

Player 2026-10-11: one bot at a time across the whole arena, separate from the lane range, for wider flicks.
The spawners are set up like the lane's (tools/build_skills_test.py bot_props: 100 health, no shield, no weapon,
disabled until a rep) and tagged kt_skills_wide_bot_tag; the A2 lane's kt_skills_test_device collects every one
inside its box (SkillsTest.verse HalfExtent 6500 x 3400 x 1500), and the WIDE tile switches a run between the lane's
spawners and these. Spots run 6 to 90 m out and from the plate's south edge to its north edge, clear of the A4
recoil wall, ordered so neighbours in the list are far apart.
"""

import sys as _sys
# RETIRED (player 2026-10-20): the Skills Test WIDE bots, which spilled into the gun range lanes were removed from the aim practice area. The Skills Test runs from its
# Start / Difficulty / Weapon buttons. Pass --i-know to rebuild anyway.
if __name__ == "__main__" and "--i-know" not in _sys.argv:
    raise SystemExit("build_skills_wide.py: retired 2026-10-20 (the Skills Test WIDE bots, which spilled into the gun range lanes). Pass --i-know to run anyway.")
if "--i-know" in _sys.argv:
    _sys.argv.remove("--i-know")

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_map as bm  # noqa: E402
import build_skills_test as st  # noqa: E402

PREFIX = "KT15_SkillsWide_"
# (metres from the A2 shoot line, sideways cm from the A2 lane centre; + is north, towards A4)
SPOTS = [(6, -2200), (9, 2600), (12, -1100), (16, 3200), (20, -2700), (24, 1500), (28, -300), (33, -3000),
         (45, 2900), (50, -1900), (58, 1000), (66, -3100), (75, 2500), (84, -800), (90, 3100)]
HALF = (6500.0, 3400.0, 1500.0)
CENTRE = (st.SHOOT_X + 2750.0, st.LANE_Y, -150.0)
RECOIL_WALL = (-31300.0, -30600.0, -85600.0)      # x0, x1, y0 (it runs north to the plate edge)


def plan():
    out = []
    for n, (m, off) in enumerate(SPOTS):
        x, y = st.SHOOT_X + m * 100.0, st.LANE_Y + off
        assert abs(x - CENTRE[0]) <= HALF[0] and abs(y - CENTRE[1]) <= HALF[1], (m, off)
        assert not (RECOIL_WALL[0] <= x <= RECOIL_WALL[1] and y >= RECOIL_WALL[2]), (m, off)
        out.append((f"{PREFIX}Bot_{n:02d}_{m}m", x, y))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    spots = plan()
    for s in spots:
        print(s)
    if args.dry_run:
        return
    b = bm.Builder()
    old = [a for a in (b.m.tool(bm.SCENE, "find_actors", name=PREFIX, collision_channels=[]) or []) if a["label"].startswith(PREFIX)]
    for a in old:
        b.m.tool(bm.SCENE, "remove_from_scene", actor={"refPath": a["actorPath"]})
    refused = []
    for label, x, y in spots:
        path = b.device(bm.GUARD, label, x, y, 0.0)
        b.face(path, 180.0)                      # face the shooter (west, -X)
        for key, value in {**st.bot_props(), **st.NO_WEAPON}.items():
            try:
                b.props(path, {key: value})
            except RuntimeError as exc:
                refused.append(f"{label}: {key} ({str(exc)[-50:]})")
        b.tag(path, "kt_skills_wide_bot_tag")
        b.m.tool(bm.SCENE, "save_actor", actor={"refPath": path})
    print(f"placed {len(spots)} wide spawners (removed {len(old)})")
    if refused:
        print("not accepted:\n  " + "\n  ".join(sorted(set(r.split(': ', 1)[1] for r in refused))))


if __name__ == "__main__":
    main()
