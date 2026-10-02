# Pixel office characters v4

20 newly generated pixel-art character sheets with ten poses each, preserving the existing identities,
large heads, compact bodies, dot eyes, dark outlines and outfit palettes.

- Native generated sheets: 1536 × 1024, saved unchanged in `viz/artwork/pixel-v4`.
- Runtime PNGs: 3072 × 2048, exported at exactly 2× using point sampling. This larger canvas
  preserves pixel clusters; it does not claim native 3K generation or add detail through interpolation.
- Idle, walk, sit and talk clips retain the previous frame names and timings.
- Atlas generation measures visible alpha and shares one logical canvas per character.
- `preview.html` provides animation playback, individual clips and zoom controls.
- Exact production prompts are in `prompts.json`; generation used the built-in image tool directly.
- Previous `characters-v3` files remain available.

Rebuild metadata: `python3 viz/public/assets/characters-v4/build_metadata.py`.
The viewer uses nearest-neighbor texture filtering for crisp pixel boundaries.
