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
const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const scrub = $<HTMLInputElement>('scrub');

const world = new World();
const scene = new OfficeScene(world, $('bubbles'));
let send: (control: Control) => void = () => {};
const hud = new Hud(world, control => send(control), agent => select(agent));
const shown = (tick: number) => {
  scrub.value = String(tick);
  hud.changed();
};

if (run === null) {
  // Live: every message is journaled; World follows the newest tick until the viewer looks back.
  const timeline = new Replay(world, shown);
  let following = true;
  const follow = (on: boolean) => {
    following = on;
    $('live').classList.toggle('on', on);
  };
  const socket = connect(params.get('ws') ?? 'ws://127.0.0.1:8765', message => {
    timeline.record(message);
    if (message.type === 'hello') {
      follow(true);
      select(null);
    }
    if (following || message.type === 'status' || message.type === 'error') world.apply(message);
    if (following) timeline.followed();
    scrub.max = String(Math.max(0, timeline.last));
    if (following) scrub.value = scrub.max;
    hud.changed();
  }, link => hud.link(link));
  // Engine controls stay with the engine; while looking back, inspect reads recorded replies.
  send = control => (!following && control.cmd === 'inspect' ? timeline.handle(control) : socket(control));
  const review = (index: number) => {
    if (index >= timeline.last) return goLive();
    follow(false);
    timeline.seek(index);
  };
  const goLive = () => {
    follow(true);
    timeline.seek(timeline.last);
  };
  scrub.oninput = () => review(Number(scrub.value));
  $('back').onclick = () => review((following ? timeline.last : timeline.tick) - 1);
  $('fwd').onclick = () => !following && review(timeline.tick + 1);
  $('live').onclick = goLive;
  $('live').hidden = false;
  scrub.hidden = $('back').hidden = $('fwd').hidden = false;
  follow(true);
} else if (run === '') {
  const runs: string[] = await (await fetch('/runs')).json();
  const list = document.createElement('div');
  list.id = 'runs';
  list.append(...runs.map(r => Object.assign(document.createElement('a'), { href: `?replay=${r}`, textContent: r })));
  list.querySelectorAll('a').forEach(a => a.after(document.createElement('br')));
  document.querySelector('main')!.replaceWith(list);
} else {
  hud.link('replay');
  const replay = await Replay.load(world, run, shown);
  const seek = (index: number) => {
    replay.handle({ type: 'control', cmd: 'pause' }); // pausing repaints the slider: read it first
    replay.seek(index);
  };
  scrub.max = String(replay.last);
  scrub.oninput = () => seek(Number(scrub.value));
  $('back').onclick = () => seek(replay.tick - 1);
  $('fwd').onclick = () => seek(replay.tick + 1);
  scrub.hidden = $('back').hidden = $('fwd').hidden = false;
  send = control => replay.handle(control);
  select(null);
}

function select(agent: string | null) {
  scene.selected = agent;
  hud.select(agent);
}
scene.onSelect = select;
if (run !== '') {
  $('game').ondblclick = () => scene.fit();
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
