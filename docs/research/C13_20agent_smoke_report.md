# C-13 20-Agent Integration Smoke Report

## Status

**PASS - INTEGRATION SMOKE TEST, NOT A RESEARCH RESULT**

- Command: `conflict-company-experiment s0_smoke --output-root runs/c13-integration-v2`
- Backend: deterministic `DemoBackend`; paid API calls: 0
- Scale: 20 agents, 1 workday, 32 ticks, 15 tasks
- Artifact: `runs/c13-integration-v2/s0_smoke/replicate-1`

## Acceptance Results

| Check | Result | Evidence |
|---|---|---|
| Initialize/finish | PASS | 20 agents initialized; 32 ticks completed without crash or deadlock |
| Meaningful path | PASS | Every agent produced 3-19 non-plan/non-rest actions |
| Task DAG | PASS | All 15 tasks reached `done`; final task completed at tick 22 |
| Dependency transitions | PASS | 14 blocked and 13 ready/unblocked events; initial root dependency explains the count difference |
| Authority/review | PASS | Scoped approve/reject/evaluate tests pass; forbidden actions are rejected with reasons |
| Handoffs and sessions | PASS | Owners, contributors, reviewers and 32 recorded sessions exercised cross-functional paths |
| Meeting/private/privacy | PASS | Scheduled turn-taking terminates; private and hearsay tests preserve provenance and audience |
| Work phases | PASS | Work/lunch/rest completed; smoke has overtime disabled by design |
| Output bundle | PASS | Config, manifest, events, memory DB, frames, corpus, summary written |
| Reporting graph | PASS | C-14 validator confirms references and acyclic reporting/task graphs |

## Rejected Actions

There were 59 safe rejections. Eight were initial office/focus-room capacity competition. The
remaining 51 were expected lifecycle or authority guards: work attempted while a task awaited
review, contribution attempted by a non-owner, or work attempted after completion. No rejection
stopped progress. An earlier run produced 154 repeated pantry-capacity rejections; the demo policy
was corrected to choose the eating space with the most free capacity, without changing C-14.

## Classification

- C-13 engine bug found and fixed: demo food-space selection repeatedly chose the first room.
- C-14 configuration issue: none found.
- Demo limitation: rule-based agents react mechanically, and their relationship/stress values are
  useful only for checking data flow. They are not behavioral findings.

## Scope Limit

The one-day smoke proves executable integration and fail-safe state transitions. Overtime is
covered by unit tests and the two-day baseline config, not by this smoke. Human plausibility and
condition effects require the separately approved real-model experiment.
