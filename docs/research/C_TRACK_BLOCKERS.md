# C Track Blockers

## Paid API Pilot Approval

- Question: Should the guarded one-run C-16 OpenAI pilot be authorized?
- Why needed: it incurs cost and is the gateway before repeated runs.
- Option A: set `ALLOW_PAID_API_EXPERIMENTS=1` and run one baseline pilot.
- Option B: keep the flag absent and retain demo/dry-run artifacts only.
- Recommendation: A only after reviewing the approximately 1,400-call conservative bound and the
  100,000-token per-run cap. No repeated experiment should start automatically.

## Overtime Stress Coefficient

- Question: Should overtime itself add stress beyond urgent/overdue workload pressure?
- Why needed: the source plan defines overtime observation but no coefficient.
- Option A: keep `p_overtime=None`; record overtime while existing pressure terms drive stress.
- Option B: preregister a coefficient and add it in a later sensitivity study.
- Recommendation: A for the main run. It avoids inventing an ungrounded parameter.

## Optional CRAFT Asset

- Question: Are compatible local CRAFT weights available for the observer pass?
- Option A: provide/approve the asset and run scoring after generation.
- Option B: leave CRAFT pending and report descriptive metrics only.
- Recommendation: do not block generation; never substitute demo values for missing scores.
