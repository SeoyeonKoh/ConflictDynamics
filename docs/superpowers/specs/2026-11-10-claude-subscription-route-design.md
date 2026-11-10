# Claude 구독 경로 설계 (Claude Agent SDK)

2026-11-10 · 대상: `src/conflict_sim/`(LLM 백엔드, 실행 설정, conflict-server), `viz/`(설정 · 실행 시작 화면)
선행 작업: `2026-11-03-viz-main-menu-design.md`(provider 카드, `/api/settings`), `2026-11-03-agent-interview-design.md`, `2026-11-10-scenario-generator-design.md`(LLM을 부르는 서버 기능 두 가지)
작업 위치: 워크트리 `../ConflictDynamics-claude-route`, 브랜치 `feat/claude-subscription-route`

## 1. 의도

지금 실제 모델로 시뮬레이션을 돌리는 길은 OpenAI API 키 하나뿐이고, 호출마다 과금된다. 사용자는 이미 Claude 구독을 쓰고 있다. 이 구독으로, API 키와 토큰 과금 없이, 같은 시뮬레이션을 돌릴 수 있는 두 번째 길을 만든다.

수단은 **Claude Agent SDK**(`claude-agent-sdk`)다. SDK가 Claude Code 실행 파일을 띄우고, 그 실행 파일이 사용자의 구독 로그인으로 모델을 부른다. `anthropic` SDK(API 키, 토큰당 과금)는 이 문서의 대상이 아니다.

## 2. 목표 / 비목표 / 반목표

**목표** (모두 사용자 결정)
- 설정에서 고를 수 있는 새 provider. 고르면 모델 호출이 Agent SDK를 거쳐 구독으로 나간다.
- 모델을 부르는 **세 군데 전부**에서 동작한다: 시뮬레이션 실행, 실행 후 인터뷰, 시나리오 생성기.
- 기본 모델은 **Claude Haiku 5.5**(`claude-haiku-5-5`). 설정에서 바꿀 수 있다.
- 임베딩은 **로컬 모델과 OpenAI 중에서 고른다**. Agent SDK에는 임베딩이 없고, 기억 검색은 매 실행마다 임베딩을 쓴다.

**비목표**
- Anthropic API 키 경로. 설정의 "Anthropic" 카드는 계속 "준비 중"으로 둔다(§10).
- `probes/`, `scripts/`, `probe.py`가 `OpenAIBackend`를 직접 만드는 곳. 연구용 도구라 이번에는 건드리지 않는다.
- 에이전트에게 도구를 주는 것. 이 경로에서 Claude는 글만 쓴다. 파일 읽기, 셸, 웹, MCP를 쓰지 않는다.
- 다른 사람에게 이 경로를 제공하는 것(공유 서버, 배포판). §3의 정책 때문에 본인 컴퓨터, 본인 구독이 전제다.
- 호출 속도 최적화(프로세스를 살려 두고 재사용). §9의 측정 결과를 보고 다음 단계로 정한다.

**반목표** (기술적으로 돌아가도 실패)
- Claude 구독을 골랐는데 API 키로 과금된다. Claude Code는 `ANTHROPIC_API_KEY`가 있으면 구독보다 그 키를 먼저 쓴다(§4.2).
- 모델이 사용자의 파일, `CLAUDE.md`, Claude Code 설정을 읽는다. 실험 조건이 오염되고, 로컬 파일이 프롬프트로 새어 나간다.
- 구독 한도에 닿았을 때 몇 시간씩 멈춰 있거나, 조용히 실패하거나, 그때까지 진행한 실행을 잃는다.
- 한 실행 안에서 임베딩 모델이 섞인다. 벡터는 같은 모델끼리만 비교된다.
- OpenAI 경로와 Demo 경로의 동작이 달라진다.

## 3. 제약

