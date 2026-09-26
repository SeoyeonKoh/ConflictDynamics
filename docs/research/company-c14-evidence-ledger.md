# C-14 Evidence Ledger

| Claim or design choice | Evidence | Classification | Confidence | Boundary |
|---|---|---|---|---|
| CL1-CL4 can represent career-development stages | S02 | Observed public policy | High | Does not define authority in this simulation. |
| Work should be modeled around roles and expertise | S02 | Observed public direction | High | Exact job catalog is synthetic. |
| Frequent manager feedback and narrative peer input are plausible | S03 | Observed public policy | High | Peer input is not a peer-issued grade. |
| Development, QA, sales/marketing, and other support job families are plausible in a large electronics company | S01, S04 | Observed broad categories | High | The 20-person counts are not observed. |
| A large campus and flexible work areas are plausible references | S05, S06 | Observed environment | Medium | Room topology and movement probabilities are synthetic. |
| Task, process, and relationship conflict should be distinguished | S20, S21, S22 | Research-derived | High | Labels are analytical constructs, not diagnoses. |
| Role ambiguity can trigger conflict | S23 | Research-derived | High | Event thresholds are assumptions. |
| Workload/resource pressure can affect strain and interaction | S25 | Research-derived | High | No deterministic path from pressure to hostility. |
| Fairness appraisals can concern outcomes, process, treatment, and information | S24 | Research-derived | High | The engine should record appraisal separately from objective allocation. |
| Conflict management changes outcomes | S26 | Research-derived | Medium | DISC does not select a fixed conflict-management mode. |
| Hybrid iterative delivery with explicit gates is defensible | S30, S31, S32 | Standard/practice-derived | High | The exact workflow is a C-14 synthesis. |
| Five agents per DISC quadrant | S10, S11 | Simulation balance | High as a design choice | Not a population estimate. |
| 32 ticks/day and 15 minutes/tick | D10 | Simulation assumption | High as a convention | Not a claim about any company. |
| Mostly neutral initial ties | D08 | Simulation assumption | High as a baseline | Chosen to reduce preloaded-conflict confounding. |
| One formal manager per agent | D06 | Simulation assumption | High as a baseline | Matrix dependencies remain non-reporting edges. |
| 20-person functional composition and all reporting lines | D03, D04, D06 | Simulation assumption | High as a locked design | Not inferred from public Samsung staffing ratios. |
| Structured authority scopes and RACI assignments | D05, D14 | Simulation assumption | High as a locked design | Public sources support role-centered work, not these exact grants. |
| Every agent participates in the task/RACI graph | D15 | Validation requirement | High | Ensures code-ready coverage, not organizational realism evidence. |
| Separate `CompanyPreset` instead of expanding `AgentSpec` | D13, D14 | Engineering decision | High | Preserves the existing 3-6 agent dialogue runtime. |

## Traceability rule

Every C-14 field is either tied to a source ID, tied to a decision ID, or tagged `synthetic_assumption`. Absence of public evidence is never filled with a claim about Samsung's internal practice.
