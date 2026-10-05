# 20-agent Token / LLM Call Audit

작성일: 2026-10-05. 기준 원격 HEAD: `86891e7d856f95de5ae21c59aab18251c073cf08`.
범위: 호출 경로 진단과 metadata instrumentation만 추가. 행동 규칙, prompt 내용,
memory 구조, 모델·예산·재시도·스케줄·난수 설정은 변경하지 않았다. 유료 API 실행 없음.

## Current pipeline

### 실제 call sites와 wrapper

- `agent/agent.py:Agent._complete` → `llm.complete`: plan, act, conversation decision,
  speech, task summary/deliverable, appraisal. `_ask`가 JSON schema와 추가 검증을 수행한다.
- `agent/memory.py:MemoryStore._ask` → `llm.complete`: reflection questions/insights,
  relation reflection, end-of-day reflection. **Agent._ask와 달리 검증 재시도가 없다.**
- `agent/agent.py:Agent._recall` → `llm.embed([query])`: act/decide/summarize의 memory 검색.
- `agent/memory.py:MemoryStore.reflect` → `llm.embed([question])`: 질문별 reflection 검색.
- `loop.py:Loop._embed` → `llm.embed(pending_texts)`: 모든 agent의 새 memory 기록을 tick당
  한 batch에 넣는다. **20명 각각 write embedding을 호출하는 구조가 아니다.**
- `company_runtime.py:generate_manager_tasks` → `llm.complete`: 선택적 manager task 생성.
  기본 고정 task DAG 경로와 구분해야 하며, 이 함수에는 tick 인자가 없다.
- `llm.py:EmbedCache.complete`는 그대로 전달; `EmbedCache.embed`는 정확한 model+text hash를
  SQLite에서 찾고 **missing text만** backend에 보낸다. 동일 batch 내 중복 text의 miss도
  원래대로 유지했다. `OpenAIBackend.complete/embed`가 실제 SDK 경계다.
- `experiment.py:run_scenario`는 현재 **OpenAIBackend를 직접 사용**한다. `cli.py`의
  `embed_cache` 옵션 경로와 다르므로, C16 runner에서 embedding cache가 사용된다고
  가정하면 안 된다. memory에 vector를 보유하는 것 자체는 query embedding cache가 아니다.

원본 근거: [loop.py](../../src/conflict_sim/loop.py),
[agent.py](../../src/conflict_sim/agent/agent.py),
[memory.py](../../src/conflict_sim/agent/memory.py),
[conversation.py](../../src/conflict_sim/conversation.py),
[llm.py](../../src/conflict_sim/llm.py),
[company_runtime.py](../../src/conflict_sim/company_runtime.py),
[experiment.py](../../src/conflict_sim/experiment.py).
아래 함수명은 실제 파일의 함수에 대응한다. `llm.complete`, `llm.embed` 전수 검색 후 작성했다.

### 한 tick의 call graph

```text
Loop.tick(t)
 ├─ phase 변화: _close_all → _close → [appraise, relation_appraisal=llm일 때]
 ├─ 이전 outbox → inbox; schedule/shock/intervention; env.advance
 ├─ arrival: 모든 20명 plan_day → Agent._ask → _complete → complete
 ├─ 모든 20명 perceive: 얼굴/메시지를 memory에 기록 (직접 LLM 호출 없음)
 ├─ busy가 아닌 모든 agent act (첫 판단은 병렬; apply는 순차)
 │   ├─ 계획을 그대로 수행: LLM 호출 없음
 │   └─ 예상 밖 상태: _recall → embed → _ask → complete
 │       └─ 환경/세션 거절: 같은 tick에서 act 대체 최대 2회
 │           └─ 각 _ask의 잘못된 JSON/검증 실패: complete 추가 최대 1회
 ├─ _summarize: 완료/review 전이 task → 검색 embed + summary/deliverable complete
 ├─ 각 live Session.step: turns_per_tick번 _round (종료되면 조기 종료)
 │   ├─ decide → 검색 embed + JSON complete
 │   ├─ 선택/확률 gate 통과 → speak → text complete (검색 결과 재사용)
 │   └─ everyone 회의: decide 생략, 정해진 순서의 speak만 호출
 ├─ 세션 종료: _close → [appraise] → outcomes (상태 갱신)
 ├─ 모든 20명 end_tick
 │   ├─ importance 임계: reflection questions complete
 │   │   └─ 질문별 query embed + insights complete
 │   └─ 관계 임계: 관계별 query embed + insights complete
 ├─ day_end: 모든 20명 end_day → review_day → complete
 └─ _embed: 새 memory 전체를 한 batch embed → tick 기록 저장
```

