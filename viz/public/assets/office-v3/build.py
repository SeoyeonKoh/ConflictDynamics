"""Draw the office floors and furniture as clean pixel art and write their atlases.

One art pixel is one world pixel: a 64x52 desk on the map is a 64x52 sprite here. Floors are
128x128 seamless tiles (a power of two, so Phaser's TileSprite repeats them without resampling).
Every sprite shares one muted palette and one light, from the top left, so rooms, corridors and
furniture read as one place. Outlines are a dark shade of the colour they border, not one flat
black. Run: python3 viz/public/assets/office-v3/build.py
"""
import json
import random
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent

# ---- palette -------------------------------------------------------------------------------
INK = (50, 42, 46)  # outlines lean towards this
OAK = [(212, 178, 132), (206, 171, 125), (199, 163, 117), (192, 156, 111)]
OAK_SEAM = (172, 136, 95)
WOOD = {"hi": (236, 203, 156), "top": (216, 178, 128), "mid": (196, 154, 104),
        "face": (170, 126, 84), "dark": (136, 98, 64), "deep": (104, 74, 50)}
CARPET = [(118, 130, 148), (113, 125, 143), (108, 120, 138), (123, 135, 153)]
CARPET_SEAM = (99, 110, 128)
CERAMIC = [(228, 224, 214), (222, 217, 206)]
GROUT = (198, 192, 180)
STONE = [(233, 227, 215), (228, 221, 208)]
STONE_SEAM = (209, 201, 187)
METAL = {"white": (234, 237, 240), "hi": (208, 212, 217), "mid": (168, 174, 182),
         "dark": (122, 128, 138), "deep": (86, 92, 102)}
PLASTIC = {"hi": (104, 108, 122), "mid": (78, 82, 95), "dark": (58, 61, 73), "deep": (42, 44, 53)}
SCREEN = {"hi": (178, 218, 240), "mid": (128, 184, 222), "dark": (86, 142, 190)}
TEAL = {"light": (140, 194, 190), "hi": (110, 170, 168), "mid": (80, 140, 141),
        "dark": (59, 111, 114), "deep": (44, 86, 90)}
LEAF = [(158, 204, 124), (118, 176, 100), (84, 146, 86), (58, 112, 72), (42, 86, 60)]
POT = {"light": (226, 164, 124), "hi": (208, 142, 104), "mid": (184, 116, 80),
       "dark": (150, 90, 60), "deep": (118, 68, 48)}
WHITE = (244, 243, 238)
PAPER = (251, 250, 245)
PAPER_SHADE = (222, 221, 214)
TEXT = (176, 180, 186)
COFFEE = (104, 66, 42)
MUSTARD = {"hi": (238, 200, 116), "mid": (222, 176, 88), "dark": (188, 142, 64)}
RED = (196, 96, 82)
BLUE = (84, 132, 176)
GREEN = (112, 166, 118)
BOOKS = [(190, 96, 82), (84, 132, 176), (218, 174, 90), (108, 154, 114), (152, 114, 164),
         (226, 222, 210), (70, 92, 122)]
WATER = {"hi": (206, 232, 247), "mid": (154, 204, 234), "dark": (120, 176, 214)}


def tint(c, d):
    return tuple(max(0, min(255, ch + d)) for ch in c)


def mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


