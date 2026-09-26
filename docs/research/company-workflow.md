# C-14 Workflow

## Release lifecycle

| Phase | Core tasks | Exit evidence | Accountable |
|---|---|---|---|
| 1. Frame | Product brief, user problem, success metrics | Approved brief | HDS-001 |
| 2. Specify | Research synthesis, requirements, acceptance criteria | Baseline specification | HDS-002 |
| 3. Shape | UX flow, feasibility, architecture, test strategy | Design/feasibility review | HDS-011, HDS-005, HDS-014 |
| 4. Build | API, backend, web, mobile, analytics, launch draft | Integration candidate | HDS-005 |
| 5. Verify | Integration, automated/manual tests, defect triage | Quality sign-off or explicit waiver | HDS-014 |
| 6. Release | Readiness review, deployment, communication | Release decision and deployment record | HDS-001 |
| 7. Learn | Metric review, incident review, retrospective | Action list with owners | HDS-001 |

## Dependency graph

```text
T01 brief ─┬─> T02 user research ─> T03 specification ─┬─> T04 UX design ───────┐
           └────────────────────────────────────────────┴─> T05 feasibility ─┐  │
T03 ─> T06 API contract ─> T07 backend ───────────────┐                   │  │
T04 ─────────────────────> T08 web/mobile ────────────┼─> T10 integration ├─> T11 QA
T05 ─> T09 test strategy ─────────────────────────────┘                   │
T03 ─> T12 launch plan ────────────────────────────────────────────────────┘
T11 ─> T13 defect triage/revision ─> T14 readiness review ─> T15 release/review
```

T04, T05, T09, and T12 may proceed in parallel once their inputs exist. A blocked predecessor raises a dependency-risk fact; it does not automatically create blame or conflict.

## Task ownership and handoff

| Task | Owner | Main contributors/reviewers | Handoff recipients |
|---|---|---|---|
| T01 Product brief | HDS-002 | HDS-003; HDS-001/011/017/019 review | HDS-012 |
| T02 Research synthesis | HDS-012 | HDS-003; HDS-011 review | HDS-003 |
| T03 Requirement specification | HDS-003 | HDS-004; leads review | HDS-005/013/014/018 |
| T04 UX flow and design | HDS-013 | HDS-011/012; client engineers review | HDS-008/009/016 |
| T05 Technical feasibility | HDS-005 | HDS-006/007/010; HDS-014 review | HDS-007/014 |
| T06 API contract | HDS-007 | HDS-006; software clients review | HDS-006/008/009 |
| T07 Backend implementation | HDS-006 | HDS-005/010 review | HDS-010 |
| T08 Web/mobile implementation | HDS-008 | HDS-009/013; HDS-005/016 review | HDS-010 |
| T09 Test strategy | HDS-014 | HDS-015/016; product/software review | HDS-015 |
| T10 Integration candidate | HDS-010 | Software contributors; software/QA leads review | HDS-015/016 |
| T11 Quality verification | HDS-015 | HDS-016; software/QA leads review | HDS-014 |
| T12 Launch plan | HDS-018 | HDS-017/020; product/design/ops review | HDS-017 |
| T13 Defect triage/revision | HDS-014 | Engineering and QA contributors | HDS-001 |
| T14 Release readiness | HDS-001 | All functional leads; release/ops review | HDS-010/017 |
| T15 Release and review | HDS-001 | Release, GTM, and operations | Terminal |

The YAML is authoritative for complete contributor, reviewer, predecessor, and handoff lists.
All 20 agents appear in at least one task or RACI reference.

## Daily operating rhythm

- Tick length: 15 minutes; workday: 32 ticks.
- Team sync: two ticks near the start of day; only blockers, decisions, and handoffs.
- Focus blocks: default work state. Agents seek clarification when acceptance criteria or dependencies are missing.
- Reviews/triage: scheduled in `meeting_room`, normally four ticks.
- Sensitive feedback: `focus_room`, unless urgency or a public decision record requires a formal meeting.
- Overtime is a scenario variable and must be logged as a job demand, never treated as proof of commitment.

## State model

`backlog -> ready -> in_progress -> review -> blocked | revision -> approved -> released`

Each transition records actor, tick, evidence, authority used, and affected dependencies. Rejection must name a failed criterion. Approval without the required evidence creates a governance exception that C-13 can expose to later events.
