import Phaser from 'phaser';
import type { Frame, Hello } from './messages';
import type { World } from './world';
import { props, Walkways, type Point, type TiledObject } from './walkways';

const ASSETS = '/assets/';
// Emoji text until the Twemoji sheet (plan §1-13); the engine sends labels, never glyphs.
const FACE: Record<string, string> = {
  neutral: '😐', pleased: '🙂', amused: '😄', surprised: '😮',
  tired: '😩', anxious: '😰', annoyed: '😒', angry: '😠',
};
// Engine action → character clip. Anything unlisted (rest, idle) stands idle.
const CLIP: Record<string, string> = {
  move: 'walk', work: 'sit', eat: 'sit',
  talk: 'talk', message: 'talk', chat: 'talk', report: 'talk',
  assign: 'talk', request: 'talk', approve: 'talk', reject: 'talk',
};
const WALK_SPEED = 120; // world px per second when ticks leave enough time
const TALK = 0xd9a12b;
const NOTE = 0x41a1cf;
// A dot over each head says what the agent is doing; walking needs none (the walk shows it).
const STATUS: Record<string, number> = {
  work: 0x41a1cf, help: 0x41a1cf,
  talk: TALK, chat: TALK, message: TALK, report: TALK, gossip: TALK, ask_help: TALK,
  approve: 0x282834, reject: 0x282834, assign: 0x282834, request: 0x282834, evaluate: 0x282834,
  eat: 0x3f7f5a, rest: 0xb4b8b4, idle: 0xb4b8b4,
};
// Calm faces are the norm in an office; only the others are worth a glyph over the head.
const CALM = new Set(['neutral', 'pleased', 'amused']);
const GATHER_MAX = 5; // larger talks keep their seats
const BUBBLES_KEPT = 3; // speech bubbles left on screen within one tick
const NAMES_FROM_ZOOM = 1.25; // closer than this every name shows; farther, only the ones in focus
interface CharacterManifest {
  animations: Record<string, { frames: string[]; durations: number[] }>;
  characters: { id: string; image: string; atlas: string; displayHeight: number;
    data: { frames: Record<string, { sourceSize: { h: number } }> } }[];
}
interface Actor {
  sprite: Phaser.GameObjects.Sprite;
  face: Phaser.GameObjects.Text;
  name: Phaser.GameObjects.Text;
  bubble: HTMLDivElement;
  action: string;
  target: Point | null; // where the latest frame puts the agent
  clip: string; // what to play once there
  walk: Phaser.Tweens.Tween | null;
}

/** Draws the office from hello.map_data and follows World's latest frame. */
export class OfficeScene extends Phaser.Scene {
  onSelect: (agent: string) => void = () => {};
  selected: string | null = null;
  private built: Hello | null = null;
  private shown: Frame | null = null;
  private ready = false;
  private eventCursor = 0;
  private seenEvents: unknown[] | null = null; // World replaces its list on hello (reconnect, replay jump)
  private actors = new Map<string, Actor>();
  private rooms = new Map<string, Phaser.GameObjects.Text>();
  private labels: Phaser.GameObjects.Text[] = []; // room and zone names, kept at one screen size
  private hovered: string | null = null;
  private mapObjects: Phaser.GameObjects.GameObject[] = [];
  private links!: Phaser.GameObjects.Graphics;
  private marks!: Phaser.GameObjects.Graphics; // on the floor, under the characters
  private notes: Phaser.GameObjects.Text[] = []; // this tick's envelopes in flight
  private lineTimers: Phaser.Time.TimerEvent[] = [];
  private areas = new Map<string, { x: number; y: number; width: number; height: number }>();
  private manifest!: CharacterManifest;
  private size = { w: 960, h: 640 };
  private fitted = true; // false once the viewer zooms or pans; resize then leaves the view alone
  /** Screen margins covered by floating panels; fitting centres the map in what is left. */
  insets = () => ({ top: 0, right: 0, bottom: 0, left: 0 });
  private walkways!: Walkways;
  private tickMs = 1000; // smoothed time between consecutive live frames
  private frameAt = 0;

