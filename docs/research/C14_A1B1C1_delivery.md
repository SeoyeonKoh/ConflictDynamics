# C-14 A1B1C1 Delivery

Status: **COMPLETE**  
Baseline: **A1B1C1**  
Validated: 2026-09-25

This is the single handoff entry point for the C-14 company-world research and configuration.

## 1. What is fixed

- A1: a connected digital product/service feature release, `Connected Home Energy Insight v1`.
- B1: a functional organization with one formal manager per agent and matrix-lite project edges.
- C1: `Hanbit Digital Systems` is wholly synthetic. Samsung Electronics is a public industry
  reference only, never a claimed reconstruction of internal teams or reporting lines.
- Twenty agents, six departments, CL1-CL4 career levels, four explicit positions, scoped
  assign/approve/reject/evaluate grants, a 15-task DAG, six office places, and ten conflict events.
- DISC is a communication prior only and is balanced D/i/S/C = 5/5/5/5. It does not encode
  aggression, competence, honesty, rationality, or job fit.
- Conflict opportunities originate in dependency, time, resource, role, workload, evaluation,
  information, feedback, or request conditions rather than being forced into a persona.

## 2. Evidence and assumptions

- Source registry: `docs/research/company-c14-sources.md`
- Claim-level evidence ledger: `docs/research/company-c14-evidence-ledger.md`
- Locked decisions and engineering boundaries: `docs/research/company-c14-decision-log.md`
- Official Samsung sources support broad job families, CL policy history, feedback/evaluation
  directions, and workplace plausibility. They do not support the synthetic 20-person ratio,
  reporting tree, authority grants, room topology, DISC mix, or interpersonal ties.
- The 2026 official report index and current Facts & Figures were checked for recency. No source
  found reverses the narrow claims retained from the 2016 and 2021 official announcements.
- Task/process/relationship conflict, role ambiguity, organizational justice, job demands, and
  conflict-management claims are tied to the peer-reviewed sources in the registry.

## 3. Human-readable design

- Persona table: `docs/research/company-personas-20.md`
- Organization chart: `docs/research/company-org-chart.md`
- Job authority and RACI: `docs/research/company-job-authority.md`
- Project and daily workflow: `docs/research/company-workflow.md`
- Office abstraction: `docs/research/company-office-reference.md`
- Initial relations: `docs/research/company-initial-relations.md`
- Conflict event catalog: `docs/research/company-conflict-events.md`

The YAML is authoritative when a compact Markdown table omits a contributor, reviewer, handoff,
or authority scope.

## 4. Machine-readable preset

Hydra entry point:

```text
conf/company/large_korean_enterprise_20.yaml
```

Composed groups:

```text
conf/personas/large_korean_enterprise_20.yaml
conf/environment/office/large_korean_enterprise.yaml
conf/environment/org/large_korean_enterprise.yaml
```

Validate without an API call:

```bash
uv run conflict-company-validate large_korean_enterprise_20
```

Expected summary:

```text
Validated hds_a1b1c1_20_v1: 20 agents, 15 tasks, 10 conflict events
```

`src/conflict_sim/company.py` owns the strict Pydantic schema and cross-file validation. The
existing dialogue `Config` and `AgentSpec` are unchanged, so the six-agent demo remains backward
compatible.

## 5. Final organization

| Function | IDs | Count |
|---|---|---:|
| Product Strategy | HDS-001-HDS-004 | 4 |
| Software Engineering | HDS-005-HDS-010 | 6 |
| Product Experience | HDS-011-HDS-013 | 3 |
| Quality Engineering | HDS-014-HDS-016 | 3 |
| Go-to-Market | HDS-017-HDS-018 | 2 |
| Business Operations | HDS-019-HDS-020 | 2 |

HDS-001 is the sole reporting root. Functional leads report to HDS-001; members report to one
functional lead. Cross-functional work is expressed through RACI, task participation, dependency,
review, and handoff references, never a second formal manager.

## 6. Validation guarantees

The validator and `tests/test_company.py` enforce:

- exactly 20 unique agent IDs and names;
- D/i/S/C = 5/5/5/5;
- catalogued department, job family, role, career level, position, and authority kind;
- one reporting root, existing manager targets, and no reporting cycle;
- valid persona dependency and RACI references;
- 15 unique tasks, existing owners/participants/dependencies, and an acyclic task graph;
- meaningful task or RACI participation for every agent;
- ten unique conflict events with theory tags, observable facts, and possible interactions;
- unique office place IDs and positive time/capacity values;
- continued resolution and validation of the existing six-agent demo configuration.

Verification result on 2026-09-25:

```text
uv sync --all-extras        -> completed (126 packages installed)
uv run --all-extras pytest  -> 195 passed, 1 skipped
uv run ruff check .         -> passed
uv run ruff format --check . -> known pre-existing failure only:
                                docs/conflict-sim-design.md would be reformatted
```

The skipped test is the optional real CRAFT model integration and is unrelated to C-14. No
OpenAI API call was made.

## 7. C-13 implementation boundary

C-13 still needs runtime behavior for:

- selecting/activating up to 20 agents from the company registry;
- translating scoped authority grants into assign/approve/reject/evaluate actions;
- task state, dependency, handoff, review, and evidence transitions;
- meetings and private sessions;
- location-based observability and hearsay;
- workload/overtime facts and evaluation/KPI/promotion mechanics;
- scheduled shocks and structured outcomes.

These are deliberately not implemented in C-14. The preset's
`runtime.executable_on_current_engine` remains `false`; validation success is not a claim that the
current demo backend performs a meaningful 20-agent company simulation.

## 8. C-15 experiment inputs

C-15 should hold this persona, organization, DISC, authority, office, relationship, and workflow
baseline fixed. Scenarios may manipulate only declared independent variables, initially:

- deadline pressure;
- scarce specialist or test-environment competition;
- evaluation-season salience;
- dependency failure or handoff transparency;
- an additional scenario only if it has a documented event mapping and does not silently alter
  the baseline world.

Recommended hooks are E02, E03, E07, and E01/E08 respectively. Scenario analysis must distinguish
objective engine facts, agent appraisals, interactions, and eventual task/process/relationship
conflict labels.

## 9. Repository state and commit

All C-14 changes are intentionally uncommitted and limited to research docs, company configuration,
the standalone validator, its tests, README/AGENT guidance, and the script entry point.

Suggested commit message:

```text
feat: add validated C-14 20-agent company preset
```
