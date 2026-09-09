# 위키 토론형 LLM 에이전트 갈등 시뮬레이터 — 설계 문서

**버전** 0.1 (초안)
**작성일** 2026-09-09
**상태** 설계 단계 / 미구현

---

## 1. 목적

소규모 LLM 에이전트가 참여하는 **단일 대화**를 시뮬레이션하여, 대화 안에서 갈등이 어떻게 발생하고 격화되며 개입에 의해 완화되는지를 관측한다.

### 연구 질문

| | 질문 | 대응 관측 대상 |
|---|---|---|
| RQ1 | 갈등은 어떤 조건에서 발생하는가 | 격화 확률 `p(t)`가 임계를 넘는 시점 |
| RQ2 | 무엇이 격화를 가속/감속시키는가 | `p(t)` 궤적의 기울기, forecast horizon |
| RQ3 | 어떤 개입이 언제 효과적인가 | 개입 발화 전후의 `p(t)` 변화 |

### 비목표 (Non-goals)

- 대규모 소셜미디어 시뮬레이션 (OASIS/MiroFish 영역) — **명시적으로 범위 밖**
- 실제 인간 행동의 예측 정확도 확보
- 실시간 모더레이션 시스템 구축

---

## 2. 범위와 설계 제약

### 2.1 도메인: 위키피디아 토크 페이지

CGA-Wiki(Conversations Gone Awry)와 동일한 형태를 목표로 한다. 편집자들이 문서 내용에 대한 합의를 시도하는 스레드형 비동기 토론.

**이 선택의 이유**: 기존 연구 자산(CGA 데이터셋, CRAFT 예측 모델, 짝지어진 검증 구조)을 도메인 전이 없이 그대로 활용할 수 있다.

### 2.2 CGA 통계에서 도출한 파라미터

| 항목 | CGA-Wiki 실측 | 본 시뮬레이터 설정 |
|---|---|---|
| 대화 수 | 4,188 | 조건당 N회 반복 |
| 코멘트 수 | 30,021 | — |
| 턴 수 | 3~19, **중앙값 6** | `max_ticks: 12` |
| 참여자 수 | 소규모 | **3~6명** |

**핵심 제약**: 위키 토론에서 갈등은 6턴 안에 터진다. 50턴, 100턴짜리 시뮬레이션은 CGA와 비교 불가능하며, 그 안에 격화가 일어나지 않는다면 파라미터 조정 대상이다.

**참여자 수 하한**: 2명이면 개입(RQ3)을 수행할 주체가 존재하지 않는다. 분쟁 당사자 2명 + 방관자 1~3명 구성으로 개입 여부 자체가 창발하도록 한다.

### 2.3 위키 토론에는 발언 순서가 없다

턴 배정이 아니라 비동기 게시 + 들여쓰기 답글 구조다. 따라서 설계 대상은 순서가 아니라 두 가지다.

1. **각 에이전트가 지금 말할 것인가** — 확률적 판단, no-op이 기본값
2. **어느 발화에 답할 것인가** — `reply_to` 선택

두 번째가 갈등 연구에서 더 중요하다. 답글 대상 선택이 갈등 다이애드를 형성하고, **답글을 달지 않는 것이 곧 무시**다. 라운드 로빈 구조에서는 둘 다 표현되지 않는다.

---

## 3. 아키텍처

```
conflict-sim/
├── pyproject.toml
├── config.yaml          # 실험 조건
├── seeds/               # CGA에서 추출한 시드 (첫 2턴)
├── runs/                # 출력 로그 (ConvoKit JSON)
└── src/
    ├── models.py        # Utterance, Thread
    ├── agent.py         # 페르소나 + decide + speak
    ├── llm.py           # LLM 호출 래퍼
    ├── engine.py        # 틱 루프
    └── score.py         # 사후 측정
```

### 3.1 데이터 모델 — ConvoKit 스키마 준수

```python
@dataclass
class Utterance:
    id: str
    speaker: str
    text: str
    reply_to: str | None    # 답글이 아니면 None
    timestamp: int          # tick 번호

@dataclass
class Thread:
    utterances: list[Utterance]

    def after(self, tick: int) -> list[Utterance]: ...
    def context(self, n: int = 10) -> str: ...
```

**설계 결정**: 처음부터 ConvoKit Corpus 스키마(Speaker / Utterance / Conversation + `reply_to`)로 출력한다. 나중에 변환하지 않는다.

**근거**: CRAFT Forecaster에 변환 없이 바로 투입할 수 있고, CGA와 동일한 분석 파이프라인을 공유할 수 있다.

