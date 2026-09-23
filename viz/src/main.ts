import Phaser from 'phaser';
import { connect } from './connection';
import { Hud } from './hud';
import { OfficeScene } from './scene';
import { World } from './world';

// Live mode: `?ws=ws://127.0.0.1:<port>` for a run on another stream_port.
const url = new URLSearchParams(location.search).get('ws') ?? 'ws://127.0.0.1:8765';

const world = new World();
const scene = new OfficeScene(world, document.getElementById('bubbles')!);
const hud = new Hud(world, control => send(control), () => select(null));
const send = connect(url, message => {
  world.apply(message);
  if (message.type === 'hello') select(null);
  hud.changed();
}, link => hud.link(link));

function select(agent: string | null) {
  scene.selected = agent;
  hud.select(agent);
}
scene.onSelect = select;

new Phaser.Game({
  type: Phaser.AUTO,
  parent: 'game',
  backgroundColor: '#1d2029',
  // Source sheets are high-resolution; linear filtering keeps the downscaled sprites smooth.
  antialias: true,
  scale: { mode: Phaser.Scale.RESIZE },
  scene,
});
