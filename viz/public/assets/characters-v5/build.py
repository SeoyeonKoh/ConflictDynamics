"""Turn the characters-v4 sheets into small pixel sprites that match the office-v3 furniture.

Only two poses are shrunk from the originals: standing (idle-0) and seated (sit-0). Every other
frame is made from those two by moving whole pixel rows, so a face never re-samples between frames
and the animation does not shimmer:

- idle: the upper body sinks one pixel on the out-breath.
- walk: one foot lifts while the body rises one pixel, then the other foot.
- talk: the head nods up one pixel.
- sit: the head and shoulders sink one pixel.

Shrinking: one art pixel is one world pixel; the figure is 44 pixels tall (46 with the outline).
Each cell takes the most common colour of its block after the pose is reduced to a fourteen-colour
palette, and the darkest colour wins a cell when it covers a fifth of it, so eyes survive. The
silhouette is cleaned of one-pixel spurs and notches, then outlined with a darkened shade of the
colour beside it rather than one flat black.
Run: python3 viz/public/assets/characters-v5/build.py
"""
import json
from collections import Counter
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "characters-v4"
BODY = 44  # art pixels, before the outline
COLOURS = 14
LINE = (46, 38, 36)
POSES = ["idle-0", "idle-1", "walk-0", "walk-1", "walk-2", "walk-3",
         "sit-0", "sit-1", "talk-0", "talk-1"]
NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def pose_canvas(sheet, entry):
    """The pose on its untrimmed canvas, so every pose of a character lines up."""
    f, at, size = entry["frame"], entry["spriteSourceSize"], entry["sourceSize"]
    canvas = Image.new("RGBA", (size["w"], size["h"]), (0, 0, 0, 0))
    canvas.paste(sheet.crop((f["x"], f["y"], f["x"] + f["w"], f["y"] + f["h"])), (at["x"], at["y"]))
    return canvas


def palette(canvas):
    alpha = canvas.getchannel("A")
    points = [p for p, a in zip(canvas.convert("RGB").getdata(), alpha.getdata()) if a >= 128]
    strip = Image.new("RGB", (len(points), 1))
    strip.putdata(points)
    return strip.quantize(COLOURS, method=Image.Quantize.MEDIANCUT, kmeans=3)


def pixelate(canvas, pal):
    """The pose as a grid {(x, y): colour} with a one-pixel margin left for the outline."""
    sw, sh = canvas.size
    w = round(sw * BODY / sh)
    indexed = canvas.convert("RGB").quantize(palette=pal, dither=Image.Dither.NONE)
    colour, alpha, rgb = indexed.load(), canvas.getchannel("A").load(), indexed.getpalette()
    dark = min(set(indexed.getdata()), key=lambda k: sum(rgb[k * 3:k * 3 + 3]))
    grid = {}
    for j in range(BODY):
        for i in range(w):
            x0, x1 = i * sw // w, (i + 1) * sw // w
            y0, y1 = j * sh // BODY, (j + 1) * sh // BODY
            votes, total = Counter(), 0
            for y in range(y0, y1, 2):
                for x in range(x0, x1, 2):
                    total += 1
                    if alpha[x, y] >= 128:
                        votes[colour[x, y]] += 1
            filled = sum(votes.values())
            if not votes or filled * 2 < total:
                continue
            k = dark if votes[dark] * 5 >= filled else votes.most_common(1)[0][0]
            grid[i + 1, j + 1] = tuple(rgb[k * 3:k * 3 + 3])
    return clean(grid), (w + 2, BODY + 2)


def clean(grid):
    """Drop one-pixel spurs and fill one-pixel notches so the silhouette reads smoothly."""
    for _ in range(2):
        spurs = [p for p in grid
                 if sum((p[0] + dx, p[1] + dy) in grid for dx, dy in NEIGHBOURS) <= 1]
        for p in spurs:
            del grid[p]
        notches = {}
        xs = [x for x, _ in grid]
        ys = [y for _, y in grid]
        for y in range(min(ys), max(ys) + 1):
            for x in range(min(xs), max(xs) + 1):
                if (x, y) in grid:
                    continue
                around = [grid[x + dx, y + dy] for dx, dy in NEIGHBOURS if (x + dx, y + dy) in grid]
                if len(around) >= 3:
                    notches[x, y] = Counter(around).most_common(1)[0][0]
        grid.update(notches)
    return grid