**알려진 차이**: ConvoKit은 각 코멘트의 root가 다른 코멘트를 가리킨다고 전제하지만, 실제 위키 토크 페이지에서는 이 속성이 엄밀히 성립하지 않는다(ConvoKit 문서에 명시된 한계). 본 시뮬레이터는 엄격한 트리를 생성하므로 실제보다 정연한 구조가 된다. 비교 시 이 차이를 감안한다.

### 3.2 에이전트 — 판단과 생성의 분리

```python
@dataclass
class Agent:
    name: str
    persona: str            # 입장 + 커뮤니케이션 스타일
    availability: float     # 0~1, 응답 가능성
    last_seen: int = 0

    def decide(self, thread) -> tuple[float, str | None]:
        """싼 모델. {urge, reply_to} JSON만 반환."""

    def speak(self, thread, target: str | None) -> str:
        """큰 모델. decide 통과 시에만 호출."""
```

**두 단계로 분리하는 이유**: 비용. 침묵할 발화까지 매번 생성하면 대부분을 폐기하게 된다.

`urge` 산정에 반영할 요소:
- 내 발화가 반박당했는가
- 내가 직접 호명되었는가
- 새 발화가 내 입장과 충돌하는가
- 내 마지막 발화 이후 경과 턴 수
- 성향 파라미터 (발언 적극성)

### 3.3 시뮬레이션 루프

```python
def run(agents, thread, cfg) -> Thread:
    silence = 0
    for tick in range(1, cfg.max_ticks + 1):
        posted = False
        for agent in order(agents, cfg.rule):     # ← ablation 지점
            if not thread.after(agent.last_seen):
                continue
            urge, target = agent.decide(thread)
            if random() < urge * agent.availability:
                thread.add(Utterance(
                    speaker=agent.name,
                    text=agent.speak(thread, target),
                    reply_to=target,
                    timestamp=tick,
                ))
                posted = True
            agent.last_seen = tick

        silence = 0 if posted else silence + 1
        if silence >= cfg.silence_limit:
            break
    return thread
```

**설계 결정 3가지**

1. **동시 발화 허용** — 한 틱에 여러 에이전트가 게시할 수 있다. 위키에서 실제로 발생하며, 막으면 발언권 경쟁이 사라진다.
2. **no-op이 기본값** — `urge` 임계를 넘지 못하면 침묵한다. 침묵은 무시이며 관측 대상이다.
3. **종료 조건은 침묵** — 턴 상한은 안전장치일 뿐, 정상 종료는 아무도 말하지 않을 때다.

---

## 4. 발언 순서 규칙은 실험 변수다

`order()`는 하드코딩하지 않고 config로 교체한다.

| 규칙 | 동작 | 갈등 표현력 |
|---|---|---|
| `round_robin` | 고정 순서 순환 | ✕ 발언권 경쟁·독점 원천 차단 |
| `random` | 매 라운드 셔플 | △ 순서 편향만 제거 |
| `bidding` | `urge` 최고값만 발언 | ◎ 격화가 발언 빈도에 반영 |
| `event_driven` | 호명·언급에 반응 | ◎ 대응/무시 구분 가능 |

**근거**: 순서 규칙은 구현 세부사항이 아니라 **실험 처치**다. 라운드 로빈은 발언권 경쟁, 끼어들기, 침묵, 무시를 구조적으로 제거하는데 이것들이 갈등의 핵심 현상이다. 순서를 하나로 고정하면 "갈등이 이렇게 전개되더라"는 결과가 순서 규칙이 만든 인공물이 된다.

최소 3개 조건(`round_robin` / `bidding` / `event_driven`)의 ablation을 수행하여, 갈등 패턴이 순서 규칙에 얼마나 민감한지를 보고한다. 이 결과 자체가 기여가 될 수 있다.

---

## 5. 페르소나 설계 원칙

`persona`는 **입장 + 커뮤니케이션 스타일**까지만 기술한다.

**금지**: "이 편집자는 공격적이다", "쉽게 화를 낸다" 같은 갈등 성향의 직접 주입.

**근거**: 공격성을 명시하면 갈등이 창발한 것이 아니라 주입된 것이 된다. CGA 대화는 전부 정중하게 시작해서 무너지는 것들이므로(초기 발화 독성 < 0.4가 데이터셋 구성 조건), 페르소나 단계에서 적대성을 넣으면 비교 대상과 전제가 어긋난다.

