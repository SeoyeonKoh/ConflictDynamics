/** Phaser 3.90+ adapter. Call preloadCharacters in Scene.preload, register in Scene.create. */
export function preloadCharacters(scene, manifest, base = '/assets/characters-v3/') {
  for (const character of manifest.characters) {
    scene.load.atlas(character.id, base + character.image, base + character.atlas);
  }
}

export function registerCharacterAnimations(scene, manifest) {
  for (const character of manifest.characters) {
    for (const [motion, clip] of Object.entries(manifest.animations)) {
      const key = `${character.id}:${motion}`;
      if (scene.anims.exists(key)) continue;
      scene.anims.create({
        key, repeat: -1,
        frames: clip.frames.map((frame, index) => ({
          key: character.id, frame, duration: clip.durations[index],
        })),
        frameRate: 8,
      });
    }
  }
}

export function createCharacter(scene, manifest, id, x, y, motion = 'idle') {
  const character = manifest.characters.find(entry => entry.id === id);
  if (!character) throw new Error(`Unknown character: ${id}`);
  if (!manifest.animations[motion]) throw new Error(`Unknown motion: ${motion}`);
  const sprite = scene.add.sprite(x, y, id, 'idle-0');
  sprite.setOrigin(0.5, 1);
  sprite.setScale(character.displayHeight / character.data.frames['idle-0'].sourceSize.h);
  sprite.play(`${id}:${motion}`);
  return sprite;
}
