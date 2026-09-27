# C 파트 진행 보고서 (팀원 공유용)

## 1. 현재 진행 상태

| 구분 | 상태 | 핵심 결과 |
|---|---|---|
| C-13 엔진 기능 | 완료 | 20인 조직, 권한, 업무 DAG, 회의·비공개 대화, 충격·개입 실행 가능 |
| C-14 페르소나·조직 | 완료 | 확정된 A1B1C1 설계를 유지한 채 엔진과 연결 |
| 20인 통합 테스트 | 통과 | 20명·15개 업무·32 ticks가 오류와 deadlock 없이 완료 |
| C-15 시나리오 | 완료 | baseline 1개, 구조적 충격 4개, intervention 3개 |
| C-16 실험 준비 | 완료 | 반복 실행 runner, seed, manifest, 결과 저장 구조 준비 |
| 실제 API 실험 | 대기 | 비용 승인이 필요한 단계라 자동 실행하지 않음 |
| C-17 보고서 | 초안 완료 | 최종 실험값만 채우면 되는 목차와 작성 기준 마련 |

현재 코드는 전체 테스트 **459개 통과, 선택적 CRAFT 테스트 1개 skip** 상태다. 작업은 로컬
커밋 5개로 나눠 저장했으며 GitHub에는 아직 push하지 않았다.

## 2. 진행한 내용

### C-13: 20인 회사 시뮬레이션 엔진

기존 엔진에 C-15/C-16 실험에 필요한 최소 기능을 추가했다.

- C-14의 20명, 보고체계, 권한, 초기 관계와 15-task DAG를 실제 실행 config로 변환
- `assign / approve / reject / evaluate` 권한을 position별 authority와 연결
- 업무의 `ready → in progress → blocked → review → done/overdue` 전이 구현
- dependency 해소, review 거절 후 rework, 권한 없는 행동의 안전한 rejection 구현
- 명시적 참가자와 agenda가 있는 회의, deterministic turn-taking, 비공개 session 구현
- public/co-present/private 범위를 구분하고 hearsay 출처를 memory에 보존
- blocked task, 불가능한 잔여 workload, overdue, unread message를 stress와 연결
- overtime, workload, evaluation 및 promotion slot을 관측 가능한 상태로 저장
- scenario YAML의 `(day, tick)`에 따라 shock과 intervention이 발생하도록 구현

관리자 LLM의 동적 task 생성도 별도 조건으로 지원하되, 재현 가능한 기본 실험에서는 C-14의
고정 15-task DAG를 사용한다.

### C-15: 실험 조건

모든 조건에서 persona, 조직, DISC, 권한, office와 기본 task 구조는 동일하게 유지한다.

| 조건 | 변경되는 변수 |
|---|---|
| S0 Baseline | 구조적 shock 없음 |
| S1 Dependency Failure | 선행 업무 T01의 일시적 이용 불가 |
| S2 Deadline Pressure | 동일 workload에서 T14 deadline만 12 ticks 단축 |
| S3 Resource Competition | meeting room 수용량만 10명에서 4명으로 감소 |
| S4 Evaluation Season | 평가 기간 활성화 및 promotion slot 1개 설정 |

Intervention은 manager clarification, deadline 일부 복원, private mediation 세 가지다. 각
intervention은 대응되는 no-intervention 조건과 비교할 수 있다.

### C-16/C-17: 실행 및 보고 준비

각 run은 resolved config, git commit, seed, model ID, token usage, event log, memory, frame,
conversation corpus와 최종 상태를 저장한다. CRAFT는 생성 이후 별도로 실행하는 observer로
유지하며, 점수가 agent의 판단이나 종료 조건에 들어가지 않는다. C-17 문서는 결과를
임의로 채우지 않고 실제 실험값을 넣을 위치만 준비했다.

## 3. 주요 판단과 근거

1. **C-14를 다시 설계하지 않았다.** 이미 팀에서 확정한 A1B1C1이 source of truth이므로,
   persona나 조직을 수정하는 대신 별도 adapter로 현재 엔진에 연결했다.
2. **갈등을 persona에 직접 넣지 않았다.** 합리적인 agent를 유지하고 dependency, deadline,
   resource, evaluation 같은 구조적 조건이 interaction을 발생시키도록 했다.
3. **scenario마다 원칙적으로 한 변수만 변경했다.** 조건 간 차이를 해석할 수 있도록
   persona와 task baseline을 고정하고 manipulation check를 명시했다.
4. **회의 발언 순서는 deterministic하게 시작했다.** 기본 실험에서 불필요한 LLM bidding
   변동을 줄이고, 참가자·시간·종료 여부를 재현할 수 있게 하기 위해서다.
5. **근거 없는 overtime stress 계수를 만들지 않았다.** 야근 ticks는 기록하지만, 별도
   계수가 정해지기 전에는 기존 workload pressure만 stress에 반영한다.
6. **유료 API를 자동 실행하지 않았다.** 약 1,400회 수준의 보수적 completion-call 상한이
   있어, 명시적인 비용 승인 전에는 demo/dry-run까지만 수행하도록 차단했다.

## 4. 통합 테스트 결과와 해석 범위

20인 scripted smoke에서 20명 모두 의미 있는 업무 또는 interaction 경로를 가졌고, 15개
업무는 tick 22까지 모두 완료됐다. 32개 session이 생성됐으며 crash, 영구 idle, session
deadlock은 없었다. 거절된 행동 59건은 공간 경쟁 8건과 권한·review state를 지키기 위한
안전한 거절 51건이었고 진행을 막지 않았다.

이 수치는 **엔진 통합 테스트 결과**이지 사람의 갈등 행동이나 scenario 효과에 대한 연구
결과가 아니다. 실제 조건 비교는 승인된 LLM pilot과 반복 실험 이후에만 해석한다.

## 5. 남은 결정과 다음 단계

팀에서 지금 결정할 핵심 사항은 **실제 OpenAI baseline pilot 1회를 실행할지**다. 실행 시
먼저 1회만 돌려 JSON 안정성, token 사용량, latency, task starvation과 session 증가를
검사한 뒤 반복 실험 여부를 다시 판단한다.

CRAFT 모델 asset과 overtime 별도 stress 계수는 후속 결정 사항이며, 현재 simulation 실행을
막지는 않는다. 다음 회의에서는 C-15 조건과 intervention 비교 범위를 확인하고, pilot 비용
승인 여부만 결정하면 된다.
