# C-16 Real API Pilot

## Status

**RUN, NOT COMPLETED - token-budget safety stop**

The user approved a limited real-API pilot on 2026-10-01. Model access to `gpt-6-luna` succeeded.
Runtime speakers use `HDS-###` identifiers and English goals/personas; Korean display names remain
documentation metadata and do not enter the generation or CRAFT corpus path.

## Attempts

| Attempt | Condition | Result | Recorded usage |
|---|---|---|---|
| 1 | two-day S0 baseline | stopped during initial planning because `max_tokens_decide=512` truncated a structured plan | 9,895 tokens |
| 2 | two-day S0 baseline, decision limit corrected to 2,048 | stopped at tick 0 by the former 100k total-token cap | 100,767 tokens |
| 3 | one-day `s0_smoke`, 500k total-token cap | stopped safely at tick 5; no additional condition started | 503,945 tokens |

Attempt 3 produced 385 events through tick 5: 143 actions, 119 decisions, 46 session events, 31
safe rejections, 29 outcomes and 17 task events. It made 204 decision, 21 speech and 180 embedding
calls. Because the run did not finish, no final summary, frames or CRAFT-ready completed corpus is
claimed.

## Cost

Using the official standard GPT-6 Luna rates available on the run date (input $0.10/M, output
$0.50/M) and a conservative embedding estimate, attempt 3 is approximately **$0.062**. The three
recorded attempts total approximately **$0.08**. The provider billing dashboard remains the
authoritative amount, especially for concurrent calls finishing near a safety stop.

## Finding and Decision

The blocker is not Korean text, model access, JSON support or a deadlock. The current 20-agent loop
performs too many reactive decisions, retrieval embeddings and reflection embeddings per tick for
the inherited budget. Raising the cap again would hide the scaling problem, so no further paid run
was started.

Before another pilot:

1. count and cap per-tick decision/retry calls;
2. batch or reduce retrieval/reflection embeddings;
3. checkpoint a graceful `budget_exhausted` result instead of losing final artifacts;
4. estimate the revised one-day budget from a no-cost scripted regression;
5. obtain fresh cost approval for exactly one rerun.

Pricing reference: <https://developers.openai.com/api/docs/models/gpt-6-luna>
