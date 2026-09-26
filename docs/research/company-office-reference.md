# C-14 Office Reference

The environment is a synthetic Korean large-enterprise product office inspired by public descriptions of Samsung Electronics Digital City. It is not a floor plan or reconstruction.

| Place | Capacity | Primary mechanism | Typical interactions |
|---|---:|---|---|
| lobby | 20 | Arrival, chance contact | Brief greetings, cross-team awareness |
| office | 16 | Focused individual and team work | Task work, quick requests, visible workload |
| meeting_room | 10 | Formal coordination and decisions | Reviews, triage, approvals, public disagreement |
| focus_room | 2 | Private or interruption-sensitive work | Sensitive feedback, private escalation, concentrated work |
| pantry | 6 | Short informal contact | Hearsay, social repair, low-stakes check-ins |
| cafeteria | 20 | Longer informal mixing | Cross-functional familiarity, shared-hobby conversation |

## Rules

- Existing engine place concepts are reused wherever possible. `focus_room` is the only required addition because privacy changes who can observe an interaction.
- A location affects visibility, interruption, and meeting capacity. It never determines emotion or conflict by itself.
- A one-hour scheduled review occupies four 15-minute ticks. Ad hoc conversations may take one or two ticks.
- Workstation assignment, building number, and campus geometry are intentionally unspecified.

The machine-readable form is `conf/environment/office/large_korean_enterprise.yaml`.

