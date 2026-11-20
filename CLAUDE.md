# CLAUDE.md

Instructions for Claude Code in this repository.

- `AGENT.md` (tracked): the project's settled design, commands, current code map and history.
  Read it before changing engine behaviour.
- `AGENTS.md` (local, gitignored, kept by graft): how to explore the code with graft. Its
  `<!-- graft:start --> ... <!-- graft:end -->` block is generated: never edit it. It also
  repeats the operating rules below for other agents.
- `README.md`: user-facing commands and options, in Korean.

## Claude-specific notes

- Commit messages carry no `Co-Authored-By` or other AI attribution trailer (`AGENT.md`).
- Sync with `uv sync --all-extras`: plain `uv sync` drops the `llm` extra and `tests/test_llm.py`
  then skips silently.
- `uv run --all-extras pytest` currently has 7 known failures in `tests/test_generator.py` and
  `tests/test_runs.py::test_generated_scenarios_appear_in_the_catalog`. They come from a
  generated scenario left in `conf/` and are not caused by run or LLM changes. Any other
  failure is new.
- For UI work, check the rendered pages in the Orca browser: open a **new** tab, and never take
  over a tab the user is watching. A live viewer (`/view.html?live=...`) belongs to a running
  experiment.
- Paid runs and anything that stops, restarts or resumes someone else's run need the user's
  go-ahead first.

## Running experiments — operating rules

**Cost guard (never bypass).**
- Paid backends (`openai`, `claude`) refuse to run without `ALLOW_PAID_API_EXPERIMENTS=1`.
- By default a paid backend gets one `--pilot` run per scenario. More (1-100 replicates) needs
  `--allow-repeated` *and* that variable.
- Always set `--max-total-tokens` (about 3,000,000 for a one-day r10 run).
- Get the user's cost approval before starting a paid run; dry-run first:
  `conflict-company-experiment ... --dry-run` prints each run's resolved config and estimated
  calls.

**OpenAI Flex (default on).**
- Calls go out with `service_tier="flex"` (half price, up to 900 s a request, SDK retries off).
- 429s are told apart:
  - a per-minute TPM/RPM limit is waited out on Flex;
  - Flex out of capacity falls back to standard processing after 2 refusals, or with
    `flex_fallback=false` / `--no-flex-fallback` waits with backoff (cap 60 s, 240 tries);
  - `insufficient_quota` stops the run.
- Off: `flex=false` (Hydra) or `--no-flex`.
- Use `--no-flex` for live debugging; use Flex with `--no-flex-fallback` for unattended batches.

**Batches in one process.**
- `conflict-company-experiment --scenarios A B C --parallel-runs N --max-in-flight M
  --replicates R` runs replicate-major (A, B, C, A, B, C, ...).
- All runs share one `SharedRateGate`: at most M calls in flight across all runs, and a 429 in
  one run holds all of them off.
- `--resume` with the same command:
  - skips finished runs, continues paused ones, starts missing ones;
  - re-applies `--flex`, `--no-flex-fallback`, `--workers`, `--max-total-tokens` and
    `--claude-max-concurrent` (models and prompts replay from `tape.sqlite`);
  - pass those flags again on every resume; `resolved_config.json` keeps the original values.

**Stopping a run.**
- Send SIGTERM (or one Ctrl+C) to the batch process.
- Every run leaves its Flex/429 wait at once and writes `paused.json` (an HTTP request already
  in flight still finishes).
- A second Ctrl+C exits immediately (code 130).
- Do not SIGKILL unless you must. After a kill:
  1. write `paused.json` (`{"status": "paused", "reason": "stopped", "tick": <last frame tick
     + 1>, "checkpoint": null}`);
  2. set `manifest.json` `status` to `"paused"`;
  3. then `--resume`.
- Never stop or restart a run, `conflict-server` (:8780) or a live stream you did not start
  unless the user asks.

**Checking results.**
- `python -m conflict_sim.run_summary <run_dir> [--format json|md] [--out PATH]` prints the
  same metrics as `/summary.html?run=<run>`.
- The `md` output is meant to be pasted into an agent prompt.
- The live viewer shows tokens spent against `max_total_tokens`.

**Prompts and caching.** OpenAI caches a byte-identical prefix of 1,024+ tokens. Keep prompts
in their layers:
1. what every agent shares (`PERSONA_ANCHOR`, norms, speech rules, the full roster);
2. the call's head;
3. the persona card;
4. the user message, which holds everything that changes tick to tick.

Never put per-tick data into the system text. Memory prompts must use
`json.dumps(..., ensure_ascii=False)`; escaped Korean costs about 2.4x the tokens.
