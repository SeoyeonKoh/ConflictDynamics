# C-14 Job and Authority Model

Authority is scoped by decision domain. `Responsible` does the work, `Accountable` owns the decision, `Consulted` provides required input, and `Informed` receives the result.

| Decision | A | R | C | I |
|---|---|---|---|---|
| Product brief and success metric | HDS-001 | HDS-002, HDS-003 | HDS-011, HDS-017, HDS-019 | All |
| Requirement/specification baseline | HDS-002 | HDS-003, HDS-004 | HDS-005, HDS-011, HDS-014 | HDS-001, delivery teams |
| Experience design decision | HDS-011 | HDS-013 | HDS-012, HDS-002, HDS-005 | HDS-014 |
| Technical architecture decision | HDS-005 | HDS-006, HDS-007, HDS-010 | HDS-008, HDS-009, HDS-014 | HDS-001, HDS-002 |
| Test strategy and quality sign-off | HDS-014 | HDS-015, HDS-016 | HDS-005, HDS-010, HDS-002 | HDS-001, HDS-017 |
| Deployment readiness | HDS-005 | HDS-010 | HDS-014, HDS-006, HDS-007 | HDS-001, HDS-017 |
| Final release decision | HDS-001 | HDS-001 | HDS-002, HDS-005, HDS-014, HDS-017 | All |
| Launch messaging and channel plan | HDS-017 | HDS-018 | HDS-002, HDS-011, HDS-019 | HDS-001 |
| Within-function task allocation | Relevant functional lead | Relevant functional lead | Assigned members | HDS-001 |
| Cross-function priority/reallocation | HDS-001 | HDS-019 | Affected functional leads | Affected members |
| Performance evaluation | HDS-001 | HDS-001 | Functional lead and narrative peer inputs | Evaluated agent |

## Engine authority mapping

| Engine action | Grant rule |
|---|---|
| `assign` | Team manager and functional leads, within scope; HDS-001 for cross-functional reallocation. |
| `approve` | Accountable owner for the decision domain. |
| `reject` | Same scope as approval, with a reason and requested evidence or revision. |
| `evaluate` | HDS-001 only in the baseline. Functional leads and peers submit evidence, not scores. |

## Guardrails

- Authority is not inferred from age, tenure, career level, DISC, or speaking confidence.
- A rejection changes task state; it is not automatically a social sanction.
- Public criticism and private corrective feedback are distinct interaction events.
- Delegation transfers responsibility for work, not final accountability, unless a scenario explicitly changes the RACI table.

