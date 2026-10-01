# C-16 Experiment Protocol

## Execution Order

1. Validate every scenario and print its call estimate with `--dry-run`.
2. Require both `ALLOW_PAID_API_EXPERIMENTS=1` and an API key.
3. Run one baseline pilot only: `--backend openai --pilot --replicates 1`.
4. Review JSON validity, token use, latency, deadlocks, starvation and session growth.
5. Only after pilot acceptance, run at most three replicates per declared condition.

The runner refuses paid execution without the approval flag, refuses non-pilot OpenAI execution,
refuses more than three replicates and refuses to overwrite a run directory.

## Reproducibility and Outputs

Each run records the resolved Pydantic config, current commit, seed, backend/model, estimated calls,
events, SQLite memory, per-tick frames, conversation corpus, final summary, token usage and status.
Frames contain relationship, task, stress and workload trajectories. Scenario, shock, evaluation,
intervention and overtime facts are in the event stream.

## Planned Scale

- Core conditions: S0-S4, three replicates each.
- Intervention comparisons: S1/I1, S2/I2 and S1/I3; execute only those needed by the final study.
- Two days per research run, 32 normal plus 2 possible overtime ticks per day.
- Conservative completion-call upper bound: about 1,400 per run before actual early/rest behavior.
- Pilot safety cap tested: `max_total_tokens=500000` for the 20-agent OpenAI runtime.

## Measurement Boundary

Generation completes before CRAFT scoring. `conflict-score <run>/corpus` is an observer pass and its
outputs are never copied into an agent prompt or termination rule. Per-session probability path,
maximum and first threshold crossing should be joined with descriptive event metrics. If local
CRAFT weights are absent, mark only that measurement pending; do not invalidate the simulation.

## Current Status

Demo dry-runs and the integration smoke pass. The approved real API pilot reached tick 5 before the
500k safety cap stopped it. This is a scaling diagnostic, not a completed experimental run. Paid
reruns remain paused until per-tick decision and embedding volume is reduced.
