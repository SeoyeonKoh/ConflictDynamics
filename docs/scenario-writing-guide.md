# 좋은 시나리오를 쓰기 위한 지침

회사 세계 시나리오(`conf/scenario/company_c15/*.yaml`)를 쓰거나 고칠 때 보는 지침이다. 2026-10-05~06
세션에서 실 API 실행과 `conflict-probe` 실험으로 확인한 내용을 근거로 한다. 근거가 된 수치는 각 항목
끝에 적었다.

## 1. 시나리오가 하는 일

시나리오는 **고정된 회사**(프리셋: 페르소나·조직·사무실·핵심 Task 그래프) 위에 **이번 실험의 조건**을
얹는다. 일정과 작업량, 처음부터 담당자가 없는 Task, 문서, 업무 자료, 부서 프로젝트, 회의, 외부 사건,
개입이 여기에 해당한다. 에이전트가 읽는 글(Task 이름, 자료, 안건, 문서 형식)도 대부분 시나리오가
정한다. 그래서 **시나리오의 문장이 곧 에이전트의 세계**다.

```bash
uv run python -c "from conflict_sim.company_runtime import build_company_config as b; b('내_시나리오')"  # 검증
uv run conflict-company-experiment 내_시나리오 --days 1                              # 데모 실행(무료)
```

새 시나리오를 실험 실행기로 돌리려면 `src/conflict_sim/experiment.py`의 `SCENARIOS`에 이름을 넣는다.

## 2. 원칙

### 2.1 갈등은 구조에서 나오게 한다

페르소나에 "증거를 무시한다", "상대를 악의로 해석한다" 같은 성향을 넣지 않는다. 갈등은 구조가 만든다.
- 희소한 자원과 인력
- 서로 물린 의존 관계
- 빠듯한 마감
- 평가·승진처럼 제로섬인 보상
- 정보 비대칭

이 원칙이 깨지면 "갈등이 났다"가 아니라 "갈등을 시켰다"가 된다(`docs/company-world-plan.md`의 원칙).
긴장은 **수치로** 심는다. 예를 들어 P6-demand의 자료는 다음 분기 수요(개발 410인일)가 가용(360인일)보다
크다. 누가 무엇을 양보할지는 에이전트가 정한다.

### 2.2 세계에 사실을 둔다 (`materials`)

근거 자료가 없으면 에이전트는 확답을 피한다. 완료 시점을 물어도 "미확인", "추후 확정"이라고만
답하고, 문서는 원칙과 주의사항의 목록이 된다. 모든 Task에 그 일을 하는 데 필요한 사실을 자료로 준다.
- 대상과 규모(몇 가구, 몇 명), 기준선과 목표 수치
- 제약: 규정, 개인정보, 예산, 인력, 기기 범위
- 일정: 베타·출시·코드 프리즈 시점
- 기존 시스템과 그 한계

자료끼리 **수치가 맞물려야** 한다. T01의 "연동 가구 42만"과 P5의 "목표 신규 연동 2만"처럼 같은
세계를 가리켜야 한다. 일을 대신해 주는 정답(완성된 요구사항 목록 등)은 넣지 않는다. 자료는 재료이고,
산출물은 에이전트가 만든다.

> 근거: 한국어 1일 실행에서 자료와 확답 유도를 넣기 전과 후를 비교했다. "언제?" 질문에 시각으로 답한
> 비율이 0/12에서 11/17로, 문서 줄 중 수치가 든 비율이 50%에서 75%로 올랐다. 문서의 "미확인" 표현은
> 9%에서 0%가 됐다.

### 2.3 회의 안건에 판단에 필요한 정보를 다 넣는다

**회의 발언 프롬프트에는 Task 목록이 없다.** 발언하는 에이전트가 아는 건 안건 문장, 앞선 발언, 자기
기억, 페르소나뿐이다. 그래서 안건이 판단의 근거가 된다.
- Task마다 **어느 팀(또는 어떤 직무)에 맞는지** 적는다.
- **"맞는 것이 없으면 해당 없다고 말한다"**를 허용한다. "각 리드는 이 중 하나를 맡는다" 같은 구조는
  늦게 말하는 리드에게 남은 것 중 하나를 고르게 만든다.
- **주최자의 역할을 못박는다.** "주최자는 직접 맡지 않고 회의 직후 배정한다." 주최자도 "리드"라서,
  적어 두지 않으면 첫 발언에서 하나를 가져간다.
