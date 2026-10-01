# C Track Blockers

## 20-Agent API Call Volume

- Question: Which decision, retry and embedding calls can be reduced without changing the study?
- Why needed: the approved one-day pilot reached the 500k token cap at tick 5.
- Option A: optimize call volume and add a graceful budget checkpoint before another pilot.
- Option B: raise the token cap without changing the loop.
- Recommendation: A. Option B increases cost while preserving an observed scaling defect.

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
