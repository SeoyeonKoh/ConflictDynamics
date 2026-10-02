"""Measure the generated office assets. Reads PNGs without changing their pixels."""
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
NAMES = [
    "desk", "office-chair", "meeting-table", "whiteboard",
    "sofa", "coffee-table", "plant", "filing-cabinet",
    "coffee-station", "water-cooler", "printer", "cafeteria-table",
    "cafeteria-chair", "bookshelf", "door", "partition",
]
# Generated objects are separated, but their centers do not form exact equal cells.
# These measured empty-space boundaries encompass each whole object in the native 1254px sheet.
ROWS = [0, 315, 620, 920, 1254]
COLS = [[0, 370, 575, 970, 1254], [0, 400, 700, 970, 1254],
        [0, 350, 590, 920, 1254], [0, 320, 650, 890, 1254]]


def frame(x, y, w, h):
    return {"frame": {"x": x, "y": y, "w": w, "h": h},
            "rotated": False, "trimmed": False,
            "spriteSourceSize": {"x": 0, "y": 0, "w": w, "h": h},
            "sourceSize": {"w": w, "h": h}}


def atlas(name, image, frames):
    data = {"frames": frames, "meta": {"image": name + ".png", "format": image.mode,
            "size": {"w": image.width, "h": image.height}, "scale": "1"}}
    (ROOT / (name + ".atlas.json")).write_text(json.dumps(data, indent=2) + "\n")
    return data


def main():
    with Image.open(ROOT / "furniture.png") as image:
        assert image.size == (2508, 2508)
        assert image.getchannel("A").getextrema()[0] == 0
        solid = image.getchannel("A").point(lambda value: 255 if value >= 128 else 0)
        frames = {}
        for i, name in enumerate(NAMES):
            row, col = divmod(i, 4)
            x, right = [v * 2 for v in COLS[row][col:col + 2]]
            y, bottom = [v * 2 for v in ROWS[row:row + 2]]
            bounds = solid.crop((x, y, right, bottom)).getbbox()
            assert bounds is not None, f"Empty object: {name}"
            left, top, r, b = bounds
            assert left > 0 and top > 0 and r < right - x and b < bottom - y, name
            left, top = max(x, x + left - 6), max(y, y + top - 6)
            r, b = min(right, x + r + 6), min(bottom, y + b + 6)
            frames[name] = frame(left, top, r - left, b - top)
        furniture = atlas("furniture", image, frames)
    with Image.open(ROOT / "floors.png") as image:
        w, h = image.width // 2, image.height // 2
        floors = atlas("floors", image, {name: frame(i % 2 * w, i // 2 * h, w, h)
                       for i, name in enumerate(["oak", "carpet", "ceramic", "stone"])})
    with Image.open(ROOT / "desk-rear.png") as image:
        assert image.getchannel("A").getextrema()[0] == 0
        desk = atlas("desk-rear", image, {"desk-rear": frame(0, 0, image.width, image.height)})
    manifest = {"version": 2, "export": "2x nearest-neighbor from newly generated originals",
                "furniture": furniture, "floors": floors, "desk-rear": desk}
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (ROOT / "gallery-data.js").write_text("window.OFFICE_ASSETS = " + json.dumps(manifest) + ";\n")
    print("Validated 16 furniture objects, 4 floor textures and rear desk.")


if __name__ == "__main__":
    main()
