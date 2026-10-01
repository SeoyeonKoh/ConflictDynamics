# C-16 실제 API Pilot 결과 공유

## 한눈에 보기

- 실행일: 2026-10-01
- 모델: `gpt-6-luna`
- 대상: HDS 20-agent company simulation
- 실제 API 연결 및 structured output: 정상
- 최종 상태: **부분 실행 후 token 안전 한도로 중단**
- 완주한 연구 run: 없음
- 세 시도 합산 추정 비용: 약 **$0.08**

이번 pilot의 목적은 실제 API 환경에서 20인 simulation이 기술적으로 실행되는지 확인하는
것이었다. 모델 연결, 영어 runtime prompt, JSON 응답, event 기록은 정상 작동했다. 다만
현재 엔진은 매 tick의 판단·재시도·memory embedding 호출량이 많아 1일 run을 완주하지
못했다. 따라서 이번 결과는 scenario 효과나 갈등 행동에 대한 연구 결과가 아니라, 다음
실험 전에 해결해야 할 scale 문제를 확인한 engineering pilot이다.

## 실행 전 언어 확인

CRAFT 적용을 고려해 실제 LLM과 corpus에 들어가는 언어를 확인했다.

- 에이전트 식별자: `HDS-001`부터 `HDS-020`
- 업무 목표, 업무 우선순위, persona: 영어
- conversation 생성 언어: 영어
- 한글 이름: 문서용 `display_name`에만 존재

따라서 한글 이름이 CRAFT 입력에 직접 들어가는 문제는 없다. 확정된 C-14 문서는 그대로
유지하고 runtime adapter만 검증했다.

## 실제 실행 결과

| 시도 | 조건 | 결과 | 기록된 token |
|---|---|---|---:|
| 1 | 2일 S0 baseline | daily plan의 512-token 출력 한도로 중단 | 9,895 |
| 2 | 판단 출력 한도를 2,048로 수정한 S0 baseline | 기존 100k 총 token 한도로 tick 0에서 중단 | 100,767 |
| 3 | 1일 `s0_smoke`, 총 500k token 상한 | tick 5에서 안전 중단 | 503,945 |

세 번째 시도는 추가 condition을 실행하지 않고 종료했다. 최종 시도에서 다음 항목이
기록됐다.

- decision calls: 204
- speech calls: 21
- embedding calls: 180
- 전체 event: 385
- action events: 143
- decision events: 119
- session events: 46
- safe rejection events: 31
- outcome events: 29
- task events: 17

## 비용

2026-10-01의 GPT-6 Luna standard 단가인 input $0.10/M tokens, output $0.50/M tokens를
기준으로 세 번째 시도는 약 $0.062로 추정된다. 세 시도의 기록된 사용량을 합산하면 약
$0.08이다. 동시 호출이 안전 중단 시점 근처에서 종료될 수 있으므로 최종 금액은 OpenAI
billing dashboard를 기준으로 확인해야 한다.

가격 출처: <https://developers.openai.com/api/docs/models/gpt-6-luna>

## 무엇을 확인했나

**정상 작동**

- API key와 `gpt-6-luna` 접근
- 20-agent 초기화
- 영어 persona와 업무 목표 전달
- structured JSON 응답
- action, decision, session, outcome, task event 저장
- token 상한 도달 시 추가 호출 차단

**아직 확인하지 못함**

- 1일 32 ticks 완주
- 최종 task 및 relationship trajectory
- 완성된 conversation corpus
- CRAFT observer scoring
- scenario 간 비교

## 판단 근거

500k token 상한을 다시 올리면 run을 더 진행할 수는 있지만, 현재 호출 구조가 비효율적인
상태에서 비용만 늘릴 가능성이 크다. 실제 기록에서도 5 ticks 동안 decision 204회와
embedding 180회가 발생했다. 따라서 이번에는 상한을 추가로 올리지 않고 engine call volume을
먼저 줄이기로 결정했다.

## 다음 단계

1. tick별 decision과 validation retry 횟수를 계측하고 상한을 둔다.
2. retrieval·reflection embedding을 batch 처리하거나 빈도를 낮춘다.
3. token 소진 시 실패가 아니라 `budget_exhausted` checkpoint와 부분 summary를 남긴다.
4. demo/scripted regression으로 32 ticks를 검증한다.
5. 예상 token과 비용을 다시 계산한 뒤 실제 API pilot 1회 승인을 받는다.

현재 결과는 **실제 API 연결과 부분 실행에 성공했지만 20인 full-day simulation은 아직
완주하지 못했다**고 공유하는 것이 정확하다.
