# AGENT.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Complete relevant verification and commit after each finished user-requested work unit.
Keep implementation consistent with the existing readable, minimal style.
Commit messages carry no `Co-Authored-By` or other AI attribution trailer.

## Status and direction

`master` is at the start of **phase A: the company simulation engine**. The code on disk is still
the Wikipedia talk-page simulator described under *Current code* below; nothing from the plan has
been built yet. The wiki simulator as it stood at the fork is preserved on branch `wiki`
(tag `wiki-fork`, commit `76d6e9e`). Wiki-direction research happens there; `master` never merges
from `wiki`. Shared improvements go `master` → `wiki` by cherry-pick.

The design source of truth is [docs/company-world-plan.md](docs/company-world-plan.md). Decisions
recorded there are settled — do not reopen them in code: English only; CRAFT scored per session;
`persona_placement: system` becomes the default; no deliberately irrational personas (conflict
comes from structure: scarce resources, zero-sum rewards, dependency failure, partial observation);
memory nested under `agent/`; one `environment/` package; websocket between engine and the Phaser
viewer; order A engine → B persona test → C visualisation.

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

Milestone A: the demo backend runs 6 agents × 1 day (32 ticks of 15 min) end to end and writes
`corpus/`, `events.jsonl`, `memory.sqlite`, `scores.json`; the wiki presets still run as a demo
smoke test through `conversation.run()`.

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
- Deferred to B, do not build in A: checkpoint/resume, embed cache, parallel LLM calls, manager-LLM
  task generation (A uses the scenario's static task list), meeting turn-taking, private/gossip
  sessions, hearsay, forgetting, KPI/promotion slots, interventions.
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
uv run conflict-sim                      # demo run, no API needed
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

## Current code (wiki simulator, pre-A)

Flow: `conf/*.yaml` + CLI overrides → `cli.parse_config` → `Config` → `storage.load_seed` →
`conversation.run` → `storage.save_run` → `runs/<date>/<time>/corpus/` in ConvoKit format.
`cli.main` installs the mandatory `ProtectOutput` Hydra callback and calls `cli.simulate`.
The callback reserves run/sweep roots using `.run.lock` before Hydra writes configuration or logs.
Only empty directories or the live UI's console.log-only directory may be claimed. Failed roots
remain reserved. Sweeps require `${hydra.job.num}` subdirectories to prevent job-path collisions.
*A:* `loop.py` takes over orchestration; `ProtectOutput` stays. Resume (B) will need an exception
to the "empty directory" rule.

**`conf/` lives at the repo root, outside the package.** `cli.py` therefore passes an *absolute*
`config_path=str(CONF_DIR)` to `@hydra.main`. A relative `config_path` will not work: Hydra
resolves it as a Python package path. `conf/` is not in the wheel — the tool runs from a checkout
via `uv run`. There are no `__init__.py` files; `conflict_sim` is an implicit namespace package.
*A:* `agent/` and `environment/` get real `__init__.py` files; `environment/__init__.py` holds the
`Environment` class. Config groups `conf/environment/office/` and `conf/environment/org/` compose
into `Config.environment`.

**`models.py` holds the config schema, the conversation models and every phase-A IO schema
(A-1 done).** Everything extends `ValidatedModel` (`strict=True, extra="forbid", frozen=True`);
strict mode rejects string numbers and booleans, `int` → `float` is still accepted. Wiki models:
`Config · AgentSpec · Utterance · Decision · Thread`. Company models, none consumed yet:
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
nothing. One `work` = one tick of effort; `approve` moves `due` to `max(due, tick) + remaining`.
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
records); `due_reflection()` (cumulative importance ≥ `reflect_threshold`) and
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
*A:* Session-type instructions live in `conversation.py`; `agent.py` does not hard-code
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
replies raise `LLMError`/`ValueError`, which `cli.simulate` turns into `SystemExit`; a failed run
leaves Hydra logs but no corpus. `save_run` stages into a sibling temporary directory then renames
to `corpus/`. Scoring requires all corpus files and a completed stop reason.
*A:* `stop_reason` gains `max_days`; `score.completed_corpus`'s whitelist must accept it.
*B:* budget exhaustion checkpoints and exits `paused` instead of failing.

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
lunch `eat` block at mid-day, `rest` "Wrap up" ending at `last_tick + 1`); `question` present →
reflection **insights** (one `Insight` citing the records about the person named in the question);
`records` present without `question` → reflection **questions** (one per person seen, most
negative first); `utterances` present → session **decide** (`json_mode=True`, replies to the last
utterance, `expression` from optional `stress`/`mood` keys) or **speak** (`json_mode=False`, one
fixed line). Act rules, in order:
`lunch` → `talk` if anyone is `present` else `eat`; a `blocked` entry waited exactly
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
*A:* `settings.py` is **frozen** — wiki presets only; company scenarios are YAML, not edited in
the UI. Do not add new `AgentSpec` fields to the editor. `dashboard.py` changes come in B
(session picker, expression timeline, per-session CRAFT via Altair) and it still never imports the
engine; spatial replay is the Phaser viewer (C), which talks to the engine only over websocket.