  constructor(private world: World, private bubbles: HTMLElement) {
    super('office');
  }

  preload() {
    this.load.json('characters', ASSETS + 'characters-v4/manifest.json');
    this.load.atlas('furniture', ASSETS + 'office-v2/furniture.png', ASSETS + 'office-v2/furniture.atlas.json');
    this.load.atlas('floors', ASSETS + 'office-v2/floors.png', ASSETS + 'office-v2/floors.atlas.json');
    // Seen from the visitor side: the worker sits behind it facing us (front-facing sprites).
    this.load.atlas('desk-rear', ASSETS + 'office-v2/desk-rear.png', ASSETS + 'office-v2/desk-rear.atlas.json');
  }

  create() {
    this.manifest = this.cache.json.get('characters');
    this.links = this.add.graphics().setDepth(1e6);
    this.marks = this.add.graphics().setDepth(1);
    this.scale.on('resize', () => this.fitted && this.fit());
    this.input.on('wheel', (pointer: Phaser.Input.Pointer, _: unknown, __: number, dy: number) => {
      this.zoomAt(pointer.x, pointer.y, dy > 0 ? 1 / 1.15 : 1.15);
    });
    this.input.on('pointermove', (pointer: Phaser.Input.Pointer) => {
      if (!pointer.isDown) return;
      const cam = this.cameras.main;
      cam.scrollX -= (pointer.x - pointer.prevPosition.x) / cam.zoom;
      cam.scrollY -= (pointer.y - pointer.prevPosition.y) / cam.zoom;
      this.fitted = false;
    });
  }

  update() {
    const hello = this.world.hello;
    if (hello && hello !== this.built) this.build(hello);
    if (!this.ready) return;
    const frame = this.world.frame;
    if (frame && frame !== this.shown) this.show(frame);
    this.floatOutcomes();
    this.follow();
  }

  private build(hello: Hello) {
    this.built = hello;
    this.ready = false;
    this.shown = null;
    for (const o of this.mapObjects) o.destroy();
    this.mapObjects = [];
    for (const actor of this.actors.values()) {
      actor.walk?.remove();
      actor.sprite.destroy(); actor.face.destroy(); actor.name.destroy(); actor.bubble.remove();
    }
    this.actors.clear();
    this.rooms.clear();
    this.labels = [];
    this.drawMap(hello.map_data);
    this.walkways = new Walkways(hello.map_data);
    // Only the appearances this run uses are loaded.
    for (const agent of hello.agents) {
      const c = this.character(agent.sprite);
      if (!this.textures.exists(c.id)) this.load.atlas(c.id, ASSETS + 'characters-v4/' + c.image, ASSETS + 'characters-v4/' + c.atlas);
    }
    this.load.once(Phaser.Loader.Events.COMPLETE, () => {
      if (hello !== this.built) return;
      for (const agent of hello.agents) this.addActor(agent.id, agent.name, agent.sprite);
      this.ready = true;
    });
    this.load.start();
  }

