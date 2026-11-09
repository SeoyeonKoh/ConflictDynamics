"""Draw the office floors and furniture as clean pixel art and write their atlases.

One art pixel is one world pixel: a 64x52 desk on the map is a 64x52 sprite here. Floors are
96x96 seamless tiles. Every sprite shares one muted palette so rooms,
corridors and furniture read as one place. Run: python3 viz/public/assets/office-v3/build.py
"""
import json
import random
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent

# ---- palette -------------------------------------------------------------------------------
LINE = (58, 52, 48)
OAK = [(214, 180, 134), (204, 168, 122), (194, 157, 112), (182, 145, 102)]
OAK_SEAM = (176, 140, 98)
WOOD = {"top": (207, 166, 113), "hi": (224, 189, 140), "face": (168, 124, 80), "dark": (130, 94, 60)}
CARPET = [(116, 128, 146), (110, 122, 140)]
CARPET_SEAM = (100, 111, 128)
CERAMIC = (226, 222, 212)
CERAMIC_ALT = (219, 214, 203)
GROUT = (196, 190, 178)
STONE = (232, 226, 214)
STONE_ALT = (226, 219, 206)
STONE_SEAM = (208, 200, 186)
METAL = {"hi": (204, 208, 212), "mid": (162, 168, 175), "dark": (114, 120, 128)}
SCREEN_BACK = (74, 78, 88)
TEAL = {"hi": (112, 170, 168), "mid": (79, 138, 139), "dark": (58, 108, 110)}
LEAF = [(126, 178, 110), (92, 150, 86), (66, 118, 70)]
POT = {"hi": (206, 140, 102), "mid": (184, 116, 80), "dark": (150, 90, 60)}
WHITE = (244, 243, 238)
PAPER = (250, 249, 244)
BOOKS = [(186, 92, 78), (82, 128, 170), (214, 170, 86), (104, 150, 110), (150, 110, 160)]
WATER = (150, 200, 230)


class Sprite:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        self.px = self.img.load()

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[x, y] = (*c, 255)

    def rect(self, x, y, w, h, c):
        for j in range(y, y + h):
            for i in range(x, x + w):
                self.put(i, j, c)

    def hline(self, x, y, w, c):
        self.rect(x, y, w, 1, c)

    def vline(self, x, y, h, c):
        self.rect(x, y, 1, h, c)

    def ellipse(self, x, y, w, h, c):
        cx, cy, rx, ry = x + (w - 1) / 2, y + (h - 1) / 2, w / 2, h / 2
        for j in range(y, y + h):
            for i in range(x, x + w):
                if ((i - cx) / rx) ** 2 + ((j - cy) / ry) ** 2 <= 1.0:
                    self.put(i, j, c)

    def shade(self, x, y, w, h, top, bottom):
        """A vertical blend from top to bottom colour, banded to whole pixel steps."""
        for j in range(h):
            t = j / max(1, h - 1)
            c = tuple(round(a + (b - a) * t) for a, b in zip(top, bottom))
            self.hline(x, y + j, w, c)

    def outline(self):
        """A one-pixel dark line around every shape (drawn shapes stay one pixel in from the edge)."""
        solid = {(x, y) for y in range(self.h) for x in range(self.w) if self.px[x, y][3]}
        for x, y in solid:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (x + dx, y + dy)
                if n not in solid and 0 <= n[0] < self.w and 0 <= n[1] < self.h:
                    self.px[n] = (*LINE, 255)
        return self


# ---- floors (96x96, seamless) ---------------------------------------------------------------
T = 96


def floor(fill):
    img = Image.new("RGB", (T, T))
    px = img.load()
    for y in range(T):
        for x in range(T):
            px[x, y] = fill(x, y)
    return img


def tint(c, d):
    return tuple(max(0, min(255, ch + d)) for ch in c)


