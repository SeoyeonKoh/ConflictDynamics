# Stale-context probes (2026-11-03)

Five `conflict-probe` cases in `probes/stale_context/`, rebuilt from HDS-008 in the real run
`runs/c16-real-r10-midweek-v2` (gpt-6-luna). Each asks the real model K times. "Before" is
master `9eedbe5` (the probe tool from this branch copied in); "after" is branch
`fix/stale-context`.

| case | problem | before | after |
| --- | --- | --- | --- |
| c1 | planned "웹 구현 마무리했어요" while 웹·모바일 구현 unfinished | 0/5 | 5/5 |
| c2 | planned "빌드와 배포가 끝났어요" before the build started | 0/5 | 5/5 |
| c3 | 16:30 judgement right after the 2nd return, old plan still in place | 5/6 | 6/6 |
| c4 | day review credits a colleague's finished task to oneself | 2/5 | 5/5 |
| c5 | a return at 16:00 re-plans, and the new plan takes up the return | 0/5 | 5/5 |

- c1, c2 and c5 fail before by construction: the planned line is sent without a model call, and
  no re-plan follows the return. After, the model is asked and gets it right every time.
- c3 is not a difference: 5/6 against 6/6 is within noise. The real run's 16:30 miss did not
  reproduce, so it was not a reliable model limitation.
- An earlier c3/c5 round shared the case's `rejections` list across worlds (fixed in the probe:
  fields are deep-copied); those rows were dropped.

Files: `before.jsonl` + `before_c3c5.jsonl`, `after.jsonl` + `after_c3c5.jsonl`.
