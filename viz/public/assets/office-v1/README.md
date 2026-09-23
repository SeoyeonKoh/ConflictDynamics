# Office visual assets v1

For the current **20-character animated set**, use
[characters-v3](../characters-v3/preview.html). This folder preserves the original static
characters and remains the source for furniture and floor textures.

## Active character redesign: chibi v2

The manifest and preview now use `characters-chibi-v2.png` and
`characters-chibi-v2.atlas.json`: eight big-headed, short-bodied characters in the user's
reference pixel-art style. Identity order, agent IDs and outfit colors are preserved.
Built-in image generation produced the 1536×1024 transparent PNG; it is unmodified.
Atlas bounds use visible alpha >=128 with 3px padding. Original v1 files below remain available.
Use the v2 filenames in the Phaser example below. Exact prompt: `characters-chibi-v2.prompt.md`.

## Original v1 assets

Generated with the built-in image generation tool on 2026-09-23. Exact prompts are in [prompts.md](prompts.md).

- `characters.png`: 8 fictional office workers, static downward-facing idle poses. Erin, Alex, Blake, Casey, Drew, Frankie map to agent-0 through agent-5; agent-6/7 are spare appearances.
- `furniture.png`: 16 objects: desk, rolling chair, meeting table, whiteboard, sofa, coffee table, plant, filing cabinet, coffee station, water cooler, printer, dining table, dining chair, bookshelf, door, partition.
- `floors.png`: oak, blue-gray carpet, ceramic and ivory stone materials.
- `*.atlas.json`: Phaser-compatible named source rectangles, measured against the actual 1254×1254 outputs. Character/furniture rectangles enclose visible alpha >=128 plus 3px padding; faint alpha specks outside these rectangles are excluded without modifying originals.
- `manifest.json`: image paths, atlas paths, frame names and agent assignments.
- [preview.html](preview.html): local asset gallery at approximate game scale; no server required.

All three PNG originals are preserved unchanged. Characters and furnishings have real alpha transparency (range 0–255). Floors are opaque. They are high-resolution pixel-style source assets, not literal 32px sprite PNGs. Scale proportionally in the viewer: character height around 40 world pixels, desk width around 64 world pixels; set character/object origin to (0.5,1), floor origin to (0,0).

```ts
// Phaser preload
this.load.atlas('office-characters', '/assets/office-v1/characters.png',
  '/assets/office-v1/characters.atlas.json');
// Phaser create
const agent = this.add.image(x, y, 'office-characters', 'agent-0');
agent.setOrigin(0.5, 1).setScale(40 / agent.height);
```

Use the same atlas-loading pattern for furnishings and floors. Floor frame rectangles can be drawn into 32px cells at runtime; this is not a Tiled-ready 32px tileset PNG. Seamless edge matching of generated floor patterns is not certified; inspect tiling when building the map. No walking animation or scene integration is included. The art is generated for this project; no third-party asset pack was imported and no third-party license claim is made.

## Reverse-facing desk

`desk-rear.png` is a standalone visitor-side view of the original desk: the back of the monitor and the wooden modesty panel face the viewer. Its visible alpha >=128 bounds are 245×201 pixels, with 3 transparent pixels of padding on each side in a 251×207 RGBA canvas. `desk-rear.atlas.json` exposes one Phaser frame named `desk-rear` at `(0, 0, 251, 207)`. Draw it at 64×52 world pixels with origin `(0.5, 1)` when a front-facing worker sits behind the desk. The exact generation prompt is in [prompts.md](prompts.md).