**사용 정책** — Claude Code 문서에서 확인한 문장이다(2026-11-10 기준, 출처 §12). 해석은 내 판단이고 법률 검토가 아니다.
- 금지: "Anthropic does not permit third-party developers to offer Claude.ai login into their own applications, or to route requests through Free, Pro, Max, or Ultra plan credentials on behalf of their users."
- 전제: "Advertised usage limits for Pro, Max, and Ultra plans assume ordinary, individual usage of Claude Code and the Agent SDK."
- 허용: `claude setup-token`과 `CLAUDE_CODE_OAUTH_TOKEN`이 "CI pipelines and scripts"용으로 문서에 있다.
- 따라서 이 경로는 **본인이 본인 컴퓨터에서 본인 구독으로 돌리는 것**까지만 다룬다. 다른 사용자에게 이 앱을 나눠 주거나 서버로 띄워 주는 경우는 API 키 경로를 써야 한다. 설정 화면에 이 범위를 한 줄로 적는다.
- 20명짜리 실행을 반복하는 것이 "ordinary, individual usage"에 드는지는 문서로 판단할 수 없다. 한도에 닿으면 멈추고 알리는 것으로 대응한다(§5.4).

**의존성** — 지금까지는 "새 Python 의존성 없음"이 원칙이었다. 이 경로는 예외가 필요하다. 필수 의존성은 늘리지 않고 선택 설치(extra)로 둔다: Agent SDK용 하나, 로컬 임베딩용 하나. 설치하지 않은 사람에게는 지금과 똑같이 동작하고, 고르려 할 때 설치 안내가 나온다.

**엔진 계약** — 엔진은 `LanguageModel` 규약(`complete`, `embed`)만 안다. 새 경로는 이 규약의 구현 하나로 끝나야 하고, 에이전트 · 대화 · 기억 코드는 바뀌지 않는다.

**보안** — conflict-server의 기존 규칙을 그대로 따른다(로컬 Host/Origin, 자격 증명은 브라우저로 가지 않음). 토큰과 CLI의 stderr 원문은 로그와 오류 메시지에 싣지 않는다.

## 4. 확인한 사실

### 4.1 코드 (master `a43d840`)

- 규약: `src/conflict_sim/llm.py`의 `LanguageModel` — `complete(*, system, prompt, model, temperature, json_mode, schema=None) -> str`, `embed(texts) -> list[list[float]]`. 구현은 `DemoBackend`, `OpenAIBackend` 둘.
- `complete`의 호출 형태는 세 가지다.
  - `schema`가 있음(에이전트 판단, 기억 성찰): OpenAI의 strict JSON schema로 강제한다. 스키마는 `strict_schema(schema)`가 만든다.
  - `json_mode=True`만 있음(시나리오 생성기 `generator._call`): 임의의 JSON 객체. 호출한 쪽이 `json.loads`로 바로 읽고, 객체가 아니면 `LLMError`.
  - 둘 다 없음(발화, 인터뷰 답변): 자유 텍스트.
