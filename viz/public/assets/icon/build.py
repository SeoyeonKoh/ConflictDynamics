"""Draw the site icon: two pixel speech bubbles, a "!" and a "...", on a dark tile.

The bubbles use the viewer's talk (amber) and message (blue) colours: a conversation with some
friction. Drawn on a 32x32 grid and written as a crisp SVG (any size) plus PNGs for browsers and
home screens that want a bitmap. Run: python3 viz/public/assets/icon/build.py
"""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT.parent.parent
N = 32
TILE, TILE_EDGE = (31, 36, 51), (46, 53, 72)
LINE = (20, 22, 30)
AMBER, AMBER_HI = (217, 161, 43), (240, 196, 98)
BLUE, BLUE_HI = (65, 161, 207), (122, 196, 230)
WHITE = (250, 249, 244)


def tile(grid):
    for y in range(N):
        for x in range(N):
            # rounded corners, radius 6
            cx = min(x, N - 1 - x)
            cy = min(y, N - 1 - y)
            if cx < 6 and cy < 6 and (5.5 - cx) ** 2 + (5.5 - cy) ** 2 > 36:
                continue
            edge = cx == 0 or cy == 0 or (cx < 6 and cy < 6 and (5.5 - cx) ** 2 + (5.5 - cy) ** 2 > 25)
            grid[x, y] = TILE_EDGE if edge else TILE


def bubble(grid, x0, y0, x1, y1, fill, hi, tail):
    """A rounded box from (x0, y0) to (x1, y1) inclusive with a stepped tail, outlined."""
    body = set()
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            corner = (x in (x0, x1)) and (y in (y0, y1))
            if not corner:
                body.add((x, y))
    body |= set(tail)
    ring = {(x + dx, y + dy) for x, y in body for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - body
    for p in ring:
        grid[p] = LINE
    for x, y in body:
        grid[x, y] = hi if y == y0 or (y == y0 + 1 and x in (x0, x1)) else fill
    return body


def draw():
    grid = {}
    tile(grid)
    bubble(grid, 4, 5, 19, 16, AMBER, AMBER_HI,
           [(7, 17), (8, 17), (6, 18), (7, 18), (5, 19)])
    for y in range(7, 11):  # "!", left of where the blue bubble covers
        grid[7, y] = grid[8, y] = LINE
    grid[7, 12] = grid[8, 12] = LINE
    bubble(grid, 12, 13, 27, 23, BLUE, BLUE_HI,
           [(23, 24), (24, 24), (24, 25), (25, 25), (26, 26)])
    for x in (15, 19, 23):  # "..."
        for dx in (0, 1):
            for dy in (0, 1):
                grid[x + dx, 18 + dy] = WHITE
    return grid


def svg(grid):
    rects = []
    for y in range(N):
        x = 0
        while x < N:
            c = grid.get((x, y))
            if c is None:
                x += 1
                continue
            run = 1
            while grid.get((x + run, y)) == c:
                run += 1
            rects.append(f'<rect x="{x}" y="{y}" width="{run}" height="1" fill="#{c[0]:02x}{c[1]:02x}{c[2]:02x}"/>')
            x += run
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {N} {N}" shape-rendering="crispEdges">'
            + "".join(rects) + "</svg>\n")


def png(grid, scale):
    img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    for (x, y), c in grid.items():
        img.putpixel((x, y), (*c, 255))
    return img.resize((N * scale, N * scale), Image.NEAREST)


def main():
    grid = draw()
    (PUBLIC / "favicon.svg").write_text(svg(grid))
    png(grid, 1).save(PUBLIC / "favicon-32.png")
    png(grid, 6).save(PUBLIC / "apple-touch-icon.png")  # 192px
    print("Wrote favicon.svg, favicon-32.png and apple-touch-icon.png")


if __name__ == "__main__":
    main()
