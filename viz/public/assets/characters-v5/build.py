"""Turn the characters-v4 sheets into small pixel sprites that match the office-v3 furniture.

Only two poses are shrunk from the originals: standing (idle-0) and seated (sit-0). Every other
frame is made from those two by moving whole pixel rows, so a face never re-samples between frames
and the animation does not shimmer:

- idle: a blink.
- walk: one foot lifts two pixels off the floor, the body rises one pixel as it passes, then the
  other foot.
- talk: the head nods up one pixel and the mouth opens.
- sit: the head and shoulders sink one pixel.

Shrinking: one art pixel is one world pixel; the figure is 44 pixels tall (46 with the outline).
Each cell takes the most common colour of its block after the pose is reduced to a fourteen-colour
palette, and the darkest colour wins a cell when it covers a fifth of it, so eyes survive. The
silhouette is cleaned of one-pixel spurs and notches, then outlined with a darkened shade of the
colour beside it rather than one flat black. Shrinking leaves the two eyes ragged and unequal and
turns glasses into stray lines, so both are redrawn as a matching pair: eyes where they are found
in the grid, glasses on the eyes of the full-size drawing.
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
EYE = (2, 4)  # every eye is redrawn at this size
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


def blobs(cells):
    """Connected groups of cells."""
    left, groups = set(cells), []
    while left:
        stack, group = [left.pop()], set()
        while stack:
            p = stack.pop()
            group.add(p)
            for dx, dy in NEIGHBOURS:
                n = (p[0] + dx, p[1] + dy)
                if n in left:
                    left.remove(n)
                    stack.append(n)
        groups.append(group)
    return groups


def box(group):
    xs, ys = [x for x, _ in group], [y for _, y in group]
    return min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1


def inner_dark(grid):
    """The darkest colour, and its cells in the head that are not on the silhouette's edge."""
    dark = min(set(grid.values()), key=sum)
    top = min(y for _, y in grid)
    cells = {p for p, c in grid.items() if c == dark and p[1] < top + 34
             and all((p[0] + dx, p[1] + dy) in grid for dx, dy in NEIGHBOURS)}
    return dark, cells


def centre_x(grid):
    xs = [x for x, _ in grid]
    return (min(xs) + max(xs)) / 2


def eye_blobs(grid):
    _, cells = inner_dark(grid)
    found = [(box(g), g) for g in blobs(cells)]
    return [(b, g) for b, g in found if 2 <= b[2] <= 4 and 2 <= b[3] <= 6]


def find_eyes(grid):
    """The two eyes: a pair of small dark blobs side by side in the middle of the face."""
    centre, found, best = centre_x(grid), eye_blobs(grid), None
    top = min(y for _, y in grid)
    for a, ga in found:
        for b, gb in found:
            apart = (b[0] + b[2] / 2) - (a[0] + a[2] / 2)
            middle = (a[0] + a[2] / 2 + b[0] + b[2] / 2) / 2
            if not (6 <= apart <= 11 and abs(a[1] - b[1]) <= 1 and abs(middle - centre) <= 5):
                continue
            if max(a[1], b[1]) > top + 22:  # that low is a collar, not a face
                continue
            score = len(ga) + len(gb) - abs(middle - centre)
            if best is None or score > best[0]:
                best = (score, a, b)
    return best and best[1:]


def skin_of(grid):
    """The face's colour: the commonest one in the middle of the head, under the fringe."""
    dark, _ = inner_dark(grid)
    centre, top = round(centre_x(grid)), min(y for _, y in grid)
    seen = Counter(grid.get((x, y)) for x in range(centre - 5, centre + 6)
                   for y in range(top + 16, top + 27))
    return next(c for c, _ in seen.most_common() if c and c != dark)