- `OpenAIBackend`를 만드는 곳이 다섯 군데로 흩어져 있다: `experiment.run_scenario`, `cli._backend`, `server.Server.generator_llm`, `server._interview_ask`, `interview.run_embedder`. `cli.py`는 `isinstance(llm, OpenAIBackend)`로 사용량과 감사 로그를 붙인다.
- 호출은 스레드에서 동시에 나간다. `loop.py`가 `cfg.workers`만큼 `ThreadPoolExecutor`를 쓰고(실제 실행 기록은 `workers: 10`), `usage` 카운터는 락으로 보호한다.
- 실패 처리가 이미 있다. `run_scenario`는 `LLMError`를 받으면 마지막 체크포인트에서 `paused`로 멈추고, 메뉴에서 이어서 실행할 수 있다. 토큰 상한(`max_total_tokens`)도 `LLMError`로 멈춘다.
- 사용량: `usage = {"decide": {...}, "speak": {...}, "embed": {...}}`, 키는 `calls / prompt_tokens / completion_tokens / total_tokens / cached_tokens / reasoning_tokens / missing_usage`. `usage.json`, 매니페스트의 `token_usage`, 실행 목록(`runs.py`), 라이브 상태가 이 모양을 읽는다.
- 감사 로그: `usage_audit`의 `log_call("completion" | "embedding" | "transport_attempt" …)`가 `llm_audit.jsonl`에 쓴다.
- 설정: `server.py`의 `PROVIDERS = ("openai", "demo")`, `DEFAULTS`(provider, 모델 셋, 상한). `provider: "anthropic"` 저장은 400이고 테스트(`tests/test_server.py:73`)가 이를 확인한다.
- 유료 확인: `live._launch`가 `backend == "openai"`이면 `paid_confirmed`를 요구하고 자식 프로세스에만 `ALLOW_PAID_API_EXPERIMENTS=1`을 준다. `experiment.py:114`가 그 값을 확인한다.
- 실행 설정: `models.py`의 `backend: Literal["demo", "openai"]`, `model_decide / model_speak / model_embed`, `reasoning_effort`(none~max), `temperature`(기본 0.8), `max_tokens_decide / max_tokens_speak`, `max_input_chars`, `workers`.
- 임베딩 캐시: `EmbedCache`와 검색 캐시의 키는 "모델 이름 + 원문"이다. 인터뷰는 그 실행이 쓴 임베딩 모델로만 질문을 임베딩한다(`interview.run_embedder`).
- 생성기: `generator_llm()`은 `max_tokens_decide=32_000`, `max_input_chars=400_000`으로 백엔드를 만들고, Demo provider에서는 409로 거절한다.

### 4.2 Claude Agent SDK (공식 문서, 실제 실행으로는 아직 확인하지 않음)

| 항목 | 문서 내용 |
|---|---|
| 설치 | `pip install claude-agent-sdk`, Python 3.10+. Claude Code 실행 파일이 패키지에 들어 있다(소스 배포판 설치만 예외). |
| 호출 | `async def query(*, prompt, options: ClaudeAgentOptions \| None = None, transport: Transport \| None = None) -> AsyncIterator[Message]`. 호출마다 새 세션, 호출마다 CLI 프로세스 하나("One agent session maps to one subprocess."). |
| 시스템 프롬프트 | `system_prompt`에 문자열을 주면 그것만 쓴다. 긴 프롬프트는 `{"type": "file", "path": ...}`: "on Linux a single argument longer than roughly 128 KB fails at process spawn." |
| 설정 읽기 | `setting_sources` 기본값은 모든 출처(사용자 · 프로젝트 · 로컬, `CLAUDE.md` 포함). `[]`이면 읽지 않는다. |
| 도구 | `tools: list[str] \| ToolsPreset \| None`, `allowed_tools`, `disallowed_tools`, `mcp_servers`. 도구를 전부 끄는 방법은 문서에 명시가 없다. |
| 모델 · 추론 | `model: str`, `effort`(low~max), `thinking`(adaptive / enabled / disabled). **temperature 옵션은 없다.** |
| 구조화 출력 | `output_format={"type": "json_schema", "schema": {...}}` → `ResultMessage.structured_output`. 실패하면 subtype `error_max_structured_output_retries`. JSON Schema draft-07, `format`은 강제하지 않는다. |
| 결과 | `ResultMessage`: `subtype`(`success`, `error_during_execution`, `error_max_turns`, `error_max_budget_usd`, `error_max_structured_output_retries`), `is_error`, `result`, `stop_reason`, `usage`(`input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`), `model_usage`, `total_cost_usd`(클라이언트 추정치), `num_turns`, `duration_ms`. |
| 한도 | `RateLimitEvent`의 `RateLimitInfo.status`가 `allowed / allowed_warning / rejected`, `rate_limit_type`에 `five_hour`, `seven_day`. 한도 초과를 알리는 예외나 result subtype은 문서에 없다. |
| 예외 | `ClaudeSDKError`, `CLIConnectionError`, `CLINotFoundError`, `ProcessError`(`exit_code`, `stderr`), `ResultError`(SDK 0.2.140+), `CLIJSONDecodeError`. |
| 인증 우선순위 | 클라우드 provider → `ANTHROPIC_AUTH_TOKEN` → `ANTHROPIC_API_KEY` → `apiKeyHelper` → `CLAUDE_CODE_OAUTH_TOKEN` → … → `/login`으로 저장된 구독 자격. 비대화 모드에서 API 키는 "always used when present". |
| 자원 | 호스팅 문서의 출발점: 에이전트 프로세스 하나에 "1 GiB RAM, 5 GiB disk, and 1 CPU". |