  private drawMap(map: Record<string, unknown>) {
    const tile = map.tilewidth as number;
    const floorScale = 96 / this.textures.getFrame('floors', 'oak').width;
    this.size = { w: (map.width as number) * tile, h: (map.height as number) * tile };
    const add = <T extends Phaser.GameObjects.GameObject>(o: T) => (this.mapObjects.push(o), o);
    add(this.add.rectangle(0, 0, this.size.w, this.size.h, 0xe4e6e0).setOrigin(0).setDepth(-3));
    for (const layer of map.layers as { objects?: TiledObject[] }[]) {
      for (const o of layer.objects ?? []) {
        const p = props(o);
        if (typeof p.place_id === 'string') {
          add(this.add.tileSprite(o.x, o.y, o.width, o.height, 'floors', (p.floor as string) ?? 'oak')
            .setOrigin(0).setTileScale(floorScale).setDepth(-2));
          add(this.add.rectangle(o.x, o.y, o.width, o.height).setOrigin(0).setStrokeStyle(3, 0x5b5f58).setDepth(-1));
          const label = add(this.add.text(o.x + 6, o.y + 6, o.name, {
            fontFamily: 'Inter, system-ui, sans-serif', fontSize: '11px', fontStyle: '600', color: '#2c2c2c',
            backgroundColor: '#ffffffeb', padding: { x: 6, y: 3 },
          }).setResolution(4).setDepth(1e6));
          this.labels.push(label);
          this.rooms.set(p.place_id, label);
          this.areas.set(p.place_id, o);
        } else if (typeof p.zone === 'string') {
          // A department's corner of a room: a low partition around it and its name.
          add(this.add.rectangle(o.x, o.y, o.width, o.height).setOrigin(0)
            .setStrokeStyle(3, 0xb8bcc6, 0.9).setDepth(-1.5));
          this.labels.push(add(this.add.text(o.x + 4, o.y + o.height - 4, p.zone, {
            fontFamily: 'Inter, system-ui, sans-serif', fontSize: '10px', color: '#646464', backgroundColor: '#f9faf7e6',
            padding: { x: 5, y: 2 },
          }).setOrigin(0, 1).setResolution(4).setDepth(1e6 - 1)));
        } else if (p.walkway === 'corridor') {
          add(this.add.tileSprite(o.x, o.y, o.width, o.height, 'floors', 'stone')
            .setOrigin(0).setTileScale(floorScale).setDepth(-2));
        } else if (p.walkway === 'door') {
          // Drawn over the walls: the opening is where the wall is missing.
          add(this.add.tileSprite(o.x, o.y, o.width, o.height, 'floors', 'stone')
            .setOrigin(0).setTileScale(floorScale).setDepth(-0.5));
        } else if (typeof p.frame === 'string') {
          // Depth by bottom edge: characters sort in front of or behind furniture by foot y.
          // A frame is in the furniture sheet or is a standalone atlas of the same name.
          const sheet = this.textures.get('furniture').has(p.frame) ? 'furniture' : p.frame;
          add(this.add.image(o.x, o.y, sheet, p.frame).setOrigin(0).setDisplaySize(o.width, o.height)
            .setDepth(o.y + o.height));
        }
      }
    }
    this.fit();
  }

  private character(id: string) {
    const c = this.manifest.characters.find(entry => entry.id === id);
    if (!c) throw new Error(`Unknown character: ${id}`);
    return c;
  }

  private addActor(id: string, label: string, appearance: string) {
    const c = this.character(appearance);
    for (const [motion, clip] of Object.entries(this.manifest.animations)) {
      const key = `${c.id}:${motion}`;
      if (this.anims.exists(key)) continue;
      this.anims.create({
        key, repeat: -1,
        frames: clip.frames.map((frame, i) => ({ key: c.id, frame, duration: clip.durations[i] })),
      });
    }
    const sprite = this.add.sprite(-100, -100, c.id, 'idle-0').setOrigin(0.5, 1)
      .setScale(c.displayHeight / c.data.frames['idle-0'].sourceSize.h)
      .setInteractive({ useHandCursor: true });
    sprite.on('pointerdown', () => this.onSelect(id));
    sprite.on('pointerover', () => { this.hovered = id; });
    sprite.on('pointerout', () => { if (this.hovered === id) this.hovered = null; });
    const face = this.add.text(0, 0, '', { fontSize: '14px' }).setOrigin(0, 0.5).setResolution(4);
    const name = this.add.text(0, 0, label, {
      fontFamily: 'Inter, system-ui, sans-serif', fontSize: '11px', fontStyle: '500', color: '#2c2c2c',
      backgroundColor: '#ffffffeb', padding: { x: 5, y: 2 },
    }).setOrigin(0.5, 0).setResolution(4);
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.hidden = true;
    this.bubbles.append(bubble);
    this.actors.set(id, { sprite, face, name, bubble, action: 'idle', target: null, clip: `${c.id}:idle`, walk: null });
  }

