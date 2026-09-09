# ConflictDynamics

소규모 편집자들의 위키 토론을 생성하는 Python 시뮬레이터입니다.
[설계 문서](docs/conflict-sim-design.md)의 구현 순서 1~2단계에 해당하는 초기 버전입니다.

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
같은 경로를 재사용하면 Hydra의 메타데이터는 갱신될 수 있으나, 기존 `corpus/`는 덮어쓰지 않습니다.

실제 LLM으로 실행하려면 [기본 설정](src/conflict_sim/conf/config.yaml)의
`model_decide`, `model_speak`에 모델 ID를
지정하고 환경 변수 `OPENAI_API_KEY`를 설정합니다. API 키는 YAML이나 로그에 저장하지 않습니다.

```bash
uv sync --extra llm
uv run --extra llm conflict-sim backend=openai hydra.run.dir=runs/llm-001
```

연결에는 [OpenAI Chat Completions SDK](https://github.com/openai/openai-python)를 사용합니다.
판단 모델은 JSON mode를, 두 모델 모두 `temperature`를 지원해야 합니다.
모델 ID는 실행자가 선택합니다. SDK 기본 환경 변수 `OPENAI_BASE_URL`도 적용됩니다.
모델/공급자의 실제 응답은 비결정적일 수 있고, `random_seed`는 엔진의 순서·확률 추첨만 고정합니다.
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
| `event_driven` | 첫 평가에는 시드를 읽고, 이후에는 새 답글 또는 정확한 `@이름` 호명에 반응 |

bidding 동점은 seeded RNG로 고릅니다. availability가 0이면 평가와 입찰을 건너뜁니다.
승자가 확률 게이트를 통과하지 못하면 해당 틱에는 게시하지 않으며 차순위자를 재선택하지 않습니다.
그 외 규칙은 한 틱에 여러 게시를 허용하고, 뒤의 에이전트는 앞의 게시를 즉시 읽습니다.
각 에이전트는 틱당 최대 한 번 평가하며, 이미 읽은 대화만 있으면 다시 판단하지 않습니다.

설계 문서의 round_robin 설명에는 강제 발언과 확률적 침묵 사이에 모호함이 있습니다.
초기 구현은 3.3절의 공통 확률 게이트를 유지하고 **평가 순서만 고정**했습니다.
event_driven의 제3자는 첫 평가 이후 직접 답글/호명을 받아야 다시 참여할 수 있습니다.
이 제약은 자발적 개입의 관측에도 영향을 주므로 순서 규칙 비교 시 고려해야 합니다.

`max_ticks`는 생성 발화 수가 아니라 틱 수 상한입니다. 여러 명이 게시하면 발화 수가 이를 넘습니다.
`silence_limit`회 연속 게시가 없으면 종료합니다. `last_seen`은 읽은 발화 수로 추적하므로
틱 0의 시드와 같은 틱 안에서 나중에 올라온 답글도 처리합니다.

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
`defaults` 목록으로 설정 그룹을 합성하고 `${max_ticks}` 같은 OmegaConf 보간을 사용할 수 있습니다.
중첩 경로의 주 설정을 전역 설정으로 사용할 때는 YAML 첫 줄에 `# @package _global_`을 둡니다.
이전 argparse의 `--rule`, `--backend`, `--output`, `--config`는 위 Hydra 문법으로 바뀌었습니다.

기본 설정과 합성 시드는 `src/conflict_sim/conf/`에 있으며 wheel에도 포함됩니다.
`seed_file`은 선택한 주 설정 파일의 디렉터리를 기준으로 찾습니다. `hydra.job.chdir=true`에서도
이 기준을 유지합니다. 시드에는 처음 두 발화만 포함하고,
원본 ID와 답글 관계를 보존하되 timestamp를 모두 0으로 정규화합니다.
`source`, 짝 정보 등 바깥 메타데이터는 저장되지만 에이전트 프롬프트에는 들어가지 않습니다.
시드의 필드 구조는 [예제](src/conflict_sim/conf/seeds/example.json)를 참고하세요.
생성 중 `reply_to: null`은 첫 발화에 대한 답글로 해석해 단일 트리를 유지합니다.
`context_size`는 최근 대화 범위를 정합니다. 아직 읽지 않은 발화는 이 범위를 넘어도 모두
프롬프트에 포함하고, 답글 생성 시 선택한 대상 발화의 본문도 별도로 전달합니다.

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
    ├── config.yaml          # 검증 및 경로 해석을 마친 실제 설정
    ├── seed.json            # 입력 시드 사본
    ├── decisions.jsonl      # 틱별 urge, 확률, 발언 여부, 미발언 이유
    └── run.json             # 설정, 시드, 종료 이유, 틱/발화 수, 프롬프트 버전
```

ConvoKit을 별도로 설치한 분석 환경에서는 `Corpus(filename="runs/demo/corpus")`로 로딩하는 형식입니다.
동일 시드의 반복 실행은 같은 발화 ID를 사용하므로 개별 corpus로 다루세요.
여러 실행을 하나로 합칠 때는 실행별 ID 네임스페이스를 별도로 부여해야 합니다.
파일 구조와 자체 재로딩은 테스트했으며 ConvoKit 런타임·CRAFT 연결 검증은 후속 단계입니다.

## 코드와 검증

`src/conflict_sim/`의 `models.py`는 대화 트리, `engine.py`는 순서/확률/종료,
`agent.py`는 프롬프트와 판단 파싱, `llm.py`는 외부 호출,
`config.py`는 Hydra 합성과 Pydantic 설정 스키마, `storage.py`는 파일 입출력,
`cli.py`는 Hydra 실행 연결을 맡습니다. `Utterance`, `Decision`은 Pydantic 모델이며
키워드 인자로 생성합니다. `Thread`의 검사는 중복 ID·답글 관계·시간 순서만 다룹니다.

```bash
uv run --extra llm pytest
uv run ruff check .
uv run ruff format --check .
uv build
```

테스트는 유료 API 호출 없이 SDK의 HTTP 경계에서 응답을 대체합니다.
Hydra로 여러 조건을 실행할 수 있지만, CRAFT 점수, `craft_tokenize`, 실제 CGA 시드 추출,
ablation 결과의 통계 분석 및 연구적 타당성 검증은 구현하지 않았습니다.
CRAFT 측정은 생성 로그만 읽는 독립 단계로 추가할 예정입니다.