Agent SDK 문서에는 구독 로그인으로 SDK를 쓰는 방법이 적혀 있지 않다(적힌 방법은 `ANTHROPIC_API_KEY`와 클라우드 provider). 구독 자격으로 도는 근거는 Claude Code 인증 문서의 우선순위 목록과 `CLAUDE_CODE_OAUTH_TOKEN` 설명이다. 그래서 §9의 첫 항목이 이것을 실제로 확인하는 일이다.

### 4.3 규모

기존 실제 실행 하나(`c16-real-r10-midweek-v2`, 에이전트 10명 · 하루 · `workers: 10`)의 `llm_audit.jsonl`이 1,890줄이다. 완성 호출과 임베딩, 전송 시도 기록이 섞인 수라 완성 호출만은 이보다 적다. 이 경로에서는 완성 호출 한 번이 CLI 프로세스 하나다.

## 5. 설계

### 5.1 이름

- provider id와 `backend` 값은 **`claude`**. 화면 표시는 "Claude (구독)".
- 기존 `anthropic` 카드는 API 키 경로를 위한 자리로 남긴다. 두 경로는 과금 방식이 달라서 한 카드로 합치지 않는다.

### 5.2 `ClaudeAgentBackend`

`LanguageModel`의 세 번째 구현. SDK는 생성자가 아니라 첫 호출에서 import한다(`OpenAIBackend`와 같은 방식, 설치가 없으면 `LLMError`로 설치 안내).

`complete` 한 번 = `query()` 한 번. 대응은 다음과 같다.

| `complete` 인자 · 동작 | Agent SDK |
|---|---|
| `system` | `system_prompt`(문자열). 길면 임시 파일을 써서 `{"type": "file", ...}`로 넘긴다. |
| `prompt` | `prompt` |
| `model` | `model` |
| `schema` 있음 | `output_format={"type": "json_schema", "schema": strict_schema(schema)}`. `structured_output`을 `json.dumps(..., ensure_ascii=False)`해서 문자열로 돌려준다(규약은 문자열). |
| `json_mode`만 | 임의 객체 스키마(`{"type": "object"}`)로 `output_format`을 건다. SDK가 받지 않으면 결과 텍스트에서 코드 펜스를 벗기고 `json.loads`로 확인한다(§9에서 정함). |
| 둘 다 없음 | `ResultMessage.result` 텍스트 |
| `temperature` | 보낼 수 없다. 무시하고, 매니페스트에 이 실행이 temperature 없이 돌았다고 적는다. |
| `max_tokens_decide / speak` | SDK에 대응 옵션이 문서에 없다(§9). 없으면 강제하지 않는다. |
| `reasoning_effort` | `none` → `thinking={"type": "disabled"}`, 그 밖 → `effort=<값>` |
| `max_input_chars` | 지금과 같은 사전 검사 |

모든 호출에 붙는 격리 옵션(반목표 "파일 · 설정을 읽는다"를 막는다):
- 도구 없음(`tools=[]`, §9에서 확인), `mcp_servers={}`.
- `setting_sources=[]`.
- `cwd`는 백엔드가 만든 빈 임시 디렉터리.
- `permission_mode="dontAsk"`: 도구가 켜진 채로 남더라도 승인을 묻는 동작은 거절된다.

동기 · 동시성:
- `complete`는 동기 함수이고 워커 스레드에서 불린다. 각 호출이 자기 스레드에서 `asyncio.run(...)`으로 `query()`를 끝까지 읽는다.
- 백엔드에 세마포어를 둬서 동시에 뜨는 CLI 프로세스를 `claude_max_concurrent`개(기본 4)로 제한한다. `cfg.workers`가 10이어도 프로세스는 4개까지다.
- 호출마다 제한 시간(기본 180초). 넘으면 프로세스를 끝내고 `LLMError`.

