# viz 메인 화면 + 통합 백엔드 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Streamlit을 대체하는 엔진 내장 HTTP 서버와 viz 메인 화면(라이브 실행·리플레이·설정·대화 보기)을 만들고, run이 어느 틱에서 멈춰도 응답 기록 재생으로 이어 가게 한다.

**Architecture:** 엔진 쪽은 실행 옵션 몇 개, LLM 응답 기록기(`Tape`), 기록 재생 resume, frames의 속마음 필드를 더한다. `conflict-server`(표준 라이브러리 HTTP)가 목록·시나리오·설정·실행/정지를 맡고 run은 기존 CLI를 별도 프로세스로 띄운다. viz는 메뉴 페이지(`index.html`)와 기존 뷰어(`view.html`)로 나누고, 뷰어에 대화 탭을 더한다.

**Tech Stack:** Python 3.11+ (pydantic, websockets, sqlite3, http.server), pytest, ruff; Vite 8 + TypeScript 7 + Phaser 3.90.

**Spec:** `docs/superpowers/specs/2026-11-03-viz-main-menu-design.md` (목업: `docs/superpowers/specs/2026-11-03-viz-main-menu/*.html`). 각 태스크는 spec의 해당 절을 함께 읽는다.

## Global Constraints

- 새 Python 의존성 없음. HTTP는 `http.server.ThreadingHTTPServer`, WS는 기존 `websockets`.
- 서버와 run의 WS는 `127.0.0.1`에만 바인딩.
- OpenAI run은 `ALLOW_PAID_API_EXPERIMENTS=1` + `--pilot` 없이는 시작되지 않는다. 서버는 비용 확인 플래그가 있는 요청의 자식 프로세스 환경에만 이 값을 넣는다. 서버 자기 환경에는 넣지 않는다.
- API 키는 `.env`에서만 읽는다. 어떤 API 응답에도 키 값이 들어가지 않는다(있음/없음만).
- 시뮬레이션 동작 불변: `tests/test_retrieval_cache.py`, `tests/test_token_hypothesis_analysis.py`의 동작 해시가 바뀌면 안 된다.
- 커밋 메시지에 AI attribution / Co-Authored-By를 넣지 않는다.
- UI 기본 언어 한국어, 글꼴 Pretendard(이미 적용). 화면 문구는 목업과 spec 4절의 문구를 쓴다.
- 매 태스크 끝: `.venv/bin/pytest -q`, `.venv/bin/ruff check src tests`, viz를 건드렸으면 `cd viz && npm run check`.

## Review Focus

1. 서버 재시작 시 `live.json`은 있는데 pid가 죽은 run → "진행 중"이 아니라 중단/실패로 보여야 한다. (Task 8 테스트)
2. `/runs/<path>` 경로 탈출(`../`, 절대경로, `.jsonl` 아닌 파일) → 404. (Task 7 테스트)
3. 같은 시나리오를 같은 분에 두 번 시작 → 폴더 이름이 겹치지 않고 run 두 개가 따로 돈다. (Task 8 테스트)
4. 응답 기록도 체크포인트도 없는 중단 run에 resume 요청 → 409, 목록 행의 `resumable: false`. (Task 8 테스트)
5. 재생(replay) 중에 정지 요청 → 기록을 잃지 않고 틱 경계에서 중단, 다시 resume 가능. (Task 4 테스트)

---

## 파일 구조

| 파일 | 책임 |
|---|---|
| `src/conflict_sim/experiment.py` (수정) | 실행 옵션, 정지, 재생 resume 배선 |
| `src/conflict_sim/models.py`, `llm.py` (수정) | 무제한 토큰 상한 |
| `src/conflict_sim/tape.py` (신규) | LLM 응답 기록·재생 백엔드 래퍼 |
| `src/conflict_sim/loop.py`, `frames.py` (수정) | frame 대사에 발화 id·속마음, hello에 표시 이름·직책 |
| `src/conflict_sim/runs.py` (신규) | run 목록·사람 목록·시나리오 카탈로그 (pandas/streamlit 없이) |
| `src/conflict_sim/server.py` (신규) | HTTP API, 정적 파일, 설정 |
| `src/conflict_sim/live.py` (신규) | 라이브 run 프로세스 관리 |
| `viz/index.html` + `viz/src/menu.ts` (신규/교체) | 메인 화면과 모달 |
| `viz/view.html` (기존 index.html 이동) | 리플레이·라이브 뷰어 |
| `viz/src/prefs.ts`, `viz/src/i18n.ts` (신규) | 언어·테마 저장, 한/영 사전 |
| `viz/src/conversations.ts` (신규) | 대화 묶기, 예전 run 속마음 붙이기, 대화 탭 렌더 |

---

### Task 1: 실행 옵션 — 모델 지정, 무제한 상한, 틱 간격

**Files:**
- Modify: `src/conflict_sim/models.py:409` (`max_total_tokens`), `src/conflict_sim/llm.py:477,545,633`, `src/conflict_sim/experiment.py` (`run_scenario`, `main`)
- Test: `tests/test_company_runtime.py`

**Interfaces:**
- Produces: `run_scenario(..., model_decide: str | None = None, model_speak: str | None = None, model_embed: str | None = None, tick_delay: float | None = None)`; CLI `--model-decide/--model-speak/--model-embed`, `--max-total-tokens 0`(= 무제한), `--tick-delay SECONDS`. `Config.max_total_tokens: int | None` (None = 무제한, 기본 100_000 유지). `OpenAIBackend(max_total_tokens: int | None)`.

