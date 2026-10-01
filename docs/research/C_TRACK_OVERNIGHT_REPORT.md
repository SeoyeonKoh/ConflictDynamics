# C Track Overnight Report

## 1. Overall Status

- C-13: **COMPLETE** for the C-15/C-16 minimum research runtime
- C-14: **COMPLETE**; A1B1C1 baseline preserved and connected by an adapter
- Integration Smoke Test: **PASS**
- C-15: **COMPLETE**; baseline + four scenarios + three interventions
- C-16 Preparation: **COMPLETE**
- Real API Pilot: **RUN / INCOMPLETE - token-budget safety stop at tick 5**
- C-17 Scaffold: **COMPLETE**

## 2. What Changed

The locked 20-agent preset now runs through the existing company engine. Scoped authority,
task/review transitions, meetings, private sessions, hearsay provenance, work pressure/overtime,
evaluation facts, deterministic shocks, interventions and structured outcomes are executable.
The 6-agent demo and wiki paths remain compatible. A repeatable runner writes configs, manifests,
events, memory, frames, corpus and summaries, while hard-blocking unapproved paid execution.

## 3. Files Created / Modified

- Runtime: `models.py`, `company_runtime.py`, `experiment.py`, loop/agent/environment/conversation.
- Config: `conf/relations/hds_initial.yaml`, `conf/scenario/company_c15/*.yaml`, C-16 manifest.
- Tests: `test_company_runtime.py` plus model/company regression updates.
- Research docs: C-13 smoke, C-15 design, C-16 protocol/pilot, blockers and C-17 outline.
- C-14 source files changed only in runtime-readiness metadata; people, org, task and office content
  were not redesigned.

## 4. Commits Created

- `61beb3c` `feat: add validated C-14 20-agent company preset`
- `2b5b088` `feat: implement C-13 company engine extensions`
- `d52756f` `test: validate 20-agent company integration`
- `5ae4347` `chore: prepare C-16 experiment protocol`

All commits are local. Nothing was pushed.

## 5. C-13 Implementation

| Capability | Status |
|---|---|
| 20-agent config/initial relations | Complete |
| Static baseline + validated manager task generation | Complete |
| assign/approve/reject/evaluate authority | Complete |
| 15-task DAG, blocked/review/rework/overdue | Complete |
| deterministic meetings and private sessions | Complete |
| public/co-present/private and hearsay provenance | Complete |
| workload, pressure and overtime observation | Complete |
| evaluation-season flag, evaluation records, promotion-slot resource | Complete minimum abstraction |
| deterministic shock/intervention scheduler | Complete |
| refused/ignored and public/private outcome facts | Complete minimum rule set |

## 6. 20-Agent Smoke Test

- Agents/duration: 20, one 32-tick workday
- Tasks: all 15 done; final completion at tick 22
- Sessions: 32
- Dependency events: 14 blocked, 13 ready/unblocked
- Overtime: 0 because the smoke condition disables it; unit coverage verifies overtime recording
- Rejections: 59 safe rejections, of which 8 were capacity competition and 51 lifecycle/authority
  guards; none caused starvation
- Errors/deadlocks: 0
- Every agent had 3-19 meaningful non-plan/non-rest actions

This is a deterministic integration result, not evidence about human conflict behavior.

## 7. C-15 Scenarios

- S0: no shock baseline
- S1: T01 dependency failure window
- S2: T14 deadline compression with unchanged effort
- S3: meeting-room capacity loss
- S4: evaluation season and one promotion slot
- I1/I2/I3: manager clarification, partial deadline restoration and private mediation

Each condition declares timing, affected state, observables, theory tags and a manipulation check.

## 8. C-16 Readiness

All eight scenario/intervention CLI dry-runs pass. The per-run conservative completion-call bound is
1,400 or 1,414 depending on scheduled meetings. The real 20-agent pilot showed that this call-count
bound understates prompt and embedding volume: a 500,000-token cap was reached at tick 5. Repeated
experiments are paused pending call-volume optimization.

## 9. Tests

- `uv run --all-extras pytest`: **459 passed, 1 skipped**
- Skip: optional local CRAFT integration asset only
- `ruff check .`: pass
- changed-file `ruff format --check`: pass after one-line correction
- all C-15/C-16 dry-runs: pass
- `git diff --check`: pass

## 10. Remaining Blockers

- Real OpenAI pilot: model access and partial execution succeeded, but no run completed; decision,
  retry and embedding volume must be reduced before another paid attempt.
- CRAFT observer scoring: optional compatible local model asset is not available in this run.
- Overtime stress coefficient: intentionally unset because the source design defines no value;
  overtime is recorded while existing workload pressure drives stress.

## 11. Recommended Next Step

1. Review the smoke and C-15 design documents.
2. Optimize per-tick LLM and embedding calls and add graceful budget checkpoints.
3. Re-estimate cost, then decide whether to authorize exactly one new pilot.