  private show(frame: Frame) {
    // Live ticks walk; a history burst, a skipped stretch or a reconnect snaps to the state.
    const live = this.shown !== null && frame.tick - this.shown.tick <= 2;
    const now = this.time.now;
    if (live && frame.tick === this.shown!.tick + 1) this.tickMs = 0.7 * this.tickMs + 0.3 * (now - this.frameAt);
    this.frameAt = now;
    this.shown = frame;
    const gather = this.gatherings(frame);
    for (const a of frame.agents) {
      const actor = this.actors.get(a.id);
      if (!actor) continue;
      actor.clip = `${actor.sprite.texture.key}:${CLIP[a.action] ?? 'idle'}`;
      actor.action = a.action;
      const spot = gather.get(a.id) ?? { x: a.x, y: a.y };
      const moved = !actor.target || actor.target.x !== spot.x || actor.target.y !== spot.y;
      actor.target = spot;
      // Gone home early: a faint figure in the lobby; otherwise visible until closing.
      if (a.action === 'leave') this.fade(actor, 0.25);
      else if (frame.phase !== 'closing') this.fade(actor, 1);
      if (moved && live) this.walk(actor);
      else if (moved) this.arrive(actor);
      else if (!actor.walk) {
        actor.sprite.play(actor.clip, true);
        if (frame.phase === 'closing') this.fade(actor, 0);
      }
      actor.face.setText(CALM.has(a.expression) ? '' : (FACE[a.expression] ?? a.expression));
      if (!frame.lines) {
        // Journals from before `lines`: each speaker's last utterance only.
        const note = a.action === 'message' || a.action === 'report';
        this.say(actor, a.bubble && note && a.target ? `✉ → ${a.target}: ${a.bubble}` : a.bubble, note);
      } else {
        this.say(actor, undefined, false);
      }
    }
    this.sendNotes(frame);
    this.playLines(frame);
    for (const [place, label] of this.rooms) {
      const resource = this.world.resources.get(place);
      const name = label.text.split(' · ')[0];
      label.setText(resource ? `${name} · ${resource.holders.length}/${resource.capacity}` : name);
      label.setColor(resource && resource.holders.length >= resource.capacity ? '#b5483b' : '#2c2c2c');
    }
  }

  private say(actor: Actor, text: string | undefined, note: boolean) {
    // The text sits in its own span: line clamping on the padded bubble lets a third line peek.
    const span = document.createElement('span');
    span.className = 'text';
    span.textContent = text ?? '';
    actor.bubble.replaceChildren(span);
    actor.bubble.title = text ?? ''; // the bubble shows two lines; the whole text on hover
    actor.bubble.classList.toggle('note', note);
    actor.bubble.hidden = !text;
  }

  /** Utterances appear in the order they were said, spread over the tick; the current speaker's
   * bubble is highlighted and earlier ones dim. DM threads are `dm:<a>:<b>:<n>`. */
  private playLines(frame: Frame) {
    for (const timer of this.lineTimers) timer.remove();
    this.lineTimers = [];
    for (const actor of this.actors.values()) actor.bubble.classList.remove('speaking');
    const lines = frame.lines ?? [];
    const gap = Phaser.Math.Clamp((this.tickMs * 0.85) / Math.max(1, lines.length), 150, 2500);
    let recent: Actor[] = [];
    lines.forEach((line, i) => {
      this.lineTimers.push(this.time.delayedCall(i * gap, () => {
        const actor = this.actors.get(line.speaker);
        if (!actor) return;
        const [kind, a, b] = line.session.split(':');
        const dm = kind === 'dm';
        this.say(actor, dm ? `✉ → ${line.speaker === a ? b : a}: ${line.text}` : line.text, dm);
        for (const other of this.actors.values()) other.bubble.classList.toggle('speaking', other === actor);
        // Only the last few speakers keep a bubble, so a table-wide talk does not stack a wall.
        recent = [...recent.filter(r => r !== actor), actor];
        while (recent.length > BUBBLES_KEPT) this.say(recent.shift()!, undefined, false);
      }));
    });
  }