- [ ] **Step 1: 실패 테스트**

```python
def test_run_options_reach_the_config(tmp_path):
    out = tmp_path / "run"
    run_scenario("s0_smoke", out, model_decide="m-d", model_speak="m-s", model_embed="m-e",
                 max_total_tokens=0, tick_delay=0)
    cfg = json.loads((out / "resolved_config.json").read_text())
    assert (cfg["model_decide"], cfg["model_speak"], cfg["model_embed"]) == ("m-d", "m-s", "m-e")
    assert cfg["max_total_tokens"] is None

def test_openai_backend_without_a_cap_never_stops_on_budget():
    backend = OpenAIBackend(object(), max_total_tokens=None)
    backend.usage["decide"]["total_tokens"] = 10**12
    backend._check_budget()  # no LLMError
```

`_check_budget()`는 지금 `complete`/`embed` 안의 `if self._spent() >= self.max_total_tokens: raise LLMError(...)` 두 곳을 하나로 뽑은 메서드다(같은 메시지 유지).

- [ ] **Step 2: 실패 확인** — `.venv/bin/pytest tests/test_company_runtime.py -k "run_options or without_a_cap" -v` → FAIL.
- [ ] **Step 3: 구현** — `run_scenario`에서 `max_total_tokens == 0`이면 `None`으로 바꿔 config에 넣는다. 모델 인자는 주어진 것만 `cfg.model_copy(update=...)`. `tick_delay`는 Stream의 `delay`로 간다: 지정 없으면 지금처럼 `0`, CLI 기본은 `--live-port`가 있고 backend가 demo면 `1.0`, 아니면 `0`. `main()`에 플래그 추가.
- [ ] **Step 4: 통과 확인** — 같은 명령 → PASS, 전체 suite PASS(해시 불변).
- [ ] **Step 5: 커밋** — `feat(experiment): model, unlimited budget and tick delay options`

### Task 2: 정지 — SIGTERM이면 틱 경계에서 일시정지

**Files:**
- Modify: `src/conflict_sim/experiment.py`
- Create: `tests/run_helpers.py` — 이후 태스크가 같이 쓰는 테스트 도구: `tick_of(request) -> int | None`(기존 `Trips`의 틱 찾기를 옮김), `stop_when_tick(monkeypatch, stop, tick, base=DemoBackend)`(`experiment.DemoBackend`를 그 틱의 첫 호출에서 `stop.set()` 하는 하위 클래스로 바꿈), `restore_demo(monkeypatch)`, `rows(run_dir, name) -> list[dict]`, `frames(run_dir) -> list[dict]`(status 행 제외 frame/event).
- Test: `tests/test_company_runtime.py`

**Interfaces:**
- Produces: `class RunStopped(Exception)`; `run_scenario(..., stop: threading.Event | None = None)`. `main()`이 `signal.signal(SIGTERM, ...)`으로 이벤트를 세운다. 정지 시 `paused.json` = `{"status": "paused", "reason": "stopped", "tick": <다음에 돌 틱>, "checkpoint": ...}`, 스트림 마지막 status `paused`.

- [ ] **Step 1: 실패 테스트**

```python
def test_a_stop_pauses_before_the_next_tick(tmp_path, monkeypatch):
    stop = threading.Event()
    class StopsAt(DemoBackend):
        def complete(self, **request):
            if _tick(request) == 12:   # the existing Trips helper's tick lookup, factored out
                stop.set()
            return super().complete(**request)
    monkeypatch.setattr(experiment, "DemoBackend", StopsAt)
    paused = run_scenario("s0_baseline", tmp_path / "run", stop=stop)
    assert paused["run_status"] == "paused" and paused["reason"] == "stopped"
    assert json.loads((tmp_path / "run" / "paused.json").read_text())["tick"] == 13
    frames = [json.loads(l) for l in (tmp_path / "run" / "frames.jsonl").read_text().splitlines()]
    assert max(f["tick"] for f in frames if f["type"] == "frame") == 12
```

- [ ] **Step 2: 실패 확인** → FAIL (`stop` 인자 없음).
- [ ] **Step 3: 구현** — `loop.before_tick`을 감싸 `stop.is_set()`이면 `RunStopped`를 던진다(스트림의 `before_tick`보다 먼저). 기존 `except (LLMError, ValueError)` 경로에 `RunStopped`를 더하고 reason은 `"stopped"`.
- [ ] **Step 4: 통과 확인** → PASS.
- [ ] **Step 5: 커밋** — `feat(experiment): stop a run at a tick boundary on SIGTERM`

### Task 3: 응답 기록 (`Tape`, 기록 모드)

**Files:**
- Create: `src/conflict_sim/tape.py`
- Modify: `src/conflict_sim/experiment.py` (백엔드 조립: 가장 바깥에서 감싼다 — `retrieval_cached_backend` 바깥)
- Test: `tests/test_tape.py`

