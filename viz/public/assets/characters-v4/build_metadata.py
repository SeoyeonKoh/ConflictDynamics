"""Inspect generated PNGs and write atlas/animation metadata. Never modifies raster images.

Run from the repo: uv run python viz/public/assets/characters-v4/build_metadata.py
"""

import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
POSES = ["idle-0", "idle-1", "walk-0", "walk-1", "walk-2", "walk-3",
         "sit-0", "sit-1", "talk-0", "talk-1"]
ANIMATIONS = {
    "idle": {"frames": ["idle-0", "idle-1"], "durations": [1800, 160]},
    "walk": {"frames": ["walk-0", "walk-1", "walk-2", "walk-3"],
             "durations": [130, 130, 130, 130]},
    "sit": {"frames": ["sit-0", "sit-1"], "durations": [1400, 400]},
    "talk": {"frames": ["talk-0", "talk-1"], "durations": [220, 260]},
}


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def character_bounds(mask):
    """Exclude neighboring-cell fragments from these two tightly packed sheets."""
    width, height = mask.size
    pixels = mask.tobytes()
    seen = bytearray(len(pixels))
    largest, bounds = 0, None
    for start, value in enumerate(pixels):
        if not value or seen[start]:
            continue
        seen[start] = 1
        stack = [start]
        area = 0
        left, top, right, bottom = width, height, 0, 0
        while stack:
            index = stack.pop()
            y, x = divmod(index, width)
            area += 1
            left, top = min(left, x), min(top, y)
            right, bottom = max(right, x + 1), max(bottom, y + 1)
            for neighbor in (index - 1 if x else -1,
                             index + 1 if x + 1 < width else -1,
                             index - width if y else -1,
                             index + width if y + 1 < height else -1):
                if neighbor >= 0 and pixels[neighbor] and not seen[neighbor]:
                    seen[neighbor] = 1
                    stack.append(neighbor)
        if area > largest:
            largest, bounds = area, (left, top, right, bottom)
    return bounds


def main():
    designs = json.loads((ROOT / "prompts.json").read_text())["prompts"]
    agents = []
    for i, design in enumerate(designs):
        key = f"agent-{i}"
        with Image.open(ROOT / f"{key}.png") as im:
            assert "A" in im.getbands(), f"{key}: missing transparency"
            alpha = im.getchannel("A")
            assert alpha.getextrema()[0] == 0, f"{key}: opaque background"
            solid = alpha.point(lambda value: 255 if value >= 128 else 0)
            bounds = []
            for n in range(10):
                x, y = round(n % 5 * im.width / 5), round(n // 5 * im.height / 2)
                right = round((n % 5 + 1) * im.width / 5)
                bottom = round((n // 5 + 1) * im.height / 2)
                cell = solid.crop((x, y, right, bottom))
                b = character_bounds(cell) if key in {"agent-5", "agent-15"} else cell.getbbox()
                assert b is not None, f"{key}: empty frame {n}"
                left, top = max(x, x + b[0] - 3), max(y, y + b[1] - 3)
                r, bot = min(right, x + b[2] + 3), min(bottom, y + b[3] + 3)
                bounds.append((left, top, r - left, bot - top))
            # A single logical canvas/scale per character keeps sitting shorter than standing.
            width = max(b[2] for b in bounds)
            height = max(b[3] for b in bounds)
            frames = {}
            for pose, (x, y, w, h) in zip(POSES, bounds):
                assert 0 <= x < x + w <= im.width and 0 <= y < y + h <= im.height
                frames[pose] = {
                    "frame": {"x": x, "y": y, "w": w, "h": h},
                    "rotated": False, "trimmed": True,
                    "spriteSourceSize": {"x": (width - w) // 2, "y": height - h,
                                         "w": w, "h": h},
                    "sourceSize": {"w": width, "h": height},
                }
            atlas = {"frames": frames, "meta": {"image": f"{key}.png",
                     "format": "RGBA8888", "size": {"w": im.width, "h": im.height},
                     "scale": "1"}}
        write_json(ROOT / f"{key}.atlas.json", atlas)
        agents.append({"id": key, "label": design["identity"].split(":")[0]
                       if i < 6 else f"Agent {i + 1:02}",
                       "description": design["identity"], "image": f"{key}.png",
                       "atlas": f"{key}.atlas.json", "data": atlas,
                       "displayHeight": 40, "origin": [0.5, 1]})
    manifest = {"version": 4, "generator": "built-in image_gen", "direction": "down",
                "worldTileSize": 32, "animations": ANIMATIONS, "characters": agents,
                "agentAssignments": dict(zip(["Erin", "Alex", "Blake", "Casey", "Drew",
                                               "Frankie"], [f"agent-{i}" for i in range(6)]))}
    write_json(ROOT / "manifest.json", manifest)
    # A script rather than fetch makes the gallery work when opened directly via file://.
    (ROOT / "gallery-data.js").write_text("window.CHARACTER_ASSETS = " + json.dumps(manifest)
                                          + ";\n")
    print(f"Validated {len(agents)} characters, {len(agents) * 10} frames, "
          f"{len(agents) * len(ANIMATIONS)} animation clips; originals unchanged.")


if __name__ == "__main__":
    main()