**ConvoKit must be 3.x, and `torch` must be imported first.** 4.x's `forecaster/__init__.py`
hard-requires `unsloth` (NVIDIA/Intel GPUs only), so CRAFT cannot load on Apple Silicon. In 3.x
CRAFT is exported only when `"torch" in sys.modules`, so `score.forecast_corpus` imports torch
before anything from `convokit.forecaster`. `craft_tokenize` is the 2.x API and no longer exists.

**`score.py` reads finished corpora or live public snapshots and imports nothing from the
package.** Generation and measurement stay separate (design §6): the scorer can be swapped without
re-running, and no score feeds back into generation. `conflict-score --live RUN` builds an
in-memory corpus from public fields only. The optional `craft` integration test needs
`CONFLICT_CRAFT_INTEGRATION=1` and real cached weights.
*A:* one corpus holds many conversations (one per session); `forecast` splits series per
conversation and `scores.json` gains `sessions: {id: metrics}` + `summary`. `forecast_public`
must stop assuming `rows[0]["id"]` is the conversation id.

**On-disk vs. in-memory field name:** ConvoKit's loader expects `reply-to` in
`utterances.jsonl`, while the Python models use `reply_to`. `save_run` renames on write.

## Ordering rules

`bidding` evaluates every agent against the same conversation snapshot, picks the single highest
`urge` (ties broken by the seeded RNG), then applies the probability gate — a loser of the gate
means *nobody* posts that round. `round_robin`, `random` and `event_driven` allow several posts
per round, and later agents immediately read earlier ones. `event_driven` reads the seed on its
first evaluation, then reacts to a direct reply, an exact `@name` mention, or a pending decision.
`random_seed` fixes only ordering and probability draws; real LLM responses stay non-deterministic.
*A:* a tick is 15 simulated minutes and `Session.step(tick)` repeats the rule `turns_per_tick`
times (talk 12, DM live 12, meeting 16 in B). `max_ticks`/`max_utterances` keep their meaning
inside the wiki wrapper.

## Scope

Wiki simulator: stages 1–5 of [docs/conflict-sim-design.md](docs/conflict-sim-design.md), private
reflection memory, pending-decision retries, persona placement, live scoring. Experiments so far
(`docs/*-experiment.md`, 2026-09-15): attacks appear only with `persona_placement: system`, and
CRAFT stayed below threshold — the rational-persona baseline with system placement is the control
for everything that follows. The bundled seed is handwritten English, not CGA data; demo output is
not evidence about conflict rates or LLM behaviour.

Company simulation: nothing built yet. Phase A tasks are plan §6 items 1–7.