`Loop._judge`의 병렬 작업과 `Session._judge_ahead`의 bidding 작업은 서로 다른 thread에서
실행된다. 계측 context는 각 submit에 `copy_context()`로 전달했다. 순서·worker 수·호출
병렬성은 유지했다. 첫 act는 이후 다른 agent의 세션에 끌려 들어갈 agent에도 이미 계산될
수 있다 (`Loop.tick`의 apply 직전 busy 검사). **호출했지만 실제 적용되지 않는 판단**도
가능하나 이번에는 이를 제거하지 않았다.

### 호출별 빈도와 input 위험

기호: N=20, F=해당 tick의 free agent 수(≤20), T=session turns_per_tick,
P=session 참여자 수, Q=reflect_questions, R=agent별 관계 성찰 대상 수,
K=이번 tick에서 summary가 필요한 task 수. 최대값은 해당 분기 단독 기준이며
서로 다른 분기의 최대가 항상 동시에 실현된다는 뜻은 아니다.

| call type | 실제 함수·파일 | 발생 조건 | agent당 빈도 | tick당 최대 빈도 | retry | input 주요 정보 | token 증가 위험 |
|---|---|---|---|---|---|---|---|
| plan_day | Agent.plan_day → _ask/_complete, agent.py | arrival | 하루 1회, 검증 포함 ≤2 | **20 기본, ≤40 completion** | JSON 검증 1회 | persona/자기 기억, task/help, 공간·자원, 하루 시간 | medium |
| act | Agent._act → _recall/_ask, agent.py | inbox, rejected, unanswered, 승인 대기, 배정할 task, help, 계획 없음, blocked, 열린 talk 등 | 첫 시도 0~1, 검증 포함 ≤2 | ≤2F completion; 모두 free면 ≤40 | JSON 검증 1회 | persona/자기 기억, task_board, plan, 검색 memory, asked_before, View | high |
| rejected action retry | Loop.tick → Agent.act, loop.py | Environment.apply 또는 세션 개설 거절 | 추가 act ≤2, completion 추가 ≤4 | 추가 ≤4F; **최초 포함 ≤6F=120** | 환경 거절 2회 × 각 JSON 검증 1회 | 위 input + 최신 거절 이유/상태 | high |
| conversation decision | Session._round/_judge_ahead → Agent.decide, conversation.py/agent.py | availability>0, unread, rule의 참여 조건 | 일반 round당 ≤1 판단, 검증 포함 ≤2; tick당 ≤2T | session당 ≤2PT; disjoint live session 전체 ≤2NT | JSON 검증 1회; 보류 decision 재시도 없음 | persona/자기 기억, 최근+미독 thread, unread IDs, 검색 memory | high |
| speech | Session._say → Agent.speak, conversation.py/agent.py | gate/선택 통과 또는 everyone turn | 일반 rule ≤T; everyone 전체 회의에서 1 turn | 일반 non-bidding session ≤PT; bidding ≤T; everyone ≤ceil(P/duration) | 자체 JSON 재시도 없음 | thread, 선택 target 본문, 최근 decide의 검색 memory | high |
| meeting | Loop._open_scheduled_meeting → Session.step, loop.py/conversation.py | schedule의 meeting/private | rule에 따라 위 decide/speak | 일반 scheduled rule은 T=1; everyone은 ceil(P/duration) turn | 각 decide 검증만 | agenda root + thread + persona/기억 | medium/high |
| task summary / deliverable | Loop._summarize → Agent.summarize, loop.py/agent.py | task가 review/done에 진입 | task별 ≤2 completion | ≤2K; K는 task 수로 제한, N만으로 상한 결정 불가 | JSON 검증 1회 | finished_task, 검색 memory; deliverable format/criteria | high (긴 문서) |
| appraisal | Loop._close → Agent.appraise, loop.py/agent.py | relation_appraisal=llm, 다른 speaker 존재 | 종료 session별 ≤2 | 종료 session 참여자 합 ×2 | JSON/명단 검증 1회 | 최근 APPRAISE_LINES 발화, 다른 speaker 목록 | medium/high |
| periodic reflection | Agent.end_tick → MemoryStore.reflect/_ask, agent.py/memory.py | importance 누적 임계 | ≤1 questions + Q insights | N(1+Q), 현재 Q=2 → ≤60 | 없음 | questions: 최근 window records; insights: 검색 evidence window | high |
| relation reflection | 같은 reflect(about=person) | 관계별 valence 임계 | 관계당 1 insights | ΣR, 최악 N(N−1)=380 | 없음 | 관계 질문, 검색 records | high |
| end-of-day reflection | Agent.end_day → MemoryStore.review_day, agent.py/memory.py | day_end | 하루 1 | **20 completion** | 없음 | 하루 계획, task status, weightiest records | medium/high |
| memory retrieval embedding | Agent._recall, agent.py | act/decide/summarize가 검색하며 vectors 존재 | 각 semantic 시도당 1 | act≤3F + session≤ΣPT + K (JSON 재시도는 검색 재실행 안 함) | 해당 act 대체 시 다시 검색 | 짧은 상황/메시지/blocked/거절 query | medium, 호출 수 위험 high |
| reflection retrieval embedding | MemoryStore.reflect, memory.py | vectors 존재, 질문별 | periodic≤Q + relation≤R | NQ+ΣR | 없음 | reflection 질문 1개 | medium, fan-out 위험 high |
| memory write embedding | Loop._embed, loop.py | 새 pending memory 존재 | agent별 호출 없음 | **batch 0~1회**, text 수는 별도 | 없음 | 모든 agent의 새 plan/action/observation/utterance/reflection description | high (text 수) |
| optional manager task generation | generate_manager_tasks, company_runtime.py | 외부에서 선택적 호출 | manager당 호출마다 1 | 기본 tick 경로 0 | 자체 재시도 없음 | agents 역할/skills, 기존 task DAG, goal/deadline | medium/high |
| provider transport retry | OpenAIBackend._waiting_out_rate_limits, llm.py | 429, quota 오류 제외 | 논리 요청당 RATE_LIMIT_WAITS=12 attempts | 위 모든 논리 요청에 중첩 가능 | wrapper 최대 12 attempts + SDK 내부 retries | 동일 request | latency high; 성공 usage와 HTTP attempts를 분리 |

