# Token Efficiency Hypothesis Analysis

기준일: 2026-10-05. 분석 시작 branch는 로컬 `master`, 1차 계측 commit은 `45893f2`.
원격 기준 코드 `86891e7` 위의 1차 계측을 재사용했다. 이번 변경은 size/hash 계측,
validation failure metadata, 분석 스크립트·테스트·문서뿐이다. prompt/pruning/cache/retry/
activation/대화/성찰/기억의 동작은 변경하지 않았다. 유료 API 실행 없음.

**결론: H3 IMPLEMENT NEXT, H1 MEASURE MORE, H2 LOW PRIORITY.**
큰 반복 입력은 확인됐지만 token 절감률은 미측정이다. 다음 구현은 최대 2개를 채우는 대신
근거가 가장 분명한 H3 한 개만 추천한다.

분석 산출물: [machine-readable summary](../../results/token_efficiency/hypothesis_analysis.json),
[재현 스크립트](../../scripts/token_efficiency_analysis.py),
[1차 진단](token_efficiency_audit.md).

## Measurement method

- 고정 scripted smoke: `build_company_config('s0_smoke')`, 20 agents, seed=1413, 32 ticks,
  기존 DemoBackend와 동일 worker/구성. S0–S4/I1–I3 연구 실험이나 ablation이 아니다.
- `TraceDemo`는 request를 그대로 DemoBackend에 전달하고 기존 `log_call`/ContextVar를
  사용한다. production OpenAIBackend와 같은 `completion_metadata`/`embedding_metadata`
  helper를 사용해 가짜 token 수를 만들지 않는다. token 필드는 **null**이다.
- `Agent._complete`에서 fixed instructions/system persona의 size/hash를 전달한다.
  backend에서는 top-level payload와 `view`의 하위 section을 분리한다. 모든 hash는 SHA-256.
  raw prompt/query/응답/error body는 저장하지 않는다. Pydantic error의 임의 필드명까지
  노출되지 않도록 error location도 hash로 기록한다.
- 문자 수는 **token이 아닌 proxy**다. JSON value를 재직렬화한 크기이며 key/구분자와 일부
  escape overhead는 section 합계에 포함되지 않는다. 비중 분모는 system+prompt 문자다.
  response_format schema·SDK envelope가 포함된 전체 API token 비용의 비중이 아니다.
- H1 연속 동일률은 같은 agent·call_type 내의 인접한 호출 쌍에 대한 exact hash 비교다.
  같은 tick의 retry도 포함하며 연속한 두 tick만을 의미하지 않는다. act의 137회에서
  agent별 최초 20회를 제외해 **117쌍**을 비교했다.
- H3 duplicate는 `(model, exact text hash)`의 총 등장 수−unique 수. normalization은
  whitespace collapse만 수행하며, 숫자/tick/agent/task ID를 임의로 제거하지 않는다.

재현 (유료 API가 아니라 고정 demo만 실행):

```bash
python scripts/token_efficiency_analysis.py --output results/token_efficiency-new
```

출력 디렉터리는 덮어쓰지 않는다. 상세 audit는 재생성 가능하고 Git에는 summary만 저장했다.

## H1 Prompt Payload Repetition

### 결과

255 completion 전체의 system+prompt: **2,253,439 characters**.
act 137회의 system+prompt: **1,677,819 characters**.
가장 큰 누적 계측 section은 `fixed_instructions`: 해당 label의 call_type 합계 **894,816 chars**
(전체 입력 문자의 39.71%). act fixed instructions만 **745,417 chars**이다.
MemoryStore의 지시문은 `system` label로 별도 측정하며 위 합계에 포함하지 않았다.

| act section | 평균 문자 | 최대 문자 | act 입력 문자 비중 | 같은 agent의 연속 act 동일 비율 |
|---|---:|---:|---:|---:|
| `fixed_instructions` | 5,441.0 | 5,441 | 44.43% | 117/117 (100.00%) |
| `view.tasks` | 3,823.6 | 11,104 | 31.22% | 17/117 (14.53%) |
| `task_board` | 665.0 | 1,248 | 5.43% | 14/117 (11.97%) |
| `memories` | 498.5 | 1,036 | 4.07% | 0/117 (0.00%) |
| `system_persona` | 331.9 | 363 | 2.71% | 117/117 (100.00%) |
| `view.present` | 324.7 | 418 | 2.65% | 38/117 (32.48%) |
| `plan` | 233.0 | 259 | 1.90% | 117/117 (100.00%) |
| `view.blocked` | 175.5 | 742 | 1.43% | 62/117 (52.99%) |
| `view.places` | 144.0 | 144 | 1.18% | 117/117 (100.00%) |
| `private_memory` | 30.2 | 119 | 0.25% | 97/117 (82.91%) |
| `view.last_meeting` | 2.0 | 2 | 0.02% | 117/117 (100.00%) |
| `view.help_wanted` | 2.0 | 2 | 0.02% | 117/117 (100.00%) |
| `asked_before` | 2.0 | 2 | 0.02% | 117/117 (100.00%) |


