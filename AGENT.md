# AGENT.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Complete relevant verification and commit after each finished user-requested work unit.
Keep implementation consistent with the existing readable, minimal style.

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

## Architecture

Flow: `conf/*.yaml` + CLI overrides → `cli.parse_config` → `Config` → `storage.load_seed` →
`engine.run` → `storage.save_run` → `runs/<date>/<time>/corpus/` in ConvoKit format.
`cli.main` installs the mandatory `ProtectOutput` Hydra callback and calls `cli.simulate`.
The callback reserves run/sweep roots using `.run.lock` before Hydra writes configuration or logs.
Only empty directories or the live UI's console.log-only directory may be claimed. Failed roots
remain reserved. Sweeps require `${hydra.job.num}` subdirectories to prevent job-path collisions.

**`conf/` lives at the repo root, outside the package.** `cli.py` therefore passes an *absolute*
`config_path=str(CONF_DIR)` to `@hydra.main`. A relative `config_path` will not work: Hydra
resolves it as a Python package path, so `"../../conf"` becomes a top-level module `conf` and
demands an `__init__.py`. As a consequence `conf/` is not in the wheel — the tool is meant to run
from a checkout via `uv run`. There are no `__init__.py` files at all; `conflict_sim` is an
implicit namespace package.

**`models.py` holds the config schema *and* the conversation models.** All four
(`Config`, `AgentSpec`, `Utterance`, `Decision`) extend `ValidatedModel`
(`strict=True, extra="forbid", frozen=True`). Strict mode rejects string numbers and booleans
where a number is expected; `int` → `float` is still accepted, so `temperature=1` works.

**`engine.run` is deliberately config-agnostic.** It takes `rule`, `max_ticks`, `silence_limit`,
`random_seed` as keyword scalars and imports nothing from the config layer. Agent count (3–6),
name uniqueness, and availability range are invariants guaranteed by `Config.check_relationships`
and are *not* re-checked in the engine — if you add a caller that bypasses `Config`, it owns
those checks.

**`Agent.last_seen` is a count of utterances already read, not a tick.** This is what lets an
agent see a reply posted earlier in the same tick, and what makes `event_driven` and the
`no_new_posts` short-circuit correct. Treat it as an index into `Thread.utterances`.
The engine separately keeps pending positive-urge decisions after a failed gate or lost bid.
Without new posts it retries those decisions without another LLM call. New posts refresh them;
a successful post or a new zero urge clears them. Pending decisions do not bypass silence limits.

**Private memory lives in `Agent.reflections`, a list of strings.** Each valid `decide` response
requires `reflection` alongside `urge` and `reply_to`, even at zero urge. Append only on a new
decision. `memory_mode=none` still asks for and logs a reflection but passes an empty
`private_memory`, isolating the model from the memory loop; `summary` passes the latest cumulative reflection to `decide` and `speak`;
`full` passes the whole history. Never add a memory manager or separate summarization call.
Memory is not an utterance or another agent's input. Run schema and prompt version 2 record
the change; decision logs distinguish `new` from `retry` and retain the original `decision_tick`.

**Seed path resolution** (`cli.simulate`): `seed_file: null` uses the bundled
`conf/seeds/example.json`; any other value resolves against `HydraConfig.runtime.cwd`, i.e. the
directory the command was launched from — which survives `hydra.job.chdir=true`. Seeds must hold
exactly the first two utterances with both timestamps normalized to 0.

**`cga.extract_seeds` reads a local CGA corpus without importing ConvoKit.** It preserves
matched pairs within one split (default `train`), excludes section headers, and takes the
chronological first two comments. The second must already reply to the first; never reparent
it or substitute later comments. An unsuitable conversation excludes its entire pair, with
reasons in `manifest.json`. Normalize only the seed root and simulation timestamps, retain
original parent/time metadata, and convert CGA's missing-parent NaN to JSON null. Original
outcomes stay outside utterances and must never enter agent prompts. Existing output is refused.
Keep raw CGA data outside a directory named `corpus/` under `runs/`, so `conflict-score --all`
cannot mistake it for one completed simulation. Seed extraction tests share `test_storage.py`.

**LLM failure is never recorded as silence.** API errors, malformed decision JSON, and truncated
replies raise `LLMError`/`ValueError`, which `cli.simulate` turns into `SystemExit`. A failed run
leaves Hydra logs but writes no corpus. `save_run` writes every file to a sibling temporary
directory, then renames it to `corpus/`; existing output is refused and failed staging is cleaned.
New run metadata includes `status: completed`. Scoring requires all corpus files and a completed
stop reason, with missing status accepted for legacy normal runs. Failed scoring returns nonzero,
continues other batch targets, and leaves previous scores intact.

**Two backends behind one `LanguageModel` protocol.** `DemoBackend` returns scripted text with no
network; `OpenAIBackend` wraps Chat Completions and uses JSON mode for decisions. `Config`
requires `model_decide`/`model_speak` only when `backend: openai`; `cli.py` substitutes `"demo"`
otherwise. `OPENAI_API_KEY` is read from the launch directory's `.env` at call time, never from
Hydra config, so it stays out of run metadata.
The shipped YAML selects `gpt-5.6-luna` for both roles and `reasoning_effort: none`; demo remains
the default backend. `OpenAIBackend` passes an explicitly configured effort, omitting it when
null for older models. API model IDs and usage counters go into Hydra's `cli.log`, without
prompts or credentials. Preserve usage details so cached and reasoning tokens can be inspected.
`max_tokens_decide`/`max_tokens_speak` are sent as `max_completion_tokens`. Reported input/output
usage is accumulated per role, including truncated responses, and saved to `usage.json` even on
failure and to completed `run.json.llm_usage`. `max_total_tokens` blocks the next call once reached;
it can overshoot by one response and is not a hard billing cap. `max_input_chars` rejects oversized
system+prompt input before a call, without silently truncating full memory. Missing response usage
fails the run rather than disabling budget checks.

