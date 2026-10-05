# Token Efficiency Final Validation Plan

작성일: 2026-10-05. **유료 API 실행 없음.** H3 검증 준비이며 H1/H2 및 simulation 정책을 변경하지 않는다.

## Current Status

- H1: act 고정 지시문 5,441 chars, 입력의 44.43%, 연속 동일률 100%. 문자는 청구 token이 아니며 provider prefix caching을 실측해야 한다.
- H2: retry 표시는 28건이지만 동일 agent/tick에서 첫 판단을 넘어선 추가 판단은 1/136 = 0.74%. 보류.
- H3: 기존 `(model, exact text)` SQLite EmbedCache를 retrieval/reflection query에 연결했다. 현재 memory를 매번 새로 점수화한다.
- 기존 C16 `--no-retrieval-cache`는 OFF, 기본은 ON이다. 이번 harness는 OFF와 ON을 모두 명시해 실행하며 production default를 바꾸지 않는다.
- 새 변경은 metadata 계측 및 별도의 검증 harness뿐이다. completion replay는 **검증 장치**이며 production completion caching이 아니다.

## H3 Demo Result

3차 보존 결과 `results/token_efficiency/h3_cache_parallel.json`:

| 지표 | OFF | ON |
|---|---:|---:|
| Logical retrieval queries | 193 | 193 |
| Retrieval embedding computations | 193 | 91 |
| Cache hits / misses | 0 / 해당 없음 | 102 / 91 |
| Reduction | — | 52.85% |
| All embedding requests | 217 | 115 |
| All embedding texts | 904 | 802 |
| Completion calls | 255 | 255 |

Memory-write 24 requests / 711 texts는 동일하다. 52.85%는 **retrieval 계산 수 감소**이지 전체 token/비용 감소율이 아니다.

단일 worker에서는 193 → 82, hit 111 (57.51%). worker=4에서는 concurrent cold miss 때문에 hit 수가 scheduling에 따라 바뀐다. 3차 행동 checksum은 두 조건 모두 `e2c72dfcb44937f7f4271fe7828090c4e89988ff87f2ac4cf310b635bc3fc333`.

4차에서는 새 harness의 8/32-tick demo와 SDK-shaped local fixture로 vector, 전체 ranking, selected IDs, scoring context, result hash, prompt hash 비교를 검증했다. 새 계측으로 인해 audit 파일 hash 자체는 이전과 달라지는 것이 정상이다. 테스트는 behavior 의미를 비교한다.

## What H3 Changes

`experiment.retrieval_cached_backend`가 `memory_retrieval_embedding`과 `reflection_retrieval_embedding`만 기존 EmbedCache에 보낸다. 같은 model + 완전히 같은 text는 vector를 재사용한다. 공백·문장 정규화 및 semantic cache는 없다.

공유 범위는 한 arm의 SQLite 파일이다. ON은 비어 있는 새 파일로 시작한다. OFF 파일과 혼용하거나 기존 warm cache를 읽지 않는다. model key와 exact-text hash를 유지한다.

## What H3 Does Not Change

query text, top-k, recency/importance/relevance/mood scoring, tie-break, 현재 memory 접근 시각 갱신, memory write, reflection frequency, persona, prompt, agent activation, action retry, tasks, conversations, social state를 바꾸지 않는다.

검색 **결과**를 cache하지 않는다. 같은 query라도 memory와 mood가 달라지면 retrieval 결과는 달라질 수 있고 매번 계산해야 한다.

## Real API Validation Questions

Q1: **같은 scoring context**에서 실제 query vector와 ranking/selected memory/prompt가 유지되는가?

Q2: query embedding requests/texts/input tokens와 실제 query latency/추정 비용이 얼마나 줄어드는가?

독립 LLM 실행에서는 같은 seed/temperature도 응답 동일성을 보장하지 않는다. 새 응답이 memory를 바꾸므로 같은 query hash만으로 이후 ranking을 비교해서는 안 된다. completion 사용량도 독립 trajectory에서 달라질 수 있다. 이는 H3가 completion prompt를 직접 바꿨다는 증거가 아니다.

## Cache OFF vs ON Experiment

추천: `s0_smoke`, 20 agents, seed 1413, workers 4, **8 ticks (0–7)**, 기존 모델 `gpt-6-luna` / `text-embedding-3-small`, temperature 0.8. cfg를 한 번 생성해서 양쪽에 같은 객체를 전달한다. personas/tasks/timing/memory/limits를 포함한 resolved config 및 SHA256를 manifest에 기록한다. 하루 길이 32를 8로 바꾸지 않고 `Loop.run_until(7)`에서 관측만 중단한다.