대화 기본 T는 talk/message=12지만 scheduled/private 개설은 별도로 T를 지정한다.
turn_taking은 round당 한 명만 평가한다. everyone은 판단 gate 없이 발언하며 turn_cursor가
전체 참여자를 소진하면 더 말하지 않는다. meeting은 별도 LLM API가 아니라 이 경로의
session_kind다. **20명을 항상 매 tick complete하는 코드는 없다.** 모든 사람의 perceive,
end_tick은 매 tick 호출되지만 completion은 조건부다. arrival 계획과 day_end 회고는 전원 호출.

현재 C14 adapter는 listener appraisal, reflection threshold=400, Q=2, window=50,
stall_recheck_ticks=4를 설정한다. 공통 model 기본값(150/3/100)과 혼동하지 않는다.
관계 성찰의 380 상한은 모든 관계가 동시에 임계를 넘는 극단적인 경우다.

### Metadata instrumentation

새 `usage_audit.py`의 ContextVar scope가 semantic caller/tick/agent를 전달하며 backend에서
실제 응답 usage를 기존 누적 counters와 별도로 기록한다.

- C16 runner 및 CLI OpenAI 실행의 run directory에 **`llm_audit.jsonl`**을 append한다.
  추가 logger는 `conflict_sim.llm.audit`; 기존 `LLM usage` 로그 형식과 counters는 유지한다.