- 결정이 회의에 달려 있으면, 회의 직후 누가 무엇을 하는지(배정, 승인)를 적는다.

> 근거: `probes/kickoff/`. 기존 안건에서는 주최자가 첫 발언에서 거의 매번 Task를 가져갔다(8회 중
> T12 6회, T06 2회). 수정한 안건에서는 6/8이 "해당 없음"이었고, 시장출시 리드는 8/8 T12를 맡았다.

### 2.4 담당자를 지우면 적합한 팀 정보를 남긴다 (`unassigned`)

`unassigned`는 Task의 원래 담당자와 공동 작업자를 지운다. 원래 담당자가 정보였다면(예: T06 API
계약은 클라우드·API 엔지니어 HDS-007) 그 정보가 사라지지 않도록 안건이나 자료에 적합한 팀을 적는다.

### 2.5 문서는 형식은 구체적으로, 기준은 통과 가능하게

`deliverables`(Task별)와 `default_deliverable`(나머지 전부)은 문서의 **형식**(`format`)과 리뷰
**기준**(`criteria`)을 정한다.
- 형식은 줄 단위로 구체적으로 쓴다. 예: `'R<n>: <요구사항> - 측정 지표: <지표>'`. 뒤 Task가 ID(R2,
  TC3)로 인용할 수 있게 한다.
- 기준은 **자료와 입력만으로 충족할 수 있게** 쓴다. 이 사무실에는 문서·기록·요약 말고 파일이 없다.
  "검증 근거를 첨부"처럼 세계에 존재할 수 없는 것을 요구하면, 증거를 중시하는 리뷰어가 반려를
  반복한다.
- 문서가 많을수록 판단 입력이 커진다. 모든 Task에 문서를 두면 토큰이 약 30~40% 는다.

> 근거: p0_kickoff v1에서 증거 부족을 이유로 한 Task가 14번 연속 반려됐다. 이후 반려는 2회까지만
> 허용한다(그다음은 승인만 가능). 모든 Task에 문서를 둔 실행은 토큰이 +36%였다.

### 2.6 일정은 계산해서 정한다 (`task_runtime`, `projects`)

- 하루는 32틱(09:00~17:00, 틱당 15분)에 야근 `overtime_ticks`가 붙는다. 2일이면 핵심 틱은 64다.
- Task마다 `effort_ticks`(작업량)와 `due`(마감 틱)를 정한다. **선행 Task의 작업량 합(크리티컬 패스)이
  마감보다 길면** 그 Task는 처음부터 늦는다. 의도한 압박이 아니라면 피한다.
- 리뷰가 있는 Task는 작업이 끝나도 승인까지 기다린다. 승인자의 부담(동시에 몇 건을 리뷰하는지)도
  계산에 넣는다.
- 부서 프로젝트(`projects`)의 단계는 그 부서 안에서 돌아가며 맡고, 프로젝트 리드가 승인한다. 다른 부서
  단계(`department`가 다른 것)는 교차 지점이다. 그 부서는 자기 일과 저울질하고, 프로젝트는 기다린다.
  `start_after`로 핵심 Task 완료를 기다리게 할 수 있다.

### 2.7 부서 ID는 그대로 두고 이름만 바꾼다

부서 ID(`Software Engineering` 등)는 사무실 지도의 자리 배치와 프로젝트 담당 순환이 키로 쓴다. 다른
언어로 바꿀 때는 ID를 그대로 두고, 조직 파일의 `department_names`에 에이전트가 들을 이름을 적는다.

### 2.8 언어

`language: Korean`으로 하면 에이전트의 발화, 메시지, 문서, 성찰이 한국어로 나온다. 한국어 시나리오는
Task 이름, 자료, 안건, 문서 형식도 한국어로 쓰고, 한국어 프리셋(`preset: large_korean_enterprise_20_ko`)을
쓴다. 엔진이 쓰는 문구(거부 사유 "T10 is blocked by T07", "I chose to …" 기록)는 영어로 남는다.

### 2.9 한 번에 한 변수만 바꾼다

비교 실험은 `extends`로 기존 시나리오를 상속하고 **조작 변수 하나만** 바꾼다. 예:
`p0_documents`는 `p0_kickoff`에 `default_deliverable` 하나만 더했다. `research_question`,
`manipulated_variable`, `manipulation_check`(조작이 실제로 들어갔는지 확인할 방법),
`observable_outputs`를 채워, 결과를 볼 때 무엇을 비교하는지 분명히 한다. `extends`는 최상위 키 단위로
덮어쓴다. `engine`을 바꾸려면 `engine` 블록 전체를 다시 써야 한다.

