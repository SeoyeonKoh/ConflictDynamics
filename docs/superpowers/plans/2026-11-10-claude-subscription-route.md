# Claude 구독 경로 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 설정에서 "Claude (구독)"을 고르면 시뮬레이션 실행 · 인터뷰 · 시나리오 생성기의 모델 호출이 Claude Agent SDK를 거쳐 사용자의 구독으로 나간다.

**Architecture:** `LanguageModel` 규약의 세 번째 구현 `ClaudeAgentBackend`를 새 모듈에 두고, `complete` 한 번을 SDK `query()` 한 번(도구 · 설정 · 작업 폴더가 격리된 CLI 프로세스 하나)으로 옮긴다. 임베딩은 백엔드에 주입하는 함수로 분리해 로컬 모델과 OpenAI 중에서 고른다. 흩어진 백엔드 생성 다섯 군데를 `llm.make_backend` 하나로 모으고, 서버 · 라이브 · 화면은 그 위에 provider `claude`를 더한다.

**Tech Stack:** Python 3.11+ (pydantic, hydra, http.server), `claude-agent-sdk`(선택 설치), `fastembed`(선택 설치), pytest, ruff; Vite + TypeScript(새 의존성 없음).

**Spec:** `docs/superpowers/specs/2026-11-10-claude-subscription-route-design.md` — 이 계획의 "§"는 그 문서의 절이다.

## Global Constraints

- provider id와 `backend` 값은 `claude`. 기존 `anthropic`은 계속 400이다(`tests/test_server.py`의 그 단언은 고치지 않는다).
- 기본 모델은 판단 · 발화 모두 `claude-haiku-5-5`.
- 필수 의존성을 늘리지 않는다. SDK와 로컬 임베딩은 `pyproject.toml`의 extra이고, import는 첫 사용 시점에 한다. 없으면 `LLMError`로 설치 명령을 알린다.
- OpenAI · Demo 경로의 동작은 바뀌지 않는다. 기존 테스트는 고치지 않고 통과해야 한다(이 계획이 명시한 곳 제외).
- 모든 Claude 호출은 도구 없음, `setting_sources=[]`, `mcp_servers={}`, 빈 임시 `cwd`, `permission_mode="dontAsk"`, `extra_args={"restricted": None, "disable-slash-commands": None, "strict-mcp-config": None, "no-session-persistence": None}`로 나간다(스파이크 결과 2 · 3).
- 스파이크 결과: `docs/superpowers/specs/2026-11-10-claude-subscription-route/spike-results.md`. 아래 Task의 "(스파이크)" 표시는 그 결과로 바뀐 값이다.
- 토큰, API 키, CLI의 `stderr` 원문은 로그 · 오류 메시지 · 매니페스트 · HTTP 응답에 싣지 않는다.
- 한도에 닿으면 기다리지 않고 `LLMError`로 멈춘다.
- 검증 명령: `uv run --all-extras pytest`, `uv run ruff check .`, `viz/`에서 `npx tsc --noEmit`.
- 커밋 메시지는 영어 conventional 형식(`feat(llm): …`)이고 AI 표기 트레일러를 붙이지 않는다(저장소 규칙).
- 실제 구독을 쓰는 단계(Task 0, Task 9)는 사용자의 구독 한도를 쓴다. 시작 전에 사용자에게 알린다.

## Review Focus

1. 셸에 `ANTHROPIC_API_KEY`가 있는 상태에서 Claude 실행을 시작한다 → API 키로 과금되지 않고, 구독이 아니면 시작이 거절된다. (Task 2 테스트, Task 9 실제 확인)
2. 실행 도중 한도에 닿는다 → 마지막 체크포인트에서 `paused`가 되고, 이어서 실행하면 같은 틱이 두 번 적용되지 않는다. (Task 4 테스트)
3. SDK나 CLI가 설치되지 않은 컴퓨터에서 Claude를 고른다 → 설정 저장과 실행 시작이 500이 아니라 설치 안내가 담긴 409로 답한다. (Task 5 테스트)
4. 로컬 임베딩 모델을 내려받을 수 없다(오프라인) → 틱 0 이전에 모델 이름이 담긴 오류로 멈추고, 반쯤 돈 실행이 남지 않는다. (Task 4 테스트)
5. Claude 실행을 끝낸 뒤 설정의 임베딩을 바꾸고 인터뷰한다 → 질문은 그 실행이 쓴 임베딩 모델로 임베딩된다. (Task 6 테스트)

---

## File Structure

| 파일 | 책임 |
|---|---|
| `src/conflict_sim/claude_backend.py` (새 파일) | `ClaudeAgentBackend`: 옵션 조립, `query()` 호출, 결과 · 사용량 · 한도 · 오류 처리 |
| `src/conflict_sim/local_embed.py` (새 파일) | `LocalEmbedder`: 로컬 임베딩 모델 한 개 |
| `src/conflict_sim/llm.py` | `make_backend`, `make_embedder` 팩토리 추가 |
| `src/conflict_sim/models.py`, `company_runtime.py` | `backend: "claude"`, `embed_backend`, `claude_max_concurrent` |
| `src/conflict_sim/experiment.py`, `cli.py` | 팩토리 사용, CLI 인자, 유료 판정, 매니페스트 |
| `src/conflict_sim/server.py`, `live.py`, `runs.py`, `interview.py` | provider, 설정 키, 유료 확인, 인터뷰 · 생성기 백엔드 |
| `viz/src/menu.ts`, `create.ts`, `interview.ts`, `i18n.ts` | 설정 카드, 비용 확인, 문구 |
| `tests/test_claude_backend.py`, `tests/test_local_embed.py` (새 파일) | 새 모듈의 테스트 |