결과 처리:
- `ResultMessage.subtype == "success"`이고 `is_error`가 거짓일 때만 성공. 그 밖의 subtype, 빈 결과, 스키마 호출인데 `structured_output`이 없는 경우, `stop_reason`이 거절(refusal)인 경우는 `LLMError`.
- 사용량이 없으면 `LLMError`(OpenAI 경로와 같은 이유: 상한을 지킬 수 없다).
- SDK 예외는 종류와 종료 코드만 담아 `LLMError`로 바꾼다. `stderr` 원문은 싣지 않는다.
- 일시적 실패(`CLIConnectionError`, `ProcessError`)는 짧게 두 번까지 다시 시도한다. 한도 초과는 다시 시도하지 않는다(§5.4).

사용량 · 감사:
- `usage`는 지금과 같은 모양으로 채운다. `prompt_tokens = input + cache_read + cache_creation`, `completion_tokens = output`, `cached_tokens = cache_read`, `total_tokens`는 둘의 합. `model_usage`가 있으면 그것을 우선한다.
- `max_total_tokens`는 그대로 적용한다. 이 경로에서는 비용이 아니라 구독 한도를 지키는 장치다. SDK가 붙이는 자체 프롬프트의 토큰도 여기에 잡힌다.
- `log_call("completion", ...)`을 같은 필드로 쓰고 provider를 구분하는 필드를 하나 더한다. `llm_audit.jsonl`을 읽는 도구가 깨지지 않아야 한다.

### 5.3 자격 증명

- **API 키가 쓰이지 않게 한다.** CLI 프로세스가 보는 환경에서 `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CODE_USE_BEDROCK / _VERTEX / _FOUNDRY`를 뺀다. 뺄 수 없는 구조라면 그 변수가 있을 때 시작을 거절하고 이유를 알린다. 어느 쪽이든 "조용히 API 키로 돈다"는 없어야 한다.
- 실제로 어떤 자격으로 돌았는지 첫 호출에서 확인해 매니페스트에 적는다(§9에서 확인 방법을 정함). 구독이 아니면 `LLMError`.
- 로그인은 사용자가 터미널에서 `claude`로 직접 한다. 이 앱은 로그인 화면을 만들지 않고 토큰을 저장하지도 않는다. 화면이 없는 환경을 위해 `.env`의 `CLAUDE_CODE_OAUTH_TOKEN`(`claude setup-token`으로 만든 값)은 CLI로 넘긴다.
- 서버는 로그인 여부를 설정 화면에 알려 준다(OpenAI 키의 "환경에서 읽음 / 키 없음"과 같은 자리). 비용 없이 확인할 방법이 없으면 "확인" 버튼을 눌렀을 때만 호출 한 번으로 확인한다.

### 5.4 구독 한도

- 스트림에서 `RateLimitEvent`의 `status == "rejected"`를 보면 `LLMError`를 낸다. 메시지에 한도 종류(5시간 / 7일)와, 이벤트에 있으면 재설정 시각을 담는다.
- 그러면 기존 동작대로 실행이 마지막 체크포인트에서 `paused`가 되고, 한도가 풀린 뒤 메뉴에서 이어서 실행한다. 한도가 풀릴 때까지 프로세스가 잠들어 기다리지 않는다.
- `allowed_warning`은 실행을 멈추지 않고 라이브 상태 메시지에 한 번 알린다.
- 인터뷰와 생성기에서는 같은 `LLMError`가 기존 오류 응답으로 나간다(생성기는 실패한 메시지를 보존하는 기존 동작 그대로).

### 5.5 임베딩

