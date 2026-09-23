# Office characters v3 — 20 animated appearances

Open [preview.html](preview.html) directly, or through a static server. It supports all-character
and per-character motion selection, play/pause, frame stepping, speed and game-size/zoom views.
Reduced-motion preference starts paused.

## Contents

- 20 original generated PNG sheets (`agent-0.png` through `agent-19.png`), ten poses each.
- 20 Phaser JSON atlases with named frames and a common logical canvas per character.
- `manifest.json`: 20 appearances, first six name assignments, frame rectangles and timings.
- `phaser.mjs`: preload, animation registration and sprite creation helpers for Phaser 3.90+.
- `prompts.json`: exact built-in image generation prompts and identity descriptions.
- `build_metadata.py`: repeatable image inspection/atlas generation; does not modify PNGs.

| Clip | Frames | Timing |
| --- | --- | --- |
| idle | 2 | 1800ms eyes open, 160ms blink |
| walk | 4 | 130ms per frame, alternating feet/arms |
| sit | 2 | 1400ms upright, 400ms relaxed |
| talk | 2 | 220ms speaking gesture, 260ms second pose |

All clips loop. This is **front-facing** animation, not four-direction movement. The sitting
poses contain no chair; seat/furniture positioning belongs to the scene. Generated frames may
have small hand-drawn shape variations; source pixels are preserved. Atlas metadata excludes
faint alpha specks using alpha >=128 bounds plus 3px padding, centers each visible frame and
anchors feet to the same logical baseline. It never stretches individual frames to fill a cell.

The original eight designs are retained in order, with twelve additional appearances. New
appearance labels do not create engine personas. The engine's hello sprite assignment now
supports agent-0 through agent-19. Live action-to-animation selection remains part of B-10.

## Phaser integration

Load the manifest before constructing the scene, or bundle it as JSON. Then:

```js
import { preloadCharacters, registerCharacterAnimations, createCharacter } from './phaser.mjs';

// Scene.preload():
preloadCharacters(this, manifest, '/assets/characters-v3/');

// Scene.create():
registerCharacterAnimations(this, manifest);
const erin = createCharacter(this, manifest, 'agent-0', 160, 200);
erin.play('agent-0:walk');
// Keep the same scale/origin when switching poses.
erin.play('agent-0:sit');
```

Use `pixelArt: true` in Phaser's game config. The helper uses native per-frame durations as
implemented in [Phaser 3.90 Animation](https://github.com/phaserjs/phaser/blob/v3.90.0/src/animations/Animation.js).
Do not override the animation frame rate at playback if you need the manifest's variable timing.

Regenerate metadata from the repo with:

```sh
uv run python viz/public/assets/characters-v3/build_metadata.py
```

Pillow is needed for that optional authoring step. Runtime loading has no Python dependency.
Images were generated with the built-in image tool using the accepted v2 sheet as the style
reference. No external asset pack is included. Original v1/v2 assets are preserved in
`../office-v1/`.