  /** Talk members leave their seats and stand in a ring around the group's centre, in-room. A
   * table-wide conversation (more than GATHER_MAX people) stays seated: a ring of twenty is a heap. */
  private gatherings(frame: Frame) {
    const spots = new Map<string, Point>();
    const at = new Map(frame.agents.map(a => [a.id, a]));
    for (const session of frame.sessions) {
      if (session.kind !== 'talk') continue;
      const members = session.participants.map(p => at.get(p)).filter(a => a !== undefined);
      if (members.length < 2 || members.length > GATHER_MAX) continue;
      const cx = members.reduce((s, a) => s + a.x, 0) / members.length;
      const cy = members.reduce((s, a) => s + a.y, 0) / members.length;
      const room = this.areas.get(members[0].place);
      const r = 14 + 5 * members.length;
      members.forEach((a, i) => {
        const angle = (i / members.length) * Math.PI * 2 + Math.PI / 2;
        let x = cx + Math.cos(angle) * r, y = cy + Math.sin(angle) * r * 0.6;
        if (room) {
          x = Phaser.Math.Clamp(x, room.x + 12, room.x + room.width - 12);
          y = Phaser.Math.Clamp(y, room.y + 44, room.y + room.height - 4);
        }
        spots.set(a.id, { x, y });
      });
    }
    return spots;
  }

  /** An envelope flies from sender to recipient for each message or report this tick. */
  private sendNotes(frame: Frame) {
    for (const n of this.notes) n.destroy();
    this.notes = [];
    for (const a of frame.agents) {
      const from = this.actors.get(a.id), to = a.target && this.actors.get(a.target);
      if ((a.action !== 'message' && a.action !== 'report') || !from || !to) continue;
      const icon = this.add.text(from.sprite.x, from.sprite.y - 30, '✉', { fontSize: '12px' })
        .setOrigin(0.5).setResolution(4).setDepth(1e6);
      this.notes.push(icon);
      // Both ends are read every frame: sender and recipient may be walking this very tick.
      this.tweens.addCounter({
        from: 0, to: 1, duration: Math.max(400, this.tickMs * 0.7), ease: 'Sine.easeInOut',
        onUpdate: tween => {
          const t = tween.getValue() ?? 0;
          if (icon.active) icon.setPosition(
            from.sprite.x + (to.sprite.x - from.sprite.x) * t,
            from.sprite.y - 30 + (to.sprite.y - from.sprite.y) * t,
          );
        },
        onComplete: () => icon.destroy(),
      });
    }
  }

  /** Walks the route at constant speed, fast enough to arrive before the next tick is due. */
  private walk(actor: Actor) {
    actor.walk?.remove();
    const { sprite } = actor;
    const path = this.walkways.route({ x: sprite.x, y: sprite.y }, actor.target!);
    const legs = path.slice(1).map((p, i) => Math.hypot(p.x - path[i].x, p.y - path[i].y));
    const total = legs.reduce((a, b) => a + b, 0);
    if (total === 0) return this.arrive(actor);
    const duration = Math.min((total / WALK_SPEED) * 1000, Math.max(150, this.tickMs * 0.85));
    sprite.play(`${sprite.texture.key}:walk`, true);
    actor.walk = this.tweens.addCounter({
      from: 0, to: total, duration,
      onUpdate: tween => {
        let d = tween.getValue() ?? 0, i = 0;
        while (i < legs.length - 1 && d > legs[i]) d -= legs[i++];
        const t = legs[i] ? Math.min(1, d / legs[i]) : 1;
        sprite.setPosition(path[i].x + (path[i + 1].x - path[i].x) * t, path[i].y + (path[i + 1].y - path[i].y) * t);
      },
      onComplete: () => this.arrive(actor),
    });
  }

  private arrive(actor: Actor) {
    actor.walk?.remove();
    actor.walk = null;
    actor.sprite.setPosition(actor.target!.x, actor.target!.y).play(actor.clip, true);
    if (this.shown?.phase === 'closing') this.fade(actor, 0); // gone home through the lobby
  }