---

### Task 0: 실제 SDK 확인 (스파이크)

**Files:**
- Create: `docs/superpowers/specs/2026-11-10-claude-subscription-route/spike-results.md`
- Modify: 스펙 §4.2 · §9, 이 계획에서 "S번호"가 붙은 값
- 스크립트는 저장소 밖(임시 폴더)에 두고 커밋하지 않는다.

**Interfaces:**
- Produces: 아래 S1~S10의 답. 뒤 Task들이 "S번호 기본값"으로 적은 결정을 이 답으로 확정하거나 고친다.

- [ ] **Step 1: 사용자에게 알린다** — 구독으로 짧은 호출 수십 번을 보낸다는 것, 필요한 준비(`claude` 로그인, `pip install claude-agent-sdk`).
- [ ] **Step 2: 스크립트로 S1~S10을 잰다**

| # | 확인할 것 | 이 계획의 기본값 |
|---|---|---|
| S1 | 구독 로그인만으로 `query()`가 도는가. 첫 `SystemMessage`(init)에서 인증 종류를 읽을 수 있는가, 구독일 때의 값 | `data["apiKeySource"] == "none"`이면 구독 |
| S2 | `ANTHROPIC_API_KEY`가 환경에 있을 때 CLI가 못 보게 하는 방법 | 백엔드 생성 시 프로세스 환경에서 지운다 |
| S3 | `tools=[]`가 내장 도구를 전부 끄는가 | `tools=[]` |
| S4 | 호출 1회의 지연 · 토큰(짧은 프롬프트). 10명 · 하루(완성 호출 약 1,500회 가정, 동시 4개)의 예상 시간 | — |
| S5 | `{"type": "object"}` 스키마와 `strict_schema()` 결과가 `output_format`에 통하는가, 구조화 출력의 턴 수 | 둘 다 통한다, `max_turns`는 주지 않는다 |
| S6 | 출력 토큰 상한을 줄 방법 | 없음(강제하지 않음) |
| S7 | `RateLimitEvent`가 스트림에 오는 모습, `rejected`일 때 필드(재설정 시각 이름)와 스트림 종료 방식 | `rate_limit_info.status`, `.rate_limit_type`, `.resets_at` |
| S8 | 동시 4개 · 10개의 안정성과 메모리 | 기본 4 |
| S9 | `claude-haiku-5-5`에서 `thinking={"type": "disabled"}` 수용 여부, 모델 id 형식 | 수용, 전체 id |
| S10 | 40만 자 입력을 `prompt`로 넘길 수 있는가 | 가능 |

- [ ] **Step 3: `spike-results.md`에 답과 측정값을 적고, 스펙 §4.2 · §9와 이 계획의 해당 값을 고친다**
- [ ] **Step 4: 사용자에게 보고하고 확인을 받는다** — S4의 예상 시간, 기본값과 달라진 항목. S4가 "10명 · 하루에 여러 시간"이면 여기서 멈추고 방향을 다시 정한다(스펙 §9).
- [ ] **Step 5: Commit** — `docs: claude sdk spike results`

---

### Task 1: `ClaudeAgentBackend.complete` — 호출 대응과 사용량

**Files:**
- Create: `src/conflict_sim/claude_backend.py`, `tests/test_claude_backend.py`
- Modify: `pyproject.toml` (`claude = ["claude-agent-sdk>=0.2.140", "python-dotenv>=1,<2"]`)

**Interfaces:**
- Consumes: `llm.LLMError`, `llm.strict_schema`, `usage_audit.log_call / completion_metadata / traced`
- Produces:

```python
Embed = Callable[[list[str]], list[list[float]]]
RunQuery = Callable[..., AsyncIterator[Any]]   # run_query(prompt=str, options=dict)
SYSTEM_PROMPT_FILE_CHARS = 60_000

class ClaudeAgentBackend:
    def __init__(self, *, embed: Embed | None = None, reasoning_effort: str | None = None,
                 max_total_tokens: int | None = 100_000, max_input_chars: int = 64_000,
                 max_concurrent: int = 4, timeout: float = 180.0,
                 audit_path: Path | None = None, run_query: RunQuery | None = None): ...
    usage: dict            # OpenAIBackend.usage와 같은 키
    audit_path: Path | None
    auth: str | None       # 첫 호출 뒤 인증 종류 (Task 2)
    warnings: list[str]    # 한도 경고 (Task 2)
    def complete(self, *, system, prompt, model, temperature, json_mode, schema=None) -> str: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...
```

- `run_query`의 기본값은 SDK를 첫 호출에서 import해 `query(prompt=..., options=ClaudeAgentOptions(**options))`를 부르는 어댑터다. 테스트는 가짜 `run_query`를 넣는다.
- 메시지는 SDK 클래스를 import하지 않고 `type(message).__name__`(`"ResultMessage"`, `"RateLimitEvent"`, `"SystemMessage"`)으로 가린다. 테스트의 가짜 메시지가 SDK 설치 없이 돌게 하기 위해서다.

- [ ] **Step 1: 실패하는 테스트를 쓴다** (`tests/test_claude_backend.py`)

가짜 준비: 이름이 `ResultMessage`인 dataclass(`subtype="success"`, `is_error=False`, `result`, `structured_output=None`, `stop_reason="end_turn"`, `usage`, `model_usage=None`), 받은 `options`를 기록하고 주어진 메시지 열을 내는 `fake_query(messages)`.