**Interfaces:**
- Produces:
  - `class Tape:` `__init__(self, inner: LanguageModel, path: Path, *, replay_until: int | None = None)`, `complete(**request) -> str`, `embed(texts: list[str]) -> list[list[float]]`, `tick: int` (기본 -1, `run_scenario`가 매 틱 시작에 `loop.tick_now`로 설정), `replaying: bool`, `close()`.
  - `truncate_tape(path: Path, *, keep_below_tick: int) -> None`.
  - `class ReplayMismatch(LLMError)`.
  - 파일 `tape.sqlite`: `completions(seq integer primary key, tick integer, key text, reply text)`, `embeddings(text text primary key, tick integer, vector blob)`. `key` = `sha256(json.dumps(request, sort_keys=True, default=str))` (schema는 이름으로 직렬화). 벡터는 **float64 바이트**(`np.asarray(v, dtype=np.float64).tobytes()`) — 비트 단위로 같아야 재생이 정확하다. spec 5.3의 "float32"는 이 결정으로 고친다.
  - 임베딩은 텍스트당 하나: 이미 기록된 텍스트는 기록된 벡터를 돌려준다(첫 기록 우선). 병렬로 같은 텍스트를 임베딩해도 재생 순서와 무관하게 같은 벡터가 된다. Demo는 결정적 해시라 동작 불변, OpenAI run은 같은 문장이 늘 같은 벡터가 된다(spec의 "임베딩 벡터 전부 기록" 결정에 따른 설계자 결정).
  - 쓰기마다 commit(프로세스가 죽어도 남게), 쓰기는 lock으로 직렬화.

- [ ] **Step 1: 실패 테스트**

```python
def test_tape_records_every_reply_and_vector_with_its_tick(tmp_path):
    tape = Tape(DemoBackend(), tmp_path / "tape.sqlite")
    tape.tick = 3
    reply = tape.complete(system="s", prompt="p", model="demo", temperature=0, json_mode=True)
    vectors = tape.embed(["a", "b"])
    tape.close()
    db = sqlite3.connect(tmp_path / "tape.sqlite")
    assert db.execute("select tick, reply from completions").fetchall() == [(3, reply)]
    assert [r[0] for r in db.execute("select text from embeddings order by text")] == ["a", "b"]

def test_the_same_text_embeds_to_its_first_vector(tmp_path):
    tape = Tape(Noisy(), tmp_path / "tape.sqlite")   # Noisy: random vector per call
    assert tape.embed(["a"]) == tape.embed(["a"])

def test_experiment_run_writes_a_tape(tmp_path):
    run_scenario("s0_smoke", tmp_path / "run")
    assert (tmp_path / "run" / "tape.sqlite").is_file()
```

`Noisy`는 `tests/test_tape.py` 안의 테스트용 백엔드다. `DemoBackend`를 상속하고, `embed`는 `random.Random(os.urandom(8))`로 만든 무작위 벡터, `complete`는 Demo 응답 JSON의 `urge`(0..1)와 `importance`(1..10) 값을 무작위로 바꾼다. Task 4가 같은 클래스를 쓴다.

- [ ] **Step 2: 실패 확인** → FAIL (모듈 없음).
- [ ] **Step 3: 구현** — 위 Interfaces대로. `run_scenario`는 `loop.before_tick` 래퍼에서 `tape.tick = loop.tick_now`를 설정하고 `finally`에서 `tape.close()`.
- [ ] **Step 4: 통과 확인** → PASS, 전체 suite PASS(해시 불변 확인).
- [ ] **Step 5: 커밋** — `feat(tape): record every completion and embedding of a run`

### Task 4: 기록 재생 resume

**Files:**
- Modify: `src/conflict_sim/tape.py`, `src/conflict_sim/experiment.py`
- Test: `tests/test_tape.py`

**Interfaces:**
- Consumes: Task 2 `stop`, Task 3 `Tape`, `truncate_tape`, `ReplayMismatch`.
- Produces: `run_scenario(resume=True)`가 run 폴더에 `tape.sqlite`가 있으면 재생 경로를 탄다:
  1. `cut = paused.json["tick"]`, `truncate_tape(tape, keep_below_tick=cut)`.
  2. 파생 파일 삭제: `events.jsonl`, `frames.jsonl`, `inspect.jsonl`, `memory.sqlite`(+`-wal`/`-shm`), `checkpoints/`, `corpus/`, `summary.json`, `paused.json`. 유지: `manifest.json`, `resolved_config.json`, `tape.sqlite`, `llm_audit.jsonl`, `retrieval_cache.sqlite`.
  3. config는 `Config.model_validate(resolved_config.json)`(+ 인자로 받은 `max_total_tokens`만 덮어씀). 틱 0부터 새로 돌린다(`loop.restore` 안 씀).
  4. `Tape(replay_until=cut)`: `tick < cut`이면 기록에서만 답한다(completion은 같은 key의 FIFO, 임베딩은 텍스트). 없으면 `ReplayMismatch("…")` → 일반 pause 경로(reason에 이유). `tick >= cut`이 되면 실제 backend로 넘어가 계속 기록한다.
  5. 재생 중에는 Stream 지연·일시정지를 건너뛰고(`stream.before_tick` 호출 안 함), 시작 시 `stream.status("replaying", str(cut))`, `cut`에 닿으면 `stream.status("running")`.
  - 기록이 없는 예전 run은 지금 체크포인트 경로 그대로.

- [ ] **Step 1: 실패 테스트**