허용되는 기술 범위:
- 문서 내용에 대한 입장 (예: 특정 출처의 신뢰성에 대한 판단)
- 커뮤니케이션 스타일 (간결/장황, 규칙 인용 빈도, 직설/우회)
- 도메인 배경 (편집 경력, 관심 주제)

---

## 6. 측정 계층

**설계 원칙: 생성과 측정을 완전히 분리한다.** `score.py`는 `runs/*.json`을 읽기만 한다. 시뮬레이션은 자신이 얼마나 갈등적인지 알지 못한다.

**근거**: (1) 측정 도구를 교체해도 재실행이 불필요하다. (2) 측정 결과가 시뮬레이션에 되먹임되는 오염을 차단한다.

### 6.1 측정 도구: CRAFT 단일

| 도구 | 입력 | 출력 | 학습 필요 |
|---|---|---|---|
| ConvoKit CRAFT Forecaster | 대화 접두사 c₁…c_k | 격화 확률 `p(t)` | 없음 (저자 제공 모델) |

CRAFT는 EMNLP 2019 "Trouble on the Horizon"의 알고리즘을 Forecaster 백엔드로 구현한 것으로, 논문 실험에 사용된 저자 제공 학습 완료 모델을 그대로 쓴다. 신규 학습은 ConvoKit 범위 밖이다.

파생 지표:
- `max p(t)` — 최대 격화 확률
- `dp/dt` — 격화 확률의 상승 속도
- **forecast horizon** — 격화가 처음 감지된 턴 (Kementchedjhieva & Søgaard 2021 도입). 개입 시점 논의의 기준선이 된다.
- 개입 발화 전후 `p(t)` 변화량 — RQ3의 주요 종속변수

### 6.2 주의사항

- CRAFT는 ConvoKit 기본 토크나이저와 다른 자체 스킴을 쓴다. 반드시 `craft_tokenize`를 사용한다.
- CRAFT의 성능 상한을 인지하고 해석한다: CGA F1 66.9 / CMV 67.3. 후속 모델(BERT-SC 69.3, FGCN 70.8)보다 낮다.
- CRAFT는 CGA로 학습되었고 본 시뮬레이터도 CGA를 모사한다. **도메인 일치는 장점이지만, 동시에 CRAFT가 포착하지 못하는 갈등 양상은 본 연구에서도 구조적으로 보이지 않는다.**

### 6.3 CRAFT 단일 측정의 한계 (명시적 기록)

**CRAFT는 강도 축을 제공하지 않는다.** 출력은 "이 대화가 인신공격으로 파탄나는가"라는 이진 사건의 확률이다. `p(t) = 0.8`은 "갈등이 심하다"가 아니라 "파탄 가능성이 높다"를 뜻한다.

따라서 본 설계로는 다음을 구분할 수 없다.

- 격렬하지만 파탄에 이르지 않고 해소되는 갈등
- 미지근하게 시작해 파탄에 이르는 갈등
- 표면적으로 정중하나 적대적인 발화 (반어법, 수동공격)

또한 CRAFT는 2인 대화 전제에 가까워, 참여자가 4명 이상일 때 다자 동역학(연합, 방관, 제3자 개입)을 포착하지 못할 수 있다. 후속 연구인 FGCN은 CRAFT가 사용자 간 관계와 발언에 대한 여론 등 다자 대화 특성을 다루는 메커니즘이 없다고 지적하며 이를 개선 대상으로 삼았다.

**결정**: 초기 버전은 CRAFT 단일 측정으로 진행한다. 강도 축이 필요하다고 판단되는 시점에 발화 단위 점수기를 추가 층으로 도입한다. 그 전까지 RQ1~RQ3은 모두 `p(t)` 기반으로 조작적 정의한다.

### 6.4 격화 라벨

CRAFT의 출력 자체가 격화 예측이므로, 별도의 자동 라벨링 규칙은 두지 않는다. CGA와 비교할 때는 CGA의 원 라벨(크라우드 어노테이션 기반 인신공격 여부)을 정답으로 삼고, 시뮬레이션 로그에 대해서는 `p(t)`가 임계를 넘는지를 격화 판정으로 사용한다. 임계값은 CGA 검증 셋에서 결정한다.

---

## 7. 검증 프로토콜

CGA는 각 격화 대화를 **같은 토크 페이지에서 나온 비슷한 길이의 비격화 대화와 짝지어** 놓았다(주제 통제 + 클래스 균형).

### 절차