```python
def test_text_call_returns_the_result_and_is_isolated():
    seen, backend = recording_backend([result("안녕")])
    assert backend.complete(system="S", prompt="P", model="claude-haiku-5-5",
                            temperature=0.8, json_mode=False) == "안녕"
    o = seen[0]["options"]
    assert seen[0]["prompt"] == "P" and o["system_prompt"] == "S" and o["model"] == "claude-haiku-5-5"
    assert o["tools"] == [] and o["setting_sources"] == [] and o["mcp_servers"] == {}
    assert o["permission_mode"] == "dontAsk"
    assert Path(o["cwd"]).is_dir() and not any(Path(o["cwd"]).iterdir())
    assert "temperature" not in o and "max_turns" not in o

def test_a_schema_becomes_output_format_and_returns_json_text():
    seen, backend = recording_backend([result("", structured_output={"action": "말하기"})])
    text = backend.complete(system="S", prompt="P", model="m", temperature=0, json_mode=True, schema=Act)
    assert seen[0]["options"]["output_format"] == {"type": "json_schema", "schema": strict_schema(Act)}
    assert text == '{"action": "말하기"}'          # ensure_ascii=False

def test_json_mode_without_a_schema_parses_the_text_reply():          # (스파이크 S5)
    seen, backend = recording_backend([result('```json\n{"reply": "ok"}\n```')])
    assert json.loads(backend.complete(system="S", prompt="P", model="m", temperature=0, json_mode=True)) == {"reply": "ok"}
    assert "output_format" not in seen[0]["options"]
    # 객체가 아닌 텍스트("네")는 LLMError

@pytest.mark.parametrize("effort, expected", [                          # (스파이크 S9)
    ("none", {"thinking": {"type": "disabled"}, "effort": "low"}), ("low", {"effort": "low"}), (None, {})])
def test_reasoning_effort_maps_to_thinking_or_effort(effort, expected): ...
    # options에서 "thinking" / "effort" 키만 뽑아 expected와 같아야 한다

def test_usage_counts_by_role_and_the_cap_stops_the_next_call():
    usage = {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 20}
    seen, backend = recording_backend([result("a", usage=usage)], max_total_tokens=135)
    backend.complete(system="S", prompt="P", model="m", temperature=0, json_mode=False)
    assert backend.usage["speak"] == {"calls": 1, "prompt_tokens": 130, "completion_tokens": 5,
        "total_tokens": 135, "cached_tokens": 100, "reasoning_tokens": 0, "missing_usage": 0}
    with pytest.raises(LLMError, match="token budget"):
        backend.complete(system="S", prompt="P", model="m", temperature=0, json_mode=True)
    assert len(seen) == 1

@pytest.mark.parametrize("message, pattern", [
    (result("x", subtype="error_max_structured_output_retries", is_error=True), "error_max_structured_output_retries"),
    (result("", structured_output=None), "structured output"),      # schema 호출인데 결과 없음
    (result("x", stop_reason="refusal"), "refusal"),
    (result("x", usage=None), "no usage"),
    (result("  "), "empty"),
])
def test_incomplete_results_are_failures_not_replies(message, pattern): ...

def test_oversized_input_is_rejected_before_any_call(): ...      # max_input_chars=10, len(seen) == 0

def test_a_long_system_prompt_goes_by_file_and_the_file_is_removed():
    system = "가" * (SYSTEM_PROMPT_FILE_CHARS + 1)
    # options["system_prompt"] == {"type": "file", "path": p}; 호출 중 p의 내용 == system; 호출 뒤 p가 없다

def test_missing_sdk_explains_the_install(monkeypatch):
    # run_query 없이 만들고 import가 실패하게 하면 LLMError 메시지에 "uv sync --extra claude"
```

- [ ] **Step 2: 실패를 확인한다** — `uv run pytest tests/test_claude_backend.py -q` → import 오류로 FAIL
- [ ] **Step 3: `claude_backend.py`를 구현한다**
  - `complete`는 스레드에서 불리므로 호출마다 `asyncio.run`으로 스트림을 끝까지 읽는다.
  - `prompt_tokens = input_tokens + cache_read_input_tokens + cache_creation_input_tokens`, `completion_tokens = output_tokens`, `cached_tokens = cache_read_input_tokens`. `model_usage`가 있으면 그 합을 쓴다. 카운터는 락으로 보호하고 `"decide"`(json_mode) / `"speak"`로 나눈다.
  - `log_call("completion", call_count=1, model=..., input_tokens=..., output_tokens=..., total_tokens=..., cached_tokens=..., provider="claude", **completion_metadata(system, prompt))`.
  - `json_mode`만 있는 경우: `output_format` 없이 부르고 결과에서 코드 펜스를 벗겨 `json.loads`로 확인, 객체가 아니면 `LLMError`(스파이크 S5).
  - 사용량은 `model_usage`를 우선한다(스파이크 결과 5). 스트림은 결과 메시지 뒤에도 끝까지 읽는다(결과 6). `is_error=True` 결과 뒤의 예외는 그 결과의 실패로 보고한다(결과 7).
- [ ] **Step 4: 통과를 확인한다** — `uv run pytest tests/test_claude_backend.py -q`, `uv run ruff check src/conflict_sim/claude_backend.py`
- [ ] **Step 5: Commit** — `feat(llm): claude agent sdk backend for completions`

---

### Task 2: 한도 · 오류 · 동시성 · 자격 증명

**Files:**
- Modify: `src/conflict_sim/claude_backend.py`, `tests/test_claude_backend.py`

**Interfaces:**
- Consumes: Task 1의 `ClaudeAgentBackend`
- Produces:

```python
SUBSCRIPTION_BLOCKERS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
                         "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY")
TRANSIENT_RETRIES = 2
def subscription_env(environ: Mapping[str, str] = os.environ) -> dict[str, str]:
    """`options.env` overrides that blank every credential outranking the subscription login."""
```

- 매 호출의 `options["env"]`에 `subscription_env()`를 넣는다. 프로세스 환경은 바꾸지 않는다(스파이크 S2). `env_file`의 `CLAUDE_CODE_OAUTH_TOKEN`은 팩토리(Task 4)가 dotenv로 읽어 둔다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```python
def test_a_rejected_limit_stops_at_once_and_names_the_window():
    seen, backend = recording_backend([limit("rejected", "five_hour", resets_at=1_800_000_000), result("x")])
    with pytest.raises(LLMError, match="five_hour") as error:
        backend.complete(system="S", prompt="P", model="m", temperature=0, json_mode=False)
    assert "구독 한도" in str(error.value) and len(seen) == 1          # 다시 시도하지 않는다

def test_a_limit_warning_is_kept_and_the_call_succeeds():
    _, backend = recording_backend([limit("allowed_warning", "seven_day"), result("x")])
    assert backend.complete(...) == "x" and len(backend.warnings) == 1

def test_transient_failures_retry_twice_then_fail_without_stderr():
    # run_query가 매번 이름이 ProcessError인 예외(exit_code=1, stderr="sk-ant-secret")를 낸다
    with pytest.raises(LLMError, match="ProcessError.*exit 1") as error: ...
    assert calls == 1 + TRANSIENT_RETRIES and "sk-ant-secret" not in str(error.value)

def test_a_hung_call_times_out():                 # timeout=0.05, run_query가 끝나지 않는다 → LLMError "timed out"

def test_at_most_max_concurrent_calls_run_together():
    # max_concurrent=2, 스레드 8개 → 관측한 동시 실행 최대값 <= 2

def test_stronger_credentials_are_blanked_and_the_oauth_token_kept():
    env = {"ANTHROPIC_API_KEY": "k", "CLAUDE_CODE_USE_BEDROCK": "1", "CLAUDE_CODE_OAUTH_TOKEN": "t", "PATH": "/bin"}
    assert subscription_env(env) == {"ANTHROPIC_API_KEY": "", "CLAUDE_CODE_USE_BEDROCK": ""}
    # 호출 옵션의 env에 그 값이 들어가고, os.environ은 그대로다

def test_a_call_that_is_not_on_the_subscription_is_refused():
    seen, backend = recording_backend([init(api_key_source="ANTHROPIC_API_KEY"), result("x")])
    with pytest.raises(LLMError, match="구독"): backend.complete(...)
    # init(api_key_source="none") 뒤에는 backend.auth == "subscription"
```

- [ ] **Step 2: 실패를 확인한다** — `uv run pytest tests/test_claude_backend.py -q`
- [ ] **Step 3: 구현한다**
  - 한도 메시지: `Claude 구독 한도에 닿았습니다 (five_hour); <재설정 시각>에 풀립니다. 그 뒤에 이어서 실행하세요.` 재설정 시각이 없으면 그 구절을 뺀다.
  - 일시적 실패는 예외 클래스 이름이 `ProcessError`, `CLIConnectionError`, `CLIJSONDecodeError`인 것. `CLINotFoundError`는 재시도하지 않고 설치 안내를 낸다. 메시지는 `Claude call failed: <클래스 이름>, exit <코드>`.
  - 세마포어는 `threading.BoundedSemaphore(max_concurrent)`, 제한 시간은 `asyncio.wait_for`.
- [ ] **Step 4: 통과를 확인한다**
- [ ] **Step 5: Commit** — `feat(llm): subscription limits, retries and credential guard for the claude backend`

---

### Task 3: 로컬 임베딩

**Files:**
- Create: `src/conflict_sim/local_embed.py`, `tests/test_local_embed.py`
- Modify: `pyproject.toml` (`embed = ["fastembed>=0.4"]` — 버전 바닥은 설치 시 uv가 고른 값으로 맞춘다)

**Interfaces:**
- Produces:

```python
DEFAULT_LOCAL_EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

class LocalEmbedder:
    def __init__(self, model: str = DEFAULT_LOCAL_EMBED_MODEL, *, encoder=None): ...
    model: str
    def __call__(self, texts: list[str]) -> list[list[float]]: ...
```

- `encoder`는 테스트용 주입구다(`encoder(texts) -> Iterable[Sequence[float]]`). 없으면 첫 호출에서 `fastembed.TextEmbedding(model)`을 만든다.
- 모델 선택 근거(스펙 §5.5): 다국어(한국어 포함), 질문 · 문서 접두어가 없는 대칭 모델, CPU, torch 불필요.

- [ ] **Step 1: 모델을 확인한다** — `fastembed.TextEmbedding.list_supported_models()`에 기본 모델이 있는지 본다. 없으면 같은 조건을 채우는 지원 모델로 `DEFAULT_LOCAL_EMBED_MODEL`을 바꾸고 스펙 §5.5에 이름을 적는다. 한국어 문장 두 쌍(비슷한 뜻 / 다른 뜻)으로 유사도 순서가 맞는지 한 번 본다.
- [ ] **Step 2: 실패하는 테스트를 쓴다**