  /** Off duty is invisible: after the closing tick people fade out, and fade in on arrival. */
  private fade(actor: Actor, alpha: number) {
    const parts = [actor.sprite, actor.face, actor.name];
    if (parts.every(p => p.alpha === alpha)) return;
    this.tweens.killTweensOf(parts);
    this.tweens.add({ targets: parts, alpha, duration: 600 });
  }

  /** Relation changes float over the judging agent, only for the tick on screen. */
  private floatOutcomes() {
    const events = this.world.events;
    if (events !== this.seenEvents) {
      this.seenEvents = events;
      this.eventCursor = events.length; // a rebuilt history is not news
    }
    for (; this.eventCursor < events.length; this.eventCursor++) {
      const e = events[this.eventCursor];
      const delta = Number(e.payload.relation_delta ?? 0);
      if (e.kind !== 'outcome' || !delta || e.tick !== this.shown?.tick) continue;
      const a = this.actors.get(String(e.payload.a));
      if (!a) continue;
      const text = this.add.text(a.sprite.x, a.sprite.y - 56, `→${e.payload.b} ${delta > 0 ? '+' : ''}${delta.toFixed(2)}`, {
        fontFamily: 'Inter, system-ui, sans-serif', fontSize: '8px', fontStyle: 'bold',
        color: delta > 0 ? '#3f7f5a' : '#b5483b', stroke: '#ffffff', strokeThickness: 2,
      }).setOrigin(0.5, 1).setResolution(4).setDepth(1e6);
      this.tweens.add({ targets: text, y: text.y - 18, alpha: 0, duration: 2500, onComplete: () => text.destroy() });
    }
  }

  private follow() {
    const cam = this.cameras.main;
    const px = 1 / cam.zoom; // one screen pixel in world units: labels and strokes keep their size
    this.links.clear();
    this.marks.clear();
    for (const label of this.labels) label.setScale(px);
    // Talk: a soft floor ring under the group. Message: a dashed line to the recipient.
    for (const session of this.shown?.sessions ?? []) {
      const members = session.participants.map(p => this.actors.get(p)).filter(a => a !== undefined);
      if (members.length < 2) continue;
      // Talk, meeting and private sessions gather people; a message thread links two of them.
      if (session.kind === 'message' || session.id.startsWith('dm:')) {
        const [a, b] = members;
        this.dashed(a.sprite.x, a.sprite.y - 22, b.sprite.x, b.sprite.y - 22, NOTE);
        continue;
      }
      if (members.length > GATHER_MAX) {
        // Seated table-wide talk: a soft rounded patch under everyone taking part.
        const xs = members.map(m => m.sprite.x), ys = members.map(m => m.sprite.y);
        const [x0, y0] = [Math.min(...xs) - 18, Math.min(...ys) - 30], [x1, y1] = [Math.max(...xs) + 18, Math.max(...ys) + 10];
        this.marks.fillStyle(TALK, 0.1).fillRoundedRect(x0, y0, x1 - x0, y1 - y0, 18);
        this.marks.lineStyle(2 * px, TALK, 0.6).strokeRoundedRect(x0, y0, x1 - x0, y1 - y0, 18);
        continue;
      }
      const cx = members.reduce((s, a) => s + a.sprite.x, 0) / members.length;
      const cy = members.reduce((s, a) => s + a.sprite.y, 0) / members.length;
      const r = 20 + 5 * members.length;
      this.marks.fillStyle(TALK, 0.14).fillEllipse(cx, cy, r * 2.4, r * 1.3);
      this.marks.lineStyle(2 * px, TALK, 0.75).strokeEllipse(cx, cy, r * 2.4, r * 1.3);
    }
    for (const a of this.shown?.agents ?? []) {
      const from = this.actors.get(a.id), to = a.target && this.actors.get(a.target);
      if ((a.action !== 'message' && a.action !== 'report') || !from || !to) continue;
      this.dashed(from.sprite.x, from.sprite.y - 22, to.sprite.x, to.sprite.y - 22, NOTE);
    }
    // Neighbours' bubbles stack upward instead of overlapping: each rises above those to its left.
    const lift = new Map<number, number>();
    const byX = [...this.actors.values()].sort((a, b) => a.sprite.x - b.sprite.x);
    for (const { sprite, bubble } of byX) {
      if (bubble.hidden) continue;
      const row = Math.round(sprite.y);
      const x = (sprite.x - cam.worldView.x) * cam.zoom;
      const y = (sprite.y - 54 - cam.worldView.y) * cam.zoom - (lift.get(row) ?? 0);
      bubble.style.transform = `translate(${x}px, ${y}px) translate(-50%, -100%)`;
      lift.set(row, (lift.get(row) ?? 0) + bubble.offsetHeight + 4);
    }
    const close = cam.zoom >= NAMES_FROM_ZOOM;
    for (const [id, { sprite, face, name, bubble, action }] of this.actors) {
      sprite.setDepth(sprite.y);
      // Labels stay above furniture so seated agents behind a desk remain identifiable.
      const head = sprite.y - 42;
      const colour = STATUS[action];
      if (colour !== undefined && sprite.alpha > 0.5) {
        this.links.fillStyle(0xffffff, 1).fillCircle(sprite.x, head, 4.5 * px);
        this.links.fillStyle(colour, 1).fillCircle(sprite.x, head, 3.2 * px);
      }
      // The feeling sits right of the status dot: one small badge over the head.
      face.setScale(px).setPosition(sprite.x + 5 * px, head).setDepth(1e5 + sprite.y);
      // Far out, twenty names would bury the room: only the selected, hovered or speaking show.
      const named = close || id === this.selected || id === this.hovered || !bubble.hidden;
      name.setScale(px).setPosition(sprite.x, sprite.y + 2).setDepth(1e5 + sprite.y).setVisible(named);
      if (id === this.selected) {
        this.links.lineStyle(2.5 * px, 0x282834, 0.9).strokeEllipse(sprite.x, sprite.y, 28, 9);
      }
    }
  }

