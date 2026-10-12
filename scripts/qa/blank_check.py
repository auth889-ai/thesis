"""Is a map area of a screenshot blank? Counts the distinct colours (quantised to 16 levels per channel) in the area, downscaled.
A drawn map has roads, water, labels: dozens of colours; a blank one (only the style's background, or white) has a handful.

    python3 scripts/qa/blank_check.py SCREENSHOT.png X Y W H      -> "<n> colours" or "BLANK <n> colours"
"""
import sys
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

from PIL import Image

MIN_COLOURS = 12


def colours(path: str, x: int, y: int, w: int, h: int) -> int:
    im = Image.open(path).convert("RGB").crop((x, y, x + w, y + h))
    im = im.resize((max(1, w // 4), max(1, h // 4)))
    return len({(r >> 4, g >> 4, b >> 4) for r, g, b in im.getdata()})


if __name__ == "__main__":
    n = colours(sys.argv[1], *(int(v) for v in sys.argv[2:6]))
    print(f"{n} colours" if n >= MIN_COLOURS else f"BLANK {n} colours")