```python
def test_vectors_come_back_as_lists_in_input_order():
    embed = LocalEmbedder("m", encoder=lambda texts: (np.array([len(t), 1.0]) for t in texts))
    assert embed(["가", "가나다"]) == [[1.0, 1.0], [3.0, 1.0]] and embed([]) == []

def test_a_count_mismatch_is_a_failure():            # encoder가 하나 덜 준다 → LLMError
def test_a_load_failure_names_the_model():           # encoder 생성이 OSError → LLMError에 모델 이름
def test_missing_package_explains_the_install():     # import 실패 → "uv sync --extra embed"
def test_the_embed_cache_keys_on_the_local_model(tmp_path):
    # EmbedCache(backend, path)가 backend.model_embed로 키를 만든다 → 모델 이름이 다르면 캐시가 섞이지 않는다
```

- [ ] **Step 3: 실패를 확인한다** — `uv run pytest tests/test_local_embed.py -q`
- [ ] **Step 4: 구현한다** — `ClaudeAgentBackend`에 `model_embed` 속성을 더해 주입된 임베더의 모델 이름을 돌려주게 한다(`EmbedCache`가 읽는 속성). `embed`는 `usage["embed"]["calls"]`만 센다(토큰 없음). OpenAI 임베더를 주입한 경우의 토큰은 Task 4의 팩토리가 맡는다.
- [ ] **Step 5: 통과를 확인한다**
- [ ] **Step 6: Commit** — `feat(llm): local embedding model for keyless runs`

---

### Task 4: 실행 설정, 팩토리, 실행 경로

**Files:**
- Modify: `src/conflict_sim/models.py:394-411,466-480`, `src/conflict_sim/company_runtime.py:200-215,308-320`, `src/conflict_sim/llm.py`, `src/conflict_sim/experiment.py:93-210,412-475`, `src/conflict_sim/cli.py:78-142`
- Test: `tests/test_models.py`, `tests/test_llm.py`, `tests/test_company_runtime.py`, `tests/test_live.py`(실행 경로)

**Interfaces:**
- Consumes: `ClaudeAgentBackend`, `LocalEmbedder`, `use_subscription_only`
- Produces:

```python
# models.py — Config
backend: Literal["demo", "openai", "claude"] = "demo"
embed_backend: Literal["openai", "local"] | None = None
claude_max_concurrent: int = Field(default=4, ge=1)

# llm.py
def make_embedder(embed_backend: str | None, model_embed: str | None, env_file: Path) -> Embed | None
def make_backend(cfg: Config, env_file: Path, *, audit_path: Path | None = None) -> LanguageModel
def is_paid(backend: str, embed_backend: str | None) -> bool      # openai, 또는 claude + openai 임베딩
```

- `make_backend`: `demo` → `DemoBackend`, `openai` → 지금과 같은 인자의 `OpenAIBackend`, `claude` → dotenv로 `env_file`을 읽은 뒤 `ClaudeAgentBackend(embed=make_embedder(...), reasoning_effort=cfg.reasoning_effort or "none", max_total_tokens=..., max_input_chars=..., max_concurrent=cfg.claude_max_concurrent, audit_path=...)`.
- `make_embedder("openai", ...)`는 `OpenAIBackend(..., max_total_tokens=None).embed`를 감싸 모델 이름을 가진 임베더를 돌려준다. OpenAI 임베딩의 토큰이 Claude 백엔드의 `usage["embed"]`에 합쳐지게 한다.
- 실행 인자: `experiment`에 `--backend claude`, `--embed-backend {openai,local}`, `--claude-max-concurrent N`. `run_scenario(..., embed_backend=None, claude_max_concurrent=None)`.
- Claude 실행도 OpenAI와 같이 `--pilot`이고 `--replicates 1`이어야 한다.
- `model_embed`는 두 경우 모두 그 실행의 임베딩 모델 이름이다. `embed_backend="local"`이고 비어 있으면 `DEFAULT_LOCAL_EMBED_MODEL`로 채워 `resolved_config.json`에 남긴다.
- 매니페스트: `"model_id"`는 `backend != "demo"`이면 `cfg.model_decide`. 새 키 `"llm": {"provider", "embed_backend", "embed_model", "temperature_sent": false, "sdk_version", "cli_version", "auth"}`. `sdk_version` 이하 셋은 첫 호출 뒤에 채운다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```python
# tests/test_models.py
def test_a_claude_run_needs_models_and_an_embedding_choice():
    # backend="claude": model_decide/model_speak 없으면 오류, embed_backend 없으면 오류,
    # embed_backend="openai"인데 model_embed 없으면 오류, 셋 다 있으면 통과
def test_openai_and_demo_runs_ignore_the_new_fields(): ...

# tests/test_llm.py
def test_make_backend_builds_each_provider(tmp_path, monkeypatch):
    # demo → DemoBackend; openai → OpenAIBackend(인자 그대로); claude → ClaudeAgentBackend(max_concurrent=cfg 값)
def test_is_paid():
    assert [is_paid("demo", None), is_paid("openai", None), is_paid("claude", "local"), is_paid("claude", "openai")] == [False, True, False, True]

# 실행 경로 (make_backend를 가짜로 바꿔 끼운다)
def test_a_keyless_claude_run_needs_no_cost_approval(tmp_path, monkeypatch):
    # ALLOW_PAID_API_EXPERIMENTS 없이 backend="claude", embed_backend="local" → 실행된다
def test_a_claude_run_with_openai_embeddings_needs_cost_approval(...):     # → PermissionError
def test_the_manifest_records_how_the_run_called_the_model(...):
    # manifest["backend"] == "claude", manifest["llm"]["embed_backend"] == "local", ["temperature_sent"] is False
def test_a_limit_mid_run_pauses_and_resume_does_not_repeat_ticks(...):     # Review Focus 2
    # 가짜 백엔드가 N번째 호출에서 LLMError("Claude 구독 한도…") → run_status "paused", paused.json의 reason에 그 문구;
    # resume=True로 다시 돌리면 completed, frames.jsonl의 틱 번호에 중복이 없다
def test_an_unusable_embedder_stops_before_the_first_tick(...):            # Review Focus 4
    # 임베더가 LLMError를 낸다 → run_scenario가 틱 0 전에 그 오류로 끝나고 frames.jsonl이 비어 있다
def test_a_run_works_with_vectors_of_another_size(...):
    # 3차원 벡터를 내는 가짜 임베더로 하루 실행이 완료된다 (기억 저장소가 차원을 가정하지 않는다)
def test_a_limit_warning_reaches_the_live_status_once(...):
    # 백엔드의 warnings에 한 줄이 생기면 다음 stream.status 메시지에 그 문구가 한 번 실린다
```