```python
@pytest.mark.parametrize("scenario,stop_at", [("p0_documents_ko", 9), ("p0_documents_ko", 40)])
def test_resume_from_any_tick_replays_to_the_same_run(tmp_path, monkeypatch, scenario, stop_at):
    # stop_at 9: a talk is open; 40: day 2, after a meeting day (pick ticks that hold for the scenario)
    straight = tmp_path / "a"; run_scenario(scenario, straight)
    stopped = tmp_path / "b"; stop = threading.Event()
    stop_when_tick(monkeypatch, stop, stop_at)          # helper as in Task 2
    run_scenario(scenario, stopped, stop=stop)
    restore_demo(monkeypatch)
    assert run_scenario(scenario, stopped, resume=True)["run_status"] == "completed"
    assert rows(straight, "events.jsonl") == rows(stopped, "events.jsonl")
    assert frames(straight) == frames(stopped)          # frames minus status rows

def test_replay_reuses_recorded_randomness_up_to_the_cut(tmp_path, monkeypatch):
    monkeypatch.setattr(experiment, "DemoBackend", Noisy)
    run = tmp_path / "r"; stop = threading.Event(); stop_when_tick(monkeypatch, stop, 20, base=Noisy)
    run_scenario("p0_documents_ko", run, stop=stop)
    before = [e for e in rows(run, "events.jsonl") if e["tick"] < 20]
    run_scenario("p0_documents_ko", run, resume=True)
    assert [e for e in rows(run, "events.jsonl") if e["tick"] < 20] == before

def test_a_mid_tick_error_drops_that_tick_and_resumes(tmp_path, monkeypatch):
    # first call at tick 15 raises ValueError("Invalid action from X") once
    ...
    assert json.loads((run / "paused.json").read_text())["tick"] == 15
    assert run_scenario("s0_baseline", run, resume=True)["run_status"] == "completed"

def test_a_tape_that_does_not_match_pauses_instead_of_calling_the_api(tmp_path, monkeypatch):
    # record a run stopped at 20, then change one completion row's key in tape.sqlite
    ...
    resumed = run_scenario("s0_baseline", run, resume=True)
    assert resumed["run_status"] == "paused" and "replay" in resumed["reason"].lower()

def test_a_stop_during_replay_keeps_the_tape(tmp_path, monkeypatch):   # Review Focus 5
    # stopped at 30; resume with stop set when tick 10 starts (still replaying)
    ...
    assert json.loads((run / "paused.json").read_text())["tick"] == 11
    assert _completion_rows(run, below=30) == rows_before   # tape rows below 30 untouched
```

빈 `...`는 `tests/run_helpers.py`의 도구(`stop_when_tick`, `rows`)로 채운다. `p0_documents_ko`의 대화가 열린 틱과 회의가 있는 날은 구현자가 straight run의 `events.jsonl`에서 골라 상수로 박는다(회의가 있는 날이 꼭 포함돼야 함 — spec 5.3).

- [ ] **Step 2: 실패 확인** → FAIL.
- [ ] **Step 3: 구현** — Interfaces대로.
- [ ] **Step 4: 통과 확인** → 5개 PASS, 기존 `test_experiment_out_of_budget_pauses_at_its_checkpoint_and_resumes`는 이제 재생 경로를 타므로 기대값(`ticks == list(range(68))`, `hello` 1개)이 그대로 맞는지 확인. 전체 suite PASS.
- [ ] **Step 5: 커밋** — `feat(tape): resume a run at any tick by replaying its recorded replies`

### Task 5: frames — 대사의 발화 id·속마음, hello의 표시 이름·직책

**Files:**
- Modify: `src/conflict_sim/loop.py:284-292` (`viewer_snapshot` lines), `src/conflict_sim/frames.py` (`hello`, `capture`), `viz/src/messages.d.ts`
- Test: `tests/test_stream.py` 또는 `tests/test_company_runtime.py`

**Interfaces:**
- Produces: frame `lines[]` = `{speaker, text, session, id, thought?}`. `thought`는 (1) 이 틱의 `decision` 이벤트 중 `posted`이고 `utterance_id == id`인 것의 `reflection`, 없으면 (2) 같은 틱에 같은 화자가 `talk`/`message` action을 했고 그 대사가 그 세션의 첫 대사면 action의 `reflection`. 공백 정리 후 대사와 같으면 넣지 않는다. hello `agents[]`에 `display_name`, `title` 추가(`name`은 그대로 id — 기존 화면 불변).

- [ ] **Step 1: 실패 테스트**

```python
def test_frame_lines_carry_the_thought_behind_them(tmp_path):
    run_scenario("p0_documents_ko", tmp_path / "r", max_days=1)
    lines = [l for f in frames(tmp_path / "r") for l in f.get("lines", [])]
    talk = [l for l in lines if l["session"].startswith("talk:")]
    assert talk and all("id" in l for l in lines)
    assert any(l.get("thought") for l in talk)
    assert all(l.get("thought") != l["text"] for l in lines)
    assert not any(l.get("thought") for l in lines if l["session"].startswith("meeting:"))
    hello = rows(tmp_path / "r", "frames.jsonl")[0]
    assert {"display_name", "title"} <= set(hello["agents"][0])
```

- [ ] **Step 2–4:** 실패 확인 → 구현 → PASS, 해시 불변.
- [ ] **Step 5: 커밋** — `feat(frames): send each line's id and thought, and people's names`

### Task 6: `runs.py` — 목록·사람·시나리오 카탈로그

