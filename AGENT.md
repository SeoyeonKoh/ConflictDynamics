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
uv run --extra llm pytest tests/test_engine.py::test_random_order_is_reproducible   # one test
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
`engine.run` → `storage.save_run` → `runs/<date>/<time>/corpus/` in ConvoKit format.
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

**`models.py` holds the config schema *and* the conversation models.** `Config`, `AgentSpec`,
`Utterance`, `Decision` extend `ValidatedModel` (`strict=True, extra="forbid", frozen=True`).
Strict mode rejects string numbers and booleans; `int` → `float` is still accepted.
`Config.n_agents` is capped at 3–6 and `settings.py` mirrors the cap.
*A:* the cap goes; every new schema (`Action`, `View`, `Task`, `MemoryRecord`, `Relationship`,
nested `EnvironmentConfig`/`MemoryConfig`) is added here and nowhere else.

**`engine.run` is deliberately config-agnostic.** It takes `rule`, `max_ticks`, `silence_limit`,
`random_seed` as keyword scalars and imports nothing from the config layer. It owns the whole tick
loop, the RNG, pending decisions and the silence counter inside one function.
*A:* this becomes `conversation.Session.step(tick)` so `loop.py` can advance several sessions in
one tick; `run()` remains as a thin wrapper that steps one session `max_ticks` times for the wiki
demo smoke test. Bit-identical reproduction of old wiki output is **not** required on `master` —
that is what the `wiki` branch is for.

**`Agent.last_seen` is a count of utterances already read, not a tick.** It lets an agent see a
reply posted earlier in the same tick and makes `event_driven` and the `no_new_posts`
short-circuit correct. The engine keeps pending positive-urge decisions after a failed gate or lost
bid and retries them without another LLM call when nothing new was posted.
*A:* unchanged — this is exactly what makes `turns_per_tick` inner rounds work (plan §1-7).

**Private memory lives in `Agent.reflections`, a list of strings.** Each `decide` response
requires `reflection` alongside `urge` and `reply_to`. `memory_mode=none|summary|full` decides
what is fed back; `summary` passes the latest *cumulative* reflection, not the latest observation.
*A:* replaced by `agent/memory.py` (memory stream + top-k retrieval + reflection tree, plan §2).
The three modes survive as `k = 0 | 1 | ∞` over `type=reflection` records for config
compatibility. `decide` additionally returns `expression` and `importance · valence · arousal`.

**`persona_placement` decides where the persona text goes, not what it says.** `payload`
(current default) keeps the persona as a JSON field; `system` prefixes both instruction strings
with `You are the editor <name>. <persona>`. `PROMPT_VERSION` is `"2"`.
*A:* default flips to `system` and the "revise earlier impressions / prior impressions can be
mistaken" guidance is softened → `PROMPT_VERSION 3`. Presets `gpt-luna` and `gpt-luna-irrational`
and `conf/scenario/*` do not set the field, so pin `persona_placement: payload` in the two old
presets before flipping the default. Session-type instructions live in `conversation.py`;
`agent.py` does not hard-code "Wikipedia talk-page" / "editor".

**Seed path resolution** (`cli.simulate`): `seed_file: null` uses the bundled
`conf/seeds/example.json`; other values resolve against `HydraConfig.runtime.cwd`. Seeds must hold
exactly the first two utterances with both timestamps normalized to 0 (`storage.parse_seed`).
*A:* company sessions start from their first utterance or message; the two-utterance rule applies
only to wiki seeds.

**`cga.extract_seeds` reads a local CGA corpus without importing ConvoKit.** Preserves matched
pairs within one split, excludes section headers, takes the chronological first two comments,
refuses existing output. Keep raw CGA data outside any `runs/**/corpus/` directory. Unchanged in A.

**LLM failure is never recorded as silence.** API errors, malformed decision JSON and truncated
replies raise `LLMError`/`ValueError`, which `cli.simulate` turns into `SystemExit`; a failed run
leaves Hydra logs but no corpus. `save_run` stages into a sibling temporary directory then renames
to `corpus/`. Scoring requires all corpus files and a completed stop reason.
*A:* `stop_reason` gains `max_days`; `score.completed_corpus`'s whitelist must accept it.
*B:* budget exhaustion checkpoints and exits `paused` instead of failing.

**Two backends behind one `LanguageModel` protocol.** `DemoBackend` returns scripted text;
`OpenAIBackend` wraps Chat Completions with JSON mode for decisions, reads `OPENAI_API_KEY` from
the launch directory's `.env` at call time, accumulates usage per role into `usage.json` /
`run.json.llm_usage`, enforces `max_total_tokens` (soft, may overshoot one response) and
`max_input_chars` (hard, no truncation). `DemoBackend` currently assumes
`payload["utterances"][-1]["id"]` exists — any payload change breaks it and the tests first.
*A:* protocol gains `embed(texts)`; demo returns deterministic hash vectors and rule-based
Actions/expressions/plans. `llm.py` stays one file; no call cache in A (caching `temperature 0.8`
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