def oak_floor():
    rnd = random.Random(3)
    rows, plank = 8, 48  # 12px tall planks, two per row, joints staggered (period 96)
    tones = {(r, k): rnd.choice(OAK) for r in range(rows) for k in range(2)}
    grain = set()
    for _ in range(70):  # short faint grain streaks along each plank
        x, y, n = rnd.randrange(T), rnd.randrange(T), rnd.randrange(4, 14)
        if y % 12 in (0, 11):
            continue
        grain.update(((x + i) % T, y) for i in range(n))

    def fill(x, y):
        r, v = divmod(y, 12)
        offset = (r * 37) % T
        k = ((x - offset) % T) // plank
        c = tones[r, k]
        if v == 11 or (x - offset) % plank == 0:
            return OAK_SEAM
        if v == 0:
            return tint(c, 8)  # lit top edge of each plank
        if (x, y) in grain:
            return tint(c, -9)
        return c
    return floor(fill)


def carpet_floor():
    def fill(x, y):
        if x % 48 == 0 or y % 48 == 0:
            return CARPET_SEAM
        square = (x // 48 + y // 48) % 2  # carpet squares laid in alternating pile direction
        if square == 0 and y % 4 == 0 and (x + y // 4) % 3 == 0:
            return CARPET[1]
        if square == 1 and x % 4 == 0 and (y + x // 4) % 3 == 0:
            return CARPET[1]
        return CARPET[0]
    return floor(fill)


def ceramic_floor():
    def fill(x, y):
        if x % 32 == 0 or y % 32 == 0:
            return GROUT
        c = CERAMIC if (x // 32 + y // 32) % 2 == 0 else CERAMIC_ALT
        if x % 32 == 1 or y % 32 == 1:
            return tint(c, 6)  # glazed edge catches the light
        return c
    return floor(fill)


def stone_floor():
    # Large pale slabs, running bond: the corridor and the lobby share this calm floor.
    rnd = random.Random(7)
    speck = {(rnd.randrange(T), rnd.randrange(T)) for _ in range(90)}

    def fill(x, y):
        row = y // 48
        shift = 24 if row % 2 else 0
        if y % 48 == 0 or (x + shift) % 48 == 0:
            return STONE_SEAM
        c = STONE if ((x + shift) // 48 + row) % 2 == 0 else STONE_ALT
        return tint(c, -7) if (x, y) in speck else c
    return floor(fill)


# ---- furniture ------------------------------------------------------------------------------
def wood_top(s, x, y, w, h):
    s.rect(x, y, w, h, WOOD["top"])
    s.hline(x, y, w, WOOD["hi"])
    s.hline(x, y + 1, w, tint(WOOD["hi"], -6))
    for gy in range(y + 4, y + h - 1, 5):  # faint grain lines
        s.hline(x + 3 + (gy * 7) % 9, gy, w // 3, tint(WOOD["top"], -8))
        s.hline(x + w // 2 + (gy * 5) % 7, gy, w // 4, tint(WOOD["top"], -8))


def monitor_back(s, x, y, w, h):
    s.rect(x, y, w, h, SCREEN_BACK)
    s.hline(x, y, w, (96, 100, 112))
    s.rect(x + 2, y + 2, w - 4, h - 4, (82, 86, 98))
    s.rect(x + w // 2 - 2, y + h, 4, 2, METAL["dark"])
    s.rect(x + w // 2 - 5, y + h + 2, 10, 1, METAL["dark"])


def desk_rear():
    """A desk seen from the visitor side: monitor back on top, a solid modesty panel in front."""
    s = Sprite(64, 52)
    wood_top(s, 1, 18, 62, 12)
    s.shade(1, 30, 62, 18, WOOD["face"], tint(WOOD["face"], -14))
    s.hline(1, 30, 62, WOOD["dark"])
    s.rect(5, 33, 54, 11, (178, 134, 90))  # recessed modesty panel
    s.hline(5, 33, 54, tint((178, 134, 90), -16))
    s.vline(5, 33, 11, tint((178, 134, 90), -16))
    s.rect(1, 48, 4, 3, WOOD["dark"])
    s.rect(59, 48, 4, 3, WOOD["dark"])
    monitor_back(s, 18, 1, 28, 16)
    s.rect(48, 13, 10, 7, PAPER)  # papers
    s.hline(49, 15, 7, (200, 200, 196))
    s.hline(49, 17, 5, (200, 200, 196))
    s.rect(6, 13, 6, 6, POT["mid"])  # mug
    s.vline(11, 13, 6, POT["dark"])
    s.hline(6, 13, 6, POT["hi"])
    return s.outline()


def desk():
    s = Sprite(64, 52)
    wood_top(s, 1, 12, 62, 20)
    s.shade(1, 32, 62, 8, WOOD["face"], tint(WOOD["face"], -12))
    s.rect(2, 40, 6, 10, WOOD["dark"])
    s.rect(56, 40, 6, 10, WOOD["dark"])
    s.rect(20, 1, 24, 14, (60, 64, 74))
    s.rect(22, 3, 20, 10, (120, 170, 210))
    s.hline(22, 3, 20, (160, 200, 230))
    s.rect(18, 22, 18, 5, (72, 76, 86))  # keyboard
    return s.outline()


def office_chair():
    s = Sprite(28, 36)
    s.shade(4, 1, 20, 16, (100, 104, 118), SCREEN_BACK)
    s.rect(2, 17, 24, 8, (92, 96, 108))
    s.hline(2, 17, 24, (112, 116, 128))
    s.rect(12, 25, 4, 6, METAL["dark"])
    s.rect(5, 31, 18, 2, METAL["dark"])
    s.rect(4, 33, 3, 2, (40, 40, 44))
    s.rect(21, 33, 3, 2, (40, 40, 44))
    return s.outline()


def meeting_table():
    s = Sprite(128, 64)
    wood_top(s, 1, 1, 126, 40)
    s.rect(5, 5, 118, 32, (214, 176, 126))
    s.hline(5, 5, 118, tint((214, 176, 126), 8))
    s.shade(1, 41, 126, 8, WOOD["face"], tint(WOOD["face"], -14))
    s.hline(1, 48, 126, WOOD["dark"])
    for x in (6, 116):
        s.rect(x, 49, 6, 14, WOOD["dark"])
        s.vline(x, 49, 14, tint(WOOD["dark"], 12))
    for x, y in ((22, 14), (86, 18)):  # papers, a laptop
        s.rect(x, y, 12, 9, PAPER)
        s.hline(x + 2, y + 3, 8, (200, 200, 196))
        s.hline(x + 2, y + 5, 6, (200, 200, 196))
    s.rect(52, 12, 20, 13, METAL["mid"])
    s.rect(54, 14, 16, 9, (120, 170, 210))
    s.rect(50, 25, 24, 3, METAL["hi"])
    return s.outline()


def whiteboard():
    s = Sprite(72, 59)
    s.rect(1, 1, 70, 40, METAL["mid"])
    s.rect(3, 3, 66, 36, WHITE)
    s.hline(3, 3, 66, (255, 255, 252))
    s.hline(9, 11, 26, (82, 128, 170))
    s.hline(9, 12, 26, (82, 128, 170))
    s.hline(9, 17, 36, (180, 190, 200))
    s.hline(9, 21, 30, (180, 190, 200))
    s.hline(9, 26, 18, (186, 92, 78))
    s.hline(9, 27, 18, (186, 92, 78))
    s.rect(46, 22, 14, 12, (238, 214, 120))  # sticky notes
    s.hline(48, 25, 9, (200, 176, 90))
    s.rect(50, 7, 12, 10, (170, 210, 170))
    s.hline(52, 10, 7, (130, 176, 130))
    s.rect(2, 40, 68, 2, METAL["dark"])
    s.rect(20, 41, 10, 2, METAL["hi"])  # marker tray
    s.vline(10, 42, 15, METAL["dark"])
    s.vline(61, 42, 15, METAL["dark"])
    s.rect(5, 56, 11, 2, METAL["dark"])
    s.rect(56, 56, 11, 2, METAL["dark"])
    return s.outline()


def sofa():
    s = Sprite(80, 51)
    s.shade(1, 1, 78, 18, TEAL["mid"], tint(TEAL["mid"], -10))  # backrest
    s.hline(1, 1, 78, TEAL["hi"])
    s.rect(1, 19, 78, 18, TEAL["hi"])  # seat cushions
    s.hline(1, 19, 78, tint(TEAL["hi"], 14))
    s.vline(40, 19, 18, TEAL["mid"])
    s.vline(39, 19, 18, tint(TEAL["hi"], -8))
    s.vline(20, 3, 15, tint(TEAL["mid"], -8))  # back tufts
    s.vline(59, 3, 15, tint(TEAL["mid"], -8))
    s.shade(1, 11, 10, 30, TEAL["mid"], TEAL["dark"])  # arms
    s.shade(69, 11, 10, 30, TEAL["mid"], TEAL["dark"])
    s.hline(1, 11, 10, TEAL["hi"])
    s.hline(69, 11, 10, TEAL["hi"])
    s.rect(1, 37, 78, 8, TEAL["dark"])
    s.rect(5, 45, 4, 5, WOOD["dark"])
    s.rect(71, 45, 4, 5, WOOD["dark"])
    return s.outline()


def coffee_table():
    s = Sprite(64, 40)
    wood_top(s, 1, 1, 62, 20)
    s.shade(1, 21, 62, 6, WOOD["face"], tint(WOOD["face"], -12))
    s.rect(3, 27, 4, 12, WOOD["dark"])
    s.rect(57, 27, 4, 12, WOOD["dark"])
    s.rect(14, 6, 14, 10, PAPER)
    s.hline(16, 9, 10, (200, 200, 196))
    s.hline(16, 11, 8, (200, 200, 196))
    s.ellipse(38, 7, 8, 8, POT["mid"])
    s.ellipse(40, 8, 4, 4, (110, 70, 44))
    return s.outline()


def plant():
    s = Sprite(28, 38)
    s.ellipse(2, 2, 24, 20, LEAF[1])
    s.ellipse(6, 1, 14, 11, LEAF[0])
    s.ellipse(3, 11, 22, 10, LEAF[2])
    s.ellipse(9, 4, 6, 4, tint(LEAF[0], 14))
    for x, y in ((8, 9), (17, 6), (20, 13), (11, 15), (5, 13), (15, 11)):  # leaf veins
        s.put(x, y, LEAF[2])
        s.put(x + 1, y + 1, LEAF[2])
    s.rect(5, 21, 18, 4, POT["hi"])
    s.hline(5, 21, 18, tint(POT["hi"], 14))
    s.shade(7, 25, 14, 11, POT["mid"], POT["dark"])
    s.vline(19, 25, 11, POT["dark"])
    return s.outline()


def filing_cabinet():
    s = Sprite(24, 50)
    s.rect(1, 1, 22, 47, METAL["mid"])
    s.hline(1, 1, 22, METAL["hi"])
    s.hline(1, 2, 22, tint(METAL["hi"], -8))
    for y in (5, 19, 33):
        s.rect(3, y, 18, 12, METAL["hi"])
        s.hline(3, y, 18, tint(METAL["hi"], 12))
        s.hline(3, y + 12, 18, METAL["dark"])
        s.rect(8, y + 4, 8, 2, METAL["dark"])
        s.rect(10, y + 8, 4, 2, PAPER)  # label
    s.vline(22, 1, 47, METAL["dark"])
    return s.outline()


def printer():
    s = Sprite(40, 44)
    s.rect(8, 1, 24, 7, PAPER)  # paper tray
    s.hline(8, 1, 24, (255, 255, 252))
    s.rect(1, 7, 38, 15, METAL["hi"])
    s.hline(1, 7, 38, tint(METAL["hi"], 14))
    s.rect(26, 10, 9, 5, (72, 76, 86))  # control panel
    s.put(28, 12, (110, 190, 120))
    s.put(31, 12, (230, 180, 80))
    s.shade(1, 22, 38, 18, METAL["mid"], tint(METAL["mid"], -14))
    s.rect(5, 25, 30, 4, (60, 64, 74))  # output slot
    s.rect(8, 29, 24, 5, PAPER)
    s.hline(10, 31, 18, (200, 200, 196))
    s.rect(1, 39, 38, 2, METAL["dark"])
    return s.outline()


def water_cooler():
    s = Sprite(20, 51)
    s.ellipse(3, 1, 14, 6, WATER)
    s.rect(3, 4, 14, 13, WATER)
    s.vline(6, 3, 13, (196, 228, 246))
    s.vline(7, 4, 11, (196, 228, 246))
    s.hline(3, 9, 14, tint(WATER, -14))
    s.rect(1, 17, 18, 31, WHITE)
    s.hline(1, 17, 18, METAL["mid"])
    s.vline(17, 18, 30, (214, 212, 206))
    s.rect(4, 23, 3, 3, (90, 140, 210))  # taps
    s.rect(12, 23, 3, 3, (200, 90, 80))
    s.rect(3, 29, 14, 2, METAL["mid"])  # drip tray
    s.rect(1, 46, 18, 2, METAL["mid"])
    return s.outline()


def coffee_station():
    s = Sprite(48, 53)
    wood_top(s, 1, 18, 46, 8)  # counter
    s.shade(1, 26, 46, 25, WOOD["face"], tint(WOOD["face"], -14))
    s.vline(24, 26, 25, WOOD["dark"])
    s.rect(19, 36, 2, 6, WOOD["dark"])  # handles
    s.rect(28, 36, 2, 6, WOOD["dark"])
    s.shade(5, 1, 18, 19, (84, 86, 96), (58, 60, 68))  # machine
    s.rect(7, 3, 14, 4, (100, 104, 116))
    s.put(18, 5, (110, 190, 120))
    s.rect(10, 11, 8, 3, (40, 40, 44))  # spout
    s.rect(11, 14, 6, 5, PAPER)  # cup
    for x in (28, 34):  # stacked cups
        s.rect(x, 12, 5, 7, PAPER)
        s.hline(x, 12, 5, (255, 255, 252))
    s.rect(40, 11, 5, 8, POT["mid"])  # sugar jar
    s.hline(40, 11, 5, POT["hi"])
    return s.outline()


def cafeteria_table():
    s = Sprite(56, 60)
    s.ellipse(1, 1, 54, 28, WOOD["face"])
    s.ellipse(1, 1, 54, 25, WOOD["top"])
    s.ellipse(6, 3, 44, 18, (214, 176, 126))
    s.ellipse(12, 5, 18, 6, tint((214, 176, 126), 8))
    s.shade(25, 28, 6, 22, METAL["mid"], METAL["dark"])
    s.ellipse(12, 49, 32, 9, METAL["mid"])
    s.ellipse(14, 49, 28, 6, METAL["hi"])
    return s.outline()


def cafeteria_chair():
    s = Sprite(24, 38)
    s.shade(4, 1, 16, 14, TEAL["hi"], TEAL["mid"])
    s.hline(4, 1, 16, tint(TEAL["hi"], 14))
    s.rect(2, 15, 20, 8, TEAL["hi"])
    s.hline(2, 15, 20, tint(TEAL["hi"], 14))
    s.rect(2, 23, 20, 2, TEAL["dark"])
    s.rect(4, 25, 2, 12, METAL["dark"])
    s.rect(18, 25, 2, 12, METAL["dark"])
    s.rect(4, 31, 16, 1, METAL["mid"])
    return s.outline()


def bookshelf():
    s = Sprite(64, 59)
    s.rect(1, 1, 62, 56, WOOD["face"])
    s.hline(1, 1, 62, WOOD["hi"])
    s.hline(1, 2, 62, WOOD["top"])
    rnd = random.Random(5)
    for shelf in range(3):
        top = 5 + shelf * 17
        s.rect(4, top, 56, 13, WOOD["dark"])
        x = 5
        while x < 56:
            w = rnd.choice((3, 4, 4, 5))
            h = rnd.choice((9, 10, 11, 12))
            c = rnd.choice(BOOKS)
            if rnd.random() < 0.12 and x < 50:  # a leaning book
                for i in range(6):
                    s.vline(x + i, top + 13 - 9 + (5 - i) // 2, 9 - (5 - i) // 2, c)
                x += 8
                continue
            s.rect(x, top + 13 - h, w, h, c)
            s.vline(x, top + 13 - h, h, tint(c, 18))
            s.hline(x, top + 15 - h, w, tint(c, -26))
            x += w + (1 if rnd.random() < 0.2 else 0)
        s.rect(1, top + 13, 62, 2, WOOD["top"])
    return s.outline()


def door():
    s = Sprite(32, 51)
    s.rect(1, 1, 30, 49, WOOD["face"])
    s.rect(3, 3, 26, 47, WOOD["top"])
    s.hline(3, 3, 26, WOOD["hi"])
    for y, h in ((7, 15), (27, 18)):  # recessed panels
        s.rect(7, y, 18, h, (190, 148, 100))
        s.hline(7, y, 18, WOOD["face"])
        s.vline(7, y, h, WOOD["face"])
    s.rect(22, 24, 4, 3, METAL["dark"])
    s.hline(22, 24, 4, METAL["hi"])
    return s.outline()


def partition():
    s = Sprite(64, 16)
    s.rect(1, 1, 62, 13, (188, 192, 202))
    s.hline(1, 1, 62, (214, 218, 226))
    s.hline(1, 13, 62, (164, 168, 178))
    return s.outline()


FURNITURE = {
    "desk": desk, "office-chair": office_chair, "meeting-table": meeting_table,
    "whiteboard": whiteboard, "sofa": sofa, "coffee-table": coffee_table, "plant": plant,
    "filing-cabinet": filing_cabinet, "coffee-station": coffee_station,
    "water-cooler": water_cooler, "printer": printer, "cafeteria-table": cafeteria_table,
    "cafeteria-chair": cafeteria_chair, "bookshelf": bookshelf, "door": door,
    "partition": partition,
}


# ---- atlases --------------------------------------------------------------------------------
def frame(x, y, w, h):
    return {"frame": {"x": x, "y": y, "w": w, "h": h}, "rotated": False, "trimmed": False,
            "spriteSourceSize": {"x": 0, "y": 0, "w": w, "h": h}, "sourceSize": {"w": w, "h": h}}


def pack(name, images, mode="RGBA"):
    """Lay frames out in one row with a 2px gap and write <name>.png and <name>.atlas.json."""
    width = sum(i.width + 2 for i in images.values())
    height = max(i.height for i in images.values())
    sheet = Image.new(mode, (width, height), (0, 0, 0, 0) if mode == "RGBA" else (0, 0, 0))
    frames, x = {}, 0
    for key, image in images.items():
        sheet.paste(image, (x, 0))
        frames[key] = frame(x, 0, image.width, image.height)
        x += image.width + 2
    sheet.save(ROOT / f"{name}.png")
    data = {"frames": frames, "meta": {"image": f"{name}.png", "format": mode,
            "size": {"w": width, "h": height}, "scale": "1"}}
    (ROOT / f"{name}.atlas.json").write_text(json.dumps(data, indent=2) + "\n")
    return data


def main():
    floors = pack("floors", {"oak": oak_floor(), "carpet": carpet_floor(),
                             "ceramic": ceramic_floor(), "stone": stone_floor()}, "RGB")
    furniture = pack("furniture", {k: f().img for k, f in FURNITURE.items()})
    rear = pack("desk-rear", {"desk-rear": desk_rear().img})
    manifest = {"version": 3, "export": "procedural pixel art, 1 art px = 1 world px",
                "furniture": furniture, "floors": floors, "desk-rear": rear}
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {len(FURNITURE)} furniture frames, 4 floors and the rear desk.")


if __name__ == "__main__":
    main()