def shift(grid, rows, dx=0, dy=0, cols=None):
    """Move the pixels in the given rows (and columns) by (dx, dy); they cover what is under them."""
    moved = {p: c for p, c in grid.items()
             if rows[0] <= p[1] < rows[1] and (cols is None or cols[0] <= p[0] < cols[1])}
    out = {p: c for p, c in grid.items() if p not in moved}
    if dy < 0:  # the row left behind keeps its pixels: the part stretches instead of tearing
        out.update({p: c for p, c in moved.items() if p[1] == rows[1] - 1})
    out.update({(x + dx, y + dy): c for (x, y), c in moved.items()})
    return out


def regions(grid):
    """Head, body and feet rows of a standing figure, and the x that splits the two legs."""
    ys = [y for _, y in grid]
    top, bottom = min(ys), max(ys) + 1
    height = bottom - top
    neck = top + round(height * 0.56)  # chibi proportions: the head is a little over half
    hips = bottom - max(3, round(height * 0.16))
    legs = [x for x, y in grid if y >= hips]
    middle = (min(legs) + max(legs) + 1) // 2
    return top, neck, hips, bottom, middle


def frames(stand, sit):
    top, neck, hips, bottom, middle = regions(stand)
    left, right = (0, middle), (middle, 999)
    lifted_left = shift(stand, (hips, bottom), dy=-1, cols=left)
    lifted_right = shift(stand, (hips, bottom), dy=-1, cols=right)
    s_top, s_neck, *_ = regions(sit)
    return {
        "idle-0": stand,
        "idle-1": shift(stand, (top, hips - 2), dy=1),
        "walk-0": lifted_left,
        "walk-1": shift(stand, (top, hips), dy=-1),
        "walk-2": lifted_right,
        "walk-3": shift(stand, (top, hips), dy=-1),
        "sit-0": sit,
        "sit-1": shift(sit, (s_top, s_neck + 3), dy=1),
        "talk-0": stand,
        "talk-1": shift(stand, (top, neck), dy=-1),
    }


def darker(c, amount):
    return tuple(round(ch + (line - ch) * amount) for ch, line in zip(c, LINE))


def render(grid, size):
    """Draw the grid; its edge pixels become a dark shade of their own colour (a soft outline)."""
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    px = img.load()
    for (x, y), c in grid.items():
        if not (0 <= x < size[0] and 0 <= y < size[1]):
            continue
        edge = any((x + dx, y + dy) not in grid for dx, dy in NEIGHBOURS)
        below_open = (x, y + 1) not in grid
        px[x, y] = (*(darker(c, 0.8 if below_open else 0.68) if edge else c), 255)
    return img


def frame(x, w, h):
    return {"frame": {"x": x, "y": 0, "w": w, "h": h}, "rotated": False, "trimmed": False,
            "spriteSourceSize": {"x": 0, "y": 0, "w": w, "h": h}, "sourceSize": {"w": w, "h": h}}


def main():
    manifest = json.loads((SOURCE / "manifest.json").read_text())
    characters = []
    for c in manifest["characters"]:
        sheet = Image.open(SOURCE / c["image"]).convert("RGBA")
        entries = c["data"]["frames"]
        stand_canvas = pose_canvas(sheet, entries["idle-0"])
        pal = palette(stand_canvas)
        stand, size = pixelate(stand_canvas, pal)
        sit, _ = pixelate(pose_canvas(sheet, entries["sit-0"]), pal)
        poses = frames(stand, sit)
        w, h = size
        strip = Image.new("RGBA", ((w + 2) * len(POSES), h), (0, 0, 0, 0))
        atlas = {}
        for n, name in enumerate(POSES):
            strip.paste(render(poses[name], size), (n * (w + 2), 0))
            atlas[name] = frame(n * (w + 2), w, h)
        strip.save(ROOT / c["image"])
        data = {"frames": atlas, "meta": {"image": c["image"], "format": "RGBA8888",
                "size": {"w": strip.width, "h": h}, "scale": "1"}}
        (ROOT / c["atlas"]).write_text(json.dumps(data, indent=2) + "\n")
        characters.append({**c, "data": data, "displayHeight": h})
    out = {**manifest, "version": 5, "generator": "pixelated from characters-v4 by build.py",
           "characters": characters}
    (ROOT / "manifest.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {len(characters)} characters, {len(POSES)} frames each, {BODY + 2}px tall.")


if __name__ == "__main__":
    main()
