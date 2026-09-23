export interface TiledObject {
  name: string; x: number; y: number; width: number; height: number; point?: boolean;
  properties?: { name: string; value: unknown }[];
}
export interface Point { x: number; y: number }

export function props(o: TiledObject): Record<string, unknown> {
  return Object.fromEntries((o.properties ?? []).map(p => [p.name, p.value]));
}

const CELL = 16;
const OUTSIDE = -1;
// Furniture occupies only its lower part, so seats behind a desk or on a chair stay close.
const FOOTPRINT = 0.4;
// Crossing furniture is costly, not forbidden: a seat on a sofa must still be entered and left.
const FURNITURE_COST = 12;
// Passing through a room that is neither start nor goal costs more, so routes follow the halls.
const THROUGH_ROOM_COST = 3;

/**
 * Walkable grid over the Tiled map: rooms (`place_id`) and corridors (`walkway: corridor`) are
 * areas, and crossing from one area into another is allowed only inside a `walkway: door` rect.
 */
export class Walkways {
  private cols: number;
  private rows: number;
  private area: Int16Array;
  private door: Uint8Array;
  private blocked: Uint8Array;

  constructor(map: Record<string, unknown>) {
    const tile = map.tilewidth as number;
    this.cols = ((map.width as number) * tile) / CELL;
    this.rows = ((map.height as number) * tile) / CELL;
    this.area = new Int16Array(this.cols * this.rows).fill(OUTSIDE);
    this.door = new Uint8Array(this.cols * this.rows);
    this.blocked = new Uint8Array(this.cols * this.rows);
    const objects = (map.layers as { objects?: TiledObject[] }[]).flatMap(l => l.objects ?? []);
    // Each room is its own area; all corridors together form one hallway area (index 0).
    const rooms = objects.filter(o => props(o).place_id !== undefined);
    rooms.forEach((o, i) => this.fill(o, cell => { this.area[cell] = i + 1; }));
    for (const o of objects) if (props(o).walkway === 'corridor') this.fill(o, cell => { this.area[cell] = 0; });
    for (const o of objects) {
      if (props(o).walkway === 'door') this.fill(o, cell => { this.door[cell] = 1; });
      if (props(o).frame !== undefined) {
        const top = o.y + o.height * (1 - FOOTPRINT);
        this.fill({ ...o, y: top, height: o.y + o.height - top }, cell => { this.blocked[cell] = 1; });
      }
    }
  }

  /** A* over 4-neighbour cells, then string-pulled; falls back to a straight line. */
  route(from: Point, to: Point): Point[] {
    const start = this.cellAt(from), goal = this.cellAt(to);
    const came = new Map<number, number>([[start, start]]);
    const cost = new Map<number, number>([[start, 0]]);
    const open = [start];
    const h = (c: number) => Math.abs((c % this.cols) - (goal % this.cols)) + Math.abs(Math.floor(c / this.cols) - Math.floor(goal / this.cols));
    while (open.length) {
      let best = 0;
      for (let i = 1; i < open.length; i++) {
        if (cost.get(open[i])! + h(open[i]) < cost.get(open[best])! + h(open[best])) best = i;
      }
      const cell = open.splice(best, 1)[0];
      if (cell === goal) break;
      for (const next of this.neighbours(cell)) {
        if (this.area[next] === OUTSIDE || !this.passable(cell, next)) continue;
        const through = this.area[next] !== 0 && this.area[next] !== this.area[start] && this.area[next] !== this.area[goal];
        const c = cost.get(cell)! + (this.blocked[next] ? FURNITURE_COST : through ? THROUGH_ROOM_COST : 1);
        if (c < (cost.get(next) ?? Infinity)) {
          cost.set(next, c);
          came.set(next, cell);
          if (!open.includes(next)) open.push(next);
        }
      }
    }
    if (!came.has(goal)) return [from, to];
    const cells = [goal];
    while (cells[0] !== start) cells.unshift(came.get(cells[0])!);
    const points = [from, ...cells.slice(1, -1).map(c => this.centre(c)), to];
    // Keep only the corners: jump to the farthest point still in a clear line.
    const path = [points[0]];
    for (let i = 0; i < points.length - 1;) {
      let j = points.length - 1;
      while (j > i + 1 && !this.clear(points[i], points[j])) j--;
      path.push(points[j]);
      i = j;
    }
    return path;
  }

  private fill(o: { x: number; y: number; width: number; height: number }, set: (cell: number) => void) {
    for (let r = Math.floor(o.y / CELL); r < Math.ceil((o.y + o.height) / CELL); r++) {
      for (let c = Math.floor(o.x / CELL); c < Math.ceil((o.x + o.width) / CELL); c++) {
        if (r >= 0 && r < this.rows && c >= 0 && c < this.cols) set(r * this.cols + c);
      }
    }
  }

  private cellAt(p: Point) {
    // Feet sit on the bottom edge of their cell, hence the 1px nudge upward.
    const c = Math.min(this.cols - 1, Math.max(0, Math.floor(p.x / CELL)));
    const r = Math.min(this.rows - 1, Math.max(0, Math.floor((p.y - 1) / CELL)));
    return r * this.cols + c;
  }

  private centre(cell: number): Point {
    return { x: (cell % this.cols) * CELL + CELL / 2, y: Math.floor(cell / this.cols) * CELL + CELL / 2 };
  }

  private neighbours(cell: number) {
    const c = cell % this.cols, out: number[] = [];
    if (c > 0) out.push(cell - 1);
    if (c < this.cols - 1) out.push(cell + 1);
    if (cell >= this.cols) out.push(cell - this.cols);
    if (cell < this.cols * (this.rows - 1)) out.push(cell + this.cols);
    return out;
  }

  private walkable(cell: number) {
    return this.area[cell] !== OUTSIDE && !this.blocked[cell];
  }

  private passable(a: number, b: number) {
    return this.area[a] === this.area[b] || this.door[a] === 1 || this.door[b] === 1;
  }

  /** A straight segment is clear when every cell it samples is walkable and legally entered. */
  private clear(a: Point, b: Point) {
    const steps = Math.ceil(Math.hypot(b.x - a.x, b.y - a.y) / 4);
    let prev = this.cellAt(a);
    for (let i = 1; i < steps; i++) {
      const cell = this.cellAt({ x: a.x + ((b.x - a.x) * i) / steps, y: a.y + ((b.y - a.y) * i) / steps });
      if (cell === prev) continue;
      if (!this.walkable(cell) || !this.passable(prev, cell)) return false;
      prev = cell;
    }
    return true;
  }
}