- completion: tick, agent, call_type, caller, operation_caller, schema, session_kind/id,
  input/output/total/cached tokens, action/validation/transport retry와 attempt,
  system/prompt/schema 문자 수, top-level payload field별 문자 수, finish_reason.
- embedding: semantic 목적, tick/agent, 요청 1회와 text_count, 실제 input/total tokens.
  write batch는 agent=null + agents/texts_by_agent로 공동 요청임을 표시한다.
  reflection query는 `reflection_retrieval_embedding`으로 분리한다.
- cache wrapper: text_count, hit/miss, **call_count=0**. cache miss의 backend embedding 이벤트가
  실제 요청을 나타낸다. C16 runner에는 원래 cache wrapper가 없으므로 이 이벤트도 없다.
- transport_attempt는 wrapper의 HTTP 시도 수, transport_response는 성공 metadata다.
  SDK 내부의 retry는 직접 관찰할 수 없다. completion/embedding 이벤트의 call_count만
  합산하면 기존 성공 응답 counters와 대조할 수 있다. transport를 함께 더하지 않는다.
- raw prompt/본문은 저장하지 않는다. 문자 수는 토큰의 proxy일 뿐이다. cached tokens는
  input에 이미 포함된 subset이므로 total에 더하지 않는다. usage가 없는 응답은 null로
  기록한 후 기존 오류를 유지한다. 파일 기록 OSError는 경고로 처리해 동작을 바꾸지 않는다.
- 직접 wrapper를 우회한 호출이나 tick 인자가 없는 초기 manager 생성은 tick=null일 수 있다.
  호출 사이 context는 복원되어 thread 간 agent와 retry 표시가 섞이지 않는다.
- JSON validation retry는 Agent._ask의 두 번째 completion, action_retry는 Loop의 같은-tick
  대체 시도에만 설정한다. 전 tick의 rejected 상태를 읽었다는 이유만으로 retry로 세지 않는다.

집계 예시 (기존 실행/향후 승인된 실행의 기록을 읽는 것만으로 가능):

```python
import json
from collections import Counter
from pathlib import Path
rows = [json.loads(x) for x in Path("RUN/llm_audit.jsonl").read_text().splitlines()]
completion = [r for r in rows if r["event"] == "completion"]
count = Counter((r["tick"], r["call_type"]) for r in completion)
tokens = Counter()
for r in completion:
    tokens[r["call_type"]] += r["total_tokens"] or 0
embedding = [r for r in rows if r["event"] == "embedding"]
# embedding_cache는 logical lookup; embedding은 실제 backend 요청이다.
```

## Pilot diagnosis

근거: [C16_real_api_pilot.md](C16_real_api_pilot.md),
[C16_experiment_protocol.md](C16_experiment_protocol.md), 당시 pilot 기록 커밋 `c808a81`의
agent/memory/loop/runtime 코드 및 현재 HEAD를 대조했다.
문서의 attempt 3: **204 decision + 21 speech + 180 embedding = 405 성공 응답 호출**,
총 503,945 tokens. 세 종류의 token 분해는 보고서에 없다. 완료된 5 ticks인지 tick index
0~5 중 일부까지인지도 집계만으로 단정하지 않는다. tick 5의 일부 작업이 실행됐다면
6번째 tick의 usage도 포함될 수 있다.

