# H3 Retrieval Embedding Cache

Date: 2026-10-05. Implementation baseline: local commit `c620905` (phase 2).
Scope: exact retrieval query embedding reuse only. No paid API calls, CRAFT scoring,
research-condition runs, prompt pruning, retry changes or simulation-rule changes.

## Why

Phase 2 observed 193 retrieval queries, 82 unique model/text keys and 111 exact
duplicates (57.51%). Within-agent duplicates accounted for 18.65% of all queries;
sharing a cache between agents offers additional reuse. These figures describe a
scripted smoke, not a measured OpenAI token or cost saving.

## Implementation

### Existing behavior verified from call sites

- `Agent._recall` in `src/conflict_sim/agent/agent.py` embeds a query and then calls
  `MemoryStore.retrieve` with the current tick, mood and configured top-k.
- `MemoryStore.reflect` in `src/conflict_sim/agent/memory.py` also embeds reflection
  questions before retrieving current evidence.
- `Loop._embed` in `src/conflict_sim/loop.py` batches new memory descriptions across
  agents. It is a memory-write operation, not a retrieval operation.
- The CLI already wraps its backend with `EmbedCache` when `cfg.embed_cache` is set.
  That existing wrapper caches both writes and retrieval queries; retrieval was
  not excluded. C16 `experiment.run_scenario` previously did not wrap its backend.
- Existing keys are SHA-256 of `model + newline + exact text`; no whitespace
  normalization or semantic similarity is applied. OpenAI keys use `model_embed`.

### Small integration

`EmbedCache` now accepts an optional `call_types` allowlist. Its default remains
the existing all-embedding behavior, preserving the CLI. C16 uses the allowlist
`memory_retrieval_embedding` and `reflection_retrieval_embedding`, obtained from
the existing ContextVar operation scopes. Missing/other scopes bypass the cache.
Memory-write batches therefore still reach the original backend unchanged.

`experiment.retrieval_cached_backend` is the shared production/comparison helper.
New C16 runs enable retrieval reuse by default. `retrieval_cache=False` or the CLI
flag `--no-retrieval-cache` disables it. The cache is shared by the run's agents.
By default it lives at `<run_dir>/retrieval_cache.sqlite`; an explicitly configured
`cfg.embed_cache` instead selects the existing shared path relative to launch cwd.
Enabled state, absolute cache path, call types and key policy are saved in the
manifest. Resume preserves that policy; manifests predating this change resume
with cache OFF. The database is closed after judgement threads have stopped.

Only the query vector is reused. Every caller still executes `MemoryStore.retrieve`:
current records, vectors, recency, importance, mood, ranking, selected IDs and
`last_access` updates are computed anew. No retrieval result is cached. No change
was made to `agent.py`, `memory.py`, `loop.py`, prompts or H1/H2 algorithms.

Existing audit records distinguish logical query lookups (`embedding_cache`,
`call_count=0`, hits/misses) from actual backend computations (`embedding`).
Only backend computations consume the backend's usage/budget counters.

## Before / After

Primary paired run uses the existing `s0_smoke` fixture: 20 agents, 32 ticks,
seed 1413, **workers=4**, unchanged DemoBackend and otherwise identical config.
Each condition starts independently; Cache ON begins with an empty database.
The comparison script records requests before forwarding them unchanged.

| Metric | Baseline OFF | Cache ON | Change |
| --- | ---: | ---: | ---: |
| Logical retrieval query texts | 193 | 193 | 0 |
| Retrieval embedding requests | 193 | 91 | -102 (-52.85%) |
| Retrieval embedding texts computed | 193 | 91 | -102 (-52.85%) |
| Cache lookups | 0 | 193 | +193 |
| Cache hits | 0 | 102 | +102 |
| Cache misses | N/A (no lookup) | 91 | N/A |
| Duplicate computations avoided | 0 | 102 | +102 |
| Cache hit rate | N/A | 52.85% | N/A |
| Memory-write embedding requests | 24 | 24 | 0 |
| Memory-write texts computed | 711 | 711 | 0 |
| All embedding requests | 217 | 115 | -102 (-47.00%) |
| All embedding texts computed | 904 | 802 | -102 (-11.28%) |
| Completion requests | 255 | 255 | 0 |

The 91 retrieval computations exceed the 82 unique keys by 9, consistent with
concurrent cold misses. This is the saved primary measurement, not a promised
hit count for every rerun: scheduling changes how many cold misses overlap.

An additional paired **workers=1** control has identical semantic results and
observes 111 hits, 82 misses, 82 retrieval computations and 106 total embedding
requests. Its 57.51% retrieval reduction reaches the sequential upper bound.
Both sides of each pair use the same workers setting. The primary workers=4
setting is the one used by the existing smoke preset and phase 2.

Primary per-agent and per-tick lookup counts are included in
`results/token_efficiency/h3_cache_parallel.json`. Examples:

