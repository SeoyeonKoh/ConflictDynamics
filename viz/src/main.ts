import Phaser from 'phaser';
import { connect } from './connection';
import { t, translate } from './i18n';
import { applyTheme, getSideHidden, setSideHidden } from './prefs';
import { Hud } from './hud';
import type { Control } from './messages';
import { Replay } from './replay';
import { OfficeScene } from './scene';
import { World } from './world';

// Live: `?ws=ws://127.0.0.1:<port>` for a run on another stream_port (default 8765).
// Replay: `?replay=<dir under runs/>`; a bare `?replay` lists the runs that have a journal.
const params = new URLSearchParams(location.search);
// The menu (index.html) picks what to view; without a choice there is nothing to show here.
if (!params.has('ws') && !params.has('live') && !params.has('replay')) location.replace('/');
applyTheme();
translate();
const run = params.get('replay');
const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const scrub = $<HTMLInputElement>('scrub');

const world = new World();
const scene = new OfficeScene(world, $('bubbles'));
scene.insets = () => {
  const bar = $('bar').getBoundingClientRect(), side = $('side')?.getBoundingClientRect();
  // From the panel's resting width, not its live box: while it slides, the map already eases
  // toward where it will end up.
  const css = getComputedStyle(document.documentElement);
  const gap = parseFloat(css.getPropertyValue('--gap')) || 16;
  const width = parseFloat(css.getPropertyValue(sideHidden() ? '--side-rail' : '--side-w')) || 360;
  return { top: bar.bottom + 8, right: side ? width + gap + 8 : 16, bottom: 56, left: 16 };
};
const sideHidden = () => document.body.classList.contains('side-hidden');
function showSide(show: boolean, slide = true) {
  if (show === !sideHidden() && slide) return;
  const before = scene.insets().right;
  document.body.classList.toggle('side-hidden', !show);
  setSideHidden(!show);
  const toggle = $('side-toggle');
  toggle.title = t(show ? 'hidePanel' : 'showPanel');
  toggle.setAttribute('aria-label', toggle.title);
  if (slide) scene.reframe(before, 250); // the map moves with the panel, on the same curve
}
showSide(!getSideHidden(), false);
$('side-toggle').onclick = () => showSide(sideHidden());
$('zoom-in').onclick = () => scene.zoomBy(1.25);
$('zoom-out').onclick = () => scene.zoomBy(1 / 1.25);
$('zoom-fit').onclick = () => scene.fit();
let send: (control: Control) => void = () => {};
const hud = new Hud(world, control => send(control), agent => select(agent));
// `&graph` opens the dependency graph, `&task=<id>` that task's evidence.
if (params.has('graph')) hud.openGraph();
if (params.get('task')) hud.showTask(params.get('task')!);
// `&tab=conversations` (or tasks, relations, timeline) opens that side tab.
if (params.get('tab')) document.querySelector<HTMLButtonElement>(`.tabs button[data-tab="${params.get('tab')}"]`)?.click();
const shown = (tick: number) => {
  scrub.value = String(tick);
  hud.changed();
};

// `?live=<id>` is a run conflict-server started: ask it where the run streams. A run that has
// ended opens as a replay instead.
const liveId = params.get('live');
let wsUrl = params.get('ws') ?? 'ws://127.0.0.1:8765';
if (liveId !== null) {
  // A run that is just starting is listed before it streams (port null): wait for its port.
  let found: { id: string; run: string; port: number | null } | undefined;
  for (let i = 0; i < 60; i++) {
    const runs: { id: string; run: string; port: number | null }[] = await (await fetch('/api/live')).json();
    found = runs.find(r => r.id === liveId);
    if (!found || found.port !== null) break;
    await new Promise(r => setTimeout(r, 500));
  }
  if (found) {
    wsUrl = `ws://127.0.0.1:${found.port}`;
    hud.runPath = found.run;
    const stop = $('stop-run');
    stop.hidden = false;
    stop.onclick = async () => {
      if (confirm(t('stopConfirm'))) await fetch(`/api/live/${encodeURIComponent(liveId)}/stop`, { method: 'POST' });
    };
  } else {
    const { runs: rows }: { runs: { run: string }[] } = await (await fetch('/api/runs')).json();
    const done = rows.find(r => r.run.startsWith(`${liveId}/`));
    location.replace(done ? `/view.html?replay=${done.run}` : '/');
  }
}

if (run === null) {
  // Live: every message is journaled; World follows the newest tick until the viewer looks back.
  const timeline = new Replay(world, shown);
  let following = true;
  const follow = (on: boolean) => {
    following = on;
    $('live').classList.toggle('on', on);
  };
  const socket = connect(wsUrl, message => {
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
  list.append(Object.assign(document.createElement('h2'), { textContent: 'Runs' }));
  list.append(...runs.map(r => Object.assign(document.createElement('a'), { href: `?replay=${r}`, textContent: r })));
  list.querySelectorAll('a').forEach(a => a.after(document.createElement('br')));
  document.querySelector('main')!.replaceWith(list);
} else {
  hud.link('replay');
  hud.runPath = run;
  const replay = await Replay.load(world, run, shown);
  if (!world.people.size) {  // journals before 2026-11 name people only by id
    const found: { id: string; name: string; title: string | null }[] = await fetch(`/api/runs/${run}/people`)
      .then(r => (r.ok ? r.json() : [])).catch(() => []);
    for (const p of found) world.people.set(p.id, { name: p.name, title: p.title });
  }
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
  if (params.get('tick')) seek(Number(params.get('tick'))); // `&tick=<n>` starts there
  if (params.get('interview')) { // `&interview=<agent>` opens an interview with them at that tick
    select(params.get('interview'));
    document.getElementById('inspect-interview')?.click();
  }
}

function select(agent: string | null) {
  scene.selected = agent;
  if (agent) showSide(true); // the inspect sheet lives in the panel
  hud.select(agent);
}
scene.onSelect = select;
if (run !== '') {
  // Canvas labels measure their font once: wait for Pretendard so they are not sized by a fallback.
  await Promise.all(['500 11px', '600 11px', '400 10px', 'bold 8px'].map(f =>
    document.fonts.load(`${f} "Pretendard Variable"`).catch(() => []))); // offline: system font
  $('game').ondblclick = () => scene.fit();
  new Phaser.Game({
    type: Phaser.AUTO,
    parent: 'game',
    transparent: true, // the page's soft wash shows around the map and through the glass
    // Keep the square pixel clusters crisp when the viewer zooms.
    pixelArt: true,
    antialias: false,
    scale: { mode: Phaser.Scale.RESIZE },
    scene,
  });
}
