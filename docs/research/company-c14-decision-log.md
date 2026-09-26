# C-14 Decision Log

Status: locked for implementation on 2026-09-25.

| ID | Decision | Rationale | Consequence |
|---|---|---|---|
| D01 | A1: connected digital product/service feature release | Creates observable dependencies across planning, design, software, QA, launch, and operations. | The shared project is `Connected Home Energy Insight`, a feature release rather than a whole-company transformation. |
| D02 | B1: functional organization with a matrix-lite project | Preserves one clear reporting line while creating cross-functional task dependencies. | Every agent has at most one `reports_to`; project dependencies live in workflow edges, not extra managers. |
| D03 | C1: anonymized synthetic data | Protects against false claims about non-public company structures or people. | The simulated company is `Hanbit Digital Systems` (HDS). Samsung Electronics Digital City is only a public reference point. |
| D04 | 20 agents in seven functions | Gives enough role diversity for conflict while staying inspectable. | Product 4, software 6, design 3, QA 3, go-to-market 2, business operations 2; the integrated product lead is counted in product. |
| D05 | Career level and positional authority are separate | A career level describes development stage; it does not automatically grant managerial power. | `career_level` is CL1-CL4. Only explicit `position` and `authorities` fields control assign/approve/reject/evaluate. |
| D06 | One formal manager per agent | Multiple formal reporting lines would create ambiguous evaluation authority in the current handoff. | Cross-functional influence is represented by RACI and task dependencies. |
| D07 | DISC is a communication prior, not a competence score | Avoids stereotyping and a built-in link between personality and conflict. | Five D, five i, five S, five C profiles are stratified across functions. DISC never changes skill, rationality, or aggression. |
| D08 | Mostly neutral initial relations | Lets conflict arise from simulated work rather than preloaded hostility. | Familiarity and trust may vary, but relationship valence starts neutral except for mild positive working ties. |
| D09 | Hybrid stage-gate workflow with iterative delivery | The release needs both parallel implementation and explicit readiness decisions. | Work moves through brief, specification, design/feasibility, build, integration/QA, release, launch, and review. |
| D10 | Daily time model is a simulation convention | Public evidence does not establish an internal company-wide tick model. | One tick is 15 minutes; a normal day is 32 ticks. A one-hour meeting maps to four ticks. |
| D11 | Office locations are mechanism-bearing only | Decorative places add complexity without explanatory value. | Reuse lobby, office, meeting room, pantry, and cafeteria; add only a focus room for private work or sensitive coordination. |
| D12 | Conflict is modeled as a sequence | A trigger alone is not a relationship conflict. | Structural trigger -> interaction -> appraisal -> task/process conflict -> possible relationship conflict. |
| D13 | C-14 uses a separate validated company preset | The current dialogue engine validates 3-6 agents and has no organization execution fields. | Hydra composes and Pydantic validates the 20-agent world now; C-13 must add/translate runtime behavior before full simulation. |
| D14 | Runtime and research fields remain separate | Adding every C-14 field to `AgentSpec` would couple the small dialogue engine to an unimplemented company engine. | Existing `Config`/`AgentSpec` stay unchanged; `CompanyPreset` validates C-14 independently. |
| D15 | Every agent must have an explicit delivery reference | A named persona without work participation is not useful to C-13 or C-15. | Every agent appears as task owner, contributor, reviewer, handoff recipient, or RACI participant. |

## Fixed interpretation

`A1B1C1` is the baseline for all C-15 scenarios. Scenario experiments may change deadline pressure, resource scarcity, evaluation salience, or dependency reliability, but must not silently alter organization, persona, or authority baselines.