class Sprite:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        self.px = self.img.load()

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[x, y] = (*c, 255)

    def clear(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[x, y] = (0, 0, 0, 0)

    def rect(self, x, y, w, h, c):
        for j in range(y, y + h):
            for i in range(x, x + w):
                self.put(i, j, c)

    def hline(self, x, y, w, c):
        self.rect(x, y, w, 1, c)

    def vline(self, x, y, h, c):
        self.rect(x, y, 1, h, c)

    def rrect(self, x, y, w, h, c, r=1):
        """A rectangle with its corners cut back by r pixels, so it reads as rounded."""
        for j in range(h):
            inset = max(0, r - min(j, h - 1 - j))
            self.hline(x + inset, y + j, w - 2 * inset, c)

    def ellipse(self, x, y, w, h, c):
        cx, cy, rx, ry = x + (w - 1) / 2, y + (h - 1) / 2, w / 2, h / 2
        for j in range(y, y + h):
            for i in range(x, x + w):
                if ((i - cx) / rx) ** 2 + ((j - cy) / ry) ** 2 <= 1.0:
                    self.put(i, j, c)

    def shade(self, x, y, w, h, top, bottom):
        """A vertical blend from top to bottom colour, banded to whole pixel steps."""
        for j in range(h):
            self.hline(x, y + j, w, mix(top, bottom, j / max(1, h - 1)))

    def bevel(self, x, y, w, h, light, dark):
        """Light on the top and left edges of a box, shadow on the bottom and right."""
        self.hline(x, y, w, light)
        self.vline(x, y, h, light)
        self.hline(x, y + h - 1, w, dark)
        self.vline(x + w - 1, y, h, dark)

    def text(self, x, y, widths, c=TEXT, gap=2):
        """Rows of 'writing': one short line per width."""
        for n, w in enumerate(widths):
            self.hline(x, y + n * gap, w, c)

    def outline(self):
        """A one-pixel line around the shape, a dark shade of the colours it borders: a little
        lighter along the lit top edge, deepest underneath. Both the colour and the depth are
        averaged over the pixels around each point, so the line keeps one even tone round a curve
        instead of flickering between its steps. Drawn shapes stay one pixel in from the edge."""
        solid = {(x, y): self.px[x, y][:3]
                 for y in range(self.h) for x in range(self.w) if self.px[x, y][3]}
        edge = {(x + dx, y + dy) for x, y in solid for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if (x + dx, y + dy) not in solid and 0 <= x + dx < self.w and 0 <= y + dy < self.h}
        for x, y in edge:
            near = [solid[x + dx, y + dy] for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                    if (x + dx, y + dy) in solid]
            colour = tuple(sum(c[k] for c in near) / len(near) for k in range(3))
            above = sum((x + dx, y + dy) in solid for dx in range(-2, 3) for dy in (-2, -1))
            below = sum((x + dx, y + dy) in solid for dx in range(-2, 3) for dy in (1, 2))
            under = (above - below) / max(1, above + below)  # 1 under the shape, -1 on top of it
            self.px[x, y] = (*mix(colour, INK, 0.77 + 0.07 * under), 255)
        return self


# ---- floors (128x128, seamless) -------------------------------------------------------------
T = 128


def floor(fill):
    img = Image.new("RGB", (T, T))
    px = img.load()
    for y in range(T):
        for x in range(T):
            px[x, y] = fill(x, y)
    return img


def oak_floor():
    rnd = random.Random(3)
    rows, plank = 8, 64  # 16px tall planks, two per row, end joints staggered
    tones = {(r, k): rnd.choice(OAK) for r in range(rows) for k in range(2)}
    offsets = [rnd.choice((0, 20, 40, 52)) + r % 2 * 8 for r in range(rows)]
    grain, knots = {}, {}
    for _ in range(64):  # short grain streaks along each plank, some lighter, most darker
        x, y, n = rnd.randrange(T), rnd.randrange(T), rnd.randrange(5, 18)
        if 2 <= y % 16 <= 13:
            d = rnd.choice((-7, -7, -5, 5))
            for i in range(n):
                grain[(x + i) % T, y] = d
    for _ in range(5):  # a few small knots
        x, y = rnd.randrange(T), rnd.randrange(8) * 16 + rnd.randrange(5, 11)
        for dx, dy, d in ((0, 0, -18), (1, 0, -13), (-1, 0, -6), (2, 0, -6), (0, -1, -5), (1, 1, -5)):
            knots[(x + dx) % T, y + dy] = d

    def fill(x, y):
        r, v = divmod(y, 16)
        along = (x - offsets[r]) % T
        c = tones[r, along // plank]
        if v == 15:
            return OAK_SEAM
        if along % plank == 0:
            return mix(c, OAK_SEAM, 0.8)
        if v == 0:
            return tint(c, 7)  # the lit top edge of each plank
        if v == 14:
            return tint(c, -4)
        if (x, y) in knots:
            return tint(c, knots[x, y])
        if (x, y) in grain:
            return tint(c, grain[x, y])
        return c
    return floor(fill)


def carpet_floor():
    # Carpet squares: a heathered weave, the pile turned a quarter between neighbours.
    rnd = random.Random(11)
    fleck = {(x, y): rnd.random() for y in range(T) for x in range(T)}

    def fill(x, y):
        if x % 64 == 0 or y % 64 == 0:
            return CARPET_SEAM
        turned = (x // 64 + y // 64) % 2
        f = fleck[x, y]
        base = CARPET[0] if not turned else CARPET[1]
        weave = (y if turned else x) % 2 == 0
        if f < 0.10:
            return CARPET[2]
        if f > 0.93:
            return CARPET[3]
        return tint(base, -2) if weave else base
    return floor(fill)


def ceramic_floor():
    rnd = random.Random(5)
    tone = {(i, j): rnd.choice((-2, 0, 0, 2)) for i in range(4) for j in range(4)}
    speck = {(rnd.randrange(T), rnd.randrange(T)) for _ in range(60)}

    def fill(x, y):
        u, v = x % 32, y % 32
        if u == 0 or v == 0:
            return GROUT
        i, j = x // 32, y // 32
        c = tint(CERAMIC[(i + j) % 2], tone[i, j])
        if u == 1 or v == 1:
            return tint(c, 7)  # the glazed edge catches the light
        if u == 31 or v == 31:
            return tint(c, -5)
        if (x, y) in speck:
            return tint(c, -5)
        return c
    return floor(fill)


def stone_floor():
    # Large pale slabs, running bond: the corridor and the lobby share this calm floor.
    rnd = random.Random(7)
    speck = {(rnd.randrange(T), rnd.randrange(T)): rnd.choice((-8, -6, 5)) for _ in range(150)}
    veins = set()
    for _ in range(7):  # faint hairline veins wandering across a slab
        x, y = rnd.randrange(T), rnd.randrange(T)
        for _ in range(rnd.randrange(8, 18)):
            veins.add((x % T, y % T))
            x += 1
            y += rnd.choice((-1, 0, 0, 1))

    def fill(x, y):
        row = y // 64
        shift = 32 if row % 2 else 0
        u, v = (x + shift) % 64, y % 64
        if v == 0 or u == 0:
            return STONE_SEAM
        c = STONE[((x + shift) // 64 + row) % 2]
        if v == 1 or u == 1:
            return tint(c, 5)
        if (x, y) in speck:
            return tint(c, speck[x, y])
        if (x, y) in veins and u > 3 and v > 3:
            return tint(c, -5)
        return c
    return floor(fill)


# ---- furniture parts ------------------------------------------------------------------------
def wood_top(s, x, y, w, h, grain=True):
    """A lit wooden surface seen from above: a bright back edge and faint grain."""
    s.rect(x, y, w, h, WOOD["top"])
    s.hline(x, y, w, WOOD["hi"])
    s.hline(x, y + 1, w, mix(WOOD["hi"], WOOD["top"], 0.5))
    if grain:
        for gy in range(y + 4, y + h - 1, 4):
            a = x + 3 + (gy * 7) % 11
            s.hline(a, gy, max(4, w // 4), tint(WOOD["top"], -7))
            s.hline(x + w // 2 + (gy * 5) % 9, gy, max(4, w // 5), tint(WOOD["top"], -7))
            s.hline(a + w // 4 + 3, gy + 2, max(3, w // 9), tint(WOOD["top"], 6))


def wood_edge(s, x, y, w):
    """The front thickness of a wooden top: two pixels, lit above, shaded under."""
    s.hline(x, y, w, WOOD["mid"])
    s.hline(x, y + 1, w, WOOD["face"])


def wood_leg(s, x, y, w, h):
    s.rect(x, y, w, h, WOOD["dark"])
    s.vline(x, y, h, WOOD["face"])
    s.vline(x + w - 1, y, h, WOOD["deep"])
    s.hline(x, y, w, WOOD["deep"])  # in the shadow of whatever it holds up


def paper(s, x, y, w, h, lines=(0.7, 0.5, 0.65)):
    s.rect(x + 1, y + 1, w, h, PAPER_SHADE)  # the sheet underneath
    s.rect(x, y, w, h, PAPER)
    for n, f in enumerate(lines):
        if y + 2 + n * 2 < y + h - 1:
            s.hline(x + 2, y + 2 + n * 2, max(2, round((w - 4) * f)), TEXT)


def mug(s, x, y, c=POT):
    """A mug seen from a little above: rim, coffee, body and a handle on the right."""
    s.rect(x, y + 1, 5, 6, c["mid"])
    s.vline(x, y + 1, 6, c["hi"])
    s.vline(x + 4, y + 1, 6, c["dark"])
    s.hline(x, y, 5, c["light"])
    s.hline(x + 1, y + 1, 3, COFFEE)
    s.put(x + 5, y + 2, c["dark"])
    s.put(x + 6, y + 3, c["dark"])
    s.put(x + 6, y + 4, c["dark"])
    s.put(x + 5, y + 5, c["dark"])


def cup_top(s, x, y):
    """A cup on its saucer, seen from above."""
    s.ellipse(x, y, 9, 7, PAPER_SHADE)
    s.ellipse(x + 1, y, 7, 6, PAPER)
    s.ellipse(x + 2, y + 1, 5, 4, COFFEE)
    s.put(x + 3, y + 2, tint(COFFEE, 30))


def monitor_back(s, x, y, w, h):
    s.rrect(x, y, w, h, PLASTIC["mid"])
    s.hline(x + 1, y, w - 2, PLASTIC["hi"])
    s.rect(x + 2, y + 2, w - 4, h - 5, PLASTIC["dark"])
    s.hline(x + 2, y + 2, w - 4, PLASTIC["deep"])
    s.rect(x + w // 2 - 1, y + h // 2 - 2, 2, 2, PLASTIC["hi"])  # maker's mark
    for i in range(x + 5, x + w - 5, 2):  # vent
        s.put(i, y + h - 2, PLASTIC["deep"])
    s.rect(x + w // 2 - 2, y + h, 4, 3, METAL["dark"])
    s.vline(x + w // 2 - 2, y + h, 3, METAL["mid"])
    s.rrect(x + w // 2 - 7, y + h + 3, 14, 3, METAL["mid"])
    s.hline(x + w // 2 - 6, y + h + 3, 12, METAL["hi"])


def monitor_front(s, x, y, w, h):
    s.rrect(x, y, w, h, PLASTIC["dark"])
    s.hline(x + 1, y, w - 2, PLASTIC["mid"])
    s.shade(x + 2, y + 2, w - 4, h - 5, SCREEN["mid"], SCREEN["dark"])
    s.hline(x + 2, y + 2, w - 4, SCREEN["hi"])
    s.rect(x + 4, y + 4, 7, 5, PAPER)  # a window
    s.hline(x + 5, y + 6, 4, TEXT)
    s.text(x + 13, y + 5, (6, 4), SCREEN["hi"])
    s.rect(x + w // 2 - 2, y + h, 4, 2, METAL["dark"])
    s.rrect(x + w // 2 - 6, y + h + 2, 12, 2, METAL["mid"])


# ---- furniture ------------------------------------------------------------------------------
def desk_rear():
    """A desk seen from the visitor side: monitor back on top, a solid modesty panel in front."""
    s = Sprite(64, 52)
    wood_top(s, 1, 18, 62, 12)
    wood_edge(s, 1, 30, 62)
    s.shade(5, 32, 54, 13, mix(WOOD["face"], WOOD["dark"], 0.35), WOOD["dark"])  # modesty panel
    s.hline(5, 32, 54, WOOD["deep"])  # the top's shadow
    s.hline(5, 33, 54, mix(WOOD["dark"], WOOD["deep"], 0.5))
    s.rect(10, 36, 44, 6, mix(WOOD["face"], WOOD["dark"], 0.2))  # recessed field
    s.bevel(10, 36, 44, 6, WOOD["deep"], WOOD["face"])
    for x in (1, 59):  # side panels down to the floor
        s.shade(x, 32, 4, 19, WOOD["face"], mix(WOOD["face"], WOOD["dark"], 0.6))
        s.hline(x, 32, 4, WOOD["dark"])
    s.vline(1, 33, 18, WOOD["mid"])
    s.vline(62, 33, 18, WOOD["dark"])
    monitor_back(s, 18, 1, 28, 15)
    mug(s, 6, 20)
    paper(s, 46, 20, 11, 8)
    s.hline(39, 26, 5, BLUE)  # pen
    s.put(44, 26, PLASTIC["deep"])
    return s.outline()


def desk():
    s = Sprite(64, 52)
    wood_top(s, 1, 14, 62, 19)
    wood_edge(s, 1, 33, 62)
    s.shade(5, 35, 54, 6, WOOD["face"], WOOD["dark"])  # apron with one drawer
    s.hline(5, 35, 54, WOOD["deep"])
    s.rect(38, 36, 18, 4, mix(WOOD["face"], WOOD["mid"], 0.4))
    s.bevel(38, 36, 18, 4, WOOD["mid"], WOOD["dark"])
    s.hline(45, 38, 4, METAL["hi"])
    for x in (1, 59):
        s.shade(x, 35, 4, 16, WOOD["face"], mix(WOOD["face"], WOOD["dark"], 0.6))
        s.hline(x, 35, 4, WOOD["dark"])
    monitor_front(s, 19, 1, 26, 15)
    s.rrect(17, 23, 22, 6, PLASTIC["mid"])  # keyboard
    s.hline(18, 23, 20, PLASTIC["hi"])
    for ky in (25, 27):
        for kx in range(19, 37, 2):
            s.put(kx, ky, METAL["mid"])
    s.rrect(43, 24, 4, 5, METAL["hi"])  # mouse
    s.put(44, 24, METAL["dark"])
    mug(s, 6, 19)
    paper(s, 50, 19, 9, 9)
    return s.outline()


def office_chair():
    s = Sprite(28, 36)
    s.rrect(5, 1, 18, 16, PLASTIC["mid"], 2)  # back
    s.rrect(7, 3, 14, 12, PLASTIC["hi"])
    s.hline(8, 3, 12, tint(PLASTIC["hi"], 16))
    for y in (6, 9, 12):  # mesh
        s.hline(8, y, 12, PLASTIC["mid"])
    for x in (2, 23):  # arms
        s.rect(x, 13, 3, 3, PLASTIC["deep"])
        s.hline(x, 13, 3, PLASTIC["mid"])
        s.rect(x + 1, 16, 1, 4, METAL["dark"])
    s.rrect(3, 17, 22, 8, PLASTIC["mid"])  # seat
    s.rect(4, 17, 20, 2, PLASTIC["hi"])
    s.hline(5, 17, 18, tint(PLASTIC["hi"], 16))
    s.rect(3, 22, 22, 3, PLASTIC["dark"])
    s.rect(12, 25, 4, 5, METAL["mid"])  # gas lift
    s.vline(12, 25, 5, METAL["hi"])
    s.vline(15, 25, 5, METAL["dark"])
    s.rect(5, 30, 18, 2, METAL["dark"])  # star base
    s.hline(5, 30, 18, METAL["mid"])
    s.rect(12, 30, 4, 3, METAL["dark"])
    for x in (4, 12, 21):  # casters
        s.rect(x, 32, 3 if x != 12 else 4, 3, PLASTIC["deep"])
    return s.outline()


def meeting_table():
    s = Sprite(128, 64)
    wood_top(s, 1, 1, 126, 40)
    for cx, cy in ((1, 1), (126, 1)):
        s.clear(cx, cy)
    s.rect(6, 6, 116, 1, tint(WOOD["top"], -12))  # inlay line
    s.rect(6, 35, 116, 1, tint(WOOD["top"], 8))
    s.rect(6, 6, 1, 30, tint(WOOD["top"], -12))
    s.rect(121, 6, 1, 30, tint(WOOD["top"], 8))
    wood_edge(s, 1, 41, 126)
    s.hline(1, 43, 126, WOOD["dark"])
    s.shade(13, 44, 102, 5, mix(WOOD["face"], WOOD["dark"], 0.5), WOOD["dark"])  # apron, set back
    s.hline(13, 44, 102, WOOD["deep"])
    for x in (6, 115):
        wood_leg(s, x, 44, 7, 19)
        s.rect(x, 61, 7, 2, WOOD["deep"])
    paper(s, 20, 13, 12, 10)
    paper(s, 90, 20, 12, 10, (0.5, 0.7, 0.6))
    s.hline(104, 24, 6, RED)  # pen
    s.put(110, 24, PLASTIC["deep"])
    cup_top(s, 38, 25)
    s.rect(96, 9, 11, 8, TEAL["dark"])  # notebook
    s.rect(96, 9, 10, 7, TEAL["mid"])
    s.vline(97, 9, 7, TEAL["hi"])
    s.hline(99, 11, 5, TEAL["light"])
    # laptop, screen towards us
    s.rrect(53, 9, 22, 14, PLASTIC["dark"])
    s.hline(54, 9, 20, PLASTIC["mid"])
    s.shade(55, 11, 18, 10, SCREEN["mid"], SCREEN["dark"])
    s.hline(55, 11, 18, SCREEN["hi"])
    for i, h in enumerate((2, 4, 3, 6, 5)):  # a small chart
        s.rect(58 + i * 3, 20 - h, 2, h, SCREEN["hi"])
    s.rrect(51, 23, 26, 6, METAL["hi"])
    s.hline(52, 23, 24, METAL["white"])
    s.hline(51, 28, 26, METAL["mid"])
    s.rect(54, 24, 20, 2, METAL["mid"])
    for kx in range(55, 73, 2):
        s.put(kx, 24, METAL["dark"])
    s.rect(61, 27, 6, 1, METAL["mid"])
    return s.outline()


def whiteboard():
    s = Sprite(72, 59)
    s.rrect(1, 1, 70, 40, METAL["mid"])
    s.hline(2, 1, 68, METAL["hi"])
    s.vline(1, 2, 38, METAL["hi"])
    s.hline(2, 40, 68, METAL["dark"])
    s.vline(70, 2, 38, METAL["dark"])
    s.rect(3, 3, 66, 36, WHITE)
    s.hline(3, 3, 66, (255, 255, 253))
    s.vline(3, 3, 36, (255, 255, 253))
    s.hline(4, 38, 65, tint(WHITE, -10))
    s.rect(8, 8, 22, 2, BLUE)  # heading
    for n, w in enumerate((24, 20, 26)):  # bullets
        s.put(8, 14 + n * 4, PLASTIC["mid"])
        s.hline(11, 14 + n * 4, w, TEXT)
    s.hline(8, 28, 16, RED)  # underlined note
    s.hline(9, 29, 12, RED)
    s.text(8, 33, (20,), TEXT)
    for (x, y, c) in ((42, 6, MUSTARD), (54, 8, {"hi": (190, 222, 186), "mid": (166, 206, 164),
                                                  "dark": (128, 172, 128)})):  # sticky notes
        s.rect(x, y, 10, 9, c["mid"])
        s.hline(x, y, 10, c["hi"])
        s.hline(x + 2, y + 3, 6, c["dark"])
        s.hline(x + 2, y + 5, 4, c["dark"])
        s.put(x + 9, y + 8, c["dark"])
        s.put(x + 4, y, RED if c is MUSTARD else BLUE)  # magnet
        s.put(x + 5, y, RED if c is MUSTARD else BLUE)
    s.vline(42, 20, 15, METAL["dark"])  # chart axes
    s.hline(42, 34, 24, METAL["dark"])
    for i, y in enumerate((31, 30, 30, 28, 27, 27, 25, 24, 22, 22)):
        s.put(44 + i * 2, y, BLUE)
        s.put(45 + i * 2, y, BLUE)
    for i, y in enumerate((32, 32, 31, 31, 30, 29, 29, 28, 28, 27)):
        s.put(44 + i * 2, y, GREEN)
    s.rect(6, 41, 60, 2, METAL["mid"])  # tray
    s.hline(6, 41, 60, METAL["hi"])
    for x, c in ((18, RED), (27, BLUE), (36, PLASTIC["dark"])):
        s.hline(x, 40, 6, c)
        s.put(x + 6, 40, WHITE)
    s.rect(47, 39, 7, 2, PLASTIC["mid"])  # eraser
    s.hline(47, 40, 7, WHITE)
    for x in (10, 60):
        s.rect(x, 43, 2, 12, METAL["dark"])
        s.vline(x, 43, 12, METAL["mid"])
    for x in (5, 55):
        s.rect(x, 55, 12, 2, METAL["dark"])
        s.hline(x, 55, 12, METAL["mid"])
        s.put(x, 57, PLASTIC["deep"])
        s.put(x + 1, 57, PLASTIC["deep"])
        s.put(x + 10, 57, PLASTIC["deep"])
        s.put(x + 11, 57, PLASTIC["deep"])
    return s.outline()


def sofa():
    s = Sprite(80, 51)
    s.rrect(4, 1, 72, 22, TEAL["mid"], 2)  # back
    s.hline(6, 1, 68, TEAL["hi"])
    for x in (11, 41):  # back cushions
        s.rrect(x, 3, 28, 17, TEAL["hi"], 2)
        s.hline(x + 2, 3, 24, TEAL["light"])
        s.rect(x + 1, 17, 26, 2, TEAL["mid"])
        s.hline(x + 2, 19, 24, TEAL["dark"])
    for x in (11, 40):  # seat cushions
        s.rrect(x, 20, 29, 15, TEAL["light"])
        s.hline(x + 1, 20, 27, tint(TEAL["light"], 14))
        s.rect(x, 32, 29, 3, TEAL["hi"])
    s.vline(39, 20, 15, TEAL["mid"])
    s.vline(40, 20, 15, TEAL["hi"])
    s.shade(11, 35, 58, 8, TEAL["mid"], TEAL["dark"])  # front
    s.hline(11, 35, 58, TEAL["dark"])
    s.rect(11, 43, 58, 2, TEAL["deep"])
    for x in (1, 69):  # arms
        s.rrect(x, 10, 10, 35, TEAL["mid"], 2)
        s.rrect(x + 1, 10, 8, 4, TEAL["hi"])
        s.hline(x + 2, 10, 6, TEAL["light"])
        s.shade(x + 1, 22, 8, 21, TEAL["mid"], TEAL["dark"])
        s.rect(x, 43, 10, 2, TEAL["deep"])
    s.vline(10, 14, 29, TEAL["dark"])
    s.vline(69, 14, 29, TEAL["dark"])
    s.rrect(13, 10, 13, 13, MUSTARD["mid"], 2)  # throw pillow
    s.rect(15, 11, 9, 2, MUSTARD["hi"])
    s.rect(14, 20, 11, 2, MUSTARD["dark"])
    s.put(19, 16, MUSTARD["dark"])
    for x in (5, 71):
        s.rect(x, 45, 4, 5, WOOD["dark"])
        s.vline(x, 45, 5, WOOD["face"])
    return s.outline()


def coffee_table():
    s = Sprite(64, 40)
    wood_top(s, 1, 1, 62, 20)
    for cx in (1, 62):
        s.clear(cx, 1)
    wood_edge(s, 1, 21, 62)
    s.hline(1, 23, 62, WOOD["dark"])
    for x in (3, 56):
        wood_leg(s, x, 24, 5, 15)
    s.rect(8, 30, 48, 3, WOOD["dark"])  # lower shelf
    s.hline(8, 30, 48, WOOD["face"])
    s.rect(9, 6, 15, 11, PAPER_SHADE)  # magazines
    s.rect(8, 5, 15, 11, BLUE)
    s.rect(8, 5, 15, 3, tint(BLUE, 34))
    s.rect(10, 10, 8, 4, SCREEN["hi"])
    s.hline(10, 6, 9, PAPER)
    cup_top(s, 30, 8)
    s.ellipse(46, 6, 11, 10, POT["dark"])  # succulent in a low bowl
    s.ellipse(46, 5, 11, 9, POT["mid"])
    s.ellipse(47, 5, 9, 7, WOOD["deep"])
    for x, y, c in ((48, 4, LEAF[2]), (52, 3, LEAF[1]), (50, 6, LEAF[1]), (47, 7, LEAF[3]),
                    (53, 7, LEAF[2]), (50, 3, LEAF[0])):
        s.rect(x, y, 3, 3, c)
        s.put(x, y, LEAF[0])
    return s.outline()


def plant():
    s = Sprite(28, 38)
    s.rect(13, 18, 2, 5, WOOD["deep"])  # stem
    lobes = [  # back to front: darker under and behind, brighter on top
        (2, 9, 11, 9, 3), (15, 8, 11, 9, 3), (7, 12, 14, 9, 4),
        (4, 3, 11, 9, 2), (13, 2, 11, 9, 2), (1, 10, 10, 8, 2), (17, 11, 10, 8, 2),
        (8, 1, 11, 9, 1), (5, 8, 10, 8, 1), (13, 8, 10, 8, 1), (9, 13, 10, 7, 2),
    ]
    for x, y, w, h, k in lobes:
        s.ellipse(x, y + 1, w, h, LEAF[min(4, k + 1)])  # each leaf's own shaded underside
        s.ellipse(x, y, w, h - 1, LEAF[k])
    for x, y, w, h in ((10, 2, 6, 3), (6, 9, 5, 3), (15, 9, 5, 3), (6, 4, 4, 2), (16, 3, 4, 2),
                       (11, 14, 5, 2)):
        s.ellipse(x, y, w, h, LEAF[0])
    for x, y in ((12, 8), (9, 13), (18, 14), (4, 15), (22, 9), (14, 17), (7, 17)):  # deep gaps
        s.put(x, y, LEAF[4])
        s.put(x + 1, y, LEAF[4])
    s.rect(6, 22, 16, 3, POT["hi"])  # rim
    s.hline(6, 22, 16, POT["light"])
    s.hline(6, 24, 16, POT["mid"])
    s.rect(7, 25, 14, 6, POT["mid"])
    s.rect(8, 31, 12, 5, POT["mid"])
    s.hline(7, 25, 14, POT["deep"])  # shadow under the rim
    for y in range(26, 36):
        left, right = (7, 20) if y < 31 else (8, 19)
        s.put(left, y, POT["hi"])
        s.put(left + 1, y, POT["hi"])
        s.put(right, y, POT["dark"])
        s.put(right - 1, y, POT["dark"])
    s.hline(8, 35, 12, POT["dark"])
    return s.outline()


def filing_cabinet():
    s = Sprite(24, 50)
    s.rect(1, 1, 22, 4, METAL["hi"])  # top
    s.hline(1, 1, 22, METAL["white"])
    s.rect(1, 5, 22, 43, METAL["mid"])
    s.hline(1, 5, 22, METAL["dark"])
    for y in (7, 20, 33):
        s.rect(3, y, 18, 12, METAL["hi"])
        s.hline(3, y, 18, METAL["white"])
        s.vline(3, y, 12, METAL["white"])
        s.hline(3, y + 11, 18, METAL["mid"])
        s.rect(8, y + 2, 8, 3, PAPER)  # label
        s.hline(9, y + 3, 5, TEXT)
        s.bevel(7, y + 1, 10, 5, METAL["dark"], METAL["mid"])
        s.rect(8, y + 7, 8, 2, METAL["deep"])  # recessed pull
        s.hline(8, y + 9, 8, METAL["white"])
    s.put(19, 9, METAL["deep"])  # lock
    s.vline(22, 5, 43, METAL["dark"])
    s.hline(1, 47, 22, METAL["deep"])
    return s.outline()


def printer():
    s = Sprite(40, 44)
    s.rect(9, 1, 22, 5, PAPER)  # sheets in the feeder
    s.hline(9, 1, 22, (255, 255, 253))
    s.hline(11, 3, 14, TEXT)
    s.rrect(4, 4, 32, 6, METAL["hi"])  # feeder
    s.hline(5, 4, 30, METAL["white"])
    s.hline(4, 9, 32, METAL["mid"])
    s.rect(8, 6, 24, 1, METAL["dark"])
    s.rrect(1, 10, 38, 12, METAL["hi"])  # scanner body
    s.hline(2, 10, 36, METAL["white"])
    s.hline(1, 21, 38, METAL["dark"])
    s.rrect(23, 12, 13, 7, PLASTIC["mid"])  # control panel
    s.rect(24, 13, 6, 4, SCREEN["mid"])
    s.hline(24, 13, 6, SCREEN["hi"])
    s.put(32, 14, (118, 198, 128))
    s.put(34, 14, (232, 184, 86))
    s.hline(32, 16, 3, PLASTIC["hi"])
    s.text(4, 13, (10, 7), METAL["mid"], 3)
    s.shade(1, 22, 38, 19, METAL["mid"], mix(METAL["mid"], METAL["dark"], 0.55))  # lower body
    s.rect(4, 23, 32, 4, PLASTIC["deep"])  # output slot
    s.rect(8, 25, 24, 5, PAPER)
    s.hline(8, 29, 24, PAPER_SHADE)
    s.text(10, 26, (16, 11), TEXT)
    for y in (32, 37):  # paper drawers
        s.hline(3, y, 34, METAL["dark"])
        s.hline(3, y + 1, 34, METAL["hi"])
        s.rect(16, y + 2, 8, 1, METAL["deep"])
        s.rect(31, y + 2, 3, 2, PAPER)
    s.vline(38, 22, 19, METAL["dark"])
    s.rect(1, 41, 38, 2, METAL["deep"])
    return s.outline()


def water_cooler():
    s = Sprite(20, 51)
    s.ellipse(4, 1, 12, 6, WATER["hi"])  # bottle, upside down
    s.rect(4, 4, 12, 13, WATER["mid"])
    s.rect(4, 4, 12, 3, WATER["hi"])  # air above the water line
    s.hline(4, 7, 12, WATER["dark"])
    s.vline(6, 3, 13, WATER["hi"])
    s.vline(7, 8, 8, tint(WATER["hi"], 6))
    s.vline(14, 5, 12, WATER["dark"])
    s.vline(15, 5, 12, WATER["dark"])
    for x, y in ((10, 10), (12, 13), (9, 14)):  # bubbles
        s.put(x, y, WATER["hi"])
    s.rect(6, 17, 8, 2, WATER["dark"])  # neck
    s.rect(1, 19, 18, 29, WHITE)
    s.rect(1, 19, 18, 2, METAL["hi"])
    s.hline(1, 19, 18, METAL["white"])
    s.hline(1, 21, 18, METAL["mid"])
    s.rect(16, 22, 3, 26, tint(WHITE, -20))  # shaded side
    s.rect(3, 23, 12, 10, tint(WHITE, -12))  # recess with the taps
    s.hline(3, 23, 12, tint(WHITE, -34))
    for x, c in ((4, BLUE), (10, RED)):
        s.rect(x, 25, 4, 2, c)
        s.hline(x, 25, 4, tint(c, 36))
        s.rect(x + 1, 27, 2, 2, METAL["dark"])
    s.rect(3, 31, 12, 2, METAL["mid"])  # drip tray
    for x in range(4, 15, 2):
        s.put(x, 31, METAL["deep"])
    s.bevel(3, 36, 12, 9, tint(WHITE, -26), tint(WHITE, -8))  # cupboard door
    s.vline(13, 39, 3, METAL["dark"])
    s.rect(1, 46, 18, 2, METAL["dark"])
    s.hline(1, 46, 18, METAL["mid"])
    return s.outline()


def coffee_station():
    s = Sprite(48, 53)
    s.rect(1, 19, 46, 6, WHITE)  # stone counter
    s.hline(1, 19, 46, (255, 255, 253))
    s.hline(1, 24, 46, tint(WHITE, -22))
    s.hline(1, 25, 46, tint(WHITE, -40))
    s.shade(1, 26, 46, 22, WOOD["face"], mix(WOOD["face"], WOOD["dark"], 0.7))  # cabinet
    s.hline(1, 26, 46, WOOD["deep"])
    for x in (3, 25):  # doors
        s.rect(x, 29, 20, 17, mix(WOOD["face"], WOOD["mid"], 0.45))
        s.bevel(x, 29, 20, 17, WOOD["mid"], WOOD["dark"])
        s.rect(x + 3, 32, 14, 11, mix(WOOD["face"], WOOD["mid"], 0.2))
        s.bevel(x + 3, 32, 14, 11, WOOD["dark"], WOOD["mid"])
    s.rect(20, 36, 2, 4, METAL["hi"])  # pulls
    s.rect(26, 36, 2, 4, METAL["hi"])
    s.rect(3, 48, 42, 3, WOOD["deep"])  # toe kick
    # espresso machine
    s.rrect(4, 1, 20, 18, PLASTIC["mid"])
    s.rect(5, 1, 18, 2, METAL["hi"])
    s.hline(5, 1, 18, METAL["white"])
    s.rect(6, 4, 16, 4, PLASTIC["dark"])
    s.put(8, 5, (118, 198, 128))
    s.put(10, 5, (232, 184, 86))
    s.rect(16, 5, 2, 2, METAL["hi"])
    s.rect(19, 5, 2, 2, METAL["hi"])
    s.rect(6, 9, 16, 8, PLASTIC["deep"])  # the bay
    s.rect(11, 9, 6, 2, METAL["mid"])  # group head
    s.hline(11, 9, 6, METAL["hi"])
    s.rect(11, 12, 6, 5, PAPER)  # cup
    s.hline(12, 12, 4, COFFEE)
    s.vline(16, 13, 4, PAPER_SHADE)
    s.rect(5, 17, 18, 2, METAL["mid"])  # drip tray
    s.hline(5, 17, 18, METAL["hi"])
    for x, top in ((27, 8), (33, 12)):  # stacks of paper cups
        s.rect(x, top, 5, 19 - top, PAPER)
        s.vline(x + 4, top, 19 - top, PAPER_SHADE)
        for y in range(top + 2, 19, 2):
            s.hline(x, y, 5, PAPER_SHADE)
        s.hline(x, top, 5, (255, 255, 253))
    s.rect(40, 9, 6, 2, METAL["mid"])  # jar
    s.hline(40, 9, 6, METAL["hi"])
    s.rect(40, 11, 6, 8, (236, 226, 204))
    s.vline(40, 11, 8, (248, 242, 226))
    for x, y in ((42, 13), (44, 15), (41, 16), (43, 17), (44, 12)):
        s.put(x, y, WOOD["mid"])
    return s.outline()


def cafeteria_table():
    s = Sprite(56, 60)
    s.ellipse(1, 4, 54, 25, WOOD["dark"])  # thickness of the top
    s.ellipse(1, 3, 54, 25, WOOD["face"])
    s.ellipse(1, 1, 54, 25, WOOD["top"])
    s.ellipse(3, 2, 50, 22, mix(WOOD["top"], WOOD["hi"], 0.35))
    s.ellipse(8, 3, 26, 8, mix(WOOD["top"], WOOD["hi"], 0.75))
    s.ellipse(12, 4, 14, 3, WOOD["hi"])
    for x, y, w in ((30, 15, 14), (14, 18, 12), (34, 20, 8)):  # grain
        s.hline(x, y, w, tint(WOOD["top"], -4))
    for x, c in ((24, PAPER), (29, PLASTIC["mid"])):  # salt and pepper
        s.rect(x, 9, 3, 5, c)
        s.hline(x, 9, 3, METAL["hi"])
        s.vline(x + 2, 10, 4, tint(c, -24))
    s.rect(22, 28, 12, 2, METAL["deep"])  # collar under the top
    for x, c in ((25, METAL["hi"]), (26, METAL["hi"]), (27, METAL["mid"]), (28, METAL["mid"]),
                 (29, METAL["dark"]), (30, METAL["dark"])):
        s.vline(x, 30, 20, c)
    s.ellipse(12, 49, 32, 9, METAL["dark"])  # foot
    s.ellipse(12, 48, 32, 8, METAL["mid"])
    s.ellipse(15, 48, 24, 4, METAL["hi"])
    s.rect(25, 48, 6, 3, METAL["mid"])
    s.vline(25, 48, 3, METAL["hi"])
    s.vline(30, 48, 3, METAL["dark"])
    return s.outline()


def cafeteria_chair():
    s = Sprite(24, 38)
    s.rrect(4, 1, 16, 15, TEAL["hi"], 2)  # shell back
    s.rect(6, 1, 12, 1, TEAL["light"])
    s.rect(5, 2, 14, 2, TEAL["light"])
    s.rect(4, 11, 16, 5, TEAL["mid"])
    s.rrect(8, 5, 8, 3, TEAL["deep"])  # grip slot
    s.hline(9, 7, 6, TEAL["dark"])
    s.rrect(2, 15, 20, 7, TEAL["light"])  # seat
    s.hline(3, 15, 18, tint(TEAL["light"], 16))
    s.rect(2, 20, 20, 2, TEAL["hi"])
    s.rect(2, 22, 20, 2, TEAL["dark"])
    for x in (7, 15):  # back legs
        s.rect(x, 24, 2, 9, METAL["deep"])
    for x in (3, 19):  # front legs
        s.rect(x, 24, 2, 12, METAL["mid"])
        s.vline(x, 24, 12, METAL["hi"])
        s.hline(x, 24, 2, METAL["deep"])
        s.hline(x, 36, 2, PLASTIC["deep"])
    s.hline(5, 30, 14, METAL["dark"])
    return s.outline()


def bookshelf():
    s = Sprite(64, 59)
    s.rect(1, 1, 62, 57, WOOD["face"])
    s.rect(1, 1, 62, 3, WOOD["top"])  # top board
    s.hline(1, 1, 62, WOOD["hi"])
    s.hline(1, 4, 62, WOOD["dark"])
    s.vline(1, 5, 53, WOOD["mid"])
    s.vline(62, 5, 53, WOOD["dark"])
    rnd = random.Random(12)
    for shelf in range(3):
        top = 6 + shelf * 17
        s.rect(4, top, 56, 14, WOOD["deep"])
        s.hline(4, top, 56, tint(WOOD["deep"], -14))  # shadow of the board above
        s.hline(4, top + 1, 56, tint(WOOD["deep"], -7))
        floor_y = top + 14
        x, end = 5, 59
        if shelf == 0:  # a plant at the end of the top shelf
            end = 47
            s.rect(50, floor_y - 5, 7, 5, POT["mid"])
            s.hline(50, floor_y - 5, 7, POT["hi"])
            s.vline(56, floor_y - 4, 4, POT["dark"])
            s.ellipse(48, floor_y - 12, 11, 8, LEAF[2])
            s.ellipse(49, floor_y - 12, 7, 5, LEAF[1])
            s.ellipse(50, floor_y - 12, 4, 2, LEAF[0])
        if shelf == 1:  # binders at the start of the middle shelf
            for i in range(3):
                bx = 5 + i * 6
                s.rect(bx, floor_y - 12, 5, 12, WHITE)
                s.vline(bx + 4, floor_y - 12, 12, PAPER_SHADE)
                s.rect(bx + 1, floor_y - 10, 3, 4, (BLUE, RED, GREEN)[i])
                s.put(bx + 2, floor_y - 3, METAL["dark"])
            x = 24
        if shelf == 2:  # a storage box at the end of the bottom shelf
            end = 42
            s.rect(45, floor_y - 9, 13, 9, (206, 190, 160))
            s.rect(45, floor_y - 9, 13, 3, (222, 208, 180))
            s.hline(45, floor_y - 6, 13, (176, 160, 130))
            s.rect(49, floor_y - 4, 5, 2, PAPER)
        while x < end - 2:
            w = rnd.choice((3, 3, 4, 4, 5))
            h = rnd.choice((9, 10, 11, 11, 12))
            c = rnd.choice(BOOKS)
            if x + w > end:
                break
            if rnd.random() < 0.1 and x + 8 < end:  # a leaning book
                for i in range(6):
                    lift = (5 - i) // 2
                    s.vline(x + i, floor_y - 10 + lift, 10 - lift, c if i else tint(c, 20))
                x += 8
                continue
            s.rect(x, floor_y - h, w, h, c)
            s.vline(x, floor_y - h, h, tint(c, 22))
            s.vline(x + w - 1, floor_y - h, h, tint(c, -22))
            band = tint(c, 46) if sum(c) < 520 else tint(c, -46)
            s.hline(x + 1, floor_y - h + 2, w - 2, band)
            if w >= 4:
                s.hline(x + 1, floor_y - 3, w - 2, band)
            x += w + (1 if rnd.random() < 0.18 else 0)
        s.rect(1, floor_y, 62, 2, WOOD["top"])  # the board
        s.hline(1, floor_y, 62, WOOD["hi"])
        s.hline(1, floor_y + 1, 62, WOOD["mid"])
    s.rect(1, 56, 62, 2, WOOD["dark"])
    return s.outline()


def door():
    s = Sprite(32, 51)
    s.rect(1, 1, 30, 49, WOOD["dark"])  # frame
    s.hline(1, 1, 30, WOOD["face"])
    s.vline(1, 1, 49, WOOD["face"])
    s.rect(3, 3, 26, 47, WOOD["top"])
    s.hline(3, 3, 26, WOOD["hi"])
    s.vline(3, 3, 47, WOOD["hi"])
    s.vline(28, 4, 46, WOOD["mid"])
    for y, h in ((7, 15), (27, 18)):  # recessed panels
        s.rect(7, y, 18, h, mix(WOOD["top"], WOOD["mid"], 0.7))
        s.bevel(7, y, 18, h, WOOD["face"], WOOD["hi"])
        s.rect(10, y + 3, 12, h - 6, mix(WOOD["top"], WOOD["mid"], 0.4))
        s.bevel(10, y + 3, 12, h - 6, WOOD["hi"], WOOD["face"])
    s.rect(23, 22, 3, 7, METAL["hi"])  # handle plate and lever
    s.vline(25, 22, 7, METAL["mid"])
    s.hline(23, 22, 3, METAL["white"])
    s.rect(20, 24, 5, 2, METAL["dark"])
    s.hline(20, 24, 5, METAL["mid"])
    s.put(24, 27, METAL["deep"])
    for y in (8, 42):  # hinges
        s.rect(3, y, 1, 3, METAL["mid"])
    s.rect(3, 47, 26, 3, WOOD["face"])  # threshold shadow
    s.hline(3, 47, 26, WOOD["mid"])
    return s.outline()


def partition():
    s = Sprite(64, 16)
    s.rect(1, 1, 62, 12, (190, 194, 204))
    s.rect(1, 1, 62, 2, METAL["hi"])
    s.hline(1, 1, 62, METAL["white"])
    s.hline(1, 3, 62, (168, 172, 184))
    for x in range(1, 63):
        if x % 2:
            s.vline(x, 5, 7, (184, 188, 198))
    for x in (16, 32, 48):
        s.vline(x, 3, 10, (160, 164, 176))
    s.hline(1, 12, 62, (160, 164, 176))
    for x in (4, 56):
        s.rect(x, 13, 4, 2, METAL["dark"])
    return s.outline()


def shadow():
    """A soft patch of shade for the floor under furniture and people; the scene stretches it."""
    w, h = 32, 12
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for y in range(h):
        for x in range(w):
            d = ((x - (w - 1) / 2) / (w / 2)) ** 2 + ((y - (h - 1) / 2) / (h / 2)) ** 2
            if d <= 1.0:
                px[x, y] = (38, 34, 44, 56 if d <= 0.4 else 40 if d <= 0.72 else 22)
    return img


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
    furniture = pack("furniture", {**{k: f().img for k, f in FURNITURE.items()},
                                   "shadow": shadow()})
    rear = pack("desk-rear", {"desk-rear": desk_rear().img})
    manifest = {"version": 3, "export": "procedural pixel art, 1 art px = 1 world px",
                "furniture": furniture, "floors": floors, "desk-rear": rear}
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {len(FURNITURE)} furniture frames, 4 floors, the rear desk and the shadow.")


if __name__ == "__main__":
    main()