### Controlled replay — 이번 준비의 기본 비교

1. OFF: 실제 completion과 memory-write embedding을 얻고 결과를 **RAM tape**에 보관한다. query embedding은 매번 실제 계산한다.
2. ON: completion과 memory-write 결과를 tape에서 재생한다. 입력/options hash가 다르면 재생을 거부하고 실패한다. query embedding은 실제 API와 기존 cold exact cache를 거친다.
3. 같은 생성 응답·memory-write vector를 쓰므로 이후 상태 차이를 retrieval query 계산의 차이로 추적할 수 있다. 모든 completion prompt 비교와 행동 checksum이 일치해야 한다.
4. 완료 후 tape는 프로세스와 함께 사라진다. raw prompt, private memory text, generated responses를 tape 파일로 저장하지 않는다. 재시작/resume는 지원하지 않는다.

이는 ON에서 completion API를 다시 실행하는 독립 2-run 연구가 아니다. H3 causal check를 위해 completion randomness를 고정한 **통제 검증**이다. 기존 C16 runner로 독립 OFF/ON을 추가할 수 있으나 별도 승인·비용 범위가 필요하고 이번 추천 pilot에는 포함하지 않는다.

### 실행과 산출물

비용 없는 사전 확인:

```bash
.venv/bin/python scripts/token_efficiency_final_validation.py --output work/h3-preflight --ticks 8
.venv/bin/python scripts/token_efficiency_final_validation.py --output work/h3-preflight --compare-only
```

유료 실행 명령은 **별도 명시적 사용자 승인 후에만**:

```bash
ALLOW_PAID_API_EXPERIMENTS=1 .venv/bin/python scripts/token_efficiency_final_validation.py \
  --backend openai --user-approved-paid-run --ticks 8 --workers 4 \
  --cost-cap-usd 0.50 --output runs/h3-approved-pilot
```

승인 flag와 environment gate가 모두 없으면 client 생성 및 출력 directory 생성 전 차단한다. 이 문서/명령 존재 자체가 실행 승인은 아니다.

`manifest.json`, `off/audit.jsonl`, `on/audit.jsonl`, 각 `summary.json`, `comparison.json`, `comparison.md`를 만든다. 이미 있는 output은 덮어쓰지 않는다. 실패 시 `status=stopped`, error type, 완료된 tick 수와 partial metadata/metrics를 남긴다. 실패를 성공으로 해석하지 않는다.

## Deterministic Equality Checks

`MemoryStore.retrieve`에서 이미 계산한 score/order를 metadata로 기록한다. 다시 검색하거나 상태를 변경하지 않는다.

각 retrieval: agent, tick, query SHA256, embedding model, numeric query vector/vector hash, 전체 ranked IDs/score/cosine similarity, selected IDs, scoring-context hash, selected-record result hash. harness는 agent/tick/query에 대응하는 cache lookup을 연결해 hit/miss/off를 기록한다. vector가 없는 초기/empty retrieval은 비교 coverage에 별도로 주의한다.

scoring context는 memory records/vectors/last_access, mood, tick, top-k, MemoryConfig의 hash이며 원문은 저장하지 않는다. 이 hash가 다르면 같은-state 비교 조건이 깨진 것이다.

completion: system, user payload, combined prompt hash. tape key는 operation + agent + tick + call type + retry + occurrence이며 request signature에 model/temperature/schema/options도 포함한다. 병렬 파일 기록 순서가 달라도 key/occurrence로 비교한다.

**필수:** query model, vector hash, 전체 ranking, selected IDs, scoring context, selected-record hash, 모든 prompt hashes, replay behavior hash가 정확히 일치. 누락된 호출/empty 비교는 PASS로 처리하지 않는다. `--compare-only`로 다시 검사할 수 있다.

실제 embeddings의 반복 응답이 float 수준에서 달라지는지는 아직 검증하지 않았다. exact vector가 달라지면 NO-GO/조사로 표시한다. 저장된 vector로 max absolute difference/cosine과 score margin을 추가 조사할 수 있으나 조용히 tolerance를 적용하거나 성공 판정을 완화하지 않는다. ranking/selected IDs/prompt 변화는 반드시 원인을 해결해야 한다.

## Behavioral Comparison

통제 replay에서는 생성 응답까지 고정했으므로 event/trajectory/utterance hashes와 다음 지표가 완전히 같아야 한다.

