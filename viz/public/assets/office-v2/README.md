# Pixel office environment v2

New pixel-art furniture, floor textures and visitor-side desk, generated with the built-in image tool.
The honey oak, teal upholstery and slate palette match the existing office.

16 furniture frames and 4 floor frames retain their previous names. The rear desk has one continuous
wooden modesty panel: no visitor-facing drawers, handles or cabinet fronts.

Generated originals are saved unchanged under `viz/artwork/pixel-v4`. Furniture and floor originals
are 1254 × 1254; their point-sampled 2× runtime exports are 2508 × 2508. The rear desk is cropped to
its transparent bounds before the 2× export. Higher export dimensions do not imply added native detail.
Floor repetition is generated rather than mathematically certified seamless; inspect repeated patterns
at the intended game scale. Old office-v1 assets are preserved.

Open `preview.html` for individual object previews. Rebuild metadata with
`python3 viz/public/assets/office-v2/build_metadata.py`.
