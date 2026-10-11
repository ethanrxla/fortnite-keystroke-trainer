"""Render the flag-room panels (assets/theme/flags/flags_NN.png) from the flag-icons SVG set (MIT, lipis/flag-icons).

    python tools/render_flag_panels.py <path to an extracted flag-icons npm package>

Player 2026-10-11: the edit wing is a flag room with the flags of every country. Each panel is a 3 x 2 grid of flags
(country.json's ISO entries, alphabetical) with the name under each flag, drawn by headless Microsoft Edge from an
HTML page that shows the SVGs as <img> (no SVG script runs). build_theme_rooms.py --only flags mounts the panels.
"""
import html
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "theme" / "flags"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
COLS, ROWS = 3, 2
CELL_W, FLAG_H, NAME_H = 320, 240, 64
W, H = COLS * CELL_W, ROWS * (FLAG_H + NAME_H)


def page(entries, pkg):
    cells = []
    for e in entries:
        src = (pkg / e["flag_4x3"]).resolve().as_uri()
        cells.append(f'<div class="c"><img src="{src}"><div class="n">{html.escape(e["name"])}</div></div>')
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:#0b0f14}}
.g{{display:grid;grid-template-columns:repeat({COLS},{CELL_W}px);grid-auto-rows:{FLAG_H + NAME_H}px}}
.c{{display:flex;flex-direction:column;align-items:center;justify-content:flex-start;padding-top:10px;box-sizing:border-box}}
img{{width:{CELL_W - 40}px;height:{FLAG_H - 30}px;object-fit:fill;border:3px solid #e8ecf4;box-sizing:border-box}}
.n{{font:600 26px Bahnschrift,'Segoe UI',sans-serif;color:#f2d14a;margin-top:6px;white-space:nowrap;overflow:hidden;
text-overflow:ellipsis;max-width:{CELL_W - 16}px;text-align:center}}
</style></head><body><div class="g">{''.join(cells)}</div></body></html>"""


def main():
    pkg = pathlib.Path(sys.argv[1])
    entries = sorted((e for e in json.loads((pkg / "country.json").read_text(encoding="utf-8")) if e.get("iso")),
                     key=lambda e: e["name"])
    OUT.mkdir(parents=True, exist_ok=True)
    per = COLS * ROWS
    tmp = pathlib.Path(tempfile.mkdtemp())
    for k in range(0, len(entries), per):
        n = k // per
        f = tmp / f"p{n}.html"
        f.write_text(page(entries[k:k + per], pkg), encoding="utf-8")
        png = OUT / f"flags_{n:02d}.png"
        subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={W},{H}",
                        f"--screenshot={png}", "--allow-file-access-from-files", f.as_uri()], check=True,
                       capture_output=True, timeout=60)
        print(png.name, len(entries[k:k + per]))


if __name__ == "__main__":
    main()
