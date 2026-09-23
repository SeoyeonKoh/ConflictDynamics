# Company viewer protocol — B-9

Animated character assets: [20-character gallery](public/assets/characters-v3/preview.html),
[manifest and Phaser integration](public/assets/characters-v3/README.md). Each appearance has
idle, walk, sit and talk clips. These are front-facing animations; engine action-to-clip wiring
remains part of the B-10 viewer.

B-9 provides the Python transport and TypeScript message declarations. The Phaser UI and
replay player are next (B-10/B-11); this directory does not yet contain a runnable web app.

```bash
uv run conflict-sim --config-name company live=true stream_paused=true
```

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
- `frame`: zero-based tick/day, phase, full agent/session state, task/resource **upserts**.
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
day-wise loading and replay scrubbing belong to B-11.

Verification: `uv run pytest -q tests/test_stream.py` covers a real demo day over WebSocket,
initial pause, step/resume, inspect, reconnect/history, journal deltas, the inspect journal,
invalid controls, directed outcomes and rollback at resume. The full suite passed (416 passed,
1 skipped).