**Files:**
- Create: `src/conflict_sim/runs.py`
- Modify: `src/conflict_sim/dashboard.py` (`discover_company_runs`를 `runs.py`에서 import해 그대로 노출 — Streamlit은 그 외 변경 없음)
- Test: `tests/test_runs.py`

**Interfaces:**
- Produces:
  - `discover_company_runs(root: Path) -> tuple[list[dict], list[str]]` (지금 dict 필드 그대로) + 필드 `paused_tick: int | None`, `resumable: bool`(= `tape.sqlite` 있음 또는 `checkpoints/day-*.json` 있음), `days: float`(= `(ticks+1) / day_span`, `resolved_config.json`의 `environment.day_span`).
  - `people(run_dir: Path) -> list[dict]` → `[{"id", "name", "title"}]` (`resolved_config.json` agents의 `name`, `display_name`, `title`).
  - `scenario_catalog(runs_root: Path) -> list[dict]` → `[{"name", "research_question", "extends", "max_days", "estimated_calls", "tokens_per_day"}]`. 순서: `r10_midweek`, `r10_enterprise_weekly`, `r10_human`, `r10_documents_ko`, 그 뒤 `experiment.SCENARIOS` 순서. `estimated_calls` = `estimate_calls(build_company_config(name))["upper_bound_completion_calls"]`. `tokens_per_day` = 같은 시나리오의 완료된 OpenAI run들의 `총 토큰 / days` 중앙값, 없으면 `None`.

- [ ] **Step 1: 실패 테스트** — `tmp_path`에 `run_scenario("s0_smoke", ...)` 하나를 만든 뒤 `discover_company_runs`가 `resumable is False`, `days == 1.0` 근처를 돌려주는지; 그 run을 Task 2 방식으로 정지시킨 사본은 `resumable is True`; `people()`이 20명과 비지 않은 `name`을 돌려주는지; `scenario_catalog(tmp_path)[0]["name"] == "r10_midweek"`이고 모든 항목이 `estimated_calls > 0`인지; `import conflict_sim.runs`가 `pandas`/`streamlit`을 import하지 않는지(`sys.modules` 확인).
- [ ] **Step 2–4:** 실패 → 구현 → PASS. `tests/test_dashboard.py` PASS 유지.
- [ ] **Step 5: 커밋** — `feat(runs): run, people and scenario listings without the dashboard`

### Task 7: `conflict-server` — 읽기 API, 파일, 설정, 정적 파일

**Files:**
- Create: `src/conflict_sim/server.py`
- Modify: `pyproject.toml` (`conflict-server = "conflict_sim.server:main"`), `.gitignore` (`.conflict-sim/`)
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: Task 6.
- Produces: `make_server(*, runs_root: Path, settings_path: Path, static_root: Path | None, port: int = 0) -> ThreadingHTTPServer`, `main()` (`--port` 기본 `8780`, `--runs` 기본 `runs`, 정적 파일 `viz/dist`가 있으면 제공).
  - `GET /api/runs` → `{"runs": [...], "broken": [...]}` (Task 6 + Task 8의 `live` 필드)
  - `GET /api/runs/<path>/people` → Task 6 `people`
  - `GET /runs/<path>/<name>.jsonl` → text/plain. 지금 `viz/vite.config.ts`의 규칙 그대로: `runs_root` 밖이면 404, `.jsonl` 아니면 404. `GET /runs` → frames가 있는 run 경로 목록(JSON, 기존 vite와 같음).
  - `GET /api/scenarios` → Task 6 `scenario_catalog`
  - `GET /api/settings` → `{"provider": "openai"|"demo", "model_decide", "model_speak", "model_embed", "max_total_tokens": int|None, "openai_key": bool}`. 기본값: provider `openai`, 모델 `gpt-6-luna`/`gpt-6-luna`/`text-embedding-3-small`, 상한 `2_000_000`. `openai_key` = `.env`에 `OPENAI_API_KEY`가 있는지(값은 읽기만, 응답에 없음).
  - `PUT /api/settings` → 같은 필드(키 제외) 검증 후 `.conflict-sim/settings.json`에 저장. provider는 `openai`/`demo`만 허용(나머지 400).
  - 그 외 경로: `static_root`의 파일, 없으면 404.

- [ ] **Step 1: 실패 테스트** — `make_server(port=0)`를 스레드로 띄우고 `urllib.request`로:

```python
def test_run_files_cannot_escape_the_runs_folder(server):          # Review Focus 2
    for path in ["/runs/../pyproject.toml", "/runs/%2e%2e/.env", "/runs/x/manifest.json"]:
        assert _status(server, path) == 404

def test_settings_round_trip_and_never_show_the_key(server, tmp_path):
    _put(server, "/api/settings", {"provider": "demo", "max_total_tokens": None, ...})
    got = _get(server, "/api/settings")
    assert got["provider"] == "demo" and got["max_total_tokens"] is None
    assert "sk-" not in json.dumps(got)
    assert _put_status(server, "/api/settings", {"provider": "anthropic"}) == 400
```

  그리고 `/api/runs`, `/api/runs/<p>/people`, `/api/scenarios`, `/runs/<p>/frames.jsonl`이 Task 6 값과 같은지.
- [ ] **Step 2–4:** 실패 → 구현 → PASS.
- [ ] **Step 5: 커밋** — `feat(server): conflict-server with run, scenario and settings APIs`

