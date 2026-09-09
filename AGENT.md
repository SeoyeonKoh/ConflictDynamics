# AGENT.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync --extra llm --extra dashboard    # always include llm; see gotcha below
uv run --extra llm --extra dashboard pytest        # full suite (90 tests)
uv run --extra llm pytest tests/test_engine.py::test_random_order_is_reproducible   # one test
uv run ruff check .
uv run conflict-sim                      # demo run, no API needed
uv run conflict-sim rule=random random_seed=12 max_ticks=6 hydra.run.dir=runs/demo
uv run conflict-sim --cfg job --resolve  # print the composed config without running
uv run conflict-sim -m rule=round_robin,bidding random_seed=7,42   # multirun sweep
uv run --extra dashboard streamlit run src/conflict_sim/dashboard.py   # browse past runs
```

**Gotcha:** plain `uv sync` *removes* the `llm` extra, and `tests/test_llm.py` (10 tests) then
silently skips on a missing `httpx` import — the suite reports success at a lower count.
`tests/test_dashboard.py` skips the same way without `--extra dashboard`.
Always sync and run with both extras.

**Known pre-existing failure:** `uv run ruff format --check .` fails on
`docs/conflict-sim-design.md` and `tests/test_llm.py`. Ruff 0.16 reformats Markdown code blocks,
and both files predate it. Unrelated to any current work — do not "fix" it as a side effect.

## Architecture

Flow: `conf/*.yaml` + CLI overrides → `cli.parse_config` → `Config` → `storage.load_seed` →
`engine.run` → `storage.save_run` → `runs/<date>/<time>/corpus/` in ConvoKit format.

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

**Seed path resolution** (`cli.main`): `seed_file: null` uses the bundled
`conf/seeds/example.json`; any other value resolves against `HydraConfig.runtime.cwd`, i.e. the
directory the command was launched from — which survives `hydra.job.chdir=true`. Seeds must hold
exactly the first two utterances with both timestamps normalized to 0.

**LLM failure is never recorded as silence.** API errors, malformed decision JSON, and truncated
replies raise `LLMError`/`ValueError`, which `cli.main` turns into `SystemExit`. A failed run
leaves Hydra logs but writes no corpus. `save_run` uses `mkdir(exist_ok=False)`, so an existing
`corpus/` aborts rather than being overwritten.

**Two backends behind one `LanguageModel` protocol.** `DemoBackend` returns scripted text with no
network; `OpenAIBackend` wraps Chat Completions and uses JSON mode for decisions. `Config`
requires `model_decide`/`model_speak` only when `backend: openai`; `cli.py` substitutes `"demo"`
otherwise. `OPENAI_API_KEY` is read from the launch directory's `.env` at call time, never from
Hydra config, so it stays out of run metadata.

**`dashboard.py` imports nothing from the package.** It is a read-only consumer of
`runs/*/corpus/`, reading only `run.json`, `utterances.jsonl`, and `decisions.jsonl`. Keep it
that way: it must never import the engine or trigger a run. Its pure functions
(`discover_runs`, `load_run`, `reply_depth`) are the tested part; the `st.*` layout is not.

**On-disk vs. in-memory field name:** ConvoKit's loader expects `reply-to` in
`utterances.jsonl`, while the Python models use `reply_to`. `save_run` renames on write.

## Ordering rules

`bidding` evaluates every agent against the same conversation snapshot, picks the single highest
`urge` (ties broken by the seeded RNG), then applies the probability gate — a loser of the gate
means *nobody* posts that tick; no runner-up is chosen. The other three rules allow several posts
per tick, and later agents immediately read earlier ones. `event_driven` reads the seed on its
first evaluation, then only reacts to a direct reply or an exact `@name` mention.

`max_ticks` caps ticks, not generated utterances. `random_seed` fixes only the engine's ordering
and probability draws; real LLM responses stay non-deterministic.

## Scope

Only stages 1–2 of [docs/conflict-sim-design.md](docs/conflict-sim-design.md) are built.
CRAFT scoring, `craft_tokenize`, real CGA seed extraction, and statistical analysis of ablations
are explicitly out of scope and planned as a separate stage that reads generation logs only.
The bundled seed is handwritten English, not extracted CGA data — demo output is not evidence
about conflict rates or LLM behavior.