- 실행 설정에 `embed_backend: "openai" | "local"`을 더한다. `backend: "openai"`인 실행은 지금처럼 OpenAI 임베딩이고 이 값이 필요 없다.
- `ClaudeAgentBackend`는 임베딩 함수를 받아서 `embed`를 그쪽으로 넘긴다.
  - `openai`: 기존 `OpenAIBackend.embed`. `OPENAI_API_KEY`가 필요하고, 사용량은 `usage["embed"]`에 잡힌다. 유료 호출이다.
  - `local`: 새 `LocalEmbedder`. 조건은 다음과 같다. CPU에서 돈다. 한국어를 다루는 다국어 모델이다. `embed(texts)`는 질문과 문서를 구분하지 않으므로 접두어 없이 쓰는 대칭 모델이거나 고정 접두어 하나로 쓴다. 같은 입력에 같은 벡터가 나온다. 모델은 처음 쓸 때 한 번 내려받고, 그 사실을 화면에 알린다.
- 매니페스트와 `resolved_config.json`에 임베딩 종류와 모델 이름을 적는다. 캐시 키가 모델 이름을 포함하므로 로컬 모델 이름이 그대로 키가 된다.
- `interview.run_embedder`는 그 실행의 `embed_backend`를 읽어 같은 임베더를 만든다. "Demo provider에서는 유료 호출을 하지 않는다"는 기존 규칙은 유지하고, 로컬 임베딩은 유료가 아니므로 언제나 쓸 수 있다.
- 기억 저장소가 벡터 차원을 1536으로 가정하는 곳이 없는지 구현 전에 확인한다.

### 5.6 실행 설정과 팩토리

- `models.py`: `backend: Literal["demo", "openai", "claude"]`. `claude`이면 `model_decide`, `model_speak`, `embed_backend`가 필요하고, `embed_backend == "openai"`이면 `model_embed`도 필요하다.
- 백엔드를 만드는 다섯 군데를 `llm.py`의 팩토리 하나로 모은다. 새 경로를 다섯 번 따로 붙이지 않기 위해서다. `cli.py`의 `isinstance(llm, OpenAIBackend)`는 "사용량과 감사 경로를 가진 백엔드인가"로 바꾼다.
- 매니페스트에 provider, SDK 버전, CLI 버전, 모델 id, 임베딩 모델, 인증 종류(구독)를 적는다. 나중에 결과를 비교할 때 어떤 조건으로 돌았는지 알아야 한다.
- `Tape`, `EmbedCache`, 검색 캐시는 `LanguageModel`을 감싸는 구조라 바뀌지 않는다.

### 5.7 서버 설정

- `PROVIDERS`에 `claude`를 더한다. `DEFAULTS`에 `claude_model_decide`, `claude_model_speak`(둘 다 `claude-haiku-5-5`), `claude_embed`(`local`), `model_embed_local`, `claude_max_concurrent`(4)를 더한다. OpenAI용 모델 이름과 섞이지 않게 키를 따로 둔다.
- `GET /api/settings`가 Claude 로그인 상태와 선택 설치 여부를 함께 돌려준다.
- 유료 확인 규칙: 유료 호출이 하나라도 있으면 확인을 받는다.
  - `openai` 실행: 지금과 같다.
  - `claude` + 임베딩 `openai`: 확인을 받는다. 문구는 "임베딩만 OpenAI로 과금"이다.
  - `claude` + 임베딩 `local`: 확인이 필요 없다. `ALLOW_PAID_API_EXPERIMENTS`도 요구하지 않는다.
- 인터뷰(`_interview_ask`)와 생성기(`generator_llm`)는 provider가 `claude`이면 팩토리로 `ClaudeAgentBackend`를 만든다. 인터뷰는 `claude_model_speak`, 생성기는 `claude_model_decide`를 쓴다. 생성기의 "OpenAI provider가 필요하다"는 409는 "실제 모델 provider가 필요하다"로 바뀐다.

### 5.8 화면

- 설정의 provider 카드에 "Claude (구독)"을 켠다. 고르면 로그인 상태, 판단 · 발화 모델, 임베딩 선택(로컬 / OpenAI), 토큰 상한이 보인다. 상한의 설명은 "구독 한도 보호"로 바꾸고, "본인 구독으로 본인 컴퓨터에서만"이라는 범위를 한 줄로 적는다.
- 실행 시작 · 이어서 실행 대화상자는 §5.7의 규칙대로 비용 확인을 보이거나 숨긴다. 지금은 `provider === 'openai'`로만 판단한다.
- 한도로 멈춘 실행은 기존 `paused` 표시에 이유(한도 종류와 재설정 시각)가 보인다.
- 문구는 `i18n.ts`에 한국어 · 영어로 더한다.