### Task 8: 라이브 run 관리 — 시작·목록·정지·resume

**Files:**
- Create: `src/conflict_sim/live.py`
- Modify: `src/conflict_sim/server.py`
- Test: `tests/test_live.py`

**Interfaces:**
- Consumes: Task 1(옵션), 2(SIGTERM), 4(resume), 6, 7.
- Produces:
  - `start(runs_root: Path, *, scenario: str, days: int, max_total_tokens: int | None, backend: str, models: dict, paid_confirmed: bool) -> dict` → `{"id", "run", "port"}`. 폴더 `runs/ui-<YYYYMMDD-HHMMSS>-<scenario>[-n]/`(겹치면 `-2`, `-3`), CLI `conflict-company-experiment <scenario> --backend <b> --pilot --days N --max-total-tokens <N|0> --live-port 0 --output-root <폴더> [--model-* ...]`. `start_new_session=True`로 띄우고 stdout을 `<폴더>/live.log`로. `Viewer WebSocket: ws://127.0.0.1:<port>` 줄을 기다려(최대 30초) 포트를 얻는다. run 폴더(`<폴더>/<scenario>/replicate-1`)에 `live.json` = `{"id", "pid", "port", "started", "scenario", "days", "backend"}`.
  - backend가 `openai`이고 `paid_confirmed`가 아니면 `PermissionError`(서버 403). 확인됐으면 자식 env에만 `ALLOW_PAID_API_EXPERIMENTS=1`.
  - `active(runs_root) -> list[dict]` → `live.json`이 있고 pid가 살아 있는 run: `{"id", "run", "port", "scenario", "tick", "day", "status"}`. `tick`/`day`는 `frames.jsonl` 마지막 frame. pid가 죽었으면 목록에서 빠지고 `discover_company_runs`의 상태(`paused`/`failed`/`completed`)를 따른다.
  - `stop(runs_root, id) -> None` → SIGTERM.
  - `resume(runs_root, run: str, *, max_total_tokens: int | None, paid_confirmed: bool) -> dict` → `start`와 같은 반환, CLI에 `--resume`, 같은 output root. `resumable`이 아니면 `ValueError`(서버 409). backend는 `resolved_config.json`/`manifest.json`의 것.
  - API: `POST /api/live`(본문 = `start` 인자, `models`는 설정에서), `GET /api/live`, `POST /api/live/<id>/stop`, `POST /api/runs/<path>/resume`. `GET /api/runs`의 각 행에 `live: {id, port} | null`.
  - experiment CLI의 `--resume`이 `--max-total-tokens`를 함께 받도록(이미 받음) 그리고 resume 시 `--days`를 무시하도록(재생 경로는 resolved_config를 씀) 확인.

- [ ] **Step 1: 실패 테스트** (Demo만, `--tick-delay 0.05`):

```python
def test_start_list_stop_and_resume_a_demo_run(tmp_path):
    started = live.start(tmp_path, scenario="s0_smoke", days=1, max_total_tokens=None,
                         backend="demo", models={}, paid_confirmed=False)
    assert [r["id"] for r in live.active(tmp_path)] == [started["id"]]
    live.stop(tmp_path, started["id"]); _wait_exit(started)
    row = _row(tmp_path, started["run"])
    assert row["status"] == "paused" and row["resumable"]
    again = live.resume(tmp_path, started["run"], max_total_tokens=None, paid_confirmed=False)
    _wait_exit(again)
    assert _row(tmp_path, started["run"])["status"] == "completed"

def test_paid_runs_need_confirmation(tmp_path):
    with pytest.raises(PermissionError):
        live.start(tmp_path, scenario="s0_smoke", days=1, max_total_tokens=None,
                   backend="openai", models={}, paid_confirmed=False)

def test_a_dead_pid_is_not_live(tmp_path):                          # Review Focus 1
    # write live.json with a pid that has exited; active() is empty, the row is not "running"

def test_two_starts_in_one_second_get_two_folders(tmp_path):        # Review Focus 3
    # two start() calls back to back → different "run" paths, both in active()

def test_resume_without_tape_or_checkpoint_is_refused(tmp_path):    # Review Focus 4
    # a paused run folder with neither tape.sqlite nor checkpoints → ValueError; API → 409
```

- [ ] **Step 2–4:** 실패 → 구현 → PASS.
- [ ] **Step 5: 커밋** — `feat(live): start, list, stop and resume runs from the server`

### Task 9: viz 페이지 분리, 개발 프록시, 언어·테마

**Files:**
- Move: `viz/index.html` → `viz/view.html` (내용 그대로, `main.ts` 그대로)
- Create: `viz/index.html` (메뉴 셸), `viz/src/menu.ts` (이번 태스크에서는 셸만), `viz/src/prefs.ts`, `viz/src/i18n.ts`
- Modify: `viz/vite.config.ts` (multi-page `build.rollupOptions.input = {index, view}`; `/runs` 미들웨어 삭제; `server.proxy`: `/api`, `/runs` → `http://127.0.0.1:8780`), `viz/src/style.css` (다크 토큰), `viz/src/main.ts`/`hud.ts`(고정 문구를 `t()`로), `viz/README.md`(실행 방법)