## 3. 필드 요약

| 필드 | 뜻 | 메모 |
|---|---|---|
| `extends` | 상속할 시나리오 | 최상위 키 단위 덮어쓰기 |
| `id`, `research_question`, `manipulated_variable`, `fixed_variables` | 실험의 정체 | 비교의 기준 |
| `preset`, `language` | 회사 프리셋, 대화 언어 | 기본 `large_korean_enterprise_20`, `English` |
| `max_days`, `overtime_ticks`, `seed` | 길이, 야근 틱, 난수 | `--days`로 실행 시 줄일 수 있음 |
| `task_runtime` | 핵심 Task별 `effort_ticks`, `due` | 프리셋의 Task와 정확히 일치해야 함 |
| `unassigned` | 담당자 없이 시작할 Task | 적합한 팀 정보를 남길 것 |
| `deliverables` | Task별 문서 `format`·`criteria` | 기준은 통과 가능하게 |
| `default_deliverable` | 나머지 모든 Task의 문서 | 토큰 +30~40% |
| `materials` | Task ID → 사실 자료 | 모든 Task에, 수치가 맞물리게 |
| `projects` | 부서 프로젝트: `id`, `name`, `department`, `lead`, `due`, `start_after`, `steps` | 단계: `key`, `name`, `effort_ticks`, `department`(교차), `after` |
| `engine.meetings` | `id`, `day`, `tick`, `duration_ticks`, `organizer`, `participants`, `agenda`, `place`, `public`, `rule` | `rule: everyone`이면 모두 한 번씩 순서대로 말함 |
| `engine.shocks` | 외부 사건(E01~E10): `kind`, `day`, `tick`, `task`, `resource`, `agent`, `amount`, `until_tick` | 의존 실패, 마감 단축, 자원 손실, 평가 발표 등 |
| `engine.interventions` | 개입: `kind`, `day`, `tick`, `actor`, `task`, `target`, `amount` | 매니저 명확화, 업무 재분배, 비공개 중재 등 |
| `engine.evaluation_season`, `promotion_slots` | 평가 시즌, 승진 자리 | 평가는 스트레스 요인 |
| `observable_outputs`, `theory_tags`, `manipulation_check` | 측정 계획 | |

## 4. 유료 실행 전 점검

1. **구성 검증:** `build_company_config('이름')`이 오류 없이 만들어지는지 확인한다(자료의 Task ID 오타도
   여기서 잡힌다).
2. **데모 1일:** `uv run conflict-company-experiment 이름 --days 1`로 무료로 끝까지 도는지 본다.
3. **프롬프트 확인:** `uv run conflict-probe 케이스.yaml --dry`로 에이전트가 실제로 받는 입력을 읽는다.
   자료·안건·Task 이름이 의도대로 보이는지 확인한다.
4. **핵심 상황 프로브:** 시나리오가 노리는 순간을 케이스로 만들어 실 API로 5~10회 돌린다. 예: 킥오프
   첫 발언(`call: speak`), 완료 시점 질문, 막힌 작업 앞의 판단. 회의 발언 하나에 몇 천 토큰이라 싸다.
   ```bash
   ALLOW_PAID_API_EXPERIMENTS=1 uv run conflict-probe probes/kickoff/*.yaml
   ```
5. **짧은 실 실행:** `--days 1 --live-port 8765`로 하루를 돌리고 뷰어로 본다. 20명 2일 실행은 입력 약
   500만~650만 토큰이었다.

## 5. 프로브로 확인할 만한 질문

| 질문 | 케이스의 모양 |
|---|---|
| 회의에서 각자 맞는 일을 맡는가 | `call: speak`, `speak.meeting`, 앞선 발언(`before`) |
| 완료 시점을 물으면 시각으로 답하는가 | `context.inbox`에 질문, `expect`에 시각 정규식 |
| 막힌 작업을 시도하지 않는가 | 실제 체크포인트, `agent: all`, `refused: false` |
| 스트레스가 말투에 드러나는가 | `context.stress: 0.8`, `call: speak` |
| 서운한 상대에게 어떻게 말하는가 | `context.relations`, `context.memories` |

케이스 예시는 `probes/`에 있다. 떼어 낸 가상 상황에서는 문제가 잘 재현되지 않는다. 실제 실행의
체크포인트에서 잰 숫자를 더 믿는다.
