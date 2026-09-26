# C-15 Scenario and Intervention Design

## Fixed Baseline

Every condition loads the same A1B1C1 C-14 personas, organization, balanced DISC distribution,
authority grants, office and 15-task DAG. Scenario files inherit `s0_baseline.yaml`; the validator
checks that the task runtime and fixed-variable declaration remain equal. Seeds are recorded and
replicates use deterministic `seed + offset` values. Conflict is measured, never required.

## Scenarios

| ID | Research question | Single manipulation and timing | Affected state | Observables / theory | Check / termination |
|---|---|---|---|---|---|
| S0 | How does the fixed organization progress without a structural shock? | None | None | task, session, stress, workload, overtime / S20,S21,S30-S32 | no shock; 2 days |
| S1 | How does a transparent prerequisite failure alter downstream coordination? | E01: T01 unavailable, day 0 tick 2-10 | T01 and downstream readiness | blocked ticks, handoffs, messages, reports / S20,S21,S23 | E01 emitted; 2 days |
| S2 | How does an earlier release deadline alter workload and coordination? | E02: T14 due reduced by 12, day 0 tick 4 | due only; effort fixed | impossible workload, overdue, stress, overtime / S22,S25 | due delta -12; 2 days |
| S3 | How does temporary room loss alter cross-functional coordination? | E03: meeting-room capacity 10 to 4, day 0 tick 10 | room capacity only | rejected meeting, sessions, task path / S24,S25 | capacity equals 4; 2 days |
| S4 | How does promotion scarcity alter evidence and credit interactions? | E07: evaluation season on, one slot, day 0 tick 4 | evaluation flag and slot | evaluations, contribution evidence, information flow, relations / S03,S24 | season on, slots=1; 2 days |

These are deterministic environment facts mapped to the C-14 event taxonomy. They do not insert
hostility into personas or expose observer scores to agents.

## Interventions

| ID | Paired condition | Trigger/timing | Actor/action | Changed state | Held fixed |
|---|---|---|---|---|---|
| I1 | S1 | after four blocked ticks; day 0 tick 6 | HDS-001 manager clarification | emits a structured clarification event | owner, due, effort, persona |
| I2 | S2 | after compression; day 0 tick 10 | HDS-001 restores 6 ticks | T14 due +6 | workload, task graph, personnel |
| I3 | S1 | after failure becomes visible; day 0 tick 8 | HDS-001 opens private session with HDS-005 | private turn-taking session only | task state, observer metrics, relationships before interaction |

Each intervention has a matching no-intervention scenario, so the comparison is S1/I1, S2/I2 or
S1/I3. CRAFT remains an observer and never selects or phrases an intervention.