**Interfaces:**
- Produces:
  - `prefs.ts`: `type Lang = 'ko' | 'en'`, `type Theme = 'light' | 'dark' | 'system'`, `getLang(): Lang`(기본 `'ko'`), `setLang(l)`, `getTheme(): Theme`(기본 `'system'`), `setTheme(t)`, `applyTheme()` — `document.documentElement.dataset.theme`를 `light`/`dark`로, `system`이면 `prefers-color-scheme` 변화도 따라감. localStorage 접근은 try/catch.
  - `i18n.ts`: `t(key: string, vars?: Record<string, string | number>): string`, 사전 `{ko: {...}, en: {...}}`. 키는 기존 HUD 고정 문구(Tasks, Relations, Events, Pause, Step, speed, Live, connecting…)와 새 화면 문구 전부.
  - `style.css`: `:root[data-theme="dark"]`에 같은 토큰 이름의 다크 값(목업 `settings.html`의 `body.dark` 값을 출발점으로). 맵 캔버스는 건드리지 않는다.
  - `view.html`의 옛 진입 호환: `index.html`이 `?replay=`·`?ws=`·`?live=` 파라미터를 받으면 `location.replace('/view.html' + location.search)`.
  - 라이브 기본값 변경: `view.html`에 `?ws`/`?live`/`?replay` 아무것도 없으면 `/`로 보낸다(기존처럼 8765에 붙지 않음).

- [ ] **Step 1:** 위 구현.
- [ ] **Step 2: 확인** — `npm run check` PASS. `conflict-server` + `npm run dev`로 `http://localhost:5173/view.html?replay=<기존 run>`이 지금처럼 리플레이되는지, `/?replay=<run>`이 view로 넘어가는지, 테마를 `dark`로 바꾸면 패널 색이 바뀌고 새로고침 후 유지되는지, 언어를 `en`으로 바꾸면 HUD 탭 이름이 영어인지 브라우저에서 확인.
- [ ] **Step 3: 커밋** — `feat(viz): split menu and viewer pages, proxy to conflict-server, language and theme`

### Task 10: 메인 화면 + 환경 설정 모달

**Files:**
- Modify: `viz/index.html`, `viz/src/menu.ts`, `viz/src/style.css`(메뉴 전용 블록)

**Interfaces:**
- Consumes: Task 7 `/api/settings`, Task 8 `/api/live`(GET), Task 9 prefs/i18n.
- Produces: `menu.ts` 안에 `openSettings()`, `openReplayPicker()`(Task 11), `openLiveSetup()`(Task 12) — 각 모달은 하나의 `<dialog>` 패턴(Esc·바깥 클릭·× 로 닫힘).
  - 메인: 목업 `main-menu.html`(세로 3버튼 + 작은 "⚙ 환경 설정"). 캐릭터는 `public/assets/characters-v4/agent-<n>.atlas.json`의 `idle-0` 프레임을 CSS로 잘라 6명. 라이브 카드의 부가 줄: 진행 중 run이 있으면 `진행 중 N개 · <시나리오> <일차>일차 HH:MM`(누르면 1개면 `view.html?live=<id>`, 여러 개면 목록), 없으면 최근 run 정보. 리플레이 카드: `저장된 run N개 · 마지막 MM/DD`. 시나리오 생성 카드: "준비 중" 배지, 눌러도 아무 일 없음.
  - 설정 모달: 목업 `settings.html`. 언어·테마는 즉시 적용(prefs), provider/모델/기본 상한은 "저장" 때 `PUT /api/settings`. Anthropic·Google·로컬은 비활성. API 키 칸은 `openai_key`에 따라 "서버 .env에서 읽음" / "서버 .env에 키가 없어요". 기본 상한 칸도 "상한/무제한" 전환.
- [ ] **Step 1:** 구현.
- [ ] **Step 2: 확인** — `npm run check`; 브라우저에서 메뉴 렌더, 설정 저장 → 새로고침 후 유지, 다크/영어 전환, 폭 375px에서 가로 스크롤 없음.
- [ ] **Step 3: 커밋** — `feat(viz): main menu and settings`

### Task 11: 리플레이 run 목록 + 이어서 실행

**Files:**
- Modify: `viz/src/menu.ts`, `viz/src/style.css`

**Interfaces:**
- Consumes: `GET /api/runs`, `POST /api/runs/<path>/resume`, Task 12의 `confirmPaid()`(같은 파일, 먼저 만들어도 됨).
- Produces: 목업 `replay-picker.html`. 검색(run 이름·시나리오), 시나리오 칩(전체 + 실제로 있는 시나리오), 표 열 = RUN(이름+시나리오) · 상태(완료/중단/진행 중) · 길이(`N일 · M틱`) · 모델 · 토큰 · 날짜, 최근순. "리플레이 열기" → `view.html?replay=<run>`. 상태가 중단이고 `resumable`이면 행에 "이어서 실행": 작은 창(토큰 상한 + 상한/무제한, 기본값 = 설정의 기본 상한, OpenAI면 `confirmPaid`) → resume → `view.html?live=<id>`. 기록 없이 체크포인트만 있는 run이면 창에 "하루 끝 저장 지점에서 이어 가며, 일부 상태가 원래 run과 다를 수 있어요" 문구.
- [ ] **Step 1:** 구현.
- [ ] **Step 2: 확인** — 브라우저: 목록·검색·칩·열기; Task 8 테스트처럼 Demo run을 정지시킨 뒤 "이어서 실행"이 라이브로 열리는지.
- [ ] **Step 3: 커밋** — `feat(viz): replay picker with resume`

