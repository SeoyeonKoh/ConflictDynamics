/* The intro page. One recorded day (replay.js, written by build.py) plays on the stage while the
   deck scrolls over it. Each slide names the tick it shows (data-tick) and the part of the office
   the camera frames (data-focus, in map pixels); the top bar is the viewer's, driven by the slide. */
(() => {
  'use strict';
  const R = window.CD_REPLAY;
  const root = document.documentElement;
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
  const h = (tag, cls, text) => {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text != null) el.textContent = text;
    return el;
  };
  const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const served = location.protocol.startsWith('http');
  const save = (key, value) => { try { localStorage.setItem(key, value); } catch { /* this visit only */ } };
  const tr = (ko, en) => (root.dataset.lang === 'en' ? en : ko);
  const isDark = () => (root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches);
  const clock = t => {
    const m = 9 * 60 + R.tickMinutes * t;
    return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
  };
  const signed = v => `${v > 0 ? '+' : '−'}${Math.abs(v).toFixed(2)}`;

  // ---- people ----
  // What agents wrote and their Korean names stay as recorded; English labels are this page's.
  const EN = {
    'HDS-001': ['Kim Minjae', 'Integrated product lead'], 'HDS-002': ['Park Soyeon', 'Senior product planner'],
    'HDS-003': ['Lee Doyun', 'Product analyst'], 'HDS-005': ['Jung Taewoo', 'Software lead'],
    'HDS-006': ['Yoon Jiho', 'Backend engineer'], 'HDS-008': ['Oh Yujin', 'Web engineer'],
    'HDS-011': ['Song Arin', 'Product experience lead'], 'HDS-013': ['Moon Jian', 'Product designer'],
    'HDS-014': ['Seo Donghyun', 'Quality engineering lead'], 'HDS-015': ['Cho Eunbyeol', 'Test automation engineer'],
  };
  const DEPT = {
    'Product Strategy': ['PS', '#41a1cf'], 'Software Engineering': ['SE', '#d5604f'],
    'Product Experience': ['PE', '#3f8f63'], 'Quality Engineering': ['QE', '#c79524'],
  };
  const people = R.agents.map(([id, name, role, dept, disc, sprite]) => ({ id, name, role, dept, disc, sprite }));
  const idx = id => people.findIndex(p => p.id === id);
  const nameOf = i => tr(people[i].name, EN[people[i].id][0]);
  const roleOf = i => tr(people[i].role, EN[people[i].id][1]);

  // ---- sprites: characters-v5 sheets, ten frames in a row, widths per character ----
  const SPR_W = [36, 35, 36, 38, 34, 39, 37, 37, 41, 37, 39, 35, 35, 37, 37, 36, 37, 36, 38, 35];
  function sprite(n, clip = 'idle') {
    const el = h('i', 'spr');
    el.style.setProperty('--w', SPR_W[n]);
    el.style.backgroundImage = `url(../assets/characters-v5/agent-${n}.png)`;
    el.style.animationDelay = `${(-Math.random() * 2).toFixed(2)}s`; // nobody blinks in step
    el.dataset.clip = clip;
    return el;
  }
  // Engine action → clip, status dot and face, as viz/src/scene.ts has them.
  const CLIP = { move: 'walk', work: 'sit', eat: 'sit', talk: 'talk', message: 'talk', chat: 'talk', report: 'talk',
    assign: 'talk', request: 'talk', approve: 'talk', reject: 'talk' };
  const TALK = '#d9a12b', DARK = '#282834';
  const STATUS = { work: '#41a1cf', help: '#41a1cf', talk: TALK, chat: TALK, message: TALK, report: TALK, gossip: TALK,
    ask_help: TALK, approve: DARK, reject: DARK, assign: DARK, request: DARK, evaluate: DARK,
    eat: '#3f7f5a', rest: '#b4b8b4', idle: '#b4b8b4' };
  const FACE = { surprised: '😮', tired: '😩', anxious: '😰', annoyed: '😒', angry: '😠' };

  // ---- stage: the map from the recording ----
  const stage = $('#stage'), world = $('#world'), things = $('#things'), tags = $('#tags'), marks = $('#marks'), links = $('#links');
  const SVG = 'http://www.w3.org/2000/svg';
  const [W, H] = R.size;
  world.style.width = `${W}px`;
  world.style.height = `${H}px`;
  links.setAttribute('viewBox', `0 0 ${W} ${H}`);

  // Floors tile from the map origin, so rooms, corridor and door openings share one pattern.
  const FLOOR_X = { oak: 0, carpet: 130, ceramic: 260, stone: 390 };
  const rect = ([x, y, w, hh], attrs) => `<rect x="${x}" y="${y}" width="${w}" height="${hh}" ${attrs}/>`;
  $('#floors').setAttribute('viewBox', `0 0 ${W} ${H}`);
  $('#floors').innerHTML =
    `<defs>${Object.entries(FLOOR_X).map(([name, x]) =>
      `<pattern id="fl-${name}" width="128" height="128" patternUnits="userSpaceOnUse"><image href="../assets/office-v3/floors.png" x="${-x}" y="0" width="520" height="128" style="image-rendering:pixelated"/></pattern>`).join('')}</defs>` +
    rect([0, 0, W, H], 'fill="#e4e6e0"') +
    R.places.map(p => rect(p.slice(2, 6), `fill="url(#fl-${p[6]})"`)).join('') +
    R.corridors.map(c => rect(c, 'fill="url(#fl-stone)"')).join('') +
    R.zones.map(z => rect(z.slice(1), 'fill="none" stroke="#b8bcc6" stroke-opacity=".9" stroke-width="3"')).join('') +
    R.places.map(p => rect(p.slice(2, 6), 'fill="none" stroke="#5b5f58" stroke-width="3"')).join('') +
    R.doors.map(d => rect(d.slice(1), 'fill="url(#fl-stone)"')).join('');

  // Furniture sorts by its bottom edge; a desk-rear therefore covers whoever sits behind it.
  const FUR_X = { 'office-chair': 66, 'meeting-table': 96, whiteboard: 226, sofa: 300, 'coffee-table': 382, plant: 448,
    'filing-cabinet': 478, 'coffee-station': 504, 'water-cooler': 554, printer: 576, 'cafeteria-table': 618,
    'cafeteria-chair': 676, bookshelf: 702, door: 768, partition: 802 };
  for (const [frame, x, y, w, hh] of R.furniture) {
    const el = h('i', frame === 'desk-rear' ? 'fur rear' : 'fur');
    el.style.cssText = `left:${x}px;top:${y}px;width:${w}px;height:${hh}px;z-index:${y + hh};background-position:${-(FUR_X[frame] ?? 0)}px 0`;
    things.append(el);
    if (frame === 'door') continue;
    const shade = h('i', 'shade'), sw = w + 4, sh = Math.min(12, 5 + w / 10);
    shade.style.cssText = `left:${x + w / 2 - sw / 2}px;top:${y + hh - 2 - sh / 2}px;width:${sw}px;height:${sh}px`;
    things.append(shade);
  }
  const roomTags = R.places.map(p => {
    const el = h('span', 'tag room', p[1]);
    el.style.cssText = `left:${p[2] + 6}px;top:${p[3] + 6}px`;
    tags.append(el);
    return el;
  });
  for (const [name, x, y, , hh] of R.zones) {
    const el = h('span', 'tag zone', name);
    el.style.cssText = `left:${x + 4}px;top:${y + hh - 4}px`;
    tags.append(el);
  }

  // ---- actors ----
  const LOBBY = R.places.findIndex(p => p[0] === 'lobby');
  const actors = people.map((p, i) => {
    const el = h('div', 'actor'), tag = h('div', 'atag');
    const spr = sprite(p.sprite), dot = h('i', 'dot'), face = h('span', 'tag face'), name = h('span', 'tag name'), bubble = h('div', 'bubble');
    dot.hidden = bubble.hidden = true;
    el.append(h('i', 'shade'), spr, dot);
    tag.append(face, name, bubble);
    things.append(el);
    tags.append(tag);
    return { i, el, tag, spr, dot, face, name, bubble, x: 0, y: 0, place: LOBBY, moving: null, action: 'idle', expr: 'neutral', say: '', target: undefined };
  });
  function put(a, x, y) {
    a.x = x;
    a.y = y;
    a.el.style.transform = a.tag.style.transform = `translate(${x}px,${y}px)`;
    a.el.style.zIndex = String(Math.round(y));
  }
  function nowAt(a) { // mid-walk, where the sprite is drawn this instant
    if (!a.moving) return { x: a.x, y: a.y };
    const m = new DOMMatrixReadOnly(getComputedStyle(a.el).transform);
    return { x: m.m41, y: m.m42 };
  }
  const setClip = (a, clip) => { if (a.spr.dataset.clip !== clip) a.spr.dataset.clip = clip; };
  function say(a, text, cls = '') {
    a.bubble.className = `bubble ${cls}`;
    a.bubble.textContent = text;
    a.bubble.hidden = !text;
  }
  function settle(a) { // arrived: the clip, status dot and face of this tick's action
    setClip(a, CLIP[a.action] ?? 'idle');
    const colour = STATUS[a.action];
    a.dot.hidden = !colour;
    if (colour) a.dot.style.setProperty('--c', colour);
    a.face.textContent = FACE[a.expr] ?? '';
  }

  // The engine records end positions only. Between rooms people go door → main hall → door.
  const door = R.places.map(p => {
    const d = R.doors.find(entry => entry[0] === p[1]);
    return { x: d[1] + d[3] / 2, y: d[2] + d[4] / 2 };
  });
  const HALL = R.corridors[0][1] + R.corridors[0][3] / 2;
  const route = (from, to, a, b) =>
    (a === b ? [from, to] : [from, door[a], { x: door[a].x, y: HALL }, { x: door[b].x, y: HALL }, door[b], to]);
  function walk(a, pts, delay, done) {
    a.moving?.forEach(m => m.cancel());
    a.moving = null;
    const to = pts[pts.length - 1];
    const lens = pts.slice(1).map((p, i) => Math.hypot(p.x - pts[i].x, p.y - pts[i].y));
    const total = lens.reduce((sum, l) => sum + l, 0);
    put(a, to.x, to.y);
    if (still || total < 3) return done();
    let run = 0;
    const frames = pts.map((p, i) => {
      if (i) run += lens[i - 1];
      return { transform: `translate(${p.x}px,${p.y}px)`, offset: run / total };
    });
    const timing = { duration: clamp(total / 0.45, 420, 1700), delay, easing: 'linear', fill: 'backwards' };
    a.el.style.zIndex = '5000'; // a walker passes in front of the furniture
    setClip(a, 'walk');
    a.moving = [a.el.animate(frames, timing), a.tag.animate(frames, timing)];
    a.moving[0].onfinish = () => {
      a.moving = null;
      a.el.style.zIndex = String(Math.round(to.y));
      done();
    };
  }

  /** Where everyone stands at a tick: recorded seats, except a small talk gathers in a ring. */
  function layout(rows, sessions) {
    const spots = rows.map(r => ({ x: r[0], y: r[1] })), rings = [];
    for (const [kind, place, who] of sessions) {
      const here = who.filter(i => rows[i][4] === place);
      if (kind !== 'talk' || here.length < 2 || here.length > 5) continue;
      const p = R.places[place], r = 12 + 5 * here.length;
      const cx = clamp(here.reduce((s, i) => s + rows[i][0], 0) / here.length, p[2] + r + 20, p[2] + p[4] - r - 20);
      let cy = here.reduce((s, i) => s + rows[i][1], 0) / here.length;
      // Step clear of anyone seated where the ring would stand.
      if (rows.some((o, i) => o[4] === place && !here.includes(i) && Math.abs(o[0] - cx) < r + 30 && Math.abs(o[1] - cy) < 26)) cy += 46;
      cy = clamp(cy, p[3] + r + 56, p[3] + p[5] - r - 12);
      here.forEach((i, k) => {
        const angle = Math.PI + (2 * Math.PI * k) / here.length;
        spots[i] = { x: cx + r * Math.cos(angle), y: cy + r * 0.55 * Math.sin(angle) };
      });
      rings.push({ cx, cy, r });
    }
    return { spots, rings };
  }
  function noteLine(from, to) { // a message: the viewer's dashed blue line
    const path = document.createElementNS(SVG, 'path');
    path.setAttribute('class', 'note');
    path.setAttribute('d', `M${from.x},${from.y - 22} L${to.x},${to.y - 22}`);
    links.append(path);
    return path;
  }
  function setTick(t, stagger = 0) {
    const [, rows, sessions] = R.frames[t];
    const { spots, rings } = layout(rows, sessions);
    const count = R.places.map(() => 0);
    marks.replaceChildren();
    links.replaceChildren();
    actors.forEach((a, i) => {
      const row = rows[i], path = route(nowAt(a), spots[i], a.place, row[4]);
      count[row[4]] += 1;
      Object.assign(a, { place: row[4], action: row[2], expr: row[3], say: row[5] || '', target: row[6] });
      a.dot.hidden = true;
      a.face.textContent = '';
      say(a, '');
      a.tag.classList.remove('speaking');
      a.el.style.opacity = a.tag.style.opacity = '';
      walk(a, path, i * stagger, () => settle(a));
    });
    roomTags.forEach((el, i) => {
      el.textContent = `${R.places[i][1]} · ${count[i]}/${R.places[i][7]}`;
      el.classList.toggle('full', count[i] >= R.places[i][7]);
    });
    for (const { cx, cy, r } of rings) {
      const ring = h('i', 'ring');
      ring.style.cssText = `left:${cx}px;top:${cy - 2}px;width:${2 * r + 38}px;height:${r + 22}px`;
      marks.append(ring);
    }
    rows.forEach((row, i) => { if (row[2] === 'message' && row[6] !== undefined) noteLine(spots[i], spots[row[6]]); });
  }

  // ---- camera ----
  let cam = { x: 0, y: 0, s: 1 }, looking = [0, 0, W, H];
  function hole(slide) { // the part of the screen a slide leaves to the stage
    const el = $('.hole', slide);
    if (!el) return { x: 0, y: 0, w: innerWidth, h: innerHeight };
    const a = el.getBoundingClientRect(), b = slide.getBoundingClientRect();
    return { x: a.left - b.left, y: a.top - b.top, w: a.width, h: a.height };
  }
  function look(box, slide = slides[active]) {
    looking = box;
    const win = hole(slide);
    const s = clamp(Math.min(win.w / box[2], win.h / box[3]) * 0.92, 0.1, 2.2);
    cam = { s, x: win.x + (win.w - box[2] * s) / 2 - box[0] * s, y: win.y + (win.h - box[3] * s) / 2 - box[1] * s };
    world.style.transform = `translate(${cam.x.toFixed(1)}px,${cam.y.toFixed(1)}px) scale(${s.toFixed(4)})`;
    world.style.setProperty('--s', s.toFixed(4)); // labels divide by it to keep their size
    stage.classList.toggle('near', s >= 1.15);
    stage.classList.toggle('far', s < 0.72);
    stage.classList.toggle('tiny', s < 0.36);
  }

  // ---- deck and bar ----
  const deck = $('#deck'), slides = $$('.slide'), scrub = $('#scrub');
  const hooks = {}; // slide id → { enter, leave, lang }
  let active = -1, timers = [], dragging = false;
  const later = (fn, ms) => { const id = setTimeout(fn, ms); timers.push(id); return id; };
  const every = (fn, ms) => { const id = setInterval(fn, ms); timers.push(id); return id; };
  const clearTimers = () => { timers.forEach(id => { clearTimeout(id); clearInterval(id); }); timers = []; };
  const go = i => deck.scrollTo({ top: slides[clamp(i, 0, slides.length - 1)].offsetTop, behavior: still ? 'auto' : 'smooth' });

  let shown = 0, counting = 0;
  function paintClock(t) { // the viewer's own wording (hud.ts)
    shown = t;
    $('#clock').textContent = `Day 1 · tick ${Math.min(t, R.ticksPerDay - 1) + 1}/${R.ticksPerDay} · ${R.frames[t][0]}`;
    $('#time').textContent = clock(t);
  }
  function bar(i) {
    if (!dragging) scrub.value = String(i);
    const target = Number(slides[i].dataset.tick);
    clearInterval(counting);
    if (still || shown === target) return paintClock(target);
    counting = setInterval(() => { // the clock runs through the ticks in between
      paintClock(shown + Math.sign(target - shown));
      if (shown === target) clearInterval(counting);
    }, clamp(700 / Math.abs(target - shown), 20, 130));
  }
  function activate(i) {
    if (i === active) return;
    const before = slides[active], slide = slides[i], first = active < 0;
    clearTimers();
    if (before) {
      before.classList.remove('on');
      hooks[before.id]?.leave?.();
    }
    active = i;
    slide.classList.add('on');
    document.body.classList.toggle('veiled', 'veil' in slide.dataset);
    stage.classList.toggle('quiet', 'quiet' in slide.dataset); // a crowd: names on hover only
    select(null);
    $$('.pin, .float', tags).forEach(el => el.remove());
    setTick(Number(slide.dataset.tick), first ? 90 : 0);
    look(slide.dataset.focus.split(',').map(Number), slide);
    bar(i);
    try { if (location.hash !== `#${slide.id}`) history.replaceState(null, '', `#${slide.id}`); } catch { /* file:// in some browsers */ }
    hooks[slide.id]?.enter?.();
  }

  // Hovering or clicking someone on the map: the deck lies over the stage, so hit-test by hand.
  let hovered = null, selected = null;
  const offStage = e => e.target.closest('.card, .hero-head');
  function actorAt(e) {
    const x = (e.clientX - cam.x) / cam.s, y = (e.clientY - cam.y) / cam.s;
    let best = null, near = Math.max(22, 16 / cam.s);
    for (const a of actors) {
      const d = Math.hypot(a.x - x, a.y - 20 - y);
      if (d < near) { near = d; best = a; }
    }
    return best;
  }
  function select(a) {
    if (selected) {
      selected.el.classList.remove('sel');
      selected.tag.classList.remove('sel');
      selected.name.textContent = nameOf(selected.i);
    }
    selected = a;
    if (a) {
      a.el.classList.add('sel');
      a.tag.classList.add('sel');
      a.name.textContent = `${nameOf(a.i)} · ${roleOf(a.i)}`;
    }
    personButtons.forEach((b, i) => b.classList.toggle('on', a?.i === i));
  }
  deck.addEventListener('pointermove', e => {
    const a = offStage(e) ? null : actorAt(e);
    if (a === hovered) return;
    hovered?.tag.classList.remove('hover');
    hovered = a;
    a?.tag.classList.add('hover');
    deck.style.cursor = a ? 'pointer' : '';
  });
  deck.addEventListener('click', e => {
    if (offStage(e)) return;
    const a = actorAt(e);
    if (a || selected) select(a === selected ? null : a);
  });

  // ---- 09:00 arrival ----
  const title = $('h1');
  title.setAttribute('aria-label', title.textContent);
  title.replaceChildren(...[...title.textContent].map((ch, i) => {
    const letter = h('span', '', ch);
    letter.style.setProperty('--i', i);
    letter.setAttribute('aria-hidden', 'true');
    return letter;
  }));
  actors.forEach((a, i) => { // everyone starts at the front door, unseen
    put(a, 864 + ((i % 5) - 2) * 15, 112 + Math.floor(i / 5) * 16);
    a.el.style.opacity = a.tag.style.opacity = '0';
  });

  // Left on the opening slide, the recording keeps playing: arrival, the stand-up, back to desks.
  hooks.arrival = {
    enter() {
      if (still) return;
      let t = 0;
      every(() => {
        t = (t + 1) % 3;
        setTick(t);
        paintClock(t);
      }, 5600);
    },
  };

  // ---- 09:30 conditions: each lever is a scenario; the pin marks where it would bite ----
  const LEVERS = [
    { box: [30, 60, 460, 300], pin: [216, 150],
      pinKo: 'T06 API 계약이 늦어지면 T08 웹·모바일 구현이 기다립니다', pinEn: 'When T06 API contract slips, T08 Web & mobile build waits',
      ko: '선행 업무가 실패한 것이 모두에게 보일 때, 뒤 단계의 조율은 어떻게 달라지는가?',
      en: 'How does a transparent prerequisite failure alter downstream coordination?' },
    { box: [32, 32, 640, 416], pin: [352, 262],
      pinKo: '출시 마감이 앞당겨집니다', pinEn: 'The release deadline moves earlier',
      ko: '출시 마감이 앞당겨지면 업무량과 조율은 어떻게 달라지는가?',
      en: 'How does an earlier release deadline alter workload and coordination?' },
    { box: [1056, 32, 448, 416], pin: [1280, 180], hatch: 2,
      pinKo: '회의실을 한동안 쓸 수 없습니다', pinEn: 'The meeting room is unavailable for a while',
      ko: '회의실을 잠시 쓸 수 없게 되면 팀 사이 조율은 어떻게 달라지는가?',
      en: 'How does a temporary meeting-room loss alter cross-functional coordination?' },
    { box: [1030, 80, 320, 240], pin: [1176, 150],
      pinKo: '평가 권한은 김민재에게 있고, 승진 자리는 부족합니다', pinEn: 'Kim Minjae holds the evaluations, and promotion slots are scarce',
      ko: '승진 자리가 부족하면 근거와 공로를 둘러싼 대화는 어떻게 달라지는가?',
      en: 'How does promotion scarcity alter evidence and credit interactions?' },
  ];
  let leverAt = 0;
  function lever(n, timed) {
    leverAt = n;
    const L = LEVERS[n];
    $$('.lever').forEach((b, i) => {
      b.classList.toggle('on', i === n);
      b.classList.toggle('timed', i === n && timed);
    });
    $('#ask').textContent = tr(L.ko, L.en);
    $$('.pin', tags).forEach(el => el.remove());
    $$('.hatch', marks).forEach(el => el.remove());
    look(L.box);
    const pin = h('div', 'pin', tr(L.pinKo, L.pinEn));
    pin.style.cssText = `left:${L.pin[0]}px;top:${L.pin[1]}px`;
    tags.append(pin);
    if (L.hatch !== undefined) {
      const p = R.places[L.hatch], el = h('i', 'hatch');
      el.style.cssText = `left:${p[2]}px;top:${p[3]}px;width:${p[4]}px;height:${p[5]}px`;
      marks.append(el);
    }
  }
  $$('.lever').forEach((b, i) => b.addEventListener('click', () => { clearTimers(); lever(i, false); }));
  hooks.conditions = {
    enter() {
      lever(0, !still);
      if (!still) every(() => lever((leverAt + 1) % LEVERS.length, true), 5200);
    },
    lang: () => lever(leverAt, false),
  };

  // ---- 10:15 office and cast ----
  const ping = i => actors.forEach((a, k) => a.el.classList.toggle('ping', k === i));
  const personButtons = people.map((p, i) => {
    const b = h('button', 'person'), ava = h('span', 'ava');
    ava.append(sprite(p.sprite));
    b.style.setProperty('--dept', DEPT[p.dept][1]);
    b.append(ava, h('b'), h('small'));
    b.addEventListener('pointerenter', () => ping(i));
    b.addEventListener('pointerleave', () => ping(null));
    b.addEventListener('focus', () => ping(i));
    b.addEventListener('blur', () => ping(null));
    b.addEventListener('click', () => {
      const a = actors[i], on = selected !== a;
      placeButtons.forEach(x => x.classList.remove('on'));
      select(on ? a : null);
      look(on ? [a.x - 260, a.y - 200, 520, 360] : [0, 0, W, H]);
    });
    $('#cast').append(b);
    return b;
  });
  function light(i) {
    $$('.roomlight', marks).forEach(el => el.remove());
    if (i == null) return;
    const p = R.places[i], el = h('i', 'roomlight');
    el.style.cssText = `left:${p[2]}px;top:${p[3]}px;width:${p[4]}px;height:${p[5]}px`;
    marks.append(el);
  }
  const placeButtons = R.places.map((p, i) => {
    const b = h('button', '', `${p[1]} · ${p[7]}`);
    b.addEventListener('pointerenter', () => light(i));
    b.addEventListener('pointerleave', () => light(null));
    b.addEventListener('click', () => {
      const on = !b.classList.contains('on');
      placeButtons.forEach(x => x.classList.toggle('on', on && x === b));
      select(null);
      look(on ? [p[2] - 20, p[3] - 20, p[4] + 40, p[5] + 40] : [0, 0, W, H]);
    });
    $('#places').append(b);
    return b;
  });
  hooks.office = {
    leave() {
      placeButtons.forEach(b => b.classList.remove('on'));
      ping(null);
    },
  };

  // ---- 11:15 one tick: drive Oh Yujin by hand; verdicts quote the engine's own reasons ----
  const YUJIN = idx('HDS-008'), DOYUN = idx('HDS-003'), JIHO = idx('HDS-006');
  const OFFICE = R.places.findIndex(p => p[0] === 'office'), PANTRY = R.places.findIndex(p => p[0] === 'pantry');
  const FOCUS = R.places.findIndex(p => p[0] === 'focus_room');
  const spotOf = (t, i) => ({ x: R.frames[t][1][i][0], y: R.frames[t][1][i][1] });
  const VERDICT = {
    idle: ['', '행동을 고르면 여기에 환경의 판정이 나옵니다.', 'Pick an action and the environment\'s verdict appears here.'],
    work: ['ok', '<code>work</code> → T08 웹·모바일 구현. Office는 일할 수 있는 곳이라 받아들여집니다.',
      '<code>work</code> → T08 Web & mobile build. The Office is a place for work, so it is accepted.'],
    rest: ['ok', '<code>rest</code> @ pantry. 쉬는 곳에서 쉬면 스트레스가 더 내려갑니다.',
      '<code>rest</code> @ pantry. Resting in a break place brings stress down further.'],
    focus: ['no', '거절: <code>focus_room is full</code>. Focus Room은 2/2입니다. 이유를 읽고 다시 고릅니다.',
      'Rejected: <code>focus_room is full</code>. The Focus Room is at 2/2. She reads the reason and chooses again.'],
    talk: ['ok', '<code>talk</code> → 이도윤. 대화는 같은 방에 있는 사람과만 열립니다.',
      '<code>talk</code> → Lee Doyun. A talk opens only with someone in the same room.'],
    message: ['ok', '<code>message</code> → 윤지호. 메시지는 어디서든 보내고, 받는 사람의 다음 View에 들어갑니다.',
      '<code>message</code> → Yoon Jiho. A message goes from anywhere and lands in the recipient\'s next View.'],
  };
  let acted = 'idle';
  function verdict(kind) {
    acted = kind;
    const [cls, ko, en] = VERDICT[kind], el = $('#verdict');
    el.className = `verdict ${cls}`;
    el.innerHTML = `<span>${tr(ko, en)}</span>`;
  }
  function act(kind) {
    const a = actors[YUJIN], mate = actors[DOYUN], steps = $$('#loop li'), bad = kind === 'focus';
    clearTimers();
    links.replaceChildren();
    say(a, '');
    a.tag.classList.remove('speaking');
    mate.action = 'rest';
    settle(mate);
    $$('#acts button').forEach(b => b.classList.toggle('on', b.dataset.act === kind));
    steps.forEach(li => { li.className = ''; });
    $('#verdict').className = 'verdict';
    $('#verdict').textContent = '';
    steps.forEach((li, n) => later(() => li.classList.add(n >= 2 && bad ? 'bad' : 'on'), n * 260));
    later(() => verdict(kind), 620);
    const from = nowAt(a);
    const moveTo = (to, place, action, then) => {
      const path = route(from, to, a.place, place);
      a.place = place;
      a.dot.hidden = true;
      walk(a, path, 0, () => { a.action = action; settle(a); then?.(); });
    };
    if (kind === 'work') moveTo(spotOf(0, YUJIN), OFFICE, 'work');
    else if (kind === 'rest') moveTo(spotOf(9, YUJIN), PANTRY, 'rest');
    else if (kind === 'focus') { // to the Focus Room door and back
      const out = [from, door[a.place], { x: door[a.place].x, y: HALL }, { x: door[FOCUS].x, y: HALL }, { x: door[FOCUS].x, y: door[FOCUS].y - 8 }];
      const keep = a.action;
      a.dot.hidden = true;
      walk(a, [...out, ...out.slice(0, -1).reverse()], 0, () => { a.action = keep; settle(a); });
    } else if (kind === 'talk') {
      const m = spotOf(9, DOYUN);
      moveTo({ x: m.x + 30, y: m.y + 4 }, PANTRY, 'talk', () => {
        mate.action = 'talk';
        settle(mate);
        a.tag.classList.add('speaking');
        say(a, '아침에 웹 접근성 점검 끝냈어요. 작지만 눈에 보이는 진척이라 기분 좋네요.', 'show');
      });
    } else if (kind === 'message') {
      a.action = 'message';
      settle(a);
      noteLine(from, actors[JIHO]);
      say(a, `✉ → ${nameOf(JIHO)}: 지호님, 웹 구현에 필요한 API 계약이 아직 안 보여서요. 대략 언제 공유 가능할지 알려주세요.`, 'show note');
    }
  }
  $$('#acts button').forEach(b => b.addEventListener('click', () => act(b.dataset.act)));
  hooks.tick = {
    enter() {
      verdict('idle');
      $$('#acts button, #loop li').forEach(el => el.classList.remove('on', 'bad'));
      later(() => select(actors[YUJIN]), 900);
    },
    lang: () => verdict(acted),
  };

  // ---- 14:00 talk: the recorded lines, then the appraisals the engine logged for this tick ----
  function type(el, text, done, per = 20) {
    if (still) { el.textContent = text; return done?.(); }
    el.textContent = '';
    el.classList.add('typing');
    let n = 0;
    const id = every(() => {
      n += 1;
      el.textContent = text.slice(0, n);
      if (n < text.length) return;
      clearInterval(id);
      el.classList.remove('typing');
      done?.();
    }, per);
  }
  function float(a, text, positive, row = 0) {
    const el = h('span', `float ${positive ? 'pos' : 'neg'}`, text);
    el.style.cssText = `left:${a.x}px;top:${a.y - 58 - row * 17}px`; // people stand close: stack the labels
    tags.append(el);
  }
  hooks.talk = {
    enter() {
      const t = Number(slides[active].dataset.tick);
      const pair = [idx('HDS-001'), idx('HDS-005')].map(i => actors[i]);
      const speak = (k, then) => {
        const a = pair[k];
        pair.forEach(p => {
          p.tag.classList.toggle('speaking', p === a);
          if (p !== a) say(p, ''); // one bubble at a time: they stand close
        });
        a.bubble.className = 'bubble show';
        a.bubble.hidden = false;
        type(a.bubble, a.say, then);
      };
      later(() => speak(0, () => later(() => speak(1, () => later(() => {
        pair.forEach(p => p.tag.classList.remove('speaking'));
        let row = 0;
        for (const [tick, from, to, delta] of R.outcomes) {
          if (tick !== t || actors[from].place !== pair[0].place) continue;
          float(actors[from], `${nameOf(from)} → ${nameOf(to)} ${signed(delta)}`, delta > 0, pair.includes(actors[from]) ? row++ : 0);
        }
      }, 900)), 500)), still ? 0 : 1700);
      relPlay(!still);
      if (still) relShow(R.frames.length - 1, false);
    },
    leave: () => relPlay(false),
    lang: () => relShow(relT, false),
  };

  // The relations circle, laid out as the viewer's Relations tab lays it out (hud.ts).
  const relSvg = $('#rel svg'), relScrub = $('#rel-scrub');
  const N = people.length, RING = 112, NODE = 17, C = 160, POS = '#3f7f5a', NEG = '#b5483b';
  const angleOf = i => -Math.PI / 2 + (2 * Math.PI * i) / N;
  const point = (angle, radius) => ({ x: C + radius * Math.cos(angle), y: C + radius * Math.sin(angle) });
  const seat = people.map((_, i) => point(angleOf(i), RING));
  relSvg.innerHTML =
    `<defs>${[['pos', POS], ['neg', NEG]].map(([id, colour]) =>
      `<marker id="rel-${id}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="${colour}"/></marker>`).join('')}</defs>` +
    [...new Set(people.map(p => p.dept))].map(dept => {
      const members = people.flatMap((p, i) => (p.dept === dept ? [i] : []));
      const step = (2 * Math.PI) / N, ring = RING + NODE + 7;
      const from = angleOf(members[0]) - step * 0.4, to = angleOf(members[members.length - 1]) + step * 0.4;
      const p0 = point(from, ring), p1 = point(to, ring), mid = point((from + to) / 2, ring + 11);
      return `<path class="arc" d="M${p0.x},${p0.y} A${ring},${ring} 0 0 1 ${p1.x},${p1.y}"/><text class="arc-label" x="${mid.x}" y="${mid.y}">${DEPT[dept][0]}</text>`;
    }).join('') + '<g id="rel-edges"></g><g id="rel-deltas"></g>';
  const relNodes = people.map((p, i) => {
    const b = h('button', 'rel-node');
    b.style.cssText = `left:${(seat[i].x / 320) * 100}%;top:${(seat[i].y / 320) * 100}%`;
    b.append(sprite(p.sprite));
    const focus = on => () => { relFocus = on ? i : null; relShow(relT, false); };
    b.addEventListener('pointerenter', focus(true));
    b.addEventListener('pointerleave', focus(false));
    b.addEventListener('focus', focus(true));
    b.addEventListener('blur', focus(false));
    $('#rel').append(b);
    return b;
  });
  const edges = new Map();
  let relT = 0, relFocus = null, relTimer = 0, relHold = 0;
  function edge(a, b) { // each direction bends to its own side, so A→B and B→A stay apart
    const key = `${a}-${b}`;
    if (edges.has(key)) return edges.get(key);
    const p = seat[a], q = seat[b], dx = q.x - p.x, dy = q.y - p.y, len = Math.hypot(dx, dy), ux = dx / len, uy = dy / len;
    const cx = (p.x + q.x) / 2 - uy * 22, cy = (p.y + q.y) / 2 + ux * 22;
    const el = document.createElementNS(SVG, 'path');
    el.setAttribute('class', 'edge');
    el.setAttribute('d', `M${p.x + ux * NODE},${p.y + uy * NODE} Q${cx},${cy} ${q.x - ux * (NODE + 2)},${q.y - uy * (NODE + 2)}`);
    el.style.opacity = '0';
    $('#rel-edges').append(el);
    const entry = { el, cx, cy };
    edges.set(key, entry);
    return entry;
  }
  const WHY = { ignored: ['메시지가 무시됨', 'message ignored'], refused: ['요청이 거절됨', 'request refused'], '': ['대화 뒤 평가', 'appraisal after a talk'] };
  /** Relations as of tick t: every relation_delta so far, summed and clamped, as the viewer does. */
  function relShow(t, burst) {
    relT = t;
    const value = new Map();
    for (const [tick, a, b, delta] of R.outcomes) {
      if (tick <= t) value.set(`${a}-${b}`, clamp((value.get(`${a}-${b}`) ?? 0) + delta, -1, 1));
    }
    for (const [key, { el }] of edges) if (!value.has(key)) el.style.opacity = '0';
    for (const [key, v] of value) {
      const [a, b] = key.split('-').map(Number), { el } = edge(a, b);
      const mine = relFocus === null || a === relFocus || b === relFocus;
      el.setAttribute('stroke', v < 0 ? NEG : POS);
      el.setAttribute('marker-end', `url(#rel-${v < 0 ? 'neg' : 'pos'})`);
      el.style.strokeWidth = String(1 + 3 * Math.abs(v));
      el.style.opacity = String(Math.abs(v) < 0.02 ? 0 : mine ? 0.35 + 0.65 * Math.abs(v) : 0.08);
    }
    relNodes.forEach((b, i) => {
      b.classList.toggle('on', i === relFocus);
      b.title = `${nameOf(i)} · ${roleOf(i)}`;
    });
    $('#rel-when').textContent = `${clock(t)} · t${t}`;
    const upTo = R.outcomes.filter(o => o[0] <= t), last = upTo.length ? upTo[upTo.length - 1][0] : -1;
    const log = $('#rel-log');
    log.replaceChildren();
    if (last < 0) log.textContent = tr('아직 변화가 없습니다.', 'No change yet.');
    for (const [tick, a, b, delta, why] of upTo.filter(o => o[0] === last).slice(0, 3)) {
      const line = h('span');
      line.append(h('b', '', `${clock(tick)} ${nameOf(a)} → ${nameOf(b)} `), h('span', delta > 0 ? 'pos' : 'neg', signed(delta)), ` ${tr(...WHY[why])}`, h('br'));
      log.append(line);
    }
    if (!burst) return;
    for (const [tick, a, b, delta] of R.outcomes) {
      if (tick !== t) continue;
      const { cx, cy } = edge(a, b), label = document.createElementNS(SVG, 'text');
      label.setAttribute('class', 'delta');
      label.setAttribute('x', cx);
      label.setAttribute('y', cy);
      label.setAttribute('fill', delta > 0 ? POS : NEG);
      label.textContent = signed(delta);
      $('#rel-deltas').append(label);
      setTimeout(() => label.remove(), 2300);
      relNodes[a].classList.remove('bump');
      void relNodes[a].offsetWidth; // restart the bump
      relNodes[a].classList.add('bump');
    }
  }
  function relPlay(on) {
    clearInterval(relTimer);
    relTimer = on ? setInterval(() => {
      if (relT >= R.frames.length - 1 && (relHold += 1) < 6) return; // rest on the day's end
      relHold = 0;
      relShow(relT >= R.frames.length - 1 ? 0 : relT + 1, true);
      relScrub.value = String(relT);
    }, 520) : 0;
    $('#rel-play .i-play').toggleAttribute('hidden', on);
    $('#rel-play .i-pause').toggleAttribute('hidden', !on);
  }
  relScrub.max = String(R.frames.length - 1);
  relScrub.addEventListener('input', () => { relPlay(false); relShow(Number(relScrub.value), false); });
  $('#rel-play').addEventListener('click', () => relPlay(!relTimer));

  // ---- screenshots of the real app, in the theme on screen ----
  const shotSrc = name => `shots/${name}${isDark() ? '-dark' : ''}.webp`;
  function swap(img) {
    const src = shotSrc(img.dataset.shot);
    if (img.getAttribute('src') === src) return;
    const next = new Image();
    img.style.opacity = '0';
    next.onload = next.onerror = () => { img.src = src; img.style.opacity = '1'; };
    next.src = src;
  }
  const paintShots = () => $$('img[data-shot]').forEach(img => { img.src = shotSrc(img.dataset.shot); });
  const zoom = $('#zoom');
  const openZoom = src => { $('img', zoom).src = src; zoom.showModal(); };
  zoom.addEventListener('click', () => zoom.close());
  document.addEventListener('click', e => {
    const img = e.target.closest('img[data-zoom]'), button = e.target.closest('[data-zoom-shot]');
    if (img) openZoom(img.src);
    else if (button) openZoom(shotSrc(button.dataset.zoomShot));
  });

  // ---- 14:30 viewer: the five tabs of the side panel ----
  const TABS = ['tasks', 'relations', 'events', 'talk', 'plans'];
  let tabAt = 'tasks';
  function tab(name) {
    tabAt = name;
    $$('#viewer-tabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === name));
    $$('#viewer-cap [data-cap]').forEach(p => { p.hidden = p.dataset.cap !== name; });
    $('#viewer-img').dataset.shot = `view-${name}`;
    swap($('#viewer-img'));
  }
  // Served by the app, the real viewer opens over the page, on this same recording.
  const liveBox = $('#live');
  $('#viewer-live').addEventListener('click', () => {
    const frame = h('iframe');
    frame.title = 'Conflict Dynamics viewer';
    frame.src = $('#live-tab').href;
    $('#live-frame').replaceChildren(frame);
    liveBox.showModal();
  });
  $('#live-close').addEventListener('click', () => liveBox.close());
  liveBox.addEventListener('close', () => $('#live-frame').replaceChildren());
  $$('#viewer-tabs button').forEach(b => b.addEventListener('click', () => { clearTimers(); tab(b.dataset.tab); }));
  $('#viewer-zoom').addEventListener('click', () => openZoom($('#viewer-img').src));
  hooks.viewer = {
    enter() { if (!still) every(() => tab(TABS[(TABS.indexOf(tabAt) + 1) % TABS.length]), 4200); },
  };

  // ---- 14:45 tasks: three marks on the graph ----
  let spotAt = 0;
  const spot = n => { spotAt = n; $$('[data-spot]').forEach(el => el.classList.toggle('on', Number(el.dataset.spot) === n)); };
  $$('[data-spot]').forEach(el => {
    const pick = () => { clearTimers(); spot(Number(el.dataset.spot)); };
    el.addEventListener('pointerenter', pick);
    el.addEventListener('focus', pick);
    el.addEventListener('click', pick);
  });
  hooks.tasks = { enter() { spot(0); if (!still) every(() => spot((spotAt + 1) % 3), 3200); } };

  // ---- 15:00 interview: a saved interview from this run, typed out ----
  const IV = {
    who: idx('HDS-005'),
    q: '방금 오유진 님 작업을 왜 돌려보내셨어요?',
    a: '제가 기억하기로는 검증이 끝나기 전엔 분류를 시작하지 않고, 심각도 기준과 개발자 3명 투입 조건만 정리해 두겠습니다. / 선행 작업 완료 전이라 진척은 내지 않고, 1% 시작과 실패율 2% 초과 시 중단 기준을 확인하겠습니다.',
    qEn: 'Why did you just send Oh Yujin\'s work back?',
    aEn: 'As I remember it, I will not start triage before verification ends; I will only set down the severity criteria and the condition of three developers. / The prerequisite is not done, so I am making no progress; I will confirm the 1% start and the stop rule above a 2% failure rate.',
  };
  $('#chat-ava').append(sprite(people[IV.who].sprite, 'talk'));
  function interview() {
    const a = actors[IV.who];
    clearTimers();
    for (const id of ['chat-q', 'chat-qg', 'chat-a', 'chat-ag']) $(`#${id}`).textContent = '';
    select(a);
    later(() => type($('#chat-q'), IV.q, () => {
      $('#chat-qg').textContent = IV.qEn;
      later(() => {
        setClip(a, 'talk');
        type($('#chat-a'), IV.a, () => {
          $('#chat-ag').textContent = IV.aEn;
          settle(a);
        }, 16);
      }, 600);
    }), still ? 0 : 1100);
  }
  $('#chat-replay').addEventListener('click', interview);
  hooks.interview = { enter: interview };

  // ---- 16:00 create: the generator's own four steps ----
  hooks.create = {
    enter() {
      const steps = $$('#flow li:not(.sep)');
      let n = 0;
      const paint = () => steps.forEach((li, i) => li.classList.toggle('on', i <= n));
      paint();
      if (!still) every(() => { n = (n + 1) % (steps.length + 1); paint(); }, 950);
      else { n = steps.length; paint(); }
    },
  };

  // ---- 17:15 leaving: out through the lobby, then gone, as the viewer fades them ----
  hooks.leave = {
    enter() { if (!still) later(() => actors.forEach(a => { a.el.style.opacity = a.tag.style.opacity = '0'; }), 4600); },
  };
  $$('[data-copy]').forEach(b => b.addEventListener('click', async () => {
    const label = b.innerHTML;
    let ok = true;
    try { await navigator.clipboard.writeText(b.dataset.copy); } catch {
      ok = false; // no clipboard here: select the command so the viewer can copy it
      const range = document.createRange();
      range.selectNodeContents($('code', b.parentElement));
      getSelection().removeAllRanges();
      getSelection().addRange(range);
    }
    b.textContent = ok ? tr('복사됨', 'Copied') : tr('선택됨', 'Selected');
    setTimeout(() => { b.innerHTML = label; }, 1400);
  }));

  // ---- language, theme, labels ----
  function paintLang() {
    const lang = root.dataset.lang;
    $$('[data-set-lang]').forEach(b => b.classList.toggle('on', b.dataset.setLang === lang));
    document.title = tr('Conflict Dynamics 소개', 'Conflict Dynamics Intro');
    actors.forEach(a => { a.name.textContent = a === selected ? `${nameOf(a.i)} · ${roleOf(a.i)}` : nameOf(a.i); });
    personButtons.forEach((b, i) => {
      b.children[1].textContent = nameOf(i);
      b.children[2].textContent = roleOf(i);
    });
    $('#chat-name').textContent = nameOf(IV.who);
    $('#chat-role').textContent = roleOf(IV.who);
    const label = { back: ['이전', 'Previous'], fwd: ['다음', 'Next'], play: ['자동으로 넘기기', 'Advance automatically'],
      theme: ['테마 바꾸기', 'Switch theme'], 'to-menu': served ? ['메인', 'Main menu'] : ['처음으로', 'Back to the start'] };
    for (const [id, words] of Object.entries(label)) {
      $(`#${id}`).title = tr(...words);
      $(`#${id}`).setAttribute('aria-label', tr(...words));
    }
    relShow(relT, false);
    hooks[slides[active]?.id]?.lang?.();
  }
  $$('[data-set-lang]').forEach(b => b.addEventListener('click', () => {
    root.dataset.lang = root.lang = b.dataset.setLang;
    save('cd.lang', b.dataset.setLang);
    paintLang();
  }));
  $('#theme').addEventListener('click', () => {
    root.dataset.theme = isDark() ? 'light' : 'dark';
    save('cd.theme', root.dataset.theme);
  });
  new MutationObserver(paintShots).observe(root, { attributes: true, attributeFilter: ['data-theme'] });
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', paintShots);

  // ---- transport ----
  let playing = 0;
  function setPlaying(on) {
    clearInterval(playing);
    playing = on ? setInterval(() => (active >= slides.length - 1 ? setPlaying(false) : go(active + 1)), 9000 / Number($('#speed').value)) : 0;
    $('#play').setAttribute('aria-pressed', String(on));
    $('#play .i-play').toggleAttribute('hidden', on);
    $('#play .i-pause').toggleAttribute('hidden', !on);
  }
  $('#play').addEventListener('click', () => setPlaying(!playing));
  $('#speed').addEventListener('change', () => { if (playing) setPlaying(true); });
  $('#back').addEventListener('click', () => go(active - 1));
  $('#fwd').addEventListener('click', () => go(active + 1));
  scrub.max = String(slides.length - 1);
  scrub.addEventListener('pointerdown', () => { dragging = true; });
  addEventListener('pointerup', () => { dragging = false; });
  scrub.addEventListener('input', () => go(Number(scrub.value)));
  $$('[data-go]').forEach(b => b.addEventListener('click', () => go(b.dataset.go === 'next' ? active + 1 : 0)));
  $('#to-menu').addEventListener('click', e => {
    if ($('#to-menu').getAttribute('href').startsWith('#')) { e.preventDefault(); go(0); }
  });
  addEventListener('keydown', e => {
    const on = selector => e.target.closest?.(selector);
    if (e.metaKey || e.ctrlKey || e.altKey || zoom.open || liveBox.open || on('input, select, textarea')) return;
    const step = { ArrowDown: 1, PageDown: 1, ArrowRight: 1, ' ': 1, ArrowUp: -1, PageUp: -1, ArrowLeft: -1 }[e.key];
    if (e.key === ' ' && on('button, a')) return; // space presses the focused control
    if (step) { e.preventDefault(); go(active + step); }
    else if (e.key === 'Home') go(0);
    else if (e.key === 'End') go(slides.length - 1);
  });
  addEventListener('resize', () => { if (active >= 0) look(looking); });

  // Served by the app (conflict-server or vite): link into it, and offer the real viewer inline.
  if (served) {
    fetch('../api/runs').then(r => (r.ok ? r.json() : Promise.reject(new Error('no api')))).then(data => {
      const rows = data.runs ?? data;
      $('#goes').hidden = false;
      $('#to-menu').href = '../';
      paintLang();
      const run = (rows.find(r => r.run.startsWith(`${R.run}/`)) ?? rows.find(r => r.status === 'completed'))?.run;
      if (!run) return;
      $('#live-tab').href = `../view.html?replay=${run}&tick=14`;
      $('#viewer-live').hidden = false;
    }).catch(() => { /* opened as a plain file, or the server is down: the page stands alone */ });
  }

  // ---- start ----
  paintShots();
  paintLang();
  const hashed = slides.findIndex(s => `#${s.id}` === location.hash);
  if (hashed > 0) {
    deck.style.scrollBehavior = 'auto';
    deck.scrollTop = slides[hashed].offsetTop;
    deck.style.scrollBehavior = '';
  }
  const seen = new IntersectionObserver(entries => {
    for (const e of entries) if (e.intersectionRatio >= 0.6) activate(slides.indexOf(e.target));
  }, { root: deck, threshold: 0.6 });
  slides.forEach(s => seen.observe(s));
})();