  private dashed(x1: number, y1: number, x2: number, y2: number, colour: number) {
    const length = Math.hypot(x2 - x1, y2 - y1), steps = Math.floor(length / 6);
    this.links.lineStyle(2 / this.cameras.main.zoom, colour, 0.9);
    for (let i = 0; i < steps; i += 2) {
      const a = i / steps, b = Math.min(1, (i + 1) / steps);
      this.links.lineBetween(x1 + (x2 - x1) * a, y1 + (y2 - y1) * a, x1 + (x2 - x1) * b, y1 + (y2 - y1) * b);
    }
  }

  private fitZoom() {
    const { top, right, bottom, left } = this.insets();
    const w = Math.max(this.scale.width - left - right, 100), h = Math.max(this.scale.height - top - bottom, 100);
    return Math.min(w / this.size.w, h / this.size.h) * 0.96;
  }

  fit() {
    const cam = this.cameras.main;
    const zoom = this.fitZoom();
    const { top, right, bottom, left } = this.insets();
    cam.setZoom(zoom);
    // The camera centres the screen; shift so the map's centre lands in the uncovered area.
    cam.centerOn(this.size.w / 2 + (right - left) / 2 / zoom, this.size.h / 2 + (bottom - top) / 2 / zoom);
    this.fitted = true;
  }

  /** Zooms keeping the world point under the cursor fixed (the camera zooms about its centre). */
  private zoomAt(x: number, y: number, factor: number) {
    const cam = this.cameras.main;
    const zoom = Phaser.Math.Clamp(cam.zoom * factor, this.fitZoom() * 0.5, 8);
    const cx = cam.width / 2, cy = cam.height / 2;
    const wx = cam.scrollX + cx + (x - cx) / cam.zoom, wy = cam.scrollY + cy + (y - cy) / cam.zoom;
    cam.setZoom(zoom);
    cam.setScroll(wx - cx - (x - cx) / zoom, wy - cy - (y - cy) / zoom);
    this.fitted = false;
  }
}
