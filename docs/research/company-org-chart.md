# C-14 Organization Chart

Synthetic company: **Hanbit Digital Systems (HDS)**  
Shared project: **Connected Home Energy Insight v1**

```text
HDS-001 Integrated Product Lead / Project Manager
├── Product Planning: HDS-002
│   ├── HDS-003 Product Analyst
│   └── HDS-004 Product Operations Coordinator
├── Software Engineering: HDS-005
│   ├── HDS-006 Backend Engineer
│   ├── HDS-007 Cloud/API Engineer
│   ├── HDS-008 Web Engineer
│   ├── HDS-009 Mobile Engineer
│   └── HDS-010 DevOps & Release Engineer
├── Product Experience: HDS-011
│   ├── HDS-012 UX Researcher
│   └── HDS-013 Product Designer
├── Quality Engineering: HDS-014
│   ├── HDS-015 Test Automation Engineer
│   └── HDS-016 QA Analyst
├── Go-to-Market: HDS-017
│   └── HDS-018 Launch Marketer
└── Business Operations: HDS-019
    └── HDS-020 Planning Operations Specialist
```

## Matrix-lite behavior

Formal accountability follows the tree above. Delivery dependencies cross the tree: product planning supplies requirements, design supplies validated flows, software supplies builds, QA supplies quality evidence, go-to-market supplies launch readiness, and operations supplies capacity and review data. These are workflow edges, not additional reporting lines.

## Level and position

`career_level` records CL1-CL4 development stage. `position` records `member`, `senior_member`, `functional_lead`, or `team_manager`. Only explicit authority entries grant actions. A CL3 member therefore does not inherit a lead's approval rights.