- [ ] **Step 2: 실패를 확인한다** — `uv run pytest tests/test_models.py tests/test_llm.py tests/test_live.py -q`
- [ ] **Step 3: 구현한다**
  - `run_scenario`와 `cli._backend`의 생성 코드를 `make_backend`로 바꾼다. `cli.py`의 `isinstance(llm, OpenAIBackend)` 두 곳은 `getattr(llm, "usage", None) is not None`으로, `cfg.backend == "openai"` 사용량 조건은 `cfg.backend != "demo"`로 바꾼다.
  - 유료 관문(`experiment.py:113`)은 `is_paid(backend, embed_backend)`로 판정한다.
  - 임베딩을 쓰는 실행(`cfg.environment`가 있고 `backend != "demo"`)은 틱 0 전에 `llm.embed(["probe"])`를 한 번 부른다.
  - 틱마다 상태를 보낼 때 `getattr(llm, "warnings", [])`에서 아직 알리지 않은 경고를 꺼내 메시지에 붙인다(스펙 §5.4의 `allowed_warning`).
  - `company_runtime.py:308`의 `backend == "openai"` 분기가 무엇을 채우는지 읽고, Claude 실행에 필요한 값(모델 이름은 CLI 인자로 온다)이 빠지지 않게 한다.
- [ ] **Step 4: 전체 테스트를 돌린다** — `uv run --all-extras pytest -q`, `uv run ruff check .`. 기존 테스트가 그대로 통과해야 한다.
- [ ] **Step 5: Commit** — `feat(experiment): claude backend runs through one backend factory`

---

### Task 5: 서버 설정과 라이브 시작

**Files:**
- Modify: `src/conflict_sim/server.py:24-32,200-226,239-246`, `src/conflict_sim/live.py:43-122`, `src/conflict_sim/runs.py`(행에 `paid`)
- Test: `tests/test_server.py`, `tests/test_live.py`, `tests/test_runs.py`

**Interfaces:**
- Consumes: `is_paid`, `make_backend`
- Produces:

```python
PROVIDERS = ("openai", "demo", "claude")
DEFAULTS |= {"claude_model_decide": "claude-haiku-5-5", "claude_model_speak": "claude-haiku-5-5",
             "claude_embed": "local", "model_embed_local": DEFAULT_LOCAL_EMBED_MODEL,
             "claude_max_concurrent": 4, "claude_max_total_tokens": 30_000_000}   # (스파이크 결과 4)
# GET /api/settings 응답에 더해지는 키
"claude_sdk": bool      # claude_agent_sdk를 import할 수 있는가
"local_embed": bool     # fastembed를 import할 수 있는가
"claude_login": bool | None   # .env에 CLAUDE_CODE_OAUTH_TOKEN이 있으면 True, 그 밖에는 None(모름)
"paid": bool            # 지금 설정으로 시작하는 실행이 유료인가 (is_paid)
# POST /api/settings/claude-check → {"ok": bool, "auth": str | None, "error": str | None}
#   짧은 호출 한 번으로 구독 로그인을 확인한다. 사용자가 버튼을 눌렀을 때만.
def _run_models(settings: dict) -> dict   # provider별 model_decide / model_speak / model_embed / embed_backend
# live.start(..., embed_backend: str | None = None, max_concurrent: int | None = None)
# live._launch(..., paid: bool, ...)      # backend == "openai" 판정을 대신한다
# runs.py의 실행 행: "paid": bool          # 매니페스트의 backend와 llm.embed_backend로 계산
```

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```python
def test_claude_settings_round_trip(server):
    # PUT provider="claude" → 200; GET의 claude_model_decide == "claude-haiku-5-5", claude_embed == "local", paid is False
    # claude_embed="openai" → paid is True; claude_embed="other" → 400; claude_max_concurrent=0 → 400
    # provider="anthropic" → 여전히 400
def test_choosing_claude_without_the_sdk_is_a_409_with_the_install_line(server, monkeypatch):   # Review Focus 3
    # claude_sdk가 False일 때 PUT provider="claude" → 409, 본문에 "uv sync --extra claude"; POST /api/live/start도 409
def test_local_embedding_without_the_package_is_a_409(server, monkeypatch):   # "uv sync --extra embed"
def test_a_keyless_claude_start_needs_no_paid_confirmation(tmp_path, monkeypatch):
    # live.start(backend="claude", embed_backend="local", paid_confirmed=False)가 시작하고,
    # 자식의 argv에 --backend claude --embed-backend local, 환경에 ALLOW_PAID_API_EXPERIMENTS가 없다
def test_claude_with_openai_embeddings_needs_confirmation(...):       # PermissionError
def test_resume_reads_the_embedding_choice_from_the_manifest(...):    # argv에 --embed-backend <매니페스트 값>
def test_run_rows_say_whether_resuming_is_paid(...):                  # runs.py 행의 paid
def test_claude_check_never_returns_credentials(server, monkeypatch): # 응답에 토큰 문자열이 없다
```

