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
const TALK = 0xffd166;
const NOTE = 0x79c0ff;
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
  private mapObjects: Phaser.GameObjects.GameObject[] = [];
  private links!: Phaser.GameObjects.Graphics;
  private marks!: Phaser.GameObjects.Graphics; // on the floor, under the characters
  private notes: Phaser.GameObjects.Text[] = []; // this tick's envelopes in flight
  private lineTimers: Phaser.Time.TimerEvent[] = [];
  private areas = new Map<string, { x: number; y: number; width: number; height: number }>();
  private manifest!: CharacterManifest;
  private size = { w: 960, h: 640 };
  private fitted = true; // false once the viewer zooms or pans; resize then leaves the view alone
  private walkways!: Walkways;
  private tickMs = 1000; // smoothed time between consecutive live frames
  private frameAt = 0;

  constructor(private world: World, private bubbles: HTMLElement) {
    super('office');
  }

  preload() {
    this.load.json('characters', ASSETS + 'characters-v3/manifest.json');
    this.load.atlas('furniture', ASSETS + 'office-v1/furniture.png', ASSETS + 'office-v1/furniture.atlas.json');
    this.load.atlas('floors', ASSETS + 'office-v1/floors.png', ASSETS + 'office-v1/floors.atlas.json');
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
    this.drawMap(hello.map_data);
    this.walkways = new Walkways(hello.map_data);
    // Only the appearances this run uses are loaded (each sheet is ~1.3 MB).
    for (const agent of hello.agents) {
      const c = this.character(agent.sprite);
      if (!this.textures.exists(c.id)) this.load.atlas(c.id, ASSETS + 'characters-v3/' + c.image, ASSETS + 'characters-v3/' + c.atlas);
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
    this.size = { w: (map.width as number) * tile, h: (map.height as number) * tile };
    const add = <T extends Phaser.GameObjects.GameObject>(o: T) => (this.mapObjects.push(o), o);
    add(this.add.rectangle(0, 0, this.size.w, this.size.h, 0x2b2f3a).setOrigin(0).setDepth(-3));
    for (const layer of map.layers as { objects?: TiledObject[] }[]) {
      for (const o of layer.objects ?? []) {
        const p = props(o);
        if (typeof p.place_id === 'string') {
          add(this.add.tileSprite(o.x, o.y, o.width, o.height, 'floors', (p.floor as string) ?? 'oak')
            .setOrigin(0).setTileScale(96 / 627).setDepth(-2));
          add(this.add.rectangle(o.x, o.y, o.width, o.height).setOrigin(0).setStrokeStyle(4, 0x4a4f5c).setDepth(-1));
          const label = add(this.add.text(o.x + 6, o.y + 4, o.name, {
            fontFamily: 'system-ui, sans-serif', fontSize: '10px', color: '#ffffff', backgroundColor: '#00000088',
            padding: { x: 3, y: 1 },
          }).setResolution(4).setDepth(1e6));
          this.rooms.set(p.place_id, label);
          this.areas.set(p.place_id, o);
        } else if (p.walkway === 'corridor') {
          add(this.add.tileSprite(o.x, o.y, o.width, o.height, 'floors', 'stone')
            .setOrigin(0).setTileScale(96 / 627).setDepth(-2));
        } else if (p.walkway === 'door') {
          // Drawn over the walls: the opening is where the wall is missing.
          add(this.add.tileSprite(o.x, o.y, o.width, o.height, 'floors', 'stone')
            .setOrigin(0).setTileScale(96 / 627).setDepth(-0.5));
        } else if (typeof p.frame === 'string') {
          // Depth by bottom edge: characters sort in front of or behind furniture by foot y.
          add(this.add.image(o.x, o.y, 'furniture', p.frame).setOrigin(0).setDisplaySize(o.width, o.height)
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
    const face = this.add.text(0, 0, '', { fontSize: '13px' }).setOrigin(0.5, 1).setResolution(4);
    const name = this.add.text(0, 0, label, {
      fontFamily: 'system-ui, sans-serif', fontSize: '7px', color: '#ffffff', backgroundColor: '#000000aa',
      padding: { x: 2, y: 0 },
    }).setOrigin(0.5, 0).setResolution(4);
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.hidden = true;
    this.bubbles.append(bubble);
    this.actors.set(id, { sprite, face, name, bubble, target: null, clip: `${c.id}:idle`, walk: null });
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
      const spot = gather.get(a.id) ?? { x: a.x, y: a.y };
      const moved = !actor.target || actor.target.x !== spot.x || actor.target.y !== spot.y;
      actor.target = spot;
      if (moved && live) this.walk(actor);
      else if (moved) this.arrive(actor);
      else if (!actor.walk) actor.sprite.play(actor.clip, true);
      actor.face.setText(FACE[a.expression] ?? a.expression);
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
    }
  }

  private say(actor: Actor, text: string | undefined, note: boolean) {
    actor.bubble.textContent = text ?? '';
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
    lines.forEach((line, i) => {
      this.lineTimers.push(this.time.delayedCall(i * gap, () => {
        const actor = this.actors.get(line.speaker);
        if (!actor) return;
        const [kind, a, b] = line.session.split(':');
        const dm = kind === 'dm';
        this.say(actor, dm ? `✉ → ${line.speaker === a ? b : a}: ${line.text}` : line.text, dm);
        for (const other of this.actors.values()) other.bubble.classList.toggle('speaking', other === actor);
      }));
    });
  }

  /** Talk members leave their seats and stand in a ring around the group's centre, in-room. */
  private gatherings(frame: Frame) {
    const spots = new Map<string, Point>();
    const at = new Map(frame.agents.map(a => [a.id, a]));
    for (const session of frame.sessions) {
      if (session.kind !== 'talk') continue;
      const members = session.participants.map(p => at.get(p)).filter(a => a !== undefined);
      if (members.length < 2) continue;
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
        fontFamily: 'system-ui, sans-serif', fontSize: '8px', fontStyle: 'bold',
        color: delta > 0 ? '#7ee787' : '#ff7b72', stroke: '#000000', strokeThickness: 2,
      }).setOrigin(0.5, 1).setResolution(4).setDepth(1e6);
      this.tweens.add({ targets: text, y: text.y - 18, alpha: 0, duration: 2500, onComplete: () => text.destroy() });
    }
  }

  private follow() {
    const cam = this.cameras.main;
    this.links.clear();
    this.marks.clear();
    // Talk: a floor ring and spokes to the group's centre. Message: a dashed line to the recipient.
    for (const session of this.shown?.sessions ?? []) {
      const members = session.participants.map(p => this.actors.get(p)).filter(a => a !== undefined);
      if (members.length < 2) continue;
      if (session.kind !== 'talk') {
        const [a, b] = members;
        this.dashed(a.sprite.x, a.sprite.y - 22, b.sprite.x, b.sprite.y - 22, NOTE);
        continue;
      }
      const cx = members.reduce((s, a) => s + a.sprite.x, 0) / members.length;
      const cy = members.reduce((s, a) => s + a.sprite.y, 0) / members.length;
      const r = 20 + 5 * members.length;
      this.marks.fillStyle(TALK, 0.18).fillEllipse(cx, cy, r * 2.4, r * 1.3);
      this.marks.lineStyle(1.5, TALK, 0.7).strokeEllipse(cx, cy, r * 2.4, r * 1.3);
      this.links.lineStyle(1.5, TALK, 0.8);
      for (const m of members) this.links.lineBetween(m.sprite.x, m.sprite.y - 22, cx, cy - 22);
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
    for (const [id, { sprite, face, name }] of this.actors) {
      sprite.setDepth(sprite.y);
      // Labels stay above furniture so seated agents behind a desk remain identifiable.
      face.setPosition(sprite.x, sprite.y - 40).setDepth(1e5 + sprite.y);
      name.setPosition(sprite.x, sprite.y + 1).setDepth(1e5 + sprite.y);
      if (id === this.selected) {
        this.links.lineStyle(2, 0xffffff, 0.9).strokeEllipse(sprite.x, sprite.y, 26, 8);
      }
    }
  }

  private dashed(x1: number, y1: number, x2: number, y2: number, colour: number) {
    const length = Math.hypot(x2 - x1, y2 - y1), steps = Math.floor(length / 6);
    this.links.lineStyle(2.5, colour, 1);
    for (let i = 0; i < steps; i += 2) {
      const a = i / steps, b = Math.min(1, (i + 1) / steps);
      this.links.lineBetween(x1 + (x2 - x1) * a, y1 + (y2 - y1) * a, x1 + (x2 - x1) * b, y1 + (y2 - y1) * b);
    }
  }

  private fitZoom() {
    return Math.min(this.scale.width / this.size.w, this.scale.height / this.size.h) * 0.96;
  }

  fit() {
    const cam = this.cameras.main;
    cam.setZoom(this.fitZoom());
    cam.centerOn(this.size.w / 2, this.size.h / 2);
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