- **행동 판단에서 가장 큰 평균/누적 section:** fixed instructions, 매번 5,441 chars,
  act input의 **44.43%**. 같은 agent 연속 판단 117/117쌍에서 동일했다.
- **단일 호출의 가장 큰 section:** `act/view.tasks`, 최대 **11,104 chars**.
  평균 3,823.6 chars/31.22%지만 연속 동일은 **14.53%**로 낮다. 업무 상태·완료 증거가
  계속 변하므로 이를 고정 불변 정보처럼 생략하면 안 된다.
- **가장 많이 반복되는 의미 있는 section:** fixed instructions, system persona, daily plan,
  장소 목록은 연속 비교에서 100% 동일. plan은 평균 233 chars/1.90%, persona는
  331.9 chars/2.71%로 fixed instructions보다 작다.
- `task_board`는 평균 665 chars/5.43%, 연속 동일 11.97%. 이번 sample에서 task board
  filtering을 가장 먼저 구현해야 한다는 근거는 약하다.
- `help_wanted`, `last_meeting`, `asked_before`는 대부분이 아니라 **이 sample에서는 모두
  빈 배열(2 chars)**이었다. 100% 반복이어도 절감 규모는 작고 실제 사용되는 경로의
  최대 크기·효과를 이 결과로 평가할 수 없다.
- 별도의 end-of-day reflection `records`는 평균 6,162 chars, 최대 7,250 chars이다.
  agent별 1회라 연속 반복률은 산출하지 않는다. act의 반복과 혼합해서 해석하지 않는다.

### 어떤 정보가 실제로 포함되나?

근거 함수: `Agent._system/_base_payload/_act/_thread_payload`, `Loop._view`,
`Environment.task_view`, `Org.record/board`.

- role/department/work priority/goal은 runtime persona에 포함된다. authority 전체가 별도의
  고정 section으로 매번 들어가는 것은 아니며, 업무 role·can_approve/can_reject 등으로
  View에 나타나는 권한 정보는 `view.tasks`에 포함된다.
- agent-owned/참여 tasks, task records와 summaries는 `view.tasks` 안에 들어간다.
  `TaskView.summary` 및 `record` 내 summary 등 일부 정보는 구조상 중복될 수 있으나
  이번에는 이를 제거하지 않았고 31.22% 전체를 중복 낭비라고 주장하지 않는다.
- blocked tasks/help wanted/present agents/공간·자원/inbox/rejected는 각각 View 하위에서
  측정한다. daily plan과 recalled `memories`, `private_memory`는 분리했다.
- conversation decision의 utterances는 평균 1,485.7 chars/36.01%, speech는
  1,447.1 chars/42.90%. `Agent.speak`가 target 본문도 다시 포함하지만, 그 발화를 명시해
  답변 대상을 제공하는 의미가 있으므로 무조건 삭제 후보로 취급하지 않는다.
- manager에게 전달하는 meeting transcript는 `view.last_meeting`; 이 smoke에서는 비어 있다.

### 예상 절감 가능성·위험

**가장 큰 반복 지점은 task_board보다 fixed instructions다.** 이미 instructions를 system의
앞에 놓고 persona를 뒤에 붙인다. 이는 입력이 없어지는 것이 아니라 provider cache가
동일 prefix를 활용할 여지를 만드는 구조다. 현재 실제 cached_tokens는 측정하지 않았다.

local hash가 같다고 모델에 그 section을 보내지 않아도 된다는 뜻은 아니다. 각 completion은
독립적인 API request다. instructions 생략/축약이나 role/task 정보 filtering은 행동 변화
위험이 있다. 정보가 중복인 field의 등가 표현도 LLM에는 prompt 변경이며 실증이 필요하다.
우선 현재 section hash/크기와 실제 cached/input tokens를 연결해 반복 입력의 유효 비용을
확인해야 한다. **44.43%는 token/cost 절감률이 아니다.**

## H2 Retry Amplification

### Call tree / theoretical maximum

