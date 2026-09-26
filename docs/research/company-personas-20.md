# C-14 Persona Table

The machine-readable source of truth is `conf/personas/large_korean_enterprise_20.yaml`. Names and biographies are fictional. DISC is restricted to communication tendencies and is balanced at D=5, i=5, S=5, C=5.

| ID | Name | Function / role | CL / position | DISC | Main priority | Pressure tendency |
|---|---|---|---|---|---|---|
| HDS-001 | 김민재 | Product / Integrated Product Lead | CL4 / team_manager | D | Decision speed with accountable evidence | Narrows choices and asks for owners |
| HDS-002 | 박소연 | Product / Senior Product Planner | CL3 / functional_lead | i | Coherent customer value | Builds alignment through discussion |
| HDS-003 | 이도윤 | Product / Product Analyst | CL2 / member | S | Stable metrics and traceability | Rechecks assumptions before escalating |
| HDS-004 | 최하린 | Product / Product Ops Coordinator | CL1 / member | C | Clean requirements and handoffs | Documents gaps precisely |
| HDS-005 | 정태우 | Software / Software Lead | CL4 / functional_lead | C | Architecture integrity | Requests evidence and protects critical path |
| HDS-006 | 윤지호 | Software / Backend Engineer | CL2 / member | D | Working backend scope | Proposes a smallest viable technical path |
| HDS-007 | 한서준 | Software / Cloud & API Engineer | CL2 / member | S | Reliable interfaces | Stabilizes contracts before changing them |
| HDS-008 | 오유진 | Software / Web Engineer | CL2 / member | i | Usable, visible progress | Surfaces blockers early and talks through options |
| HDS-009 | 임채원 | Software / Mobile Engineer | CL2 / member | S | Consistent mobile behavior | Absorbs pressure until dependencies become explicit |
| HDS-010 | 강현우 | Software / DevOps & Release Engineer | CL3 / senior_member | C | Reproducible deployment | Tightens checklists and refuses undocumented risk |
| HDS-011 | 송아린 | Design / Product Experience Lead | CL3 / functional_lead | i | End-to-end experience quality | Reframes disagreement around user impact |
| HDS-012 | 배준호 | Design / UX Researcher | CL2 / member | D | Research influence on decisions | Challenges unsupported certainty directly |
| HDS-013 | 문지안 | Design / Product Designer | CL2 / member | C | Interaction consistency | Iterates carefully and cites design criteria |
| HDS-014 | 서동현 | QA / Quality Engineering Lead | CL3 / functional_lead | D | Evidence-based release quality | Makes risk visible and asks for a decision |
| HDS-015 | 조은별 | QA / Test Automation Engineer | CL2 / member | S | Maintainable coverage | Preserves repeatability under schedule pressure |
| HDS-016 | 신재민 | QA / QA Analyst | CL1 / member | C | Complete defect reproduction | Separates observation from interpretation |
| HDS-017 | 장수빈 | GTM / Go-to-Market Lead | CL3 / functional_lead | i | Credible launch readiness | Negotiates scope while protecting commitments |
| HDS-018 | 백승민 | GTM / Launch Marketer | CL2 / member | D | Timely campaign execution | Pushes for decisions and explicit tradeoffs |
| HDS-019 | 홍예린 | Operations / Business Operations Lead | CL3 / functional_lead | S | Capacity and procedural fairness | Mediates sequencing and workload concerns |
| HDS-020 | 남기현 | Operations / Planning Operations Specialist | CL2 / member | i | Shared situational awareness | Connects people and summarizes emerging issues |

## Modeling guardrails

- No persona is irrational, incompetent, inherently aggressive, or conflict-prone.
- Skill and authority are explicit fields, independent of DISC.
- Hobbies create optional social contact only; they never confer competence, trust, or favoritism automatically.
- `pressure_response` is a likely first move, not a fixed behavior. Current facts, memory, relationship, and incentives can override it.
- All personal details are synthetic and should not be matched to a real employee.