### 1. 왜 decision 204회인가?

`OpenAIBackend.complete`는 **json_mode=True인 모든 성공 응답을 decide counter에 합산**한다.
따라서 204는 Session의 대화 판단 204회가 아니다. plan_day, act, JSON 재시도, 대화 판단,
성찰 Q/insights, 선택적으로 appraisal/task generation 등이 섞인다. 현재의 task summary는
pilot 이후 추가된 코드이므로 attempt 3에 소급 포함할 수 없다.

arrival의 20 plans만으로 시작하며, free agent들의 reactive act와 추가 재시도, 같은 tick의
여러 대화 rounds, end_tick 성찰이 더해진다. 예를 들어 20 plans + 100 reactive actions만으로
120회가 되고 남은 84회는 재시도/대화/성찰 등의 경로에서 충분히 발생할 수 있다. 이 식은
**실제 분해가 아니라 구조상 가능한 예시**다. 당시 로그 원본이 저장소에 없어 정확한
원인별 204회 재구성은 불가능하다. 119 decision events에는 no_new_posts/no_event/확률 gate
등 completion이 없는 경우도 포함되며, 143 action events와 API calls도 1:1이 아니다.

### 2. 한 agent가 한 tick에 여러 decide completion을 호출하는 경로

- arrival plan_day 뒤 act.
- 환경 거절 후 act 대체 2회.
- 각 Agent._ask의 잘못된 JSON/행동 schema/추가 검증 실패 후 재질문 1회.
- initial act 판단 후 같은 tick에 참여한 session의 여러 rounds에서 decide.
- end_tick importance 성찰과 관계별 성찰이 각각 여러 JSON completion을 만든다.
- session 종료 appraisal은 LLM 모드에서만 가능; C14 pilot은 listener 설정이므로 기본 원인 아님.

근거 함수: `Loop.tick`, `Agent._ask/_act/decide/end_tick`, `MemoryStore.reflect`,
`Session.step/_round`, `Loop._close`.

### 3. rejection retry는 얼마나 증가시키는가?

`Loop.tick`의 **최초 + 대체 2회 = 최대 3 action 선택**.
각 선택은 `Agent._ask`에서 최대 2 completion → **agent당 tick 최대 6 completion**.
20명 모두 free·reactive·거절·JSON 재시도를 겪으면 action 계층만 최대 120회/tick이다.
이는 상한이며, 첫 계획 수행/집에 간 agent 등은 LLM 없이 action을 반환할 수 있다.
JSON 재시도는 payload를 다시 사용하므로 query embed 추가 없음. 환경 거절 대체는 새 act
payload/검색을 구성하므로 query embed도 최대 3회/agent/tick이다.
31 safe rejection events만으로 31번 추가 completion이었다고 판정할 수 없다.

### 4. conversation의 추가 호출

`Session.step`은 T rounds를 수행한다. 새 발화를 읽고 참여 가능한 사람은 `Agent.decide`의
검색 embedding + JSON completion을 호출한다. urge/선택/gate를 통과한 발언자만 별도
`speak` completion을 호출한다. speak는 decide의 `_recalled`를 재사용하여 새 query embed를
만들지 않는다. 새 발화가 생길수록 다른 참가자는 다시 판단할 수 있다. bidding은 한 명만
발언해도 여러 참가자의 판단을 소비한다. 확률 gate 실패/urge=0도 이미 판단 비용을 쓴다.
발화는 참여자별 기억으로 복제되어 tick-end write batch와 추후 성찰을 늘린다.
meeting everyone은 이후 추가된 경로이므로 attempt 3의 원인을 설명하는 데 사용하지 않는다.

### 5. embedding 180회의 가장 가능성 높은 구성

