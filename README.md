# ConflictDynamics

LLM 에이전트들이 집단 토론에서 어떻게 개입하고 갈등을 키우거나 완화하는지 실험하기 위한 Python 시뮬레이터입니다.
현재 구현은 소규모 위키 토론을 중심으로 대화 생성, CRAFT 채점, CGA 시드 추출까지 포함합니다.

이 저장소는 시뮬레이션 엔진과 실험 재현성을 우선합니다. 실행마다 Hydra 설정, 로그, corpus를 분리 저장하고, API 사용량·출력 한도·실패 조건을 명시적으로 기록합니다.

## 주요 구성

| 영역 | 내용 |
|---|---|
| Dialogue simulation | 여러 에이전트가 순서 규칙에 따라 발언 여부와 답글 대상을 결정 |
| Turn-order rules | `round_robin`, `random`, `bidding`, `event_driven` 비교 |
| Memory modes | `none`, `summary`, `full`로 개인 기억 효과를 분리 |
| Evaluation data | CGA-WIKI corpus에서 구조 조건을 만족하는 paired seeds 추출 |
| Output format | ConvoKit 호환 corpus, Hydra 설정, 토큰 사용량 로그 저장 |

## 실행

Python 3.11 이상과 [uv](https://docs.astral.sh/uv/)가 필요합니다.

```bash
uv sync
uv run conflict-sim
```

기본 `demo` 모드는 API 없이 고정된 응답으로 엔진과 저장 흐름을 확인합니다.
예제 시드는 직접 작성한 영어 대화이며, CGA에서 추출한 데이터가 아닙니다.
데모 결과를 갈등 발생률이나 LLM 행동의 근거로 사용하면 안 됩니다.
Hydra가 실행마다 `runs/<날짜>/<시간>/`을 만들고, 그 안의 `corpus/`에 결과를 저장합니다.
직접 경로를 정하려면 `hydra.run.dir=runs/demo`를 지정합니다.
기존 실행 경로는 Hydra가 로그나 설정을 쓰기 전에 거부합니다. `.run.lock`으로 동시 실행도
막으며, 실패한 실행도 새 경로로 다시 시작합니다. 비어 있는 디렉터리와 실시간 UI가
`console.log`만 준비한 디렉터리는 사용할 수 있습니다.

실제 LLM으로 실행하려면 실행 디렉터리의 `.env`에 `OPENAI_API_KEY`를 설정합니다.
[기본 설정](conf/config.yaml)의 판단·발언 모델은 `gpt-5.6-luna`이며,
`reasoning_effort: none`으로 추론 비용을 제한합니다. API 키는 YAML이나 로그에 저장하지 않습니다.

```bash
uv sync --extra llm
uv run --extra llm conflict-sim backend=openai hydra.run.dir=runs/llm-001
```

연결에는 [OpenAI Chat Completions SDK](https://github.com/openai/openai-python)를 사용합니다.
판단 모델은 JSON mode를, 두 모델 모두 `temperature`를 지원해야 합니다.
모델 ID는 실행자가 바꿀 수 있습니다. 추론 설정을 받지 않는 모델은 `reasoning_effort=null`로
지정하면 해당 인자를 보내지 않습니다. SDK 기본 환경 변수 `OPENAI_BASE_URL`도 적용됩니다.
API가 반환한 모델 ID·입출력 토큰·캐시/추론 토큰은 Hydra의 `cli.log`에 `LLM usage`로 기록합니다.
모델/공급자의 실제 응답은 비결정적일 수 있고, `random_seed`는 엔진의 순서·확률 추첨만 고정합니다.
판단은 `max_tokens_decide=512`, 발언은 `max_tokens_speak=384`를 기본 출력 한도로 사용합니다.
이 한도는 Chat Completions의 `max_completion_tokens`로 전달되며 추론 토큰도 포함합니다.
`max_total_tokens=100000`은 API가 보고한 입력+출력 사용량의 합이 도달하면 **다음 호출을 차단**합니다.
응답 후 사용량을 알 수 있으므로 한 호출만큼 초과할 수 있고, 금액을 보장하는 예산은 아닙니다.
`max_input_chars=64000`은 시스템 지시문과 JSON 입력을 합친 문자 수의 상한입니다.
`full` 기억을 포함해 상한을 넘으면 내용을 임의로 자르지 않고 API 호출 전에 실패합니다.
실행의 `usage.json`과 완료 corpus의 `run.json.llm_usage`에 판단·발언별 호출 수, 입력·출력·전체
토큰과 캐시·추론 토큰을 합산합니다. 사용량을 반환받은 잘린 응답도 포함합니다.
API 오류로 사용량을 받지 못한 요청은 집계할 수 없으며, 성공 응답에 사용량이 없어도 실행을 중단합니다.
API 오류, 잘못된 판단 JSON, 잘린 응답은 실행 실패로 처리하며 침묵으로 기록하지 않습니다.
생성에 실패한 실행에는 Hydra 로그만 남고, 완료된 corpus는 저장하지 않습니다.

## 순서 규칙

```bash
uv run conflict-sim rule=round_robin
uv run conflict-sim rule=random
uv run conflict-sim rule=bidding
uv run conflict-sim rule=event_driven
```

| 규칙 | 현재 구현 의미 |
|---|---|
| `round_robin` | 매 틱 설정된 순서로 모두 평가하며 확률적 침묵을 허용 |
| `random` | 매 틱 평가 순서를 셔플하며 확률적 침묵을 허용 |
| `bidding` | 동일한 대화 상태에서 가장 높은 urge 한 명을 선택한 뒤 확률 게이트 적용 |
| `event_driven` | 첫 평가에는 시드를 읽고, 이후 새 답글·정확한 `@이름` 호명 또는 보류 판단이 있을 때 참여 |

bidding 동점은 seeded RNG로 고릅니다. availability가 0이면 평가와 입찰을 건너뜁니다.
승자가 확률 게이트를 통과하지 못하면 해당 틱에는 게시하지 않으며 차순위자를 재선택하지 않습니다.
그 외 규칙은 한 틱에 여러 게시를 허용하고, 뒤의 에이전트는 앞의 게시를 즉시 읽습니다.
각 에이전트는 틱당 최대 한 번 참여합니다. 새 글이 없으면 LLM에 다시 판단을 요청하지 않고,
게시하지 못한 양수 urge의 판단으로 재시도합니다. 새 글을 읽으면 판단을 갱신하며,
게시 성공 또는 새 `urge=0`이면 보류 판단을 제거합니다. `urge=0`은 `no_urge`로 기록합니다.

설계 문서의 round_robin 설명에는 강제 발언과 확률적 침묵 사이에 모호함이 있습니다.
초기 구현은 3.3절의 공통 확률 게이트를 유지하고 **평가 순서만 고정**했습니다.
event_driven의 제3자는 첫 평가 이후 보류 판단이 없다면 직접 답글/호명을 받아야 다시 참여할 수 있습니다.
이 제약은 자발적 개입의 관측에도 영향을 주므로 순서 규칙 비교 시 고려해야 합니다.

`max_ticks`는 생성 발화 수가 아니라 틱 수 상한입니다. 여러 명이 게시하면 발화 수가 이를 넘습니다.
`max_utterances`를 지정하면 시드 두 발화를 제외한 생성 발화 수를 제한합니다. 한 틱 중간에도
정확히 그 수에서 `max_utterances`로 종료합니다. 기본값 `null`은 기존 틱 기반 동작을 유지합니다.
규칙 비교에서는 같은 틱 수만 사용하지 말고 공통 발화 상한을 함께 설정하세요.
침묵이나 틱 상한 때문에 목표 발화 수에 못 미친 실행은 도달한 실행과 따로 집계해야 합니다.

```bash
uv run conflict-sim -m rule=round_robin,bidding,event_driven max_utterances=8 max_ticks=24
```

`silence_limit`회 연속 게시가 없으면 종료합니다. `last_seen`은 읽은 발화 수로 추적하므로
틱 0의 시드와 같은 틱 안에서 나중에 올라온 답글도 처리합니다.
보류 판단이 있어도 연속 무게시 틱이 `silence_limit`에 도달하면 종료합니다.

## 설정과 시드

Hydra가 YAML 합성·보간·CLI override를 처리하고, Pydantic이 최종 설정의 타입과 범위를 검증합니다.
strict 모드로 숫자 문자열/불리언의 묵시적 숫자 변환을 거부하고, 알 수 없는 필드도 거부합니다.
에이전트는 고유한 이름을 가진 3~6명이어야 하고 `n_agents`와 목록 길이가 같아야 합니다.
시드 발언자도 에이전트 목록에 포함해야 합니다. 페르소나는 입장·말투·배경만 기술합니다.

```bash
# 설정 변경 및 확인
uv run conflict-sim rule=random random_seed=12 max_ticks=6
uv run conflict-sim --cfg job --resolve

# 3개 순서 규칙 × 2개 난수 시드 = 6개 실행
uv run conflict-sim -m rule=round_robin,bidding,event_driven random_seed=7,42

# 별도 디렉터리의 config.yaml 사용
uv run conflict-sim --config-path /absolute/path/to/configs --config-name config
```

멀티런은 `runs/multirun/<시간>/<작업 번호>/corpus/`에 각각 저장합니다.
멀티런 루트도 한 번만 사용합니다. 작업 간 경로 충돌을 막기 위해 `hydra.sweep.subdir`는
기본값 `${hydra.job.num}`만 허용하며, 다른 값은 저장 전에 거부합니다.
`defaults` 목록으로 설정 그룹을 합성하고 `${max_ticks}` 같은 OmegaConf 보간을 사용할 수 있습니다.
중첩 경로의 주 설정을 전역 설정으로 사용할 때는 YAML 첫 줄에 `# @package _global_`을 둡니다.
이전 argparse의 `--rule`, `--backend`, `--output`, `--config`는 위 Hydra 문법으로 바뀌었습니다.

기본 설정과 합성 시드는 저장소 최상위 `conf/`에 있습니다. 패키지 밖이라 wheel에는 들어가지
않으므로 저장소를 체크아웃해 `uv run`으로 실행합니다.
`seed_file`이 `null`이면 `conf/seeds/example.json`을 쓰고, 경로를 적으면 실행을 시작한
디렉터리를 기준으로 찾습니다. `hydra.job.chdir=true`에서도 이 기준을 유지합니다.
시드에는 처음 두 발화만 포함하고,
원본 ID와 답글 관계를 보존하되 timestamp를 모두 0으로 정규화합니다.
`source`, 짝 정보 등 바깥 메타데이터는 저장되지만 에이전트 프롬프트에는 들어가지 않습니다.
시드의 필드 구조는 [예제](conf/seeds/example.json)를 참고하세요.
생성 중 `reply_to: null`은 첫 발화에 대한 답글로 해석해 단일 트리를 유지합니다.
`context_size`는 최근 대화 범위를 정합니다. 아직 읽지 않은 발화는 이 범위를 넘어도 모두
프롬프트에 포함하고, 답글 생성 시 선택한 대상 발화의 본문도 별도로 전달합니다.

## CGA 시드 추출

[공식 CGA-WIKI 배포본](https://www.convokit.cornell.edu/documentation/awry.html)의 로컬 corpus에서
짝지어진 시드를 추출합니다. `conversations.json`과 `utterances.jsonl`이 필요하며,
추출 자체에는 ConvoKit·LLM 호출이 필요하지 않습니다.

```bash
uv run conflict-seeds runs/cga/source/cga-wiki runs/cga/seeds/train
# 검증·테스트 분할은 명시적으로 선택합니다.
uv run conflict-seeds runs/cga/source/cga-wiki runs/cga/seeds/val --split val
```

기본 분할은 `train`입니다. 섹션 헤더를 제외하고 시간순 첫 댓글 두 개를 고르며,
동일 시각에는 원본 파일 순서를 유지합니다. **둘째 댓글이 첫 댓글의 직접 답글일 때만**
사용하고, 어느 한 대화라도 조건을 충족하지 못하면 짝 전체를 제외합니다. 빈 댓글,
짝 정보 불일치, 분할 불일치도 제외 사유입니다. 답글 관계에 맞추려고 이후 댓글을
대신 선택하거나 둘째 댓글의 부모를 바꾸지 않습니다.

`manifest.json`에 보존한 짝과 시드 파일명, 제외한 짝과 이유를 기록합니다.
각 시드의 첫 댓글만 시뮬레이션 루트로 두고 두 timestamp를 0으로 정규화합니다.
원본 ID·본문·발언자와 둘째 댓글의 부모를 보존하고, 원래 부모·시각은 `original_seed`에 둡니다.
배포본의 결측 부모 `NaN`은 JSON `null`로 바꿉니다. 원본 라벨과 짝 정보는 `cga`에
저장되며 에이전트 입력에 포함하지 않습니다. 이후 발화는 시드에 담지 않습니다.

기존 출력 디렉터리는 덮어쓰지 않습니다. 적합한 쌍이 없으면 manifest를 남기고 실패로 종료합니다.
2026-09-10 배포본 확인에서는 train 1,254쌍 중 704쌍(시드 1,408개)을 보존하고 550쌍을
제외했습니다. 격화·비격화 클래스 균형은 유지하지만 구조로 선택한 부분집합이므로
CGA 전체에 대한 성능과 구분해야 합니다.

추출된 시드를 실행하려면 `seed_file`과 해당 발언자의 이름·주제에 맞는 `agents`를 설정하세요.
주제별 페르소나 생성, CGA 검증 셋에서의 임계값 결정, 반복 실험은 아직 구현하지 않았습니다.

## 성찰과 개인 기억

`decide`는 `urge`, `reply_to`와 함께 2~4문장의 `reflection`을 반환합니다. 이전 기억과
현재 대화를 바탕으로 갱신한 관점이며, `urge=0`이거나 실제로 게시하지 못해도 저장합니다.
별도 성찰·요약 호출 없이 같은 응답으로 받습니다.

| `memory_mode` | 다음 판단·발언에 전달하는 자기 기억 |
|---|---|
| `none` | 성찰은 기록하되 프롬프트에 넣지 않음. 모델 효과와 기억 효과를 분리하는 대조 조건 |
| `summary` (기본값) | 가장 최근 성찰 하나. 매번 이전 기억을 반영한 누적 요약으로 갱신 |
| `full` | 성찰 전체 이력. 자동으로 줄이지 않으므로 긴 실행에서는 입력 길이가 증가 |

```bash
uv run conflict-sim memory_mode=full
uv run conflict-sim -m memory_mode=none,summary,full
```

모든 모드에서 새 성찰 원문은 판단 로그에 전부 남깁니다. 재시도는 기존 성찰을 재사용하고
기억에 중복 추가하지 않습니다. `full`은 성찰 이력의 범위이며 대화 본문의 `context_size`와는 별개입니다.
기억은 자기 판단·발언 입력에만 전달하고, 다른 에이전트나 공개 corpus·CRAFT 입력에 별도 필드로 넣지 않습니다.
성찰은 모델이 생성한 자기보고이며 실제 내적 상태를 직접 측정한 자료는 아닙니다.

## 출력

각 실행은 [ConvoKit corpus 구조](https://www.convokit.cornell.edu/documentation/data_format.html)를
따르는 디렉터리에 저장합니다. 실제 [ConvoKit 로더](https://github.com/CornellNLP/ConvoKit/blob/master/convokit/model/corpus_helpers.py)에
맞춰 파일에서는 `reply-to`를 사용하고 Python 모델에서는 `reply_to`를 사용합니다.

```text
runs/demo/
├── .hydra/              # 합성된 설정, Hydra 설정, CLI overrides
├── cli.log
└── corpus/
    ├── utterances.jsonl     # 시드 + 생성 발화, conversation_id와 reply-to 포함
    ├── speakers.json
    ├── conversations.json
    ├── corpus.json
    ├── index.json
    ├── seed.json            # 입력 시드 사본
    ├── decisions.jsonl      # 틱별 판단·성찰, 재사용 여부, 게시 결과
    └── run.json             # 설정, 종료 이유, 틱/발화 수, 프롬프트 버전
```

새 실행의 `run.json`은 `schema_version: 2`, `prompt_version: "2"`를 기록합니다.
판단이 있는 행에는 `reflection`, `decision_source`(`new`/`retry`), 최초 판단의 `decision_tick`이
포함됩니다. 판단을 생략한 행에는 성찰을 채워 넣지 않습니다. 기존 실행 파일은 변경하지 않습니다.

ConvoKit을 별도로 설치한 분석 환경에서는 `Corpus(filename="runs/demo/corpus")`로 로딩하는 형식입니다.
corpus는 같은 파일시스템의 임시 디렉터리에 모두 저장한 뒤 이름을 바꿔 공개합니다.
저장 중 실패하면 임시 파일을 정리하고 불완전한 `corpus/`를 남기지 않습니다.
새 `run.json`에는 `status: completed`를 기록합니다. 이 필드가 없는 기존 정상 실행도 읽습니다.
동일 시드의 반복 실행은 같은 발화 ID를 사용하므로 개별 corpus로 다루세요.
여러 실행을 하나로 합칠 때는 실행별 ID 네임스페이스를 별도로 부여해야 합니다.
파일 구조와 자체 재로딩 외에 아래 선택 통합 테스트로 실제 ConvoKit·CRAFT 연결을 확인합니다.

## 격화 측정

```bash
uv sync --extra score
uv run --extra score conflict-score runs/llm-rr6
uv run --extra score conflict-score --all runs
```

[설계 문서](docs/conflict-sim-design.md) 6장의 측정 계층입니다. 생성과 측정을 분리하여,
`score.py`는 완료된 corpus 또는 실시간 공개 대화 스냅샷을 읽고 시뮬레이터를 실행하지 않습니다. ConvoKit의 CRAFT
Forecaster에 저자 제공 `craft-wiki-finetuned` 가중치를 그대로 사용하며, 첫 실행 때
약 550MB를 `~/.convokit/saved-models/`에 내려받습니다.

결과는 실행 디렉터리의 `scores.json`에 저장합니다. `schema_version: 2`의 주요 지표는 다음과 같습니다.
검색은 `run.json`을 포함한 corpus 파일이 모두 있는 실행만 대상으로 합니다. 채점 전에 완료 상태를
확인하고, 발화 ID마다 유효한 확률이 정확히 하나인지 검사합니다. 누락·중복·알 수 없는 ID가 있으면
실패하며 기존 `scores.json`은 유지합니다. 새 점수 파일도 저장 완료 후 한 번에 교체합니다.
여러 실행 중 실패가 있어도 나머지는 계속 채점하고, 마지막에 성공·실패 건수를 출력합니다.
실패가 하나라도 있으면 종료 코드 `1`을 반환합니다. 중복 지정된 경로는 한 번만 처리합니다.

| 필드 | 의미 |
|---|---|
| `max_p`, `final_p` | 전체 발화 중 최대 예측 확률, 마지막 발화까지 읽은 뒤의 예측 확률 |
| `max_delta_p` | 인접 발화 간 `p[i] - p[i-1]`의 최댓값. 틱당 기울기가 아니며 모두 하락하면 음수 |
| `threshold_exceeded` | 한 번이라도 `p > decision_threshold`였는지 여부. 임계값과 같으면 `false` |
| `first_threshold_crossing` | 최초 임계 초과 발화의 `{index, id, tick}`. 초과가 없으면 `null` |

시드를 포함한 전체 발화 순서를 사용하며 `index`는 0부터 시작합니다. 첫 발화가 이미 임계를
초과하면 위치는 0입니다. 같은 틱의 발화 사이에서도 확률 변화량을 계산합니다.
`max_delta_p_at`은 변화가 끝나는 발화의 위치이며, 발화가 하나뿐이면 변화량은 0으로 두고
그 발화를 가리킵니다. 실제 사건 위치 라벨이 없으므로 사건까지 남은 발화 수인 **forecast horizon은 산출하지 않습니다.**

v1의 `forecast_horizon`, `escalated`, `max_dp`, `max_dp_at`은 각각
`first_threshold_crossing`, `threshold_exceeded`, `max_delta_p`, `max_delta_p_at`으로 변경했습니다.
v1 결과를 갱신할 때는 키만 바꾸지 말고 저장된 `series`와 `decision_threshold`를
`derive_metrics`에 전달해 재계산해야 합니다. 임계값과 같은 경우의 판정도 달라졌기 때문입니다.

`p(t)`는 갈등 강도가 아닌 **인신공격으로 파탄날 가능성에 대한 모델 예측값**입니다.
임계 초과도 실제 인신공격의 관측을 뜻하지 않습니다. 설계 문서 6.3의 한계가 그대로 적용됩니다.

ConvoKit은 3.x가 필요합니다. 4.x는 forecaster 패키지가 `unsloth`(NVIDIA·Intel GPU 전용)를
무조건 import하여 다른 환경에서는 CRAFT를 불러올 수 없습니다.

## 실시간 데모와 실행 결과 보기

```bash
uv sync --all-extras
uv run --no-sync streamlit run src/conflict_sim/dashboard.py
```

기본 화면 **Live simulation**에서 설정을 고르고 **Start simulation**을 누릅니다.

**Scenario / 시나리오**에서 현재 설정, ‘조사 결과의 해석과 표현’, ‘문서 재구성과 편집 절차’를
선택하고 **불러오기**를 누릅니다. ‘초기 대화와 참여자 입장’을 펼치면 편집한 시드와 참여자를 확인할 수
있습니다. 두 추가 프리셋은 각각 네 명의 페르소나와 영어 합성 시드를 함께 적용합니다.
프리셋은 갈등 발생을 보장하거나 강도를 지정하는 조건이 아닙니다.

프리셋은 `conf/scenario/*.yaml`의 Hydra 설정 그룹입니다. 저장소 루트에서 CLI로도 실행할 수 있습니다.
다른 디렉터리에서 CLI로 실행할 때는 `seed_file`을 절대 경로로 지정하세요. UI는 이를 자동 처리합니다.

```bash
uv run conflict-sim +scenario=wording
uv run conflict-sim +scenario=editing
```

- `demo`: API 없이 고정 응답으로 실행합니다. 진행을 볼 수 있도록 상태 갱신마다 0.2초 쉽니다.
- `openai`: 실행 디렉터리의 `.env` 키와 Hydra에 설정된 모델로 실제 대화를 생성합니다.
- **실행 조건**: 순서 규칙, 기억 모드, 최대 틱·생성 발화 수, 무발화 종료 조건, 난수 시드.
- **에이전트**: 3~6명의 이름, 화면 표시용 입장, LLM에 전달할 성향, 참여 가능성.
- **초기 대화**: 첫 두 발화의 작성자와 본문. 답글 관계와 원본 ID는 유지합니다.
- **모델·예산**: 판단·발언 모델, 언어, 추론 수준, 온도, 문맥 수, 출력·전체 토큰 및 입력 문자 상한.

**설정 출처**에서는 시나리오, 저장한 설정, 실행 기록을 선택할 수 있습니다. 선택 후 **불러오기**를
누르면 편집 칸 전체를 선택한 값으로 바꿉니다. 실행 기록은 `corpus/seed.json`의 시드 사본을 읽으므로
원래 시드 파일이 바뀌거나 없어져도 해당 실행의 입력을 복원합니다. **불러온 설정과 비교**에서
바뀐 항목을 확인하고, 새 이름을 입력해 **다른 이름으로 저장**을 누르세요.

설정은 `conf/experiments/<이름>/config.yaml`과 `seed.json`으로 함께 저장됩니다. 기본 설정이
나중에 바뀌어도 영향을 받지 않도록 전체 값을 저장하며, 같은 이름은 덮어쓰지 않습니다.
저장 완료 후 ‘저장한 설정’에서 다시 불러올 수 있고, 이 폴더는 Git으로 관리할 수 있습니다.
초기 대화 본문이나 작성자를 바꾸면 시드의 바깥 메타데이터에 `edited: true`를 남깁니다.
잘못된 설정은 화면에 오류를 표시하고 저장·실행을 막습니다. 불러오기와 저장은 API를 호출하지 않습니다.

저장소 루트에서 저장한 설정을 CLI로 실행할 수도 있습니다.

```bash
uv run --no-sync conflict-sim --config-path "$PWD/conf/experiments/방어적-Alex-v1" --config-name config
```

저장하지 않은 편집 내용도 **Start simulation**으로 바로 실행할 수 있습니다. 실행 직전에
`runs/live/<고유 실행명>/inputs/`에 설정과 시드를 고정한 뒤, 같은 폴더의 `run/`을 Hydra 출력
경로로 사용합니다. 따라서 편집 화면이나 저장된 설정을 이후에 바꿔도 진행 중인 실행은 바뀌지 않습니다.

판단이나 발화가 완료될 때 공개 대화와 에이전트별 최신 성찰이 갱신됩니다. API 응답을
기다리는 동안에는 현재 작업 중인 에이전트를 표시합니다. 게시하지 않은 에이전트의 성찰,
urge, 기억 재사용 여부도 확인할 수 있습니다. 성찰은 관찰자 화면에만 보이며 다른 에이전트에게
전달되지 않습니다. 이름 옆에는 설정된 짧은 입장(`agents[].stance`)을 표시합니다.
이 필드는 관찰자용으로만 저장하며 LLM 프롬프트에는 넣지 않습니다. 이전 기록에 입장 필드가
없으면 기존 페르소나의 첫 문장을 짧게 표시합니다. `tick`, `urge`, `bidding`에는 한국어 설명을 제공합니다.

사이드바의 **실시간 채점** 토글은 기본적으로 꺼져 있습니다. 켜면 새 공개 발화를 별도 CRAFT
프로세스가 분석합니다. CRAFT 객체와 체크포인트를 작업 내에서 재사용하고, 생성이 더 빨리 진행되면 최신 대화 전체를
분석해 중간 발화의 점수도 포함합니다. 성찰만 갱신되면 다시 채점하지 않습니다. 화면에는 채점된
발화 수 / 현재 발화 수를 표시하며, 모델 로딩·추론 때문에 대화보다 점수가 늦게 나타날 수 있습니다.
OpenAI 호출은 추가하지 않습니다. 채점 결과는 에이전트에게 전달하지 않습니다.

실시간 결과는 `live-scores.json`에 원자적으로 저장합니다. 정상 종료 후 공개 대화가 완성된 corpus와
일치할 때 `scores.json`도 확정합니다. 실패·중지된 실행의 부분 점수는 최종 점수로 승격하지 않습니다.
토글을 끄면 채점만 중지하고 대화 생성은 계속합니다. 오류가 나면 `score.log`를 화면에 표시하며,
토글을 껐다 켜서 재시도할 수 있습니다. 새 실행의 채점을 시작하면 이전 채점 작업은 종료합니다.
CLI에서도 `uv run --no-sync conflict-score --live runs/live/<실행명>/run`으로 같은 기능을 사용할 수 있습니다.
이미 `live.json`이 생성된 실행 경로를 지정해야 합니다.

**Stop simulation**은 실행 프로세스를 종료하고 마지막 진행 상태를 남깁니다.
탭을 닫는 것만으로는 실행이 중지되지 않습니다. 오류·중지와 정상 완료를 구분해서 표시하며,
실행 중에는 중복 시작을 막습니다. 완료된 실행은 `runs/live/<고유 실행명>/run/corpus/`에 저장됩니다.
오류·중지된 실행은 완료된 corpus로 저장하지 않고 `live.json`에 부분 기록만 남깁니다.
CLI 로그는 같은 디렉터리의 `cli.log`와 `console.log`에서 확인할 수 있습니다.

대시보드는 기존 Hydra CLI를 별도 프로세스로 실행하고 진행 파일을 0.5초마다 읽습니다.
CLI에서 `live=true`를 주면 같은 진행 파일을 만들며, 기본 `live=false`에서는 생성하지 않습니다.

사이드바의 **Saved runs**로 전환하면 기존 결과 뷰어를 사용할 수 있습니다.
Transcript의 **기록 재생**을 켜면 처음·이전 tick·재생/일시정지·다음 tick, 위치 슬라이더,
0.5/1/2배속을 사용할 수 있습니다. 각 틱 종료 시점까지의 공개 대화와 최신 성찰을 함께 보여주며
미래 발화나 성찰은 재생 화면에 미리 표시하지 않습니다. 같은 틱의 발화는 함께 나타납니다.
기록을 바꾸면 처음부터 시작하고, 마지막 틱에서 자동으로 멈춥니다. 상단 요약 통계와 Measurements는
전체 실행 기준입니다. 기록 재생은 LLM 호출이나 원본 파일 변경 없이 동작합니다.
저장된 실행에서도 실시간 채점 토글을 켜면 선택한 실행을 한 번 채점하고 Measurements를 갱신합니다.

`runs/` 아래에서 `corpus/run.json`을 가진 디렉터리를 모두 찾아 최신순 목록으로 보여주고,
고른 실행의 트랜스크립트와 판단 로그를 각각 탭으로 엽니다. Decisions 탭에서는 에이전트와
틱을 선택해 성찰 원문 및 재사용 여부를 확인합니다. Mean urge는 재시도를 제외한 새 판단만 집계합니다.
성찰 필드가 없는 이전 실행도 열 수 있습니다. 트랜스크립트는 MediaWiki 토론
페이지의 콜론 들여쓰기와 서명 배치를 따라 그리며, 깊이 6을 넘으면 실제 토론에서 `{{outdent}}`를
쓰는 지점처럼 들여쓰기를 멈추고 원래 깊이를 서명에 적습니다. 합성 데이터임을 알리는 고지가
상단에 항상 붙습니다. 판단 로그에는 `probability_gate`,
`no_new_posts` 같은 미발언 사유가 남아 있어 조용한 틱의 원인을 확인할 수 있습니다.
사이드바에서 결과를 저장하고 탐색할 디렉터리를 지정할 수 있습니다.
`Measurements` 탭은 `scores.json`의 발화별 예측 확률과 임계선, 최초 임계 초과 발화를 표시합니다.
에이전트별 발언 수·비중은 시드를 제외한 생성 발화로 계산합니다. 점수가 없어도 발언 비중은
확인할 수 있으며, 점수 스키마가 오래됐거나 corpus의 발화 ID·순서와 다르면 재채점을 안내합니다.
저장 목록은 하위 `run.json`의 경로와 변경 정보를 캐시 키에 포함합니다. 외부 CLI의 새 실행이나
판단 로그 수정, 채점 결과 추가는 화면을 다시 실행하면 반영되며 `Reload`를 누를 필요가 없습니다.

## 코드와 검증

`src/conflict_sim/`의 `models.py`는 설정 스키마와 대화 트리, `engine.py`는 순서/확률/종료,
`agent.py`는 프롬프트와 판단 파싱, `llm.py`는 외부 호출, `storage.py`는 파일 입출력,
`cli.py`는 Hydra 합성과 실행 연결, `cga.py`는 CGA 짝 선별과 시드 추출을 맡습니다.
`Config`, `Utterance`, `Decision`은
Pydantic 모델이며 키워드 인자로 생성합니다. `Thread`의 검사는 중복 ID·답글 관계·시간 순서만 다룹니다.

```bash
uv run --all-extras pytest
uv run ruff check .
uv run ruff format --check .
uv build
```

테스트는 유료 API 호출 없이 SDK의 HTTP 경계에서 응답을 대체합니다.
일반 테스트와 별도로, 선택 통합 테스트는 실제 CRAFT 가중치로 고정된 네 발화를 추론합니다.
모델 자산 조회만 로컬 캐시로 연결하고, 실제 입력 맥락 순서·토큰화·추론·점수 누락 검사·저장을
수행합니다. 먼저 `~/.convokit/saved-models/craft-wiki-finetuned/`에 `craft_full.tar`,
`word2index.json`, `index2word.json`을 준비하세요. 유료 API는 호출하지 않습니다.

```bash
CONFLICT_CRAFT_INTEGRATION=1 uv run --all-extras pytest tests/test_score.py -m craft -q
```

CRAFT 측정은 공개 생성 로그만 읽는 독립 단계입니다. Hydra로 여러 조건을 실행할 수 있지만,
ablation 결과의 통계 분석 및 연구적 타당성 검증은 아직 수행하지 않았습니다.
