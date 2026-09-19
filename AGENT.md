# AGENT.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Complete relevant verification and commit after each finished user-requested work unit.
Keep implementation consistent with the existing readable, minimal style.
Commit messages carry no `Co-Authored-By` or other AI attribution trailer.

## Status and direction

`master` has reached **milestone A: the company simulation engine runs a demo day** (plan §6
tasks 1–7 done; `uv run conflict-sim --config-name company`) and **A-8 is done** (real-API
preparation: checkpoint/resume, embed cache, parallel judgements). Next: **phase B, visualisation**
(B-9 frames + websocket stream, B-10 Phaser viewer, B-11 replay), then **phase C, persona tests**
(C-13 onwards). Plan §1-14 and §6 were revised on 2026-09-19: the viewer comes before the
persona tests because it is how a real-LLM run gets checked before scenarios and experiments are
built on it, and the phases were renamed to match (B = visualisation, C = persona tests).
The wiki simulator as it stood at the fork is preserved on branch `wiki`
(tag `wiki-fork`, commit `76d6e9e`). Wiki-direction research happens there; `master` never merges
from `wiki`. Shared improvements go `master` → `wiki` by cherry-pick.

The design source of truth is [docs/company-world-plan.md](docs/company-world-plan.md). Decisions
recorded there are settled — do not reopen them in code: English only; CRAFT scored per session;
`persona_placement: system` becomes the default; no deliberately irrational personas (conflict
comes from structure: scarce resources, zero-sum rewards, dependency failure, partial observation);
memory nested under `agent/`; one `environment/` package; websocket between engine and the Phaser
viewer; order A engine (incl. A-8 real-API prep) → B visualisation → C persona tests (renamed
2026-09-19).

**Phase A target** (plan §5, §6). Two packages and a few renamed files — no more than that:

```
src/conflict_sim/
  models.py          every schema: Config · AgentSpec · Action · View · Task · MemoryRecord · Relationship
  llm.py             + embed(); rule-based demo that can run a full day without an API
  conversation.py    engine.py renamed: Session.step(tick) · ordering rules · session prompts · outcome hook · run() wrapper
  agent/             agent.py (perceive · act · decide/speak · flat daily plan) · state.py (stress · mood · expression · relation) · memory.py
  environment/       __init__ (Environment.apply · view · snapshot) · office.py · org.py
  loop.py            tick loop · phases · shock schedule · action apply · session scheduling · end-of-tick writes
  storage.py         multi-conversation corpus · events.jsonl        (in place)
  score.py           per-session CRAFT                              (in place, no internal imports)
  cli.py · settings.py (frozen, wiki presets only) · dashboard.py
```

Milestone A (reached): the demo backend runs 6 agents × 1 day (32 ticks of 15 min) end to end and
writes `corpus/`, `events.jsonl`, `memory.sqlite`, and `conflict-score` writes `scores.json` per
session; the wiki presets still run as a demo smoke test through `conversation.run()`
(`tests/test_cli.py::test_company_demo_day_writes_corpus_events_memory_and_scores`).

Rules while building A (plan §5-3, audit in §6):

- `environment/` and `agent/` never import each other. Types they exchange live in `models.py`.
  Agents see a read-only `View` and return an `Action`; `loop.py` applies it.
  Action validity (authority, place, capacity) is checked in `Environment.apply` only — no
  precondition module or utility selector on the agent side; the Action is the LLM's output.
  `talk · message · chat` are not physical: `apply` only validates them; session creation, DM
  append and live switching are the loop's.
- `models.py` holds **immutable IO schemas only** (`frozen=True` as today): `Config · AgentSpec ·
  TaskSpec · Action · View · Outcome · Event · MemoryRecord`. Mutable runtime state is a dataclass
  in its owning package — `environment/org.py: Task`, `agent/state.py: AgentState · Relationship`.
  `MemoryRecord` has no `last_access` field; `MemoryStore.last_access{id→tick}` does.
- The loop assembles `View`: `Environment.env_view(agent)` gives place, co-present **ids**, my
  tasks, blocked, resources; the loop adds co-present agents' `expression` (read-only), inbox,
  the previous tick's rejected Action, and my `stress`/`mood`.
- `Session.step` only calls `decide · speak`. At session end it returns `outcomes()`; the loop
  dispatches `agent.apply_outcome()`. Sessions never mutate agents.