`Loop._embed`는 tick당 최대 **1회 batch**이므로 tick 5까지 memory write만으로 180회가
발생할 수 없다. tick 0~5를 포함하더라도 정상적인 write batch는 최대 6회다(중단되면 더 적음).
나머지는 주로 `Agent._recall`의 act/decide query 및 `MemoryStore.reflect`의 질문별 query
embedding이다. 최초 vector가 없을 때는 검색 embed를 생략한다. 이후 저장 vector가 생기면
검색마다 별도 호출한다. 당시 reflection 기본 Q=3이면 성찰 한 번에서 질문 검색도 최대 3회.
C16 runner가 EmbedCache를 씌우지 않는 점도 중요하다. 180 중 두 query 종류의 정확한 비중은
과거 원본 로그 없이 확인 불가. **180 calls와 180 texts는 다른 지표**다.

### 6. prompt의 반복 정보

매 reactive act에 system instructions/persona, 자기 reflection 기억, manager, plan,
검색 memory, View가 다시 전송된다. task_board와 업무 description/완료 기록/deliverable도
다수 agent가 반복 읽는다. 현재 act는 task_board를 View에서 exclude해 **같은 요청 내부의
중복은 제거**하지만, agent 간·tick 간 반복 전송은 남는다. decide와 speak는 같은 thread를
연속으로 다시 보며 speak에는 target 본문도 별도로 포함된다. `_thread_payload`는 unread를
context_size 밖에서도 보존하므로 context_size가 hard cap은 아니다.
`memory_mode=summary`는 private_memory의 reflection 하나만 제한하며 검색 memory나
MemoryStore reflection evidence window를 제한하지 않는다.

정확한 반복 token 비율·field별 token 수는 아직 없다. 새 field별 문자 수로 우선 큰 payload를
찾고 실제 cached/input tokens와 함께 검증할 수 있다. `a6d2071` 커밋 메시지의 ~80% input,
<1% cached, 487 reflections는 **후속 2일 run의 작성자 기록**이며 attempt 3 측정값이 아니다.
이후 Q/window/threshold/stall frequency/prompt prefix가 이미 수정되었다. 이를 이번 작업의
최적화 성과나 현재 API 실측으로 주장하지 않는다.

### 7. 20-agent scaling 위험

- free reactive 판단·검색은 기본 O(N), retry가 상수 배수를 곱한다.
- 공유 공간의 비중립 표정 관찰은 agent가 다른 agent를 관찰하므로 O(N²) memory records까지
  증가할 수 있다. 전원 비중립·동일 공간의 극단적 경우 20×19=380 관찰/tick. neutral은 skip.
- 발언당 P개의 개인 기억 및 관계 관측, 질문별 evidence 성찰이 기록 폭증을 후속 completion으로
  바꾼다. 관계 성찰도 최대 N(N−1) 대상이다.
- global task_board가 agent/task 수에 따라 커지면 N개의 판단 각각에 큰 payload를 반복
  전송한다. task 수가 N에 비례할 때 aggregate prompt 크기가 O(N²) 성격을 가질 수 있다.
- session cost는 ΣP×T; bidding은 winner 한 명 대비 다수 판단을 소비한다.

### 유료 API 없는 현재 구조 확인

현재 HEAD의 `build_company_config('s0_smoke')`, seed=1413, 20 agents × 32 ticks,
DemoBackend, 동일 설정으로 계측 전/후를 별도 process에서 비교했다.
이벤트, memory rows/vector/retrieval log, agent snapshot, completion request multiset,
embedding batch 입력 multiset의 SHA-256이 동일:
`bece6540fa109233575014f9645c6b8a61e01f8d21fd599c18dacea66185a8e3`.

| 현재 scripted smoke 호출 | 횟수 |
|---|---:|
| plan_day | 20 |
| act | 137 |
| conversation decision | 41 |
| speech | 22 |
| task summary | 15 |
| end-of-day reflection | 20 |
| completion 합계 | 255 |
| memory retrieval embedding | 193 |
| memory write embedding batches | 24 |
| embedding 합계 / 총 text 수 | 217 / 904 |