| Group | Queries | Hits | Misses |
| --- | ---: | ---: | ---: |
| HDS-001 | 16 | 7 | 9 |
| HDS-007 | 13 | 8 | 5 |
| HDS-020 | 8 | 8 | 0 |
| Tick 1 | 21 | 2 | 19 |
| Tick 17 | 61 | 54 | 7 |
| Tick 31 | 20 | 15 | 5 |

## Behavioral Equivalence

Both paired runs match exactly for the following canonical JSON/hash components:

| Component | OFF vs ON |
| --- | --- |
| All events | Equal |
| Memory records and float64 vectors written each tick | Equal |
| Retrieval queries and selected memory IDs | Equal |
| Final agent state | Equal |
| Tasks and environment snapshots at every tick | Equal |
| Conversation utterances and session metadata | Equal |
| Relationships, stress and other agent state at every tick | Equal |
| Completion request inputs (multiset, including prompt/schema/model) | Equal |
| Detached tick state, last_access and viewer state | Equal |

The behavior checksum, excluding the intentionally reduced backend embedding
request stream, is identical for baseline and optimized in both workers settings:

```text
e2c72dfcb44937f7f4271fe7828090c4e89988ff87f2ac4cf310b635bc3fc333
```

For continuity, the baseline also reproduces the phase-1/2 checksum that includes
the original embedding inputs:

```text
bece6540fa109233575014f9645c6b8a61e01f8d21fd599c18dacea66185a8e3
```

That legacy checksum is expected to differ for Cache ON because its backend
embedding requests have deliberately changed. Component hashes and the new
behavior checksum are the equivalence checks, not the old request-stream hash.

An additional integration test uses actual C16 `run_scenario` OFF/ON and compares
summary, saved memory records/vectors, events, viewer frames and inspect data.
Only the viewer hello's `run_id` (the intentionally different output directory
name) is excluded from that journal comparison. Simulation data are equal.

Unit tests also verify exact whitespace distinctions, separate models, persistent
warm hits, write bypass, reflection query scope and changing current memory/mood/
last_access despite a repeated query vector. A barrier-controlled concurrent test
forces two cold requests to the same key: both may compute, return equal vectors,
write safely, and a later warm request performs no backend computation.

## Limitations

- Existing SQLite reads/writes have a thread lock, and no new single-flight system
  was introduced. Parallel cold misses can compute the same vector multiple times.
  Benefit depends on scheduling, backend latency, cache scope and warm-up.
- The cache is a vector cache keyed by embedding model identifier and exact text.
  It does not detect a provider changing embedding behavior behind an unchanged
  model name. Use a fresh cache when changing provider/model implementation or
  embedding configuration; don't share arbitrary custom backends under one name.
- DemoBackend is deterministic. No paid API was used to establish real-provider
  numerical reproducibility, ranking equivalence, latency, rate-limit impact,
  token usage or cost savings. Request-count savings are not total-token savings.
- Cache misses still send the original query to the backend. Cache stores hashed
  keys and vectors, not raw query text; audit saves metadata, not raw prompts.
- Fewer billed embeddings may move a budget stop later in a real pilot. Completed
  same-horizon semantics should be compared separately from budget-stop timing.
- Config remains unchanged; the manifest is the source of the cache ON/OFF policy.
  Resume intentionally retains that saved policy rather than the supplied new flag.
- The optional actual CRAFT integration remains outside this work; no research
  scenario/condition experiment was executed.

## Conclusion

**GO for enabling this exact query cache in a separately authorized, bounded real
API pilot.** The no-cost smoke meets the required implementation, savings, cache
hit and behavioral equivalence criteria. This is a recommendation, not paid-run
authorization or a claim of proven real API equivalence.

Next verify real embedding usage, hit/miss attribution, stable vectors/ranking and
budget accounting in that pilot. Keep H1/H2 changes on hold. Consider cold-miss
coalescing only as a future hypothesis if measured duplicate misses justify it.

Reproduce without paid API:

```bash
.venv/bin/python scripts/token_efficiency_h3_cache.py --output work/h3-parallel
.venv/bin/python scripts/token_efficiency_h3_cache.py --output work/h3-sequential --workers 1
.venv/bin/pytest tests/test_retrieval_cache.py -q
```

Each output directory must be new so that cache warm-up is controlled. Full
verification commands and their final results are recorded below.

- `.venv/bin/pytest -q`: **519 passed, 1 skipped** (optional actual CRAFT integration).
- `.venv/bin/pytest tests/test_retrieval_cache.py -q`: **7 passed**.
- Ruff check and format check on all five changed/new Python files: **passed**.
- The first full test run was blocked by the sandbox's localhost socket restriction
  in two existing WebSocket tests. After network permission for local testing, the
  final full suite passed. Paid API calls remained **zero**.

Changes are committed locally; this work does not push to GitHub or create a PR.