### Task 12: 라이브 실행 설정 + 라이브 화면 연결

**Files:**
- Modify: `viz/src/menu.ts`, `viz/src/main.ts`, `viz/view.html`, `viz/src/hud.ts`, `viz/src/style.css`

**Interfaces:**
- Consumes: `GET /api/scenarios`, `GET /api/settings`, `POST /api/live`, `GET /api/live`, `POST /api/live/<id>/stop`.
- Produces:
  - 설정 모달: 목업 `live-setup.html`. 이름 검색(이름만), 시나리오 카드(이름·연구 질문·`← extends`), 일수 −/+(1..10, 기본 = `max_days` 없으면 1), 토큰 상한 + 상한/무제한(기본 = 설정 값), 예상 사용량(`tokens_per_day`가 있으면 `약 X.XM 토큰 · 호출 약 N회` = `tokens_per_day×일수`, `estimated_calls×일수`; 없으면 호출 수만), provider 줄 + "환경 설정에서 변경".
  - `confirmPaid(estimate: string, unlimited: boolean): Promise<boolean>` — OpenAI일 때만 뜨는 확인 창. 무제한이면 경고 문구 추가. Demo면 바로 `true`.
  - 시작 → `POST /api/live` → `view.html?live=<id>`.
  - `main.ts`: `?live=<id>`면 `GET /api/live`에서 포트를 찾아 기존 라이브 경로로 `ws://127.0.0.1:<port>`에 붙는다. 못 찾으면(이미 끝남) `view.html?replay=<run>`으로.
  - 상단 바: "← 메인"(모든 뷰어), 라이브(`?live`)에만 "정지" — 확인 창 후 `POST /api/live/<id>/stop`. status `replaying`이면 맵 위에 "기록 재생 중 · t / <cut>" 표시, `running`이 오면 숨김.
- [ ] **Step 1:** 구현.
- [ ] **Step 2: 확인** — 브라우저: Demo `r10_midweek` 1일 시작 → 틱 진행 → 탭 닫기 → `/`에 진행 중 표시 → 다시 붙기 → 정지 → 목록에서 중단 → 이어서 실행 시 "기록 재생 중" 뒤 진행. OpenAI 선택 시 확인 창 없이는 시작 안 됨(서버도 403).
- [ ] **Step 3: 커밋** — `feat(viz): live setup, attach to server runs, stop`

### Task 13: 대화 탭

**Files:**
- Create: `viz/src/conversations.ts`
- Modify: `viz/src/world.ts`(lines에 `id`, `thought`), `viz/src/hud.ts`(탭 추가), `viz/view.html`(탭 버튼·패널), `viz/src/main.ts`(리플레이 시 `/api/runs/<run>/people`), `viz/src/style.css`

**Interfaces:**
- Consumes: Task 5 frame 형식, `world.engineEvents`(리플레이의 `events.jsonl`), Task 7 `people`.
- Produces:
  - `conversations(lines: Line[], sessions: Map<string, SessionInfo>): Conversation[]` — 세션별 묶음 `{id, kind: 'talk'|'meeting'|'message', place, participants, first, last, lines}`, 최근 시작순. DM은 frames `sessions`에 없을 수 있으니 id `dm:A:B:day`에서 참여자를 만든다.
  - `attachThoughts(lines: Line[], events: EngineEvent[]): void` — `thought`가 없는 대사에만, Task 5와 같은 규칙으로 `decision`(utterance_id)·`action`(`talk:{tick}:{actor}` 또는 같은 틱·같은 화자의 첫 대사)에서 붙인다. 대사와 같은 속마음은 버린다. 회의는 붙이지 않는다.
  - 탭: 목업 `conversation.html`. "대화" 탭(기존 Tasks·Relations·Events 옆), 왼쪽 목록, 오른쪽 스레드, 대사마다 "💭 속마음" `<details>`, 위쪽 "속마음 모두 펼치기", 회의 대사 아래 "회의 발언은 속마음 기록이 없어요". 이름·직책: 라이브는 hello `display_name`/`title`, 리플레이는 hello에 없으면 `people` API, 그래도 없으면 id. 라이브에서는 새 대사가 열린 스레드에 바로 붙는다.
- [ ] **Step 1:** 구현.
- [ ] **Step 2: 확인** — `npm run check`; 브라우저: 예전 run(`runs/c16-real-r10-midweek-v3-stale/...`) 리플레이에서 대화 목록·속마음 펼침(1:1 대화는 대부분 속마음 있음, 스탠드업 회의는 없음 문구), Demo 라이브에서 대사가 실시간으로 붙는지.
- [ ] **Step 3: 커밋** — `feat(viz): conversation tab with inner thoughts`

### Task 14: 마무리

**Files:**
- Modify: `README.md`(실행 방법: `conflict-server`, `npm run dev`, 빌드 후 단일 서버), `docs/superpowers/specs/2026-11-03-viz-main-menu-design.md`(벡터 float64로 정정)
- [ ] **Step 1:** 문서 수정.
- [ ] **Step 2: 확인** — `npm run build` 후 `conflict-server`만으로 spec 6절 성공 기준 1–9를 Demo로 처음부터 끝까지 확인. 전체 pytest·ruff·`npm run check` PASS.
- [ ] **Step 3: 커밋** — `docs: run the viewer through conflict-server`