이 smoke에서는 periodic/relation reflection·LLM appraisal·deliverable이 발생하지 않았다.
**Demo 행동 경로의 기능 확인 수치이며 실제 API token 비용·갈등 행동 예측치가 아니다.**
현재 query embedding fan-out을 확인하지만 attempt 3의 180회 분해를 대신하지 않는다.

## Top token/call bottlenecks

순위는 코드와 제한된 기록을 바탕으로 정한 **다음 계측 우선순위**다. 현재 API token 기여도
순위를 실제로 측정한 것은 아니다.

### 1. Reactive act의 큰 payload 반복 전송

- 현상: inbox/review/assignment/blocked 등으로 계획 실행이 reactive 판단으로 바뀌며 동일
  task board·persona·plan·기억을 여러 agent와 tick에서 반복 전송한다.
- 코드상 원인: `Agent._act`의 unexpected와 payload; `_base_payload`, `_system`.
  최초 병렬 act를 계산한 뒤 busy 검사로 적용하지 않는 경우도 있음 (`Loop.tick`).
- 예상 영향: input token 누적의 가장 유력한 원인. task/산출물 증가에 따라 call당 입력도 증가.
- 다음 단계 아이디어: field별 문자 비중·cached token 비율과 task board 변경 빈도 확인 후,
  event-driven activation / payload pruning 가설을 별도 실험. 이번에는 구현하지 않음.

### 2. 관찰 → memory → 질문/insight 성찰의 fan-out

- 현상: agent 수·공유공간 관찰·관계 악화가 기록과 threshold-triggered 성찰을 증폭.
- 코드상 원인: `Agent.perceive/end_tick`; `MemoryStore.reflect`의 1+Q completion과 Q query
  embeddings, 관계별 insights. 후속 2일 run의 487 reflections 기록도 관련 근거이나 현재 값 아님.
- 예상 영향: 기록 수 O(N²), evidence payload 반복으로 input와 embedding text를 함께 증가.
- 다음 단계 아이디어: reflection_scope/schema별 호출·토큰, threshold를 유발한 기록 구성을
  계측한 뒤 빈도/window에 대한 가설 검증. memory 삭제나 threshold 변경은 이번 범위 밖.

### 3. 행동 거절 × JSON 검증의 중첩 재시도

- 현상: 한 agent tick에서 action 판단이 최대 6 completion까지 늘 수 있음.
- 코드상 원인: `Loop.tick`의 range(2) 대체와 `Agent._ask`의 range(2) 검증.
- 예상 영향: input 재전송, latency 증가, 대체 시 query embedding도 재호출.
- 다음 단계 아이디어: rejection reason별 추가 token 비중과 validation_retry를 분리한 뒤,
  환경 상태 전달/재시도 감소 가설 검증. 이번에는 retry 횟수·검증 규칙 그대로 유지.

### 4. Memory retrieval query의 개별 embedding 호출

- 현상: act/decide/summary와 reflection 질문마다 한-text query 요청.
- 코드상 원인: `Agent._recall`, `MemoryStore.reflect`; C16 runner의 cache wrapper 부재.
- 예상 영향: API 왕복 및 rate limit 위험. 180 calls 중 write batch는 소수이며, 현재 scripted
  smoke도 query 193 vs write 24. embedding 자체가 completion보다 token 비용의 주원인이라고
  단정할 수는 없음.
- 다음 단계 아이디어: exact query 재사용률, cache hit/miss, batch 가능한 독립 query를 검증.
  **검색 결과 캐시와 query vector 캐시는 다름**: 기억/mood/last_access가 바뀌면 결과도 바뀜.

### 5. Conversation rounds의 판단→발언→기억 복제