### 5.9 테스트

- CLI 없이 돈다. `query()`의 `transport` 인자에 가짜 전송을 넣거나 `query`를 바꿔 끼워서 메시지 열을 흉내 낸다.
- 다룰 경우: 세 가지 호출 형태, 사용량 누적과 상한 정지, `rejected` → `LLMError`, 실패 subtype들, SDK 예외 → `LLMError`(stderr가 메시지에 없음), 격리 옵션이 매 호출에 붙는지, 환경에서 API 키가 빠지는지, 세마포어가 동시 실행 수를 지키는지.
- 서버: `provider: "claude"` 저장, 유료 확인 규칙 세 가지, 인터뷰 · 생성기의 백엔드 선택. `provider: "anthropic"`은 계속 400이다.
- 실제 구독으로 한 번 돌려 보는 확인은 자동 테스트에 넣지 않고 손으로 한다(§9와 같은 스크립트).

## 6. 단계

0. 확인(§9). 결과에 따라 이 문서를 고친다.
1. `ClaudeAgentBackend` + 팩토리 + 테스트. 화면 없이 `backend: claude` 설정 파일로 실행이 돈다.
2. 임베딩 선택(`embed_backend`, `LocalEmbedder`).
3. 서버 설정 · 유료 확인 규칙 · 설정 화면 · 실행 시작 화면.
4. 인터뷰.
5. 시나리오 생성기. 한 번에 긴 구조화 출력을 내므로 따로 확인한다.

단계마다 OpenAI · Demo 경로의 기존 테스트가 그대로 통과해야 한다.

## 7. 다른 provider와 결과를 비교할 때

temperature를 보낼 수 없고 출력 길이 상한도 강제되지 않을 수 있다. 같은 시나리오라도 OpenAI 실행과 Claude 실행은 모델 말고도 이 조건이 다르다. 매니페스트에 적어 두는 것으로 대응하고, 조건을 맞추는 일은 이번 범위가 아니다.

## 8. 위험

실측(2026-11-11, `2026-11-10-claude-subscription-route/live-check.md`): 10명 실행에서 판단 호출 하나가
약 1.6만 토큰, 호출 63회에 3분 48초. 10명·하루(완성 약 370회)를 끝까지 돌리면 약 20분, 약 600만 토큰.

- **느리다.** 호출마다 프로세스를 띄운다. 10명 · 하루가 몇 시간이 걸릴지는 §9에서 잰다. 감당이 안 되면 프로세스 재사용을 다음 단계로 올린다.
- **한도.** 긴 실행은 5시간 한도에 여러 번 닿을 수 있다. 멈추고 이어 가는 것으로만 대응한다.
- **문서와 실제의 차이.** §4.2는 문서에서 읽은 것이다. 구독 인증, 도구 끄기, 한도 이벤트의 실제 모습은 확인 전이다.
- **정책 변화.** 구독을 SDK로 쓰는 것에 대한 문구가 바뀔 수 있다. 이 경로는 선택 설치이고 OpenAI 경로와 분리돼 있어서, 막히면 이 경로만 끄면 된다.

## 9. 먼저 확인할 것 (구현 전, 버리는 스크립트로)

결과(2026-11-11): `2026-11-10-claude-subscription-route/spike-results.md`. 바뀐 결정 — API 키는 `options.env` 덮어쓰기로 막는다, 스키마 없는 JSON 호출은 텍스트를 파싱한다, 추론 끄기는 `effort="low"`를 함께 보낸다, 호출별 출력 상한은 걸지 않는다, CLI 플래그 넷(`--restricted --disable-slash-commands --strict-mcp-config --no-session-persistence`)을 붙인다, Claude 실행의 토큰 상한 기본값을 따로 둔다(3,000만). CLI가 계정 · 환경 · 날짜를 컨텍스트에 덧붙이는 것은 막을 수 없다(§8).

