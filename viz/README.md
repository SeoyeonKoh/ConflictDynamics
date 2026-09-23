# Company viewer protocol — B-9

Animated character assets: [20-character gallery](public/assets/characters-v3/preview.html),
[manifest and Phaser integration](public/assets/characters-v3/README.md). Each appearance has
idle, walk, sit and talk clips. These are front-facing animations; engine action-to-clip wiring
remains part of the B-10 viewer.

B-9 provides the Python transport and TypeScript message declarations. B-10 is the live Phaser
viewer below; replay is B-11.

```bash
uv run conflict-sim --config-name company live=true stream_paused=true
cd viz && npm install && npm run dev   # http://localhost:5173, add ?ws=ws://127.0.0.1:<port>
```

Live mode journals every message too (`src/replay.ts`): ◀ ▶ and the slider look back at earlier
ticks while the run goes on, and ● Live returns to the newest. Engine controls (pause, step, speed)
still go to the engine; while looking back, inspect shows the latest reply recorded for that
tick, so only agents inspected live have panels.

The side panel's Relations tab draws everyone's directed relations (A → B, how A sees B; green
positive, red negative, thicker is stronger) at the tick on screen. They are rebuilt from outcome
events, adding each `relation_delta` and clamping to [-1, 1], which reproduces the engine's values
exactly (checked against real-day10's final inspect panels); clicking a person inspects them.

Replay (B-11): `http://localhost:5173/?replay` lists every run under `runs/` that has a
`frames.jsonl`; `?replay=real-day8` plays one. The dev server serves only `.jsonl` files from
`runs/` (`vite.config.ts`). `src/replay.ts` answers the same controls as the socket — pause,
resume, step, speed (ticks per second), inspect — so HUD and scene have no replay branch; the
slider in the bar scrubs. Stepping forward applies one tick and walks; a jump rebuilds World from
hello and snaps. Inspect uses `inspect.jsonl` (last line per agent with `tick <= t`). Journals
recorded before one-tick sessions entered frames show no talk rings.

The viewer draws the office from hello's `map_data`: each place's `floor` property picks a floor
texture and the `furniture` object layer places `office-v1/furniture` frames (Tiled rectangles,
depth-sorted by bottom edge). The `seats` layer holds points with a `seat` property naming a place:
`frames.py` gives each occupant the first free seat from its own index, so seats stay put while
others come and go, and anyone left over stands in a grid. Desk seats sit behind the desk (head and
shoulders show); cafeteria and lobby seats sit on chairs and the sofa. Characters load only the `characters-v3` sheets the run uses.
Action → clip: `move` walk, `work`/`eat` sit, speech acts talk, otherwise idle.

Talk and message look different. A talk's members leave their seats and stand in a ring around
the group's centre (clamped to the room) over a yellow floor ellipse with spokes; a message or
report draws a dashed blue line to its `target` with a flying ✉ and a blue bubble "✉ → name".
A session runs up to `turns_per_tick` rounds inside one tick, so one speaker may say several
things per tick. `frame.lines` carries every utterance of the tick in order (talk, live and async
DM threads; DM thread ids are `dm:<a>:<b>:<n>`); the viewer spreads them over the tick, outlines
the current speaker's bubble and dims earlier ones, and lists them in the timeline as `says` rows.
`bubble` still holds each speaker's last utterance for older viewers and journals.
Talks usually open and close inside one tick, so `frames.py` adds this tick's session-start events
to `frame.sessions` and gives their members that `session` (and `talk` instead of `idle`).

Commuting: after each day's closing tick the engine sends everyone out through the lobby
(`Office.leave`), where the next day's arrival starts. The closing frame therefore shows them
walking to the lobby; the viewer fades them out once there and fades them in on the next frame.

Walking is the viewer's alone (`src/walkways.ts`); the engine still sends only end positions. The
`walkways` layer holds `corridor` rects (one shared hallway area) and `door` rects straddling a
wall. On a 16px grid, A* may cross from one area into another only inside a door; furniture's
lower 40% costs extra rather than blocking, so seats inside a sofa stay reachable, and rooms other
than start and goal cost extra so routes follow the halls. The route is string-pulled to its
corners and walked at 120 px/s, capped to finish within 85% of the measured tick interval. A new
frame with the same target leaves a walk running; frames more than two ticks apart (history,
reconnect) snap. Bubbles, task board, inspect panel and event timeline
are DOM (`src/hud.ts`); `src/world.ts` is the message reducer replay will reuse. Scroll zooms at
the cursor, drag pans, double-click fits. Expressions are emoji text (no Twemoji sheet, by decision).

Connect a WebSocket client to `ws://127.0.0.1:8765`. Override `stream_port` for parallel runs;
port `0` selects an available port, printed at startup. With `stream_paused=true`, send
`{"type":"control","cmd":"step"}` or `{"type":"control","cmd":"resume"}` to begin.
Other commands: `pause`, `speed` with numeric `value` in `(0,100]`, and `inspect` with `agent`.
Demo live pacing is 0.2 seconds / speed between tick starts. Real API runs are unpaced;
pause/step take effect at the next tick boundary, without cancelling an in-flight LLM call.
The server closes after publishing the terminal status. It binds only to loopback and permits
local HTTP browser origins and clients without an Origin header.

Every company run (including `live=false`) writes `frames.jsonl`. Each line is one protocol-v1
server message. A connection receives `hello`, all recorded messages in order, then new
messages. Reconnection resets client state and repeats that sequence. Socket writes run on
client threads and never hold the engine's publication lock.

See `src/messages.d.ts` for the contract:

- `hello`: version, run id, agents, tick duration, full initial task/resource tables, and the
  Tiled map embedded as `map_data` so a recording is self-contained. `map` is its logical name.
- `frame`: zero-based tick/day, phase, full agent/session state (sessions include any that
  opened this tick, even if already closed; `target` names a message or report's recipient),
  task/resource **upserts**.
  Reconstruct task/resource tables from hello plus successive deltas; do not replace with an
  individual frame's delta array. A resumed segment sends full tables on its first frame.
- `event`: existing engine kinds (`task`, `rejected`, `outcome`, `shock`, `session`), actors,
  text and original payload. Directed outcome fields remain in payload (`a`, `b`,
  `relation_delta`); no CRAFT scores enter this protocol.
- `inspect`: latest completed snapshot's reflection, stress/mood, relationships and last
  retrieval ids, sent privately on request. Before tick 0, it contains initial state.
- `status`: running/paused/completed/failed, message and usage. `error` is a private control
  validation response; it does not change run status.

Inspect panels are journaled separately in `inspect.jsonl`, never sent as socket history. It
holds one `inspect` message per agent whenever that agent's panel changed, starting with the
initial state. Replay rule: an agent's panel at tick `t` is its last line with `tick <= t`, in file
order. Replay inspect therefore needs neither `events.jsonl` nor `memory.sqlite`.

Names serve as existing engine IDs. Sprite names are placeholders for B-10 artwork.
Resource `holders` means current occupants, not a reservation; the current engine does not
have reservation expiry timestamps.

`src/conflict_sim/maps/office.json` contains the small office's Tiled place rectangles, without
artwork. Use `stream_map=/absolute/path/to/map.json` for another office: each configured place
must have one object with a `place_id` string property. Engine configs contain no coordinates.

On checkpoint resume, the journal retains only hello and frame/event messages before the
checkpoint tick, then appends the new segment; `inspect.jsonl` likewise keeps lines before it.
A partial final line is discarded. Historical status messages are removed. The current implementation holds serialized history in memory;
replay loads a whole journal (a real day is ~110 KB); day-wise loading waits for multi-day runs.

Verification: `uv run pytest -q tests/test_stream.py` covers a real demo day over WebSocket,
initial pause, step/resume, inspect, reconnect/history, journal deltas, the inspect journal,
invalid controls, directed outcomes and rollback at resume. The full suite passed (416 passed,
1 skipped).