| 영역 | 자동 저장 지표 |
|---|---|
| Task | task별 owner/due/worked/done tick/status/progress, completed/overdue tasks, blocked task×ticks |
| Work | agent workload, overtime ticks, stress/mood/workload/overtime tick trajectory |
| Conversation | sessions, utterances, 평균 session utterances, message/gossip/report action counts |
| Social | 관계/familiarity/task trust, grievance count, 관계 trajectory hash |
| Conflict | shock/task/evaluation event counts, ignored/refused outcomes, report escalation proxy, rejected actions |
| Exact structure | all events, all utterances, full checkpoint trajectory hashes |

blocked task×ticks는 매 tick **status=blocked**인 task를 더하며 blocked event 수와 다르다. message actions는 의도/시도 수이며 전달 성공률을 뜻하지 않는다. report는 escalation proxy이지 새로운 escalation detector가 아니다. 이 지표는 CRAFT scoring을 포함하지 않는다.

독립 생성 run을 후속으로 승인받는 경우 action/문구/대화 내용은 달라도 된다. 처음 prompt가 갈라진 tick을 찾고 그 이전의 생성 응답 분기와 retrieval context를 확인한다. 과업 완료/차단/대화/관계/stress에 큰 차이가 있으면 조사하지만, 1쌍으로 임의 5% 기준이나 통계적 비열등성을 주장하지 않는다. 특히 새 장기 차단, 주요 task 미완료, 새 ignored/refused 관계 악화는 사례 단위로 검토한다.

8 ticks에는 end-of-day reflection, lunch talk, overtime가 포함되지 않으므로 전체 하루 안정성을 주장할 수 없다.

## Efficiency Metrics

실제 호출과 counterfactual full-pipeline을 명시적으로 구분한다.

- actual paid OFF: completion + memory-write + 모든 query embedding.
- actual paid ON: cache miss query embedding만. completion/write는 재생되므로 API 비용 0.
- counterfactual ON: OFF completion/write usage + 실제 ON query usage. 이것이 H3만 적용한 전체 pipeline의 비용/total token 추정이다. independently measured ON completion으로 표시하지 않는다.

자동 표: retrieval queries, retrieval/all embedding API requests, embedding texts/input tokens, cache hits/misses, logical completion calls, completion input/output/cached tokens, total tokens. agent/tick별 cache 통계도 기존 helper로 집계한다. JSON에는 actual incremental estimated USD, counterfactual estimated USD, wall time, completion/query/write backend seconds를 함께 저장한다.

Demo token은 `null`/unknown으로 유지하며 chars를 tokens로 변환해 실측인 것처럼 표시하지 않는다. API fixture에서는 provider-shaped usage 합산과 counterfactual 차이를 검사한다. cached tokens는 completion input의 부분집합이므로 total에 더하지 않는다. output에는 reasoning token이 포함되어 중복 가산하지 않는다.

ON wall time은 completion/write replay 덕분에 줄어들므로 **H3 end-to-end 속도 개선으로 해석하지 않는다**. 실제 query backend elapsed 합계와 hit/miss를 먼저 비교한다. retrieval metadata의 context hashing 및 파일 기록도 CPU/I/O overhead를 추가하므로 계측 없는 run의 latency와 혼용하지 않는다. 병렬 elapsed 합계는 wall time보다 클 수 있다. 전체 latency는 이후 독립 실행에서 재측정해야 한다.

## Pilot Size Recommendation

| Option | 정보와 한계 | 선택 |
|---|---|---|
| 20×5, ticks 0–4 | 가장 저렴하지만 demo duplicate coverage가 작다. 옛 attempt는 tick 5까지 일부 관측했으므로 정확히 같은 범위가 아니다. | 최소 smoke 대안 |
| 20×8–10 | 반복 query가 늘고 초기 state/prompt equivalence를 검증할 수 있다. 하루 전체 결과는 미검증. | **8 추천** |
| 20×32 | lunch/conversations/day review 포함. 비용·run time 증가. 실제 단계 1 검증에 필수 아님. | 통제 pilot 통과 뒤 별도 결정 |

4차 demo 8 ticks에서는 retrieval 59건, completion inputs 79건을 검사했다. cache hits가 발생했다. scheduling에 따른 miss 수 변화는 정상이며 특정 hit 수를 성공 기준으로 강제하지 않는다. 32 ticks에서는 retrieval 193건/prompt 255건을 검사했다.

## Estimated Cost