- [ ] **Step 2: 실패를 확인한다** — `uv run pytest tests/test_server.py tests/test_live.py tests/test_runs.py -q`
- [ ] **Step 3: 구현한다** — `_put_settings`의 모델 문자열 검사는 `model_`로 시작하는 키와 `claude_model_`로 시작하는 키 모두에 적용한다. 기존 테스트 `test_settings_round_trip_and_never_show_the_key`는 고치지 않는다.
- [ ] **Step 4: 통과를 확인한다** — `uv run --all-extras pytest -q`
- [ ] **Step 5: Commit** — `feat(server): claude provider settings and paid-run rule`

---

### Task 6: 인터뷰

**Files:**
- Modify: `src/conflict_sim/interview.py:139-164`, `src/conflict_sim/server.py:290-314`
- Test: `tests/test_interview.py`, `tests/test_server.py`

**Interfaces:**
- Consumes: `make_embedder`, `make_backend`, `_run_models`
- Produces: `interview.run_embedder(run_dir, env_file)`가 Claude 실행을 다룬다. `question_embedder(run_backend, provider, env_file, run_dir)`의 규칙은 아래와 같다.

| 그 실행의 임베딩 | 지금 provider | 질문 임베딩 |
|---|---|---|
| demo | 아무거나 | `DemoBackend().embed` (지금과 같음) |
| 로컬 | 아무거나 | 그 실행의 로컬 모델 (유료가 아니다) |
| OpenAI | `demo` | 없음 — 최근성 · 중요도로만 (지금과 같음) |
| OpenAI | `openai` 또는 `claude` | 그 실행의 OpenAI 모델, 키가 없으면 없음 |

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```python
def test_a_question_about_a_claude_run_uses_that_runs_embedder(tmp_path):      # Review Focus 5
    # resolved_config: backend="claude", embed_backend="local", model_embed="모델-A"
    # 설정의 model_embed_local이 "모델-B"여도 run_embedder가 만든 임베더의 model == "모델-A"
def test_local_embeddings_answer_even_on_the_demo_provider(tmp_path): ...
def test_openai_embeddings_of_a_claude_run_stay_unpaid_on_demo(tmp_path): ...  # → None
def test_interview_on_the_claude_provider_asks_claude(server, monkeypatch):
    # make_backend를 가짜로 바꾼다 → ask가 그 백엔드와 settings["claude_model_speak"]로 불린다
    # interview.start의 기록에 provider == "claude", model == "claude-haiku-5-5"
```

- [ ] **Step 2: 실패를 확인한다** — `uv run pytest tests/test_interview.py tests/test_server.py -q`
- [ ] **Step 3: 구현한다** — 인터뷰용 Claude 백엔드는 `max_total_tokens=None`, `reasoning_effort="none"`으로 만든다. `interview.run_reasoning_effort`는 OpenAI 실행에만 쓴다.
- [ ] **Step 4: 통과를 확인한다**
- [ ] **Step 5: Commit** — `feat(interview): interviews on the claude provider`

---

### Task 7: 시나리오 생성기

**Files:**
- Modify: `src/conflict_sim/server.py:76-83,350-366`
- Test: `tests/test_server.py`, `tests/test_generator.py`

**Interfaces:**
- Consumes: `ClaudeAgentBackend`, `GENERATION_TOKEN_CAP`
- Produces: `Server.generator_llm() -> tuple[LanguageModel, str]`이 provider에 따라 백엔드를 고른다. 거절 문구가 바뀐다: `"scenario generation needs a real model provider"`(provider가 `demo`), `"the Claude Agent SDK is not installed"`(SDK 없음). OpenAI의 `"no OpenAI key in the server's .env"`는 그대로다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```python
def test_the_generator_runs_on_the_claude_provider(server, monkeypatch):
    # provider="claude", generator_llm을 가짜로 바꾸지 않고 ClaudeAgentBackend의 run_query만 가짜로:
    # 초안 메시지 한 번 → 200, 사용된 model == settings["claude_model_decide"],
    # 백엔드의 max_total_tokens == GENERATION_TOKEN_CAP, max_input_chars == 400_000
def test_the_demo_provider_still_refuses_generation(server):          # 409, 새 문구
def test_a_limit_during_generation_keeps_the_message(server, monkeypatch):
    # run_query가 rejected 한도 → 기존 "실패한 메시지는 보존" 동작 그대로, 응답에 한도 문구
def test_a_backend_failure_from_claude_is_reported_like_openai(...):  # _backend_failure가 LLMError를 그대로 다룬다
```

- [ ] **Step 2: 실패를 확인한다**
- [ ] **Step 3: 구현한다** — Claude 생성기 백엔드는 `reasoning_effort="none"`, `max_concurrent=1`. 생성기의 `complete`는 `json_mode=True`, 스키마 없음(Task 1의 임의 객체 경로)이다.
- [ ] **Step 4: 통과를 확인한다** — `uv run --all-extras pytest -q`
- [ ] **Step 5: Commit** — `feat(generator): scenario generation on the claude provider`

---

### Task 8: 화면

**Files:**
- Modify: `viz/src/menu.ts:15-18,137-200,280-290,340-370`, `viz/src/create.ts:15,83,141-150`, `viz/src/interview.ts:46-47`, `viz/src/i18n.ts`
- 자동 테스트 없음(viz에는 테스트 러너가 없다). 검증은 타입 검사 · 빌드 · 아래 수동 확인.