def eyes_of(grid, like=None):
    """Where a matching pair of eyes belongs: {left, right, top, size, dark, skin}. `like` is the
    same character's other pose: when only one eye survived shrinking here, it gives the spacing."""
    dark, _ = inner_dark(grid)
    spec = {"size": EYE, "dark": dark, "skin": skin_of(grid), "lens": None}
    pair = find_eyes(grid)
    if pair:
        a, b = pair
        tall = max(a, b, key=lambda k: k[3])
        return {**spec, "left": round(a[0] + a[2] / 2 - 1), "right": round(b[0] + b[2] / 2 - 1),
                "top": tall[1] + (tall[3] - EYE[1] + 1) // 2}
    found = [b for b, _ in eye_blobs(grid) if b[3] >= 4]
    if not (like and found):
        return None
    centre = centre_x(grid)
    one = min(found, key=lambda k: abs(abs(k[0] + k[2] / 2 - centre) - 4.5))
    x, apart = round(one[0] + one[2] / 2 - 1), like["right"] - like["left"]
    left = x if one[0] + one[2] / 2 < centre else x - apart
    return {**spec, "left": left, "right": left + apart, "top": one[1] + (one[3] - EYE[1] + 1) // 2}


def source_eyes(canvas):
    """The two eye centres, in grid cells, read from the full-size drawing. There the eyes are
    solid dark blocks and glasses frames and outlines are thin lines: wear every dark shape back
    by more than a line's width and of the face only the eyes are left."""
    sw, sh = canvas.size
    step, reach = 4, 2
    small = canvas.resize((sw // step, sh // step), Image.Resampling.BOX)
    rgb, alpha = small.convert("RGB").load(), small.getchannel("A").load()
    dark = {(x, y) for y in range(small.height) for x in range(small.width)
            if alpha[x, y] >= 128 and max(rgb[x, y]) < 60}
    core = {p for p in dark if all((p[0] + dx, p[1] + dy) in dark
            for dx in range(-reach, reach + 1) for dy in range(-reach, reach + 1))}
    k, found = BODY / sh * step, []
    for group in blobs(core):
        x, y, w, h = box(group)
        if 40 <= len(group) <= 130 and h >= w:
            found.append(((x + w / 2) * k + 1, (y + h / 2) * k + 1))
    centre, best = (round(sw * BODY / sh) + 1) / 2, None
    for a in found:
        for b in found:
            middle = (a[0] + b[0]) / 2
            if 6 <= b[0] - a[0] <= 12 and abs(a[1] - b[1]) <= 1 and abs(middle - centre) <= 5:
                if best is None or abs(middle - centre) < best[0]:
                    best = (abs(middle - centre), a, b)
    return best and best[1:]


def glasses_of(grid, round_frames, eyes=None):
    """Shrinking turns glasses into stray lines. Describe a clean pair instead: small eyes behind
    two frames, placed on the eyes of the full-size drawing (`eyes`) when those were found, or
    else on the eyes or the band of lines left in the grid."""
    dark, cells = inner_dark(grid)
    skin = skin_of(grid)
    centre, top = centre_x(grid), min(y for _, y in grid)
    marks = [(x, y) for x, y in cells if abs(x - centre) <= 10 and top + 13 <= y <= top + 27]
    if not marks:
        return None
    ys = sorted(y for _, y in marks)
    cy, cx = ys[len(ys) // 2], round(centre)
    left, right, old = cx - 5, cx + 3, set()
    pair = find_eyes(grid)
    if eyes:
        (lx, ly), (rx, ry) = eyes
        left, right, cy = round(lx - 1), round(rx - 1), round((ly + ry) / 2 - 1)
        old = {(x, y) for x, y in cells
               if min(abs(x - lx), abs(x - rx)) <= 2.5 and abs(y - (ly + ry) / 2) <= 4}
    elif pair:  # the eyes came through the shrinking: use them, not the stray lines
        a, b = pair
        left, right = round(a[0] + a[2] / 2 - 1), round(b[0] + b[2] / 2 - 1)
        tall = max(a, b, key=lambda k: k[3])
        cy = tall[1] + (tall[3] - 2) // 2
        old = {(x, y) for x, y in cells for k in pair
               if k[0] <= x < k[0] + k[2] and k[1] <= y < k[1] + k[3]}
    return {"size": (2, 2), "dark": dark, "skin": skin, "left": left, "right": right, "top": cy,
            "old": old,
            "lens": tuple(round(s + (g - s) * 0.3) for s, g in zip(skin, (236, 244, 252))),
            "frame": tuple(round(d + (s - d) * 0.22) for d, s in zip(dark, skin)),
            "round": round_frames}


def wipe_face(grid, spec):
    """Clear the old eye and glasses pixels around the new eyes back to skin."""
    _, cells = inner_dark(grid)
    w, h = spec["size"]
    reach = (4, 3) if spec["lens"] else (1, 1)
    for x, y in sorted(spec.get("old", ())):  # the eyes as they were shrunk: back to whatever
        around = Counter(grid[x + dx, y + dy] for dx in (-1, 0, 1) for dy in (-1, 0, 1)  # is there
                         if grid.get((x + dx, y + dy), spec["dark"]) != spec["dark"])
        grid[x, y] = around.most_common(1)[0][0] if around else spec["skin"]
    for x, y in cells:
        near = any(x0 - reach[0] <= x < x0 + w + reach[0] for x0 in (spec["left"], spec["right"]))
        between = spec["lens"] and spec["left"] <= x <= spec["right"]
        if (near or between) and spec["top"] - reach[1] <= y < spec["top"] + h + reach[1]:
            grid[x, y] = spec["skin"]
    if not spec["lens"]:
        return
    top, skin = spec["top"], spec["skin"]
    for y in range(top - 2, top + h + 1):  # what is left of the old bridge
        for x in range(spec["left"] + w + 2, spec["right"] - 2):
            grid[x, y] = skin
    for y in range(top - 5, top - 2):  # brows and frame tops left floating above the new frames;
        for x in range(spec["left"] - 3, spec["right"] + w + 3):  # a fringe hangs from hair: kept
            if grid.get((x, y)) != skin and grid.get((x, y - 1)) == skin:
                grid[x, y] = skin
    for y in range(top + h + 3, top + h, -1):  # and the old rims left hanging under them
        for x in range(spec["left"] - 2, spec["right"] + w + 2):
            if grid.get((x, y)) != skin and grid.get((x, y + 1)) == skin:
                grid[x, y] = skin


def draw_face(grid, spec, closed=False, mouth=False):
    """Draw the eyes (and glasses) of a spec onto a copy of the grid."""
    grid = dict(grid)
    w, h = spec["size"]
    top = spec["top"]
    for x0 in (spec["left"], spec["right"]):
        if spec["lens"]:
            for i in range(-2, w + 2):
                for j in range(-2, h + 1):
                    edge = i in (-2, w + 1) or j in (-2, h)
                    corner = i in (-2, w + 1) and j in (-2, h)
                    if corner and spec["round"]:
                        continue
                    grid[x0 + i, top + j] = spec["frame"] if edge else spec["lens"]
        for i in range(w):
            for j in range(h):
                shut = closed and j != h - (1 if spec["lens"] else 2)
                grid[x0 + i, top + j] = (spec["lens"] or spec["skin"]) if shut else spec["dark"]
    if spec["lens"]:
        for x in range(spec["left"] + w + 2, spec["right"] - 2):  # bridge
            grid[x, top - 1] = spec["frame"]
        for x0, step in ((spec["left"] - 3, -1), (spec["right"] + w + 2, 1)):  # temples
            for n in range(3):
                if grid.get((x0 + n * step, top - 1)) != spec["skin"]:
                    break
                grid[x0 + n * step, top - 1] = spec["frame"]
    if mouth:
        x = (spec["left"] + spec["right"] + w) // 2
        colour = tuple(round(s + (m - s) * 0.75) for s, m in zip(spec["skin"], (150, 62, 60)))
        for i in (-1, 0):
            if grid.get((x + i, top + h + 2)) == spec["skin"]:
                grid[x + i, top + h + 2] = colour
    return grid


def face(grid, glasses, like=None, eyes=None):
    """Redraw a pose's eyes; returns (grid, spec), the spec None when no eyes were found."""
    spec = glasses_of(grid, glasses == "round", eyes) if glasses else eyes_of(grid, like)
    if not spec:
        return grid, None
    wipe_face(grid, spec)
    grid = draw_face(grid, spec)
    _, cells = inner_dark(grid)
    for speck in blobs(cells):  # stray dark dots left alone on the skin
        around = {(x + dx, y + dy) for x, y in speck for dx, dy in NEIGHBOURS} - speck
        if len(speck) <= 3 and all(grid.get(n) == spec["skin"] for n in around):
            for cell in speck:
                grid[cell] = spec["skin"]
    return grid, spec


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


def lift(grid, rows, cols, by=2):
    """Raise one foot off the floor: the leg slides up behind the body, which hides its top."""
    leg = {p: c for p, c in grid.items() if rows[0] <= p[1] < rows[1] and cols[0] <= p[0] < cols[1]}
    out = {p: c for p, c in grid.items() if p not in leg}
    out.update({(x, y - by): c for (x, y), c in leg.items() if y - by >= rows[0]})
    return out


def frames(stand, sit, stand_eyes):
    top, neck, hips, bottom, middle = regions(stand)
    lifted_left = lift(stand, (hips, bottom), (0, middle))
    lifted_right = lift(stand, (hips, bottom), (middle, 999))
    s_top, s_neck, *_ = regions(sit)
    blink = draw_face(stand, stand_eyes, closed=True) if stand_eyes else stand
    speak = draw_face(stand, stand_eyes, mouth=True) if stand_eyes else stand
    return {
        "idle-0": stand,
        "idle-1": blink,
        "walk-0": lifted_left,
        "walk-1": shift(stand, (top, hips), dy=-1),
        "walk-2": lifted_right,
        "walk-3": shift(stand, (top, hips), dy=-1),
        "sit-0": sit,
        "sit-1": shift(sit, (s_top, s_neck + 3), dy=1),
        "talk-0": stand,
        "talk-1": shift(speak, (top, neck), dy=-1),
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
        sit_canvas = pose_canvas(sheet, entries["sit-0"])
        sit, _ = pixelate(sit_canvas, pal)
        words = c["description"]
        glasses = "glasses" in words and ("round" if "round glasses" in words else "square")
        stand, stand_eyes = face(stand, glasses, eyes=source_eyes(stand_canvas))
        sit, sit_eyes = face(sit, glasses, stand_eyes, source_eyes(sit_canvas))
        if not (stand_eyes and sit_eyes):
            print(f"{c['id']}: eyes left as shrunk (no clear pair found)")
        poses = frames(stand, sit, stand_eyes)
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
