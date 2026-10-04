import { readFileSync, writeFileSync, mkdirSync, copyFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const records = JSON.parse(readFileSync(resolve(root, 'artwork/pixel-v4/generation.json')));
const sourceDir = resolve(root, 'artwork/pixel-v4');
mkdirSync(sourceDir, { recursive: true });
for (const record of records) {
  const character = record.id.startsWith('agent-');
  const directory = resolve(root, 'public/assets', character ? 'characters-v4' : 'office-v2');
  mkdirSync(directory, { recursive: true });
  const original = resolve(sourceDir, record.id + '.png');
  const source = resolve(root, record.path);
  if (source !== original) copyFileSync(source, original);
  // Point sampling preserves the newly drawn pixel clusters without interpolation.
  const args = [original];
  if (record.id === 'desk-rear') {
    // Ignore barely visible alpha specks when measuring transparent margins.
    const bounds = execFileSync('magick', [original, '-alpha', 'extract', '-threshold', '50%',
      '-format', '%@', 'info:'], { encoding: 'utf8' }).trim();
    args.push('-crop', bounds, '+repage', '-bordercolor', 'none', '-border', '3');
  }
  args.push('-filter', 'point', '-resize', '200%', resolve(directory, record.id + '.png'));
  execFileSync('magick', args);
}
const designs = JSON.parse(readFileSync(resolve(root, 'public/assets/characters-v3/prompts.json')));
designs.generator = 'built-in image generation tool; no imagegen skill';
designs.version = 4;
designs.export = '2x nearest-neighbor; native generated originals in viz/artwork/pixel-v4';
designs.prompts.forEach(design => {
  const record = records.find(entry => entry.id === design.id);
  if (record) design.prompt = record.prompt;
});
writeFileSync(resolve(root, 'public/assets/characters-v4/prompts.json'), JSON.stringify(designs, null, 2) + '\n');
writeFileSync(resolve(root, 'artwork/pixel-v4/prompts.json'), JSON.stringify(records.map(({id, prompt}) => ({id, prompt})), null, 2) + '\n');
console.log(`Exported ${records.length} newly generated assets; originals preserved.`);