**Interfaces:**
- Consumes: Task 5의 `/api/settings` 응답(`claude_sdk`, `local_embed`, `claude_login`, `paid`, `claude_*` 키), `POST /api/settings/claude-check`, 실행 행의 `paid`
- Produces:

```ts
export interface Settings {
  provider: 'openai' | 'demo' | 'claude'; /* 기존 키 */
  claude_model_decide: string; claude_model_speak: string; claude_embed: 'local' | 'openai';
  model_embed_local: string; claude_max_concurrent: number;
  claude_sdk: boolean; local_embed: boolean; claude_login: boolean | null; paid: boolean;
}
export function confirmPaid(paid: boolean, estimate: string, cap: number | null, embedOnly?: boolean): Promise<boolean>
```

- [ ] **Step 1: 설정 대화상자** — provider 카드에 `prov('claude', 'Claude', 'claudeDesc', true)`를 OpenAI 다음에 넣는다. Anthropic 카드는 그대로 "준비 중"이다. `claudeFields`: 로그인 상태 줄(`claude_login`이 true → 확인됨, null → "확인" 버튼이 `claude-check`를 부른다), 판단 · 발화 모델, 임베딩 `segmented`(로컬 / OpenAI), 토큰 상한, 안내 두 줄. `claude_sdk`가 false이면 필드 대신 설치 안내를 보인다. 저장은 `claude_*` 키를 함께 보낸다.
- [ ] **Step 2: 비용 확인** — `confirmPaid`는 `paid`로 판단한다. 시작: `paid_confirmed: s.paid`. 이어서 실행: `paid_confirmed: row.paid`. Claude + OpenAI 임베딩이면 확인 문구가 `embedOnlyCost`다.
- [ ] **Step 3: 나머지** — 시작 화면의 provider 줄(`Claude · <모델>`), `interview.ts`의 `paid`(`s?.paid`), `create.ts`의 거절 문구 매핑과 `providerNote`(Claude이면 생성 가능).
- [ ] **Step 4: 문구를 `i18n.ts`에 한국어 · 영어로 더한다**

| 키 | 한국어 |
|---|---|
| `claudeDesc` | 구독 로그인 · API 키 없음 |
| `claudeScope` | 본인 Claude 구독으로 이 컴퓨터에서만 씁니다. 다른 사람에게 제공하려면 API 키 경로가 필요해요. |
| `claudeLimitNote` | 과금은 없지만 구독 한도를 씁니다. 한도에 닿으면 실행이 멈추고, 풀린 뒤 이어서 실행할 수 있어요. |
| `claudeLoginOk` / `claudeLoginUnknown` / `claudeLoginCheck` | 구독 로그인 확인됨 / 로그인 상태를 모릅니다 / 확인 |
| `claudeNeedsSdk` | Claude Agent SDK가 설치되지 않았어요: `uv sync --extra claude` |
| `embedChoice` / `embedLocal` / `embedOpenai` | 임베딩 / 로컬 (무료) / OpenAI (소액 과금) |
| `embedNeedsPackage` | 로컬 임베딩 패키지가 없어요: `uv sync --extra embed` |
| `capForLimits` | 토큰 상한 (구독 한도 보호) |
| `embedOnlyCost` | 이 실행은 임베딩만 OpenAI로 과금됩니다. |

- [ ] **Step 5: 검증한다** — `cd viz && npx tsc --noEmit && npm run build`. 수동 확인(conflict-server + vite): Claude 카드를 고르고 저장 → 다시 열면 유지, 임베딩을 OpenAI로 바꾸면 시작할 때 비용 확인이 뜨고 로컬이면 뜨지 않는다, Demo · OpenAI 화면은 전과 같다, 라이트 · 다크에서 카드와 필드가 깨지지 않는다.
- [ ] **Step 6: Commit** — `feat(viz): claude subscription provider in settings and run start`

---

### Task 9: 실제 구독으로 끝까지 확인하고 문서를 맞춘다

**Files:**
- Modify: `AGENT.md`(명령 · provider 설명), `README.md`(설치 extra, 범위 한 줄), 스펙 §8 · §9
- Create: `docs/superpowers/specs/2026-11-10-claude-subscription-route/live-check.md`

- [ ] **Step 1: 사용자에게 알린다** — 구독 한도를 쓰는 실제 실행이다.
- [ ] **Step 2: 확인한다** (결과를 `live-check.md`에 적는다)
  - `ANTHROPIC_API_KEY`를 셸에 넣은 채로 Claude + 로컬 임베딩 실행을 시작한다 → 매니페스트 `llm.auth`가 구독이고, Anthropic Console 사용량에 호출이 없다. (Review Focus 1)
  - 가장 작은 시나리오를 하루 돌린다 → 완료, 걸린 시간, 호출 수, `usage.json`.
  - 토큰 상한을 낮게 잡아 멈춘 뒤 이어서 실행한다 → 완료.
  - 그 실행에서 인터뷰 질문 하나, 생성기 메시지 하나.
  - 호출 중인 CLI 프로세스의 작업 폴더가 빈 임시 폴더이고, 응답에 저장소의 `CLAUDE.md` 내용이 드러나지 않는다.
- [ ] **Step 3: 문서를 고친다** — 측정한 시간과 한도 소모를 스펙 §8에, 설치 · 로그인 · 범위를 `README.md`와 `AGENT.md`에 적는다.
- [ ] **Step 4: 전체 검증** — `uv run --all-extras pytest -q`, `uv run ruff check .`, `cd viz && npx tsc --noEmit`
- [ ] **Step 5: Commit** — `docs: claude subscription route setup and live check`