- 현상: 발화 한 번에 다수 판단과 참여자별 기억, 이후 성찰이 연결됨.
- 코드상 원인: `Session.step/_round/_judge_ahead/_say`, `Agent.decide/speak`, `Loop._step/_close`.
- 예상 영향: ΣP×T completion, 같은 thread와 target 중복 input, session close에서 조건부 appraisal.
  C14 listener에서는 appraisal completion은 기본 0이므로 현재 주원인으로 과장하지 않는다.
- 다음 단계 아이디어: session_kind/rule별 판단 대비 실제 speech 비율, no_urge/gate/적용 취소
  비중, appraisal 활성 조건을 측정한 뒤 conversation/appraisal frequency 가설 검증.

별도 계측 문제: `experiment.estimate_calls`는 N×ticks action + plan + scheduled meeting 및
appraisal만 세며 rejection/JSON retry, 비예정 대화, periodic/relation/end_day reflection,
summary/deliverable, embedding을 완전하게 포함하지 않는다. 문서의 ~1,400은 **진정한 hard
upper bound가 아니다**. 이번에는 estimator를 바꾸지 않고 위험을 기록했다.

## Next hypotheses

아래는 다음 단계의 검증 제안이며 이번 작업에서 구현하지 않았다.

1. **Prompt payload pruning / 캐시 가능한 prefix**: task_board·View·memory·thread가 input의
   대부분인지, 실제 cached_tokens 비율이 낮은지 먼저 확인. 동일 request의 의미를 유지할 수
   있는 중복 제거 후보부터 별도 제안. 문자 수만으로 절감 token 비율을 확정하지 않는다.
2. **Rejection retry 감소**: action_retry/validation_retry 각각의 calls/tokens와 환경 거절 이유를
   기준으로 반복이 유효한 행동 전환을 만드는지 확인. 기존 동작을 기준군으로 보존한다.
3. **Memory retrieval caching**: 반복 query의 exact model/text cache 가능률을 계측하고 C16
   runner와 CLI cache 경로 차이를 확인. query vector만 캐시해도 retrieval은 매번 재평가해야 함.
4. **Event-driven agent activation**: 이미 계획 수행 fast path가 있는 점을 전제로, board/inbox/
   rejection/review 변경이 없는 추가 reactive 판단을 실제로 얼마나 찾을 수 있는지 검증.
5. **Reflection 및 conversation/appraisal frequency**: 현행 400/2/50과 listener를 기준으로
   scope별 토큰·발화 결과를 계측. 과거 150/3/100 pilot 결과를 현행 코드로 단순 외삽하지 않음.

### 검증과 한계

- 전체 테스트: **501 passed, 1 skipped** (선택적 real CRAFT integration).
  이후 추가한 meeting/reflection attribution 두 테스트를 포함한 계측 테스트: **9 passed**.
  최종 관련 회귀 (`test_usage_audit`, `test_llm`, `test_cli`, `test_company_runtime`):
  **102 passed**. `ruff check .`, 변경 Python 파일 format check, `git diff --check` 통과.
- MockTransport 테스트로 token/cached attribution, thread isolation, cache hits/misses와 text
  batch, 두 retry 구분, rate-limit retry, missing usage 오류 유지, context cleanup 확인.
- 기존 테스트와 scripted smoke 비교로 request/결과 불변성 확인. 기존 테스트는 수정하지 않음.
- 실제 API 없이 현재 모델의 입력/출력·캐시 토큰 분포, field별 실제 token 기여,
  실제 latency/rate limits, 32틱 LLM 완주, 가설의 행동 보존·효과는 확정할 수 없다.
- 과거 원본 usage/event/prompt 로그는 Git에 없다. 문서 aggregate만으로 attempt 3의
  call-type별 token·rejection·embedding 내역을 복원할 수 없다.
- SDK 내부 retry의 HTTP 시도/사용량과 usage를 반환하지 않은 API 실패 비용은 계측 범위 밖.
- 새로운 JSONL은 resume에서도 append해 실제 지출 이력을 유지한다. replay events의
  truncation과 다르므로 재개 시 tick만으로 deduplicate하지 않는다.