`Loop.tick`은 최초 action 이후 환경 거절 시 대체 action 최대 2회를 요청한다.
각 action의 `Agent._ask`는 JSON/Pydantic/추가 검증 실패 시 completion을 1회 더 요청한다.

```text
initial act (semantic attempt 0)
 ├─ completion 1 → invalid JSON/schema
 └─ completion 2 → valid action → environment rejects
replacement act 1
 ├─ completion 3 → invalid JSON/schema
 └─ completion 4 → valid action → environment rejects
replacement act 2
 ├─ completion 5 → invalid JSON/schema
 └─ completion 6 → valid action → accept or final rejection
```

따라서 **agent당 tick당 action 선택에 최대 6 completion**:
첫 판단 대비 최대 5회 추가(+500%, 6배)다. 전원 free/reactive인 극단적 tick에서는
20×6=120 action completions. plan/conversation/reflection은 이 상한 밖의 별도 호출이다.
이 경로를 강제 invalid→valid/환경 거절 fixture로 테스트해 6회를 확인했다. fixture 수치는
실제 demo 발생률에 넣지 않았다.

API/rate-limit transport retry는 별도 계층이다. wrapper는 RATE_LIMIT_WAITS=12까지 시도하며
SDK 내부 retry도 있을 수 있다. 성공 응답 usage와 HTTP 시도 수는 다르다. 이번 demo에는
실제 transport가 없으므로 발생 빈도를 관찰한 것으로 해석하지 않는다.

### Observed demo frequency

| 항목 | 관측값 |
|---|---:|
| 전체 completions / JSON decisions / speech | 255 / 233 / 22 |
| JSON first-attempt (두 retry flag 모두 false) | 205 |
| act completions | 137 |
| act normal first-attempt flag | 109 |
| environment/action retry flag만 true | 28 |
| JSON validation retry / 중첩 retry | 0 / 0 |
| 동일 agent·tick의 act completion 그룹 | 136 |
| 2회 이상 act completion이 있는 그룹 | **1** |
| 같은 그룹에서 첫 completion 위로 추가된 호출 | **1** |
| retry flag는 있지만 선행 act completion이 없는 그룹 | **27** |

flagged/unflagged 비율은 28/109=25.69%다. 그러나 이는 **25.69%의 불필요한 LLM 증폭이
관측됐다는 뜻이 아니다**. 계획 fast path가 LLM 없이 work action을 반환한 뒤 환경에서
거절될 수 있다. 그 뒤의 27 retry completion은 해당 agent·tick의 첫 LLM 판단이었다.

실제 동일 agent·tick별로 한 completion을 기준으로 보면 **137/136=1.00735**, 추가 판단은
**1/136=0.735%**다. 이 역시 136개의 호출 그룹을 기준으로 한 계수이며, 모든 simulation
행동 640회가 분모이거나 그 1회가 불필요하다는 의미는 아니다.

### 주요 원인과 절감 가능성

환경 rejection은 28건: **awaiting review 27건**, **already done 1건**.
근거: `Environment._refusal`의 work lifecycle/done 검사와 `Loop._apply`의 rejected event.
계획 fast path와 그 이후 최신 환경 적용 사이의 상태 차이가 retry를 유발할 수 있다.
`Agent._act`의 free-work 후보는 review를 제외하지만 모든 기존 planned block의 무효 상태를
같은 방식으로 해결하는 것은 아니다.

demo JSON validation failure는 0건. rate-limit은 N/A. 강제 validation failure fixture와
mock transport test는 계측 및 상한 검증이며 실제 발생률의 근거가 아니다.

가장 안전한 후속 검토는 rejection reason과 계획의 lifecycle 조건 불일치를 정확히 좁히는
것이다. 다만 이미 첫 LLM 판단인 27회를 제거하면 대체 행동을 정할 경로도 함께 고려해야
한다. **거절 event를 예방해도 27 completion이 줄어든다고 볼 수 없다.** retry 횟수를
일괄 줄이거나 JSON validation을 약화하는 방법은 추천하지 않는다. 이 sample의 call 절감
근거로 H2를 먼저 구현하기에는 효과가 작고 실제 API의 잘못된 출력 빈도도 미측정이다.

## H3 Retrieval Embedding Repetition

### 결과