1. 구독 로그인만 있는 상태에서 `query()`가 도는가. 어떤 자격으로 돌았는지 응답에서 알 수 있는가.
2. 환경에 `ANTHROPIC_API_KEY`가 있을 때 CLI가 그것을 못 보게 할 수 있는가(`env` 옵션으로 빼지는지, 부모 환경에서 지워야 하는지).
3. `tools=[]`가 내장 도구를 전부 끄는가. 아니면 무엇으로 끄는가.
4. 호출 한 번의 지연과 토큰(짧은 시스템 프롬프트 + 짧은 답). 여기서 10명 · 하루 실행의 예상 시간과 토큰을 계산한다.
5. `output_format`과 `{"type": "object"}` 스키마, `strict_schema`가 만든 스키마가 그대로 통하는가. 구조화 출력에 턴이 몇 번 드는가.
6. 출력 토큰 상한을 줄 방법이 있는가.
7. `RateLimitEvent`가 `query()` 스트림에 어떤 모습으로 오는가. `rejected`일 때 스트림은 어떻게 끝나는가.
8. 4개, 10개를 동시에 띄웠을 때의 안정성과 메모리.
9. Haiku 5.5에서 `thinking={"type": "disabled"}`가 받아들여지는가. 모델 id는 전체 이름으로 넘기는가.
10. 생성기 크기의 입력(수십만 자)을 `prompt`로 넘길 수 있는가.

4번의 결과가 "10명 · 하루에 여러 시간"이면 구현을 시작하기 전에 사용자에게 알리고 방향을 다시 정한다.

## 10. 내가 정한 것 (사용자가 확인할 것)

- provider 이름을 `claude`로 하고, `anthropic` 카드는 API 키 경로용으로 "준비 중"인 채 둔다.
- Claude 실행의 기본 추론 설정은 꺼짐(`reasoning_effort: none`)이다. 호출 수가 많아서 속도와 한도를 우선했다.
- 동시 프로세스 기본 4개, 호출 제한 시간 180초, 일시적 실패 재시도 2회.
- Claude provider의 임베딩 기본값은 로컬이다. 목적이 과금 없는 실행이라서다.
- 한도에 닿으면 기다리지 않고 멈춘다.
- temperature는 무시하고 매니페스트에 적는다.
- 백엔드 생성 다섯 군데를 팩토리 하나로 모은다(새 경로와 함께 하는 정리).
- `probes/`, `scripts/`는 건드리지 않는다.
- 선택 설치 두 개를 새로 둔다(기존 "새 의존성 없음" 원칙의 예외).

## 11. 빌더에게 맡기는 것

- 파일 배치(`llm.py`에 더할지 새 모듈로 뺄지)와 팩토리의 시그니처.
- 로컬 임베딩 라이브러리와 모델(§5.5의 조건 안에서). torch를 새 필수 의존성으로 끌어오지 않는 쪽을 우선한다.
- 로그인 상태를 확인하는 방법, 인증 종류를 확인하는 방법(§9의 결과에 따라).
- 긴 시스템 프롬프트를 파일로 넘기는 기준 길이와 임시 파일 정리.
- 감사 로그에 더하는 필드 이름, 설정 키 이름, 화면 문구.
- SDK 최소 버전(`ResultError`는 0.2.140+).

## 12. 출처

- Agent SDK: `https://code.claude.com/docs/en/agent-sdk/overview`, `/python`, `/structured-outputs`, `/quickstart`, `/cost-tracking`, `/modifying-system-prompts`, `/hosting`
- 인증 · 정책: `https://code.claude.com/docs/en/authentication`, `/legal-and-compliance`, `/headless`
- 2026-11-10에 읽었다. `/python` 문서의 뒷부분(`ResultMessage` 필드, 예외 목록)은 요약본으로 확인한 것이라 구현 때 원문과 맞춰 본다.