- Embeddings are batched by the loop once per tick across all agents (`memory.pending_texts()` →
  one `embed` → `memory.set_embeddings()`); `agent/memory.py` calls the LLM directly only for
  reflection. `memory.sqlite`'s schema and writes belong to `storage.py`; `agent/memory.py`
  hands back `pending_writes` and never opens the file.
- `conversation.py` and `agent/` never import `storage.py`. `loop.py` owns persistence and writes
  `events.jsonl` and `memory.sqlite` once per tick (single writer; agents hand back records).
- `score.py` keeps importing nothing from the package. `storage.py` imports `agent.PROMPT_VERSION`,
  so routing the scorer through storage would pull the engine into it.
- No extra LLM calls for record scoring: utterance `importance · valence · arousal` ride in the
  `decide` JSON; observation records use the expression table. No small "importance model".
- The only free experimental parameter is `alpha_mood` (mood-congruent recall). Everything else in
  plan §2-6 is a fixed default in `conf/config.yaml`.
- Deferred to C (plan §6 row 13), do not build earlier: manager-LLM task generation (A uses the
  scenario's static task list), meeting turn-taking, private/gossip sessions, hearsay, forgetting,
  KPI/promotion slots, interventions, overtime, shock schedule. Checkpoint/resume, embed cache and
  parallel LLM calls were A-8 and exist.
- `Agent` = `spec` (immutable `AgentSpec`) + `state` (`stress · mood · expression · relations`) +
  `memory` + `plan` + intent methods (`act · decide · speak · observe · apply_outcome · end_tick ·
  snapshot`). Per-thread bookkeeping (`last_seen`, `pending`) lives on `conversation.Participant`,
  owned by the `Session`; scheduling state (current session, inbox) lives in `loop.py`. Today's
  `Agent.last_seen` moves to `Participant` — do not turn it into a `dict[thread_id, int]`.
- Nothing outside `agent/` mutates `agent.state`. A session produces an `Outcome` (facts: valence
  toward me, rejected/ignored/sided, public); `Agent.apply_outcome()` owns the numeric rules.
  `MemoryStore` takes the `llm` by injection and is the only place that calls it for reflection.
- Do not split a file before it is actually large. `org.py` gets a `tasks.py` only when the Task
  part outgrows it.

Update the *Current code* section below as each piece lands; do not describe planned code as
existing.

## Commands

```bash
uv sync --all-extras                     # llm, dashboard, score; see gotcha below
uv run --all-extras pytest               # full suite
uv run --extra llm pytest tests/test_conversation.py::test_random_order_is_reproducible  # one
uv run ruff check .
uv run conflict-sim                      # wiki demo run, no API needed
uv run conflict-sim --config-name company hydra.run.dir=runs/company  # one company day, demo backend
uv run conflict-sim rule=random random_seed=12 max_ticks=6 hydra.run.dir=runs/demo
uv run conflict-sim --cfg job --resolve  # print the composed config without running
uv run conflict-sim -m rule=round_robin,bidding random_seed=7,42   # multirun sweep
uv run --all-extras streamlit run src/conflict_sim/dashboard.py   # live + saved + scoring
uv run --extra score conflict-score --all runs   # CRAFT p(t) for every run
uv run conflict-seeds runs/cga/source/cga-wiki runs/cga/seeds/train  # new output only
```

**Gotcha:** plain `uv sync` *removes* the `llm` extra, and `tests/test_llm.py` (10 tests) then
silently skips on a missing `httpx` import — the suite reports success at a lower count.
`tests/test_dashboard.py` skips the same way without `--extra dashboard`.
Sync with `--all-extras`, or use `uv run --no-sync` when the extras are already installed.

**Known pre-existing failure:** `uv run ruff format --check .` fails on
`docs/conflict-sim-design.md`. Ruff 0.16 reformats Markdown code blocks.
Unrelated to current work — do not "fix" it as a side effect.

## Current code

**`loop.py` is the tick loop (A-6 done) and the only module that touches `environment/`,
`agent/` and `conversation.py` together.** `Loop(cfg, agents, env, llm, rng, writer)`;
`run()` = `max_days × ticks_per_day` ticks, `run_until(tick)` for tests. The loop keeps no event
history — every tick's events and memory rows go to the `TickWriter` and are dropped
(`tests/test_loop.py::Recorder` stands in for storage). `phase_of(tick, ticks_per_day)`: tick 0
of a day `arrival`, then `morning`, a 4-tick `lunch` from mid-day, `afternoon`, the last tick
`closing`; no overtime in A. One tick: a phase change `finish`es every live session (outcomes
dispatched) → last tick's `outbox` becomes this tick's `inbox` (a message is never read the tick
it was sent, whatever the acting order) → `env.advance` (`task` events) → on `arrival` every
agent `plan_day`s (an `action` event with `payload.kind = "plan"`) and `outstanding` is cleared →
per agent, in config order: `_view` (env part + co-present faces read from
`agent.state.expression` + inbox + unanswered + last rejection + stress/mood; an agent in a live
session gets an empty inbox so queued messages are recorded once, when it is free again),
`perceive`, and, unless busy, `act` → `env.apply`; `talk`/`chat` then open a session and
`message`/`report` append to the pair's DM thread (`dm:<a>:<b>:<day>`) and the target's outbox;
`outstanding[(from, to)]` shows a `View.unanswered` entry exactly once, the tick the silence
reaches `no_reply_ticks` → every live session `step`s (`decision` events; each new utterance
becomes an `utterance` record for every participant: the speaker's with the decision's axes, a
listener's with the valence of the first judgement it made after hearing it, 0 if none — plan
§2-3a names only the speaker's decide axes, so this is the loop's rule) → on the run's last tick
every live session is finished with reason `end` → `end_tick` per agent → one `llm.embed` batch
for every new record → `writer.write_tick`. Session ids are conversation ids and equal their root
utterance id (`talk:<tick>:<opener>`, `dm:…`). A `talk` session takes everyone co-present who is
not already busy, rule `event_driven`; a `chat` needs today's thread and a free partner and runs
`bidding` on it (plan §1-7 would answer a busy partner asynchronously, but a `chat` carries no
text, so the loop refuses it and the agent can `message` next tick — a deliberate deviation);
both use `cfg.turns_per_tick[kind]`. `Outcome.refused/ignored/rebutted/opposed` stay empty in A —
the loop does not derive them from Actions yet. Loop-level refusals (partner busy, nobody free)
look like environment ones (`Rejected` in the next view, a `rejected` event). `sessions` holds
the meta (`kind · participants · place · start · end · public`) that `conversations.json`
carries; `end` is set for `talk` only — a DM thread stays open for async messages after a live
segment, whose start and end are `session` events.

**Checkpoint and resume (A-8).** Every day's last tick closes all live sessions (`day_end`) and
the loop hands `writer.write_checkpoint(day, loop.checkpoint())` a JSON-friendly dict: next
`tick`, the `rng` state, `env.snapshot()`, every `agent.snapshot()` (state, `PlanItem` dumps,
memory counters — records and vectors are already in `memory.sqlite`), threads, session meta,
inbox/outbox/outstanding/rejected — not the backend's `usage`: the loop stays inside the
`LanguageModel` protocol, so `max_total_tokens` is a **per-process** budget and a resumed run
starts a fresh one. `RunWriter` writes `checkpoints/day-<n>.json`. `cli._company_run` catches
*every* `LLMError` in a company run (budget, API error, refusal, empty reply) and writes
`paused.json` (`status · reason · tick · checkpoint`) with exit status 0 instead of failing;
`resume: true` on the
same `hydra.run.dir` (`Config.resume`, `ProtectOutput` lets it through when `checkpoints/` exists
and `corpus/` does not) reads the latest checkpoint, `storage.truncate_run`s the partial day's
rows from `events.jsonl` and `memory.sqlite`, `Loop.restore`s with `storage.read_memory`, and
continues; `tests/test_loop.py::test_a_restored_loop_replays_the_second_day_exactly` proves the
replay is bit-identical on the demo backend. `Environment`, `Task`, `AgentState`, `MemoryStore`
and `Agent` all pair `snapshot()` with `restore()`.

**Embedding cache (A-8).** `llm.EmbedCache(backend, path)` wraps any backend and answers `embed`
from a sqlite table keyed by `sha256(model_embed + text)`, calling the backend only for misses;
`complete` and `usage` pass through untouched — completions are never cached (plan §1-10: a
cached `temperature 0.8` call would collapse "3 runs per condition" into one). `Config.embed_cache`
is a path relative to the launch directory (`conf/company.yaml`: `runs/embed-cache.sqlite`, shared
across runs); `cli.simulate` wraps the backend when it is set.

**Parallel judgements (A-8).** `Config.workers > 1` gives the loop a `ThreadPoolExecutor`
(threads, not asyncio: the OpenAI client is sync and thread-safe). Judgements are independent
per agent and run through `Loop._judge`: every free agent's `act` on the same tick-start views,
`plan_day` on arrival, `end_tick` (reflections); a `bidding` session's fresh `decide`s run through
`Session._judge_ahead` before the round proceeds (`round_robin · random · event_driven` let
later participants read earlier posts, so they stay sequential). Applying — `env.apply`,
session opening, posting, outcomes — is sequential in config order, and an agent that an
earlier `talk` pulled into a session this tick has its judged action dropped (one session per
agent; the judgement is a sunk cost, plan §1-10), so
`tests/test_loop.py::test_parallel_judgements_reproduce_the_sequential_run_and_use_several_threads`
holds. Agents mutate only themselves during a judgement; `EmbedCache` guards its sqlite
connection with a lock and `OpenAIBackend` its usage counters with another; `Loop.close()`
shuts the pool down and `cli._company_run` calls it in `finally`. `conf/company.yaml` sets
`workers: 4`.

**Run files.** `storage.RunWriter(run_dir)` appends `events.jsonl` (one `Event` per line) and
commits `memory.sqlite` (`records` with float64 embedding blobs, `retrievals`) once per tick; it
owns the schema. `save_company_run` publishes `corpus/` with one ConvoKit conversation per session
(utterance rows carry `conversation_id`, `conversations.json` carries the session meta) and
`run.json` with `stop_reason: max_days · ticks · days`; decisions are `events.jsonl` rows, so
there is no `decisions.jsonl` or `seed.json` (`score.CORPUS_FILES` is the shared set,
`WIKI_CORPUS_FILES` adds those two). `save_run` (wiki) shares `_write_corpus` and counts
generated posts from `RunResult.seed_count`. `score.score_run` still writes the whole-run
`metrics` and now adds `sessions: {id: metrics}` (`read_sessions` groups by `conversation_id`;
rows without one form a single session) and `summary` (`sessions · exceeded ·
exceeded_fraction · first_exceeded {session, tick}`); `completed_corpus` accepts `max_days`;
`forecast_public` still serves the wiki live snapshot only. `cli.simulate` branches on
`cfg.environment`: set → `_company_run` (no `live.json`, dashboard live mode is wiki-only until B),
None → `_wiki_run` (unchanged behaviour).


Flow: `conf/*.yaml` + CLI overrides → `cli.parse_config` → `Config` → `storage.load_seed` →
`conversation.run` → `storage.save_run` → `runs/<date>/<time>/corpus/` in ConvoKit format.
`cli.main` installs the mandatory `ProtectOutput` Hydra callback and calls `cli.simulate`.
The callback reserves run/sweep roots using `.run.lock` before Hydra writes configuration or logs.
Only empty directories or the live UI's console.log-only directory may be claimed. Failed roots
remain reserved. Sweeps require `${hydra.job.num}` subdirectories to prevent job-path collisions.
`loop.py` runs company days; `ProtectOutput` stays and lets `resume=true` through when
`checkpoints/` exists and `corpus/` does not (A-8).

**`conf/` lives at the repo root, outside the package.** `cli.py` therefore passes an *absolute*
`config_path=str(CONF_DIR)` to `@hydra.main`. A relative `config_path` will not work: Hydra
resolves it as a Python package path. `conf/` is not in the wheel — the tool runs from a checkout
via `uv run`. There are no `__init__.py` files; `conflict_sim` is an implicit namespace package.
`agent/` and `environment/` are real packages with `__init__.py`; `environment/__init__.py`
holds the `Environment` class. Config groups `conf/environment/office/` and
`conf/environment/org/` compose into `Config.environment` (`conf/company.yaml`).

**`models.py` holds the config schema, the conversation models and every phase-A IO schema
(A-1 done).** Everything extends `ValidatedModel` (`strict=True, extra="forbid", frozen=True`);
strict mode rejects string numbers and booleans, `int` → `float` is still accepted. Wiki models:
`Config · AgentSpec · Utterance · Decision · Thread`. Company models:
`Action` (kind + args, `ACTION_ARGUMENTS` says which args a kind needs), `TaskSpec`, `View`
(`TaskView · BlockedTask · Message · Unanswered · Rejected`), `Outcome` (`Received`), `Event`,
`MemoryRecord`, and nested `Config.environment: EnvironmentConfig{office: OfficeConfig(places),
org: OrgConfig(departments, titles→authority, tasks)}` / `Config.memory: MemoryConfig`.
`environment` is `None` for wiki runs; when set, `AgentSpec.department/title/reports_to` and
`TaskSpec.owner/depends_on` must resolve. `Expression` is the closed 8-label set with
`EXPRESSION_VALENCE`; `Decision` requires `expression · importance · valence · arousal`
(the v3 decide prompt asks for them). Plan §2-6 C parameters are flat
`Config` fields (`w_valence · w_structural · public_mult · w_arousal · stress_decay · mood_window ·
turns_per_tick · blocked_nudge_ticks · blocked_report_ticks · no_reply_ticks`) plus
`max_days · ticks_per_day`; all ticks are global (never reset at day end). `Config.n_agents` has
no upper bound; `settings.py` keeps its wiki-editor cap of 6. Mutable runtime state (`Task`,
`AgentState`, `Relationship`) is *not* here — it belongs to the owning package.

**`environment/` is the world the loop applies Actions to (A-5 done).** `Environment(config.
environment, config.agents)` wraps `office.Office` (places, `location{name→place}`, co-presence,
free seats of capped places) and `org.Org` (titles→authority, `manager{name→reports_to}`,
mutable `@dataclass Task` per `TaskSpec`: `owner · due · worked · done_tick · blocked_since ·
overdue · request`). `apply(actor, action, tick) -> Rejected | None` is the one validity check:
`_refusal` returns a reason string per kind (unknown place, full room, not my task, blocked by an
unfinished prerequisite, no desk here, no food here, alone / target not here for `talk`, no such
agent for `message · chat`, `report` only to my `reports_to`, `assign · approve · reject` need
the title's authority, `request` needs ownership and no pending request), `_perform` mutates only
`move · work · assign · request · approve · reject`; `talk · message · chat · report` change
nothing beyond that. A `place` on *any* kind means "go there first" (moving costs no tick, plan
§1-1): capacity is checked, the agent is moved, then the kind is judged where it now stands, and
`talk` co-presence is judged at the destination. One `work` = one tick of effort; `approve`
moves `due` to `max(due, tick) + remaining`.
`advance(tick)` sets `blocked_since` / `overdue` and returns `(task_id, "blocked" | "unblocked" |
"overdue")` pairs for the loop to log; `env_view(name) -> EnvView` (frozen dataclass: `place ·
present ids · TaskView tuple · BlockedTask tuple · resources`) reads `blocked_since`, so call
`advance` first each tick. `snapshot()` is plain dicts. Never imports `agent`, `llm`, `storage`
(a test greps for it). Config groups: `conf/environment/office/small.yaml` (5 places, meeting room
capacity 4) and `conf/environment/org/flat.yaml` (one manager, `spec` gates `api` and `ui`,
`docs` unowned for `assign`); `conf/company.yaml` composes them with 6 English personas.

**`conversation.py` (A-3, was `engine.py`) owns sessions; the loop owns ticks.**
`Session(id, kind, participants, thread, rng, instructions, rule, turns_per_tick, silence_limit,
max_utterances, on_update)` is config-agnostic and imports nothing from the config layer.
`step(tick)` runs the ordering rule (all judge → gate → post) up to `turns_per_tick` rounds and
returns that tick's decision events (the old `decisions.jsonl` rows plus a `session` key); rounds
stop early when nobody posted and nobody has a pending decision, because further rounds would be
identical. End conditions: `kind="talk"` (public) ends after `silence_limit` ticks without a post;
`kind="message"` (a live DM, private) ends after the first *round* nobody posts — the loop flips
the thread back to async; `max_utterances` ends either. `finished` holds the stop reason
(`silence · max_utterances`, or whatever the loop passes to `finish(reason)` at a phase end) and
`step` raises once it is set. `public` is derived from `kind`. A session may call only
`agent.decide(thread, instructions, seen=…)` and `agent.speak(thread, target, instructions,
seen=…)` and never assigns to an agent (the tests use a frozen scripted agent to prove it).
`outcomes() → {name: Outcome}` is rule-based (plan §1-7): `received` lists the `valence · arousal`
of every generated post that replied to or @-mentioned the participant, taken from the
`Decision` that produced it (`Session.axes`); seed posts carry no decision and count for nothing.
`refused · ignored · rebutted · opposed` stay empty — a conversation alone has no request
structure to derive them from; the loop fills them from Actions if it ever can.
`run(agents, thread, rule=, max_ticks=, silence_limit=, random_seed=, max_utterances=,
on_update=)` is the wiki wrapper: one `talk` session with `WIKI` instructions, one round per
tick, stepped `max_ticks` times from the seed's last timestamp + 1; `RunResult` is unchanged.
Bit-identical reproduction of old wiki output is **not** required on `master` — that is what the
`wiki` branch is for.

**Session instructions live in `conversation.py`, not `agent.py`.** `Instructions(decide, speak)`
comes in three flavours — `WIKI` (talk page, editor), `TALK` (co-present colleagues), `MESSAGE`
(private DM) — sharing one JSON field spec and reflection rules. `agent.py` no longer mentions
"Wikipedia" or "editor": the payload key is `speaker`, the system prefix is `You are <name>.
<persona>`, and the prompt kind is whatever the session passes in.

**`Participant.last_seen` is a count of utterances already read, not a tick.** It lets an agent
see a reply posted earlier in the same tick and makes `event_driven` and the `no_new_posts`
short-circuit correct. The session keeps pending positive-urge decisions (`Participant.pending`)
after a failed gate or lost bid and retries them without another LLM call when nothing new was
posted; inner rounds (`turns_per_tick`) re-draw the gate for pending decisions, which is what
makes a 15-minute tick hold several exchanges (plan §1-7). Both fields moved off `Agent`: the
agent gets `seen` as an argument and stays free of per-thread state.

**`agent/` is spec + state + memory + plan + intent methods (A-4 done).** `Agent(spec, config,
llm)` — the whole `Config` comes in, so prompt knobs, §2-6 weights and memory parameters are read
from it and tests vary them by building a `Config`. `agent/state.py`: mutable `AgentState(stress ·
mood · expression · relations{name → Relationship(relation · grievances · summary ·
last_interaction_tick)})` with the §1-7 arithmetic: `apply_outcome(outcome, cfg, tick)` returns the
relation delta per other (`w_valence · mean received valence − w_structural · [refused or
ignored]`, `× public_mult` when public; stress `+= w_arousal · Σ arousal + w_structural · [refused]`;
`rebutted`/`opposed` only create the relation entry — no weight for them in §2-6) and
`end_tick(recent_valences, cfg)` decays stress by `stress_decay` and sets mood to the mean valence
of records in the last `mood_window` ticks (0 when none). `agent/memory.py`: `MemoryStore` keeps
immutable `MemoryRecord`s in memory (`id = "<agent>:<n>"`, `self_relevance = 1` when I am a subject
or `about_my_task`), queues `pending_writes` and a `retrieval_log` that the loop `drain()`s once per
tick for `storage.py`; embeddings are the loop's (`pending_texts()` → `set_embeddings()`); `retrieve
(query, vector, tick, mood, k)` scores min-max-scaled recency (`recency_decay ^ (tick −
last_access)`) + importance + cosine relevance + `alpha_mood · |valence|` when mood and valence
share a sign, bumps `last_access` and logs `{tick, query, ids}`; `reflections(k)` is the wiki
`memory_mode` channel (`none | summary | full` → `k = 0 | 1 | None` over `type=reflection`
records); `due_reflection()` (cumulative importance of non-reflection records ≥
`reflect_threshold` — the trigger counts events perceived, not thoughts about them) and
`due_relation_reflections()` (a subject's cumulative valence ≤ `relation_reflect_threshold`)
trip `reflect(tick, mood, about=None)`: questions → per-question retrieval → `Insight`s stored as
`reflection` records citing `evidence` ids (unknown ids dropped); a relation reflection asks one
fixed question about that person. Only `reflect` calls the LLM here. `agent/agent.py`:
`plan_day(view, tick)` (one LLM call → `PlanItem` blocks + a `plan` record), `perceive(view,
tick)` (faces → `observation` records at `observation_importance` with the label's valence; inbox
messages → records with valence 0; no LLM), `act(view, tick)` (follows the current plan block
with no LLM call and `importance 1`; when `inbox · rejected · blocked · unanswered` is non-empty
or the plan is exhausted it asks the LLM with `{"view", "manager", "plan", "memories"}` and
records the reaction as an `action` record), `decide` (payload gains `memories`, the reflection
becomes a `reflection` record whose subjects are the unread speakers), `speak` (reuses the last
retrieval), `observe(...)` (the loop's hook for utterance records), `apply_outcome(outcome, tick)`
(state rule + a grievance `observation` record whose id goes on `Relationship.grievances`; returns
`outcome` event rows `{a, b, relation_delta, grievance}`), `end_tick(tick)` (state + reflections;
a relation reflection's first insight becomes `Relationship.summary`), `snapshot()`. Retrieval
embeds the query through `llm.embed` only when the store already has vectors — only the loop makes
them, so wiki runs never embed and never carry `memories`. `PROMPT_VERSION` stays `"3"`; the act
and plan instructions live here, session instructions in `conversation.py`.

**`persona_placement` decides where the persona text goes, not what it says.** `system`
(default since A-1) prefixes both instruction strings with `You are the editor <name>. <persona>`;
`payload` keeps the persona as a JSON field. Presets `gpt-luna` and `gpt-luna-irrational` pin
`payload` to stay reproducible; `conf/scenario/*` follow the default. `PROMPT_VERSION` is `"3"`
(A-2): the decide prompt asks for the four session fields and no longer tells the agent to
"revise earlier impressions" or that "prior impressions can be mistaken" — it keeps the concerns
that still matter.
Session-type instructions live in `conversation.py`; `agent/agent.py` does not hard-code
"Wikipedia talk-page" / "editor".

**Seed path resolution** (`cli.simulate`): `seed_file: null` uses the bundled
`conf/seeds/example.json`; other values resolve against `HydraConfig.runtime.cwd`. A seed holds
one or more utterances (`storage.parse_seed`, A-3): a session starts from its first utterance or
message, timestamps are the ticks those posts were made at, and the run continues from the last
one. `cga.extract_seeds` still writes two-utterance, tick-0 seeds; the editor validates through
the same `parse_seed`.

**`cga.extract_seeds` reads a local CGA corpus without importing ConvoKit.** Preserves matched
pairs within one split, excludes section headers, takes the chronological first two comments,
refuses existing output. Keep raw CGA data outside any `runs/**/corpus/` directory. Unchanged in A.

**LLM failure is never recorded as silence.** API errors, malformed decision JSON and truncated
replies raise `LLMError`/`ValueError`. In a wiki run `cli.simulate` turns them into
`SystemExit`; a failed run leaves Hydra logs but no corpus. In a company run an `LLMError`
pauses at the last day-end checkpoint instead (see *Checkpoint and resume*); a `ValueError`
still fails. `save_run` stages into a sibling temporary directory then renames to `corpus/`.
Scoring requires all corpus files and a completed stop reason; `max_days` is accepted since A-6.

**Two backends behind one `LanguageModel` protocol: `complete` and `embed` (A-2).**
`OpenAIBackend` wraps Chat Completions with JSON mode for decisions and the Embeddings API for
`embed` (`Config.model_embed`, optional — only memory retrieval embeds, so wiki runs and the old
presets leave it unset and `embed` raises `LLMError` if called without it), reads
`OPENAI_API_KEY` from the launch directory's `.env` at call time, accumulates usage per role
(`decide · speak · embed`) into `usage.json` / `run.json.llm_usage`, enforces `max_total_tokens`
(soft, may overshoot one response) and `max_input_chars` (hard, no truncation). `DemoBackend`
is rule-based and never an observation: `embed` is a sha256 → 32-dim unit vector, and
`complete` reads the prompt kind off the payload's **top-level keys** — this is the contract the
real prompts (A-4) must keep: `view` present → **act** (`{"view": View.model_dump(),
"manager": id | null, …}` → `Action` JSON); `tasks` present without `view` → **daily plan**
(`{"speaker", "day", "tick", "last_tick", "place", "places", "tasks": [TaskView…], …}` →
`{"plan": [PlanItem…]}`: move to the first desk/office, the two most urgent tasks split around a
one-tick lunch `eat` then a `talk` block at the food place — lunch starts at `first + (last + 1
− first) // 2`, the same tick as `loop.phase_of` — work until `last_tick`; the closing tick is
left unplanned so the end of the day is a judgement); `question` present →
reflection **insights** (one `Insight` citing the records about the person named in the question);
`records` present without `question` → reflection **questions** (one per person seen, most
negative first); `utterances` present → session **decide** (`json_mode=True`, replies to the last
utterance, `expression` from optional `stress`/`mood` keys) or **speak** (`json_mode=False`, one
fixed line). Act rules, in order:
`lunch` → `talk` when at a pantry/cafeteria with someone `present`, else `eat` there (`place`
set, so the environment moves the agent first); a `blocked` entry waited exactly
`blocked_report_ticks` → `report` to `manager` (skipped when null), exactly
`blocked_nudge_ticks` → `message` its `owner` (exact ticks, not ≥, so a stateless demo does not
spam every tick); else `work` on the earliest-due unfinished task that is not itself blocked;
else `rest`. `expression_for(stress, mood)` is the fixed band table, first row wins: stress ≥ 0.7
anxious · mood ≤ −0.6 angry · mood ≤ −0.3 annoyed · stress ≥ 0.4 tired · mood ≥ 0.5 amused ·
mood ≥ 0.2 pleased · else neutral; an act's `valence` is the label's table value and `arousal`
its magnitude. `llm.py` stays one file; no call cache in A (caching `temperature 0.8`
completions would collapse "3 runs per condition" into one).

**`dashboard.py` does not import the engine.** Live mode starts `python -m conflict_sim.cli` as
a subprocess with `live=true`; Streamlit polls `live.json` every 0.5 s. `settings.py` is the
named-settings editor over `conf/experiments/<name>/{config.yaml,seed.json}`; it shares
`storage.parse_seed` with the CLI, freezes a draft under `runs/live/<id>/inputs/` before launch,
and never starts generation on load/save. UI tests use Streamlit AppTest.
`settings.py` is **frozen** — wiki presets only; company scenarios are YAML, not edited in
the UI. Do not add new `AgentSpec` fields to the editor. `dashboard.py` changes come in C
(session picker, expression timeline, per-session CRAFT via Altair) and it still never imports the
engine; spatial replay is the Phaser viewer (B), which talks to the engine only over websocket.

**ConvoKit must be 3.x, and `torch` must be imported first.** 4.x's `forecaster/__init__.py`
hard-requires `unsloth` (NVIDIA/Intel GPUs only), so CRAFT cannot load on Apple Silicon. In 3.x
CRAFT is exported only when `"torch" in sys.modules`, so `score.forecast_corpus` imports torch
before anything from `convokit.forecaster`. `craft_tokenize` is the 2.x API and no longer exists.

**`score.py` reads finished corpora or live public snapshots and imports nothing from the
package.** Generation and measurement stay separate (design §6): the scorer can be swapped without
re-running, and no score feeds back into generation. `conflict-score --live RUN` builds an
in-memory corpus from public fields only. The optional `craft` integration test needs
`CONFLICT_CRAFT_INTEGRATION=1` and real cached weights.
Since A-6 one corpus holds many conversations (one per session) and `scores.json` carries
`sessions: {id: metrics}` + `summary` next to the whole-run `metrics`; `forecast_public` takes
`conversation_id` (default: the first row's id, the wiki live case).

**On-disk vs. in-memory field name:** ConvoKit's loader expects `reply-to` in
`utterances.jsonl`, while the Python models use `reply_to`. `save_run` renames on write.

## Ordering rules

`bidding` evaluates every agent against the same conversation snapshot, picks the single highest
`urge` (ties broken by the seeded RNG), then applies the probability gate — a loser of the gate
means *nobody* posts that round. `round_robin`, `random` and `event_driven` allow several posts
per round, and later agents immediately read earlier ones. `event_driven` reads the seed on its
first evaluation, then reacts to a direct reply, an exact `@name` mention, or a pending decision.
`random_seed` fixes only ordering and probability draws; real LLM responses stay non-deterministic.
A tick is 15 simulated minutes and `Session.step(tick)` repeats the rule `turns_per_tick`
times (talk 12, DM live 12; meeting 16 in C). `max_ticks`/`max_utterances` keep their meaning
inside the wiki wrapper.

## Scope

Wiki simulator: stages 1–5 of [docs/conflict-sim-design.md](docs/conflict-sim-design.md), private
reflection memory, pending-decision retries, persona placement, live scoring. Experiments so far
(`docs/*-experiment.md`, 2026-09-15): attacks appear only with `persona_placement: system`, and
CRAFT stayed below threshold — the rational-persona baseline with system placement is the control
for everything that follows. The bundled seed is handwritten English, not CGA data; demo output is
not evidence about conflict rates or LLM behaviour.

Company simulation: phase A complete (plan §6 items 1–8). Known gaps to close in C-13, not now:
the demo manager never `assign`s the unowned task; `Outcome.refused/ignored/rebutted/opposed`
are never filled; no overtime phase; no shock schedule (`Event.kind = "shock"` exists, nothing
emits it); `stress` rises only through outcomes (no deadline term); `dashboard.py` cannot show
a company run; a `chat` to a busy partner is refused rather than answered asynchronously.
