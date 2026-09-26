# C-14 Conflict Event Catalog

An event is a structured opportunity for conflict, not a scripted argument. C-13 should first write the objective fact, then each observer's appraisal, then any interaction.

| ID | Trigger | Theory | Observable engine fact | Possible interaction |
|---|---|---|---|---|
| E01 | Task dependency failure | S20/S21/S23 | Predecessor misses due tick or acceptance criterion | Recovery request, blame attribution, owner confirmation |
| E02 | Deadline compression | S22/S25 | Due tick moves earlier while scope/quality stays fixed | Scope tradeoff, overtime request, quality-risk escalation |
| E03 | Scarce resource competition | S24/S25 | Ready tasks require the same unavailable resource | Priority request, allocation dispute, transparent reallocation |
| E04 | Priority disagreement | S20/S22 | Functions submit incompatible ranked outcomes | Evidence challenge, coalition building, accountable decision |
| E05 | Role ambiguity or overlap | S23 | Ownership, review, or approval reference is missing/conflicting | Duplicate work, ownership request, RACI clarification |
| E06 | Unequal workload allocation | S24/S25 | Assigned effort differs without recorded rationale | Fairness question, rebalance request, constraint explanation |
| E07 | Evaluation or promotion salience | S03/S24 | Limited recognition/evaluation timing becomes salient | Credit claim, evidence submission, withholding risk |
| E08 | Information delay or missing handoff | S21/S23/S24 | Named update misses recipient and due tick | Status request, downstream rework, handoff repair |
| E09 | Public criticism / face threat | S20/S22/S24 | Corrective feedback identifies a person before multiple attendees | Defensive reply, withdrawal, private follow-up |
| E10 | Ignored or refused request | S23/S24/S26 | Request misses acknowledgement SLA or refusal lacks rationale | Repeat request, authority escalation, rationale and repair |

## Required event fields

`event_id`, `type`, `tick`, `initiator`, `affected_agents`, `task_ids`, `location`, `objective_facts`, `visibility`, `severity`, `appraisals`, `responses`, `authority_actions`, `outcome`, and `evidence_tags`.

## Conflict labels

- `task`: disagreement about content, evidence, goals, or solution.
- `process`: disagreement about ownership, sequencing, allocation, coordination, or method.
- `relationship`: perceived disrespect, dislike, hostility, or identity/face threat.

Do not infer `relationship` merely from a terse message or a rejected proposal. The label requires interaction evidence or an explicit appraisal. A single event may change labels over time; preserve the transition rather than replacing the earlier label.

## C-15 scenario hooks

1. Deadline pressure: activate E02, then observe E04/E06 without changing personas.
2. Resource competition: activate E03 around HDS-010 or a shared test environment.
3. Evaluation season: activate E07 while holding workload and deadlines constant.
4. Dependency failure: activate E01 or E08 on one critical edge, varying transparency of the cause.