**`dashboard.py` does not import the engine.** Live mode starts `python -m conflict_sim.cli`
as a subprocess with Hydra overrides and `live=true`; Streamlit polls `live.json` every 0.5s.
The CLI atomically replaces progress snapshots before API calls and after decisions/posts,
using the engine's optional observation callback. Normal CLI runs skip this work. Live demo
updates pause 0.2s for visibility; OpenAI calls get no artificial delay. A failed or stopped
run retains its partial live snapshot, but is not saved as a completed corpus. Stop terminates
the child process; closing a browser tab does not. Keep the launch process in session state
so UI reruns do not start duplicate runs. Do not add a second scheduler or a service layer.
Saved-run mode still reads corpus files; old logs without reflection/source fields must open.
UI tests use Streamlit AppTest and clear its shared cache between fixtures. Average urge counts
new decisions only. Private reflections are shown to the observer, never added to public utterances.
`settings.py` owns editing and named settings. Load a preset, a saved YAML/seed bundle, or a run's
archived config and seed. Keep the original separate from the current draft for the diff; retain
widget values when editing is disabled during a run. `storage.parse_seed` is shared with file
loading so the editor cannot save a seed the CLI rejects. Saved `conf/experiments/<name>/` folders
contain a full config and seed, published together without overwriting. Editor text is literal,
including Hydra interpolation syntax. Changes to seed speakers/text mark the seed `edited: true`.
Before live launch, freeze the draft in `runs/live/<id>/inputs/` and let the existing CLI reserve
the sibling `run/` output folder. Loading/saving never starts generation; old run layouts still load.
Cache stamps must not start with `_` (Streamlit excludes such arguments from keys). Discovery
stamps include nested run.json paths and file metadata; run details stamp all input files.
Measurements reads scores.json on rerun, shows CRAFT curves/crossings, and counts generated-post
share excluding seeds. Score series must match the public corpus IDs in order.
Scenario presets use existing Hydra groups in conf/scenario with matching synthetic seeds.
The UI previews their public seed and participant stances before launching the same CLI.
AgentSpec.stance is an optional observer label, never an LLM input. Old logs fall back to persona.
Replay filters public posts and decisions through the selected completed tick. Keep future
reflections hidden, preserve the slider position across control reruns, and stop at the last tick.
The auto-scoring toggle owns one separate scoring process. Turning it off stops only scoring.
Failed attempts stay failed until toggled off/on; reruns must not repeatedly launch a worker.

**ConvoKit must be 3.x, and `torch` must be imported first.** ConvoKit 4.x's
`forecaster/__init__.py` eagerly imports `TransformerDecoderModel`, which hard-requires
`unsloth` — NVIDIA and Intel GPUs only — so CRAFT cannot load at all on Apple Silicon.
Stubbing the missing modules works only for some import orders and is not worth keeping.
In 3.x that same `__init__` exports CRAFT only when `"torch" in sys.modules`, so
`score.forecast_corpus` imports torch before anything from `convokit.forecaster`.
Note that `craft_tokenize`, which the design document requires in 6.2, exists in neither
3.x nor 4.x — it is the ConvoKit 2.x API, and the modern Forecaster tokenises internally.

**`score.py` reads finished corpora or live public snapshots.** Generation
and measurement stay separate on purpose (design 6): the scorer can be swapped without
re-running a simulation, and no score can feed back into generation. `derive_metrics` and score
publication are covered by unit tests. The optional `craft` test uses real cached weights,
records the context entering real tokenization, checks every prefix in corpus order, and verifies
one valid score per utterance plus persisted scores.json. Only model asset lookup is redirected
to the local cache. Enable with `CONFLICT_CRAFT_INTEGRATION=1` and use the same torch / convokit
facade / CRAFTModel import order as production.
`conflict-score --live RUN` loads one model, polls live.json, and scores only changed public
utterances. It builds an in-memory ConvoKit corpus from explicit public fields, not decisions or
personas. Newest-prefix scoring is serial; it must not build an unbounded queue behind generation.
live-scores.json holds partial scores. Only a normal completion matching the saved corpus may
publish scores.json. Stopped/failed runs never become completed corpora or final score reports.

**On-disk vs. in-memory field name:** ConvoKit's loader expects `reply-to` in
`utterances.jsonl`, while the Python models use `reply_to`. `save_run` renames on write.

## Ordering rules

`bidding` evaluates every agent against the same conversation snapshot, picks the single highest
`urge` (ties broken by the seeded RNG), then applies the probability gate — a loser of the gate
means *nobody* posts that tick; no runner-up is chosen. The other three rules allow several posts
per tick, and later agents immediately read earlier ones. `event_driven` reads the seed on its
first evaluation, then reacts to a direct reply, an exact `@name` mention, or a pending decision.

`max_ticks` caps ticks, not generated utterances. `random_seed` fixes only the engine's ordering
and probability draws; real LLM responses stay non-deterministic.
`max_utterances` optionally caps generated posts (excluding the seed), including in the middle
of a multi-post tick. Compare rules at common post counts and account separately for early silence.

## Scope

Stages 1–5 of [docs/conflict-sim-design.md](docs/conflict-sim-design.md), private reflection memory,
and pending-decision retries are built. CGA format and one seed pair's CRAFT preprocessing were
checked with ConvoKit 3.5. Topic-specific personas, validation-set threshold calibration, and
statistical analysis of ablations remain future work. Scoring reads public generation logs only.
The bundled seed is handwritten English, not extracted CGA data — demo output is not evidence
about conflict rates or LLM behavior.