| 항목 | 관측값 / 분모 |
|---|---:|
| retrieval query text / 요청 | **193 / 193** (전부 single-text) |
| unique exact `(model,text)` | **82** |
| query 문자 합계 / 평균 / 최대 | **13,714 / 71.1 / 249 chars** |
| exact duplicate text의 문자 합계 | **6,721 chars** (조건부 재사용 상한) |
| exact duplicate | **111/193 = 57.51%** |
| whitespace-normalized unique / duplicate 비율 | 82 / 57.51% |
| 같은 agent 내 중복 | **36/193 = 18.65%** (pooled) |
| 같은 agent 연속 query 쌍 | **36/173 = 20.81%** |
| 여러 agent가 공유한 exact query hash 수 | 27 |
| agent 간 공유 cache의 추가 가능성 | 111−36 = **75 texts** |
| agent당 전체 query 수 범위 | 5–16 |
| agent당 중복률 범위 | 0–40% |
| 한 agent·tick의 최대 retrieval query 수 | 7 |
| memory write embedding batches | 24 (retrieval과 분리) |

per-agent와 agent·tick 내역은 JSON에 저장했다. 이번 smoke의 193개는 모두
`Agent._recall`에서 생성됐으며 reflection query는 발생하지 않았다. vectors가 있는
act/decide/summarize가 한 query씩 호출한다. query는 상황/위치, inbox, blocked owner와 거절
이유 또는 마지막 conversation text/task 설명으로 구성된다. agent persona 자체는 query에
포함되지 않으므로 다른 agent도 같은 query를 만들 수 있다.

### Cache가 실제 적용되는가?

`cli.simulate`는 config의 embed_cache가 있으면 전체 llm을 EmbedCache로 감싼다. 따라서
**CLI 경로에서는 retrieval query도 cache 적용 대상**이다. purpose별 우회가 없다.
반면 **`experiment.run_scenario`는 OpenAIBackend를 직접 사용**한다. C14 adapter가 반환하는
config의 embed_cache도 기본 null이며, C16 runner에 cache wrapper가 연결돼 있지 않다.
즉 C16 runner는 exact 반복 query가 있어도 재계산한다.

`EmbedCache.embed`의 키는 model+exact text의 hash다. whitespace 차이는 서로 다른 key지만
이번 관측에서는 whitespace normalization으로 추가 duplicate가 늘지 않았다. 남은 unique
query에는 phase/place, task dependency/owner, inbox/새 발화, 거절 원인이 실제로 달라지는
경우가 있다. 숫자나 ID를 제거하면 의미가 달라질 수 있으므로 cache normalization을
구현하거나 semantic similarity 모델을 추가하지 않는다.

### 예상 절감 가능성 / semantics

cold cache, 동일 model, exact text, 순차 miss 또는 single-flight 처리라는 조건에서 이 sample의
retrieval **최대 111 texts 및 single-text requests**를 재사용할 수 있다. 이는 57.51%의
**retrieval 요청 상한**이지 completion/input token/전체 비용 절감률이 아니다.

**절대 입력 규모도 함께 본다.** 검색 query 전체는 13,714 chars, exact duplicate가 차지하는
문자는 6,721 chars다. act 입력 1,677,819 chars와는 규모가 다르므로 H3를 전체 token 비용
낭비의 주원인으로 확정하지 않는다. H3 1순위의 근거는 명확한 요청 재사용 가능성과 작은
구현 범위이며, 최대 금액 절감 순위는 실제 API 자료가 필요하다.

현재 EmbedCache는 동시 cold miss를 모두 병합하는 single-flight가 아니다. 여러 thread가
동시에 같은 query를 처음 요청하면 중복 API 호출이 남을 수 있어 실현 절감은 상한보다 낮다.
이번에는 cache를 연결하거나 miss 동작을 바꾸지 않았다. write embedding까지 포함한
cache 효과를 111회 수치에 섞지도 않았다.

query **vector만** 같은 model/text에서 재사용하고 `MemoryStore.retrieve`는 매번 실행하면
현재 agent의 records/mood/recency/last_access를 반영하는 ranking과 memory update를 유지할
수 있다. **retrieved IDs/결과를 캐시하는 것은 다른 변경**이며 추천 범위 밖이다. model/text
키·vector shape·model 변경 시 invalidation을 검증해야 한다. 저위험이지만 실제 embedding
재현성과 LLM concurrency/latency, token-budget pause 시점 변화까지 0위험이라고 보장하지
않는다. 완료 run의 동작 비교와 budget/usage 기록 검증이 필요하다.

## Comparison