1. 짝지어진 대화 쌍 선택 (같은 페이지, 하나는 격화 / 하나는 비격화)
2. **각각의 첫 2턴만 시드로 주입**, 나머지는 에이전트가 생성
3. 쌍마다 N회씩 시뮬레이션
4. 격화 쌍에서 나온 시뮬레이션의 격화율이 비격화 쌍보다 유의하게 높은가?

주제가 통제되어 있으므로, 차이가 관측된다면 **초기 대화 신호가 궤적을 결정한다**는 Zhang et al. (2018)의 핵심 주장을 시뮬레이션으로 복제한 것이 된다.

### 알려진 위험: 시뮬레이터의 갈등 과대 생성

Voat v/technology를 30일 × 30회 복제한 검증 연구에서, 유니크 유저·루트 게시물·일일 활성 유저는 99% 신뢰구간이 겹쳤으나 **댓글 수, 평균 스레드 길이, 평균 독성은 시뮬레이션 쪽이 더 높았다.** 나아가 독성이 계층별로 잘못 배분되어, 시뮬레이션 루트 게시물은 실제보다 훨씬 독성이 높은 반면 시뮬레이션 댓글은 실제보다 덜 독성이었다.

갈등 강도를 종속변수로 삼는 본 연구에 직접적인 위협이다. 해당 연구의 5개 검증 차원(활동 패턴, 네트워크 구조, 독성, 주제 커버리지, 문체 수렴)을 그대로 차용하여 사전 캘리브레이션을 수행한다.

---

## 8. 설정 파일

```yaml
n_agents: 4
rule: bidding              # round_robin | random | bidding | event_driven
max_ticks: 12
silence_limit: 2
seed_file: seeds/cga_0042_derail.json
random_seed: 7
model_decide: <작은 모델>
model_speak: <큰 모델>
temperature: 0.8
```

config를 로그와 함께 저장한다. LLM은 완전 결정론적이지 않으므로 `random_seed`와 `temperature`를 반드시 기록한다.

---

## 9. 구현 순서

1. `models.py` + `engine.py` — `decide`를 `lambda: (0.5, None)` 스텁으로 두고 루프 검증
2. `llm.py` + `agent.py` — 실제 LLM 연결, 소규모 수동 검토
3. `score.py` — CRAFT Forecaster 연결, `p(t)` 산출
4. CGA 포맷 호환성 확인 (`craft_tokenize` 포함)
5. 시드 추출 파이프라인 (CGA 짝 구조에서)
6. Ablation 실험 (순서 규칙 3조건)

---

## 10. 열린 이슈

- **강도 축의 부재** — CRAFT 단일 측정으로는 갈등의 정도를 잴 수 없다(6.3 참조). 격화의 발생 여부와 시점만 관측 가능하다. RQ1~RQ3을 이 제약 안에서 답할 수 있는 형태로 재진술할 것인지, 아니면 후속 단계에서 강도 층을 추가할 것인지 결정 필요.
- **언어** — 영어로 진행하면 CGA·CRAFT·Detoxify를 그대로 쓸 수 있다. 한국어로 갈 경우 세 도구 모두 사용 불가하며 별도 설계가 필요하다. **현재 미결정.**
- **`urge` 산정 방식** — LLM 호출 vs 휴리스틱. 비용과 타당성의 트레이드오프.
- **다자 대화 예측기** — CRAFT는 2인 대화 전제에 가깝다. 참여자가 4명 이상일 때 FGCN 계열 검토 필요.
- **개입 정책** — ConvoKit 4.1.2의 DecisionPolicy(신념 추정기와 결정 정책의 분리)를 차용할지 여부.

---

## 참고 문헌

- Zhang et al. (2018). *Conversations Gone Awry: Detecting Early Signs of Conversational Failure.* ACL.
- Chang & Danescu-Niculescu-Mizil (2019). *Trouble on the Horizon: Forecasting the Derailment of Online Conversations as they Develop.* EMNLP.
- Wulczyn et al. (2017). *Ex Machina: Personal Attacks Seen at Scale.* WWW. (Wikipedia Detox)
- Cercas Curry et al. (2021). *ConvAbuse: Data, Analysis, and Benchmarks for Nuanced Abuse Detection in Conversational AI.* EMNLP.
- Vidgen et al. (2021). *Introducing CAD: the Contextual Abuse Dataset.* NAACL.
- Hada et al. (2021). *Ruddit: Norms of Offensiveness for English Reddit Comments.* ACL.
- Chang et al. (2020). *ConvoKit: A Toolkit for the Analysis of Conversations.*
- Yang et al. (2024). *OASIS: Open Agent Social Interaction Simulations with One Million Agents.* (범위 밖 참고)
