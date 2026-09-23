import Phaser from 'phaser';
import { connect } from './connection';
import { Hud } from './hud';
import type { Control } from './messages';
import { Replay } from './replay';
import { OfficeScene } from './scene';
import { World } from './world';

// Live: `?ws=ws://127.0.0.1:<port>` for a run on another stream_port (default 8765).
// Replay: `?replay=<dir under runs/>`; a bare `?replay` lists the runs that have a journal.
const params = new URLSearchParams(location.search);
const run = params.get('replay');

const world = new World();
const scene = new OfficeScene(world, document.getElementById('bubbles')!);
let send: (control: Control) => void = () => {};
const hud = new Hud(world, control => send(control), () => select(null));

if (run === null) {
  send = connect(params.get('ws') ?? 'ws://127.0.0.1:8765', message => {
    world.apply(message);
    if (message.type === 'hello') select(null);
    hud.changed();
  }, link => hud.link(link));
} else if (run === '') {
  const runs: string[] = await (await fetch('/runs')).json();
  const list = document.createElement('div');
  list.id = 'runs';
  list.append(...runs.map(r => Object.assign(document.createElement('a'), { href: `?replay=${r}`, textContent: r })));
  list.querySelectorAll('a').forEach(a => a.after(document.createElement('br')));
  document.querySelector('main')!.replaceWith(list);
} else {
  const scrub = document.getElementById('scrub') as HTMLInputElement;
  hud.link('replay');
  const replay = await Replay.load(world, run, tick => {
    scrub.value = String(tick);
    hud.changed();
  });
  scrub.max = String(replay.last);
  scrub.hidden = false;
  scrub.oninput = () => {
    const index = Number(scrub.value); // pausing repaints the slider, so read it first
    replay.handle({ type: 'control', cmd: 'pause' });
    replay.seek(index);
  };
  send = control => replay.handle(control);
  select(null);
}

function select(agent: string | null) {
  scene.selected = agent;
  hud.select(agent);
}
scene.onSelect = select;
if (run !== '') {
  document.getElementById('game')!.ondblclick = () => scene.fit();
  new Phaser.Game({
    type: Phaser.AUTO,
    parent: 'game',
    backgroundColor: '#1d2029',
    // Source sheets are high-resolution; linear filtering keeps the downscaled sprites smooth.
    antialias: true,
    scale: { mode: Phaser.Scale.RESIZE },
    scene,
  });
}