2026-10-05 공식 standard short-context 가격: GPT-6 Luna input $0.10/M, cached input $0.01/M, cache writes $0.125/M, output $0.50/M. [공식 모델 페이지](https://developers.openai.com/api/docs/models/gpt-6-luna).

text-embedding-3-small input $0.02/M. [공식 embedding 모델 페이지](https://developers.openai.com/api/docs/models/text-embedding-3-small).

가격은 같아도 계정/service tier/지역/실제 cache-write 청구를 실행 전 확인해야 한다. 현재 config의 64k input-char guard 때문에 long-context tier를 가정하지 않는다. harness의 추정 비용은 일반 input/cached/output/embedding usage 기준이며 별도 cache-write usage가 API에 없으면 실제 청구와 차이 날 수 있다.

옛 attempt 3: 503,945 total tokens, tick 5에서 stop, 문서상 약 $0.062. input/output/embed split과 raw usage는 저장소에 없다. 따라서 52.85%를 $0.062 전체에 곱하면 안 된다.

8-tick 계획용 민감도: 기존 total에 8/6–8/5를 곱한 **약 672k–806k mixed tokens**를 임시 scale로 사용한다. tick 5 일부 관측 및 memory 성장 때문에 선형 예측은 검증되지 않았다. 아래는 token split을 명시한 *조건부 가정*이지 API 실측/신뢰구간이 아니다. mixed tokens를 completion token으로 과대 배정해 planning margin을 둔다.

| Case | 가정 | OFF 상당액 | 추가 ON query 계산 포함 계획 범위 |
|---|---|---:|---:|
| Best | 672k, input 45% + cached 50% + output 5% | $0.050 | 약 $0.05–0.067 |
| Expected | 672k–806k, input 95% + output 5%, cache discount 없음 | $0.081–0.097 | 약 $0.08–0.113 |
| Conservative | 806k, input 75% + output 25%, cache discount 없음 | $0.161 | 약 $0.16–0.178 |

추가 ON query 상단 $0.016은 planning scale의 모든 806k tokens를 embedding input으로 잡은 과대한 allowance ($0.02/M)다. 정확한 query token split은 pilot에서 계측해야 한다. 역사적 비용의 단순 8/6–8/5 projection은 $0.083–0.099로 expected case와 비슷하지만 새로운 trajectory를 보장하지 않는다.

**제안 승인 한도: 두 arm 합계 $0.50의 보수적 client reservation cap**, 최대 8 ticks/arm, 한 번의 controlled pair. input UTF-8 bytes와 schema bytes + 8192 envelope token allowance, 최대 output limit을 request 전에 예약하고 환불하지 않는다. input은 더 높은 $0.125/M로 예약한다. 양 arm이 예산을 공유하며 실패한 요청의 예약도 유지한다. SDK retry=0 및 harness transport retries=0이라 hidden retry를 예산에서 놓치지 않는다. 이 제한은 production의 retry 정책을 바꾸지 않는다.

예약이 초과되면 API 전 중단하고 partial 결과를 저장한다. provider 요금 변경/별도 fees/예상치 못한 billing을 막는 provider-side hard dollar cap은 아니므로 provider billing이 최종 기준이다. 낮은 예약 한도는 실제 지출보다 훨씬 일찍 run을 멈출 수 있다. token limit도 그대로 적용한다.

## GO / NO-GO Checklist

- [x] Explicit OFF/ON, cold isolated cache files, existing output overwrite 방지
- [x] 동일 cfg/model/seed/temperature/persona/task/memory, config hash 저장
- [x] Query model/exact text 분리 — 3차 model-mixing 테스트 유지
- [x] Demo embedding/ranking/selected memory/prompt equality
- [x] Prompt drift 발생 시 replay 거부 및 비교 failure 확인
- [x] SDK-shaped local fixture token/cost accounting 및 no-network 검증
- [x] Positive finite cost cap 및 max ticks 제한
- [x] 비용 cap 도달 시 API 호출 전 stop / partial artifacts 저장 / ON 미실행
- [x] API client 생성 전 승인/env gate 차단
- [ ] **실제 OpenAI embedding numeric equality, real token/cached-token/latency 측정**
- [ ] 실행 당일 pricing/account/service tier 및 provider billing settings 확인
- [ ] **User explicitly approved paid run**

**Preparation GO; Paid execution NO-GO**. 마지막 승인이 없으므로 이번에는 유료 pilot을 실행하지 않는다. 실제 API 항목은 준비 전에 통과할 수 있는 checkbox가 아니라 pilot에서 확인할 연구 질문이다.

## Related Prior Work

직접 관련된 primary sources 3개만 검토했다. 각 시스템의 절감률을 우리 simulation에 그대로 전이하지 않는다.

| Study/System | Optimization | Token/Call impact | Relevance |
|---|---|---|---|
| Generative Agents 공개 구현 | memory node embeddings를 `embeddings` dictionary에 저장; retrieve는 focal query에 `get_embedding` 호출 | memory vector 저장/재사용 구조 확인. 이 코드에서 exact query cache의 절감률은 보고하지 않음 | agent memory에서 vector 재사용과 매번 relevance 계산을 구분하는 사례. 우리 H3와 동일한 query cache 구현이라고 주장하지 않음 |
| LangChain CacheBackedEmbeddings | text hash key, model namespace; query_embedding_cache 별도 opt-in | exact hit는 underlying embedding 계산을 피함. simulation별 수치 없음 | H3와 직접 같은 engineering 원리. document cache가 있어도 query cache는 별도 연결 필요 |
| SGLang / RadixAttention | 동일 token prefix의 KV 상태 재사용 | 반복 prefill compute를 피함. API 청구 token 수 감소와 동일 의미 아님 | H1의 반복 입력을 축약하기 전 provider prefix/cache 실측이 필요한 이유. H3 vector cache와 다른 계층 |

[Generative Agents memory 코드](https://github.com/joonspk-research/generative_agents/blob/main/reverie/backend_server/persona/memory_structures/associative_memory.py), [retrieval 코드](https://github.com/joonspk-research/generative_agents/blob/main/reverie/backend_server/persona/cognitive_modules/retrieve.py).

[LangChain 공식 cache 설명](https://docs.langchain.com/oss/python/integrations/embeddings#caching), [SGLang 저자 설명](https://www.lmsys.org/blog/2024-01-17-sglang/).

결론: deterministic embedding/KV 계산을 재사용하는 것은 일반적인 효율화 원리다. 우리 20-agent simulation에서의 효과는 query 빈도, warm-up, concurrency, provider usage를 직접 재야 한다. sparse activation/retrieval-result cache는 이번 구현·검증 범위가 아니다.

## Final Recommendation

검증 결과: 전체 `pytest -q` **531 passed, 1 skipped** (81.36s). skip은 선택적 real CRAFT integration이다. 처음 sandbox에서 실패한 localhost WebSocket 2건은 network 권한 후 통과했다. 관련 새/H3 테스트 19개 통과, Ruff 및 `git diff --check` 통과. 모든 SDK 테스트는 local fixture이며 실제 유료 호출은 0회다.

**H3만 유지한 20×8 controlled replay pair를 다음 승인 대상으로 추천한다.** vector/ranking/selected IDs/prompt/input coverage 전부 정확히 같고 query 실제 tokens/requests가 줄면 H3 실제 API 적용 GO를 판단한다. 실패/partial stop/누락된 비교는 HOLD. 이후 full-day 독립 LLM 안정성은 별도 승인·목표를 가진 후속 검증으로 남긴다.

H1 pruning, H2 retry, event-driven activation, memory/reflection/conversation 축소, CRAFT, S1–S4 연구 실험은 하지 않았다.

# Meeting Brief

**지금까지:** H1은 큰 반복 입력 존재, 실제 cached token 측정 필요. H2는 추가 판단 +0.74%로 보류. H3는 exact query embedding cache 구현 완료.

**H3 demo:** 193 → 91 retrieval embedding computations, **52.85% 감소**, 행동 checksum 동일. 전체 embedding texts는 904 → 802이므로 52.85%를 전체 token 절감으로 해석하면 안 된다.

**4차 준비:** 새 OFF/ON harness, vector/ranking/selected memory/context/result/prompt hash 비교, task/conversation/social/conflict 지표, usage·비용·latency 집계, 승인/예산/max-tick guards를 준비했다. 8/32-tick no-cost demo와 local SDK fixture에서 검증했다.

**아직 모름:** actual input tokens/cost reduction, query latency, real embedding 반복의 numeric equality, full independent LLM-day stability. replay의 ON completion 비용 0은 실험 장치이며 H3 completion 절감 효과가 아니다.

**다음 결정:** controlled real API pilot을 승인할 것인가?

**추천 범위:** s0_smoke, 20 agents × 8 ticks (0–7), seed 1413, workers 4, GPT-6 Luna / text-embedding-3-small, OFF → cold-cache ON. completion/write는 RAM replay로 고정한다. 계획 예상 약 **$0.05–0.18**, 보수적 client 예약 한도 **두 arm 합계 $0.50**. 기존 usage split이 없어 조건부 추정이며 실제 provider hard billing cap은 아니다.

**판정:** preparation GO, paid execution NO-GO — 새로운 명시적 사용자 승인 전에는 실행하지 않는다.

**Paid API executed: NO**