| 가설 | 관측된 문제 크기 | 예상 절감 효과 | 구현 난이도 | 행동 변화 위험 | 근거 강도 | 추천 |
|---|---|---|---|---|---|---|
| H1 Prompt repetition | act instructions 5,441 chars/44.43%, 연속 100% 동일; tasks 31.22% | 실제 cached/input tokens 없음. 반복 문자 규모만 확인 | cache 검증 낮음; pruning 중간 | instructions/task pruning 중간~높음 | 반복·크기 강함, 실제 token 절감 미확인 | **MEASURE MORE** |
| H2 Retry amplification | retry flag 28; 실제 같은 agent·tick 추가 completion 1 | 이 sample의 추가 판단은 1회; 28회 절감으로 해석 불가 | 원인별 repair 중간 | 선택/종료·오류 처리에 영향 가능 | 상한 강함; API failure 빈도 미확인 | **LOW PRIORITY** |
| H3 Retrieval embedding reuse | 193 queries 중 111 exact duplicate, 57.51% | 조건부 최대 111 texts/requests, actual 비용 미확인 | 기존 wrapper 연결 낮음 | vector만 재사용하면 낮음; result cache는 별개 | exact duplicate·미연결 코드 강함, API 실현 효과 미확인 | **IMPLEMENT NEXT** |

## Recommendation

**다음 1–2시간 구현 작업은 H3 한 개만 추천한다.**

1. C16 runner에 기존 exact model/text EmbedCache를 명시적으로 연결하는 작은 변경.
   현재 null인 cache config/path와 CLI 경로를 맞추고, retrieval ranking은 매번 계산한다.
   vector 동일성·usage/budget 처리·동시 cold miss·기록 경로·회귀를 mock/scripted로 검증한다.
   목표는 source가 분명한 111 repeat texts의 재사용 가능성 검증이며 API 비용 절감률을
   사전 확정하지 않는다. 별도 cache algorithm이나 결과 cache까지 한 번에 확장하지 않는다.

**2위는 H1의 추가 측정**이다. 현재 44.43% 지시문 반복과 31.22% task payload를 actual
cached/input tokens와 연결해야 한다. 이번에는 실제 pruning/task board filtering을 다음
구현 대상으로 승인할 충분한 행동 보존 근거가 없다. H2는 보류: 실제 API에서 validation
retry가 높다는 새 근거가 생기면 순위를 재검토한다.

Event-driven activation, agent sampling, 대화 제한, reflection 제거, memory 삭제 같은
큰 architecture 변경은 이번 추천에서 제외한다. 이번 작업에서는 위 H3도 구현하지 않았다.

## Validation

- 1차 기준과 이번 계측 smoke의 결과, event, memory rows/vector/retrieval log, agent snapshot,
  completion request multiset, embedding batch 입력 multiset checksum이 동일:
  `bece6540fa109233575014f9645c6b8a61e01f8d21fd599c18dacea66185a8e3`.
  255 completions, 217 embedding calls, 904 embedded texts도 동일하다.
- size/hash 및 whitespace 차이, payload 값 변경 반영, raw text 미노출, validation error
  metadata의 민감 문자열 미노출, thread별 system section 격리, retry 분모, model별 query key,
  실제 nested retry 최대 6회 경로를 테스트했다. 기존 테스트 파일의 기존 테스트는 유지했다.
- 최종 전체 suite: **512 passed, 1 skipped** (선택적 real CRAFT integration).
  계측/분석 tests: **18 passed**; 마지막 query 문자 크기 summary 확장 후 분석 tests
  **4 passed**. `ruff check .`, 변경 Python format check, `git diff --check` 통과.
  최초 전체 실행의 localhost bind 권한 실패 2건은 권한 부여 후 재실행에서 해결했다.

## What remains unknown without a real API run

- 지금 모델의 input/output/cached tokens와 section별 실질 token/cost 기여도.
- actual query vector cache의 동시 miss율, 재사용 후 API latency/rate limits와 비용 절감.
- 실제 JSON/Pydantic validation failure 및 transport retry 빈도.
- 실제 persona/대화/긴 task deliverable이 만든 payload 크기와 32틱 완주 여부.
- 0건/빈 section인 reflection query, meeting transcript, asked_before/help의 다른 경로 효과.
- caching/pruning/repair 이후 LLM 행동 및 token-budget pause 시점의 변화.

이 sample의 57.51%/44.43%/0.735%는 각각 다른 분모를 가진 문자·query·completion 지표다.
서로 곱하거나 전체 API token/cost 절감률로 변환하지 않는다. 승인된 API run이 없으므로
과거 pilot의 call/token 분해를 이번 scripted 데이터로 대체하지 않는다.
