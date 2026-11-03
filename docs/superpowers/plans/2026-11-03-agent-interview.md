# 사후 에이전트 인터뷰 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 뷰어에서 아무 시점의 에이전트 한 명에게 그 시점까지의 기억만으로 답하는 채팅 인터뷰를 하고, 대화를 run 폴더에 저장한다.

**Architecture:** `interview.py`가 run 폴더 파일(기억 DB, inspect, frames, events, resolved_config)로 시점 t의 에이전트를 다시 만들고, 엔진의 `MemoryStore.retrieve`로 기억을 고른 뒤 LLM에 한 번 묻는다. conflict-server가 인터뷰 API와 저장을 맡고, 뷰어의 inspect 패널에서 채팅 패널을 연다.

**Tech Stack:** Python 3.11 (numpy, sqlite3, pydantic), pytest, ruff; Vite + TypeScript.

**Spec:** `docs/superpowers/specs/2026-11-03-agent-interview-design.md` (목업 `docs/superpowers/specs/2026-11-03-agent-interview/interview.html`).

## Global Constraints

- 새 Python 의존성 없음. 서버는 기존 `server.py` 규칙(로컬 Host/Origin, JSON 본문, 오류는 HTTPError) 그대로.
- 인터뷰는 run 폴더에서 `interviews/` 말고는 아무 파일도 쓰지 않는다. 기억 DB는 읽기 전용으로 연다.
- 테스트는 Demo만. 유료 호출 없음.
- 데모 동작 해시 테스트 불변.
- 커밋에 AI attribution 없음.
- 매 태스크 끝: `.venv/bin/pytest -q`, `.venv/bin/ruff check src tests`, viz를 건드렸으면 `cd viz && npm run check`.

## Review Focus

1. 기억 DB의 벡터 차원과 질문 임베딩 차원이 다름(OpenAI run을 Demo 서버로) → 실패하지 않고 관련도 없이 고름. (Task 1 테스트)
2. t가 run의 첫 틱 이전(-1, 0)이거나 마지막 틱 뒤 → 그때까지 있는 것만으로 답함, 오류 아님. (Task 1 테스트)
3. 질문이 비었거나 매우 김 → 400 / 잘라서 보냄. (Task 3 테스트)
4. 저장된 인터뷰의 run이 이후 다시 만들어짐(세그먼트 수 증가) → `stale: true`로 보임. (Task 2 테스트)
5. 존재하지 않는 에이전트 id·인터뷰 id·경로 탈출 → 404. (Task 3 테스트)

---

### Task 1: 시점 t의 에이전트 다시 만들기와 기억 고르기

**Files:**
- Create: `src/conflict_sim/interview.py`
- Test: `tests/test_interview.py`

**Interfaces:**
- Produces:
  - `@dataclass class Moment: agent: str; tick: int; name: str; title: str | None; persona: str; language: str; stress: float; mood: float; relationships: list[dict]; reflections: list[str]; place: str | None; action: str | None; plan: list[str]; memory: MemoryStore; clock: str` (`clock` = "N일차 HH:MM", 한국어 시나리오 기준, `ticks_per_day`·`day_span` 사용).
  - `moment(run_dir: Path, agent: str, tick: int) -> Moment` — `Config.model_validate(resolved_config.json)`; `human.Directory(cfg)` + `human.persona_card(d, agent)`; `storage.read_memory(run_dir)`에서 그 에이전트 기록 중 `created_tick <= tick`; `last_access` = `retrievals` 표에서 `tick <= t`인 행의 ids 마지막 tick, 없으면 `created_tick`; inspect/frames/events는 `tick <= t` 마지막 줄. 기억 DB는 `sqlite3.connect(f"file:{path}?mode=ro", uri=True)`. 에이전트가 없으면 `KeyError`, 설정 검증 실패는 `ValueError("run config cannot be read: …")`.
  - `run_embedder(run_dir: Path, env_file: Path) -> Callable[[list[str]], list[list[float]]] | None` — `resolved_config.json`의 backend가 demo면 `DemoBackend().embed`, openai면 `.env`에 키가 있을 때 `OpenAIBackend(create_openai_client(env_file), model_embed=cfg.model_embed, max_total_tokens=None).embed`, 아니면 `None`.
  - `recall(m: Moment, question: str, embed: Callable | None, k: int = 10) -> list[MemoryRecord]` — 질문 벡터 차원이 기억 벡터 차원과 다르거나 `embed`가 None이면 `vector=None`으로 `m.memory.retrieve(question, None, m.tick, m.mood, k)`.

- [ ] **Step 1: 실패 테스트** — 모듈 픽스처로 `run_scenario("p0_documents_ko", tmp/"r", max_days=1)` 한 번.

```python
def test_a_moment_knows_only_what_happened_by_then(run):
    early, late = moment(run, "HDS-001", 5), moment(run, "HDS-001", 30)
    assert all(r.created_tick <= 5 for r in early.memory.records)
    assert len(early.memory.records) < len(late.memory.records)
    assert early.name and early.persona and early.clock == "1일차 10:15"

def test_recall_never_reaches_past_the_moment(run):
    m = moment(run, "HDS-001", 12)
    got = recall(m, "왜 쉬었어요?", run_embedder(run, run / "no.env"))
    assert got and all(r.created_tick <= 12 for r in got)

def test_vectors_of_another_size_fall_back_to_recency(run):      # Review Focus 1
    m = moment(run, "HDS-001", 12)
    assert recall(m, "q", lambda texts: [[0.1] * 1536 for _ in texts])  # no exception

def test_moments_before_and_after_the_run_are_empty_or_full(run):  # Review Focus 2
    assert moment(run, "HDS-001", -1).memory.records == []
    assert len(moment(run, "HDS-001", 10_000).memory.records) == len(moment(run, "HDS-001", 33).memory.records)

def test_an_unknown_agent_is_a_key_error(run):
    with pytest.raises(KeyError):
        moment(run, "NOBODY", 3)
```

  `clock` 기대값은 구현자가 픽스처 run의 `ticks_per_day`로 확인해 박는다(09:00 + 15분 × (t % ticks_per_day)).
- [ ] **Step 2–4:** 실패 확인 → 구현 → PASS.
- [ ] **Step 5: 커밋** — `feat(interview): rebuild an agent at any tick from its run files`

### Task 2: 답하기와 저장

**Files:**
- Modify: `src/conflict_sim/interview.py`
- Test: `tests/test_interview.py`

**Interfaces:**
- Consumes: Task 1.
- Produces:
  - `INSTRUCTIONS_KO`, `INSTRUCTIONS_EN` — 시스템 지시: "너는 {name}이다. 지금은 {clock}이다. 너는 이 시점까지의 일만 안다. 1인칭으로, 네 말투로 짧게 답하라. 기억에 없는 것은 모른다고 하라. 이것은 연구용 인터뷰이며 네 행동을 바꾸지 않는다."
  - `prompt(m: Moment, memories: list[MemoryRecord], turns: list[dict], question: str) -> tuple[str, str]` → (system, prompt). system = 지시 + persona. prompt = 지금 상태(장소·하던 일·스트레스·기분·오늘 계획·최근 회고·관계) + 기억 목록(시각과 원문) + 앞선 문답(최근 8개) + 질문.
  - `class DemoInterviewer: complete(**request) -> str` — 고른 기억 중 앞의 두 개를 인용해 "제가 기억하기로는 …" 형식으로 답(결정적).
  - `start(run_dir: Path, agent: str, tick: int, provider: str, model: str) -> dict` — `interviews/<YYYYMMDD-HHMMSS>-<agent>-t<tick>[-n].json` = `{id, agent, tick, clock, provider, model, started, segments, turns: []}`; `segments` = `len(manifest["token_usage_segments"])`(없으면 0). 돌려줄 때 `summary` = `{name, title, stress, mood, clock}` 포함.
  - `ask(run_dir: Path, interview_id: str, question: str, llm, model: str, embed) -> dict` — 질문 공백 제거 후 비면 `ValueError`, 2,000자 초과면 자름. Task 1 `moment`/`recall` → `prompt` → `llm.complete(system=…, prompt=…, model=model, temperature=0.7, json_mode=False)` → 턴 `{q, a, at, retrieved: [{id, tick, text}]}` 추가 저장, 턴 반환.
  - `load(run_dir, interview_id) -> dict`(+ `stale` = 지금 세그먼트 수 ≠ 저장된 것), `listing(run_dir, agent: str | None) -> list[dict]`(`{id, agent, tick, clock, questions, started, stale}`, 최근 것 먼저). 인터뷰 id는 `^[\w.-]+$`만 허용(아니면 `KeyError`).

- [ ] **Step 1: 실패 테스트**

```python
def test_an_interview_is_saved_and_leaves_the_run_alone(run):
    before = {p: p.read_bytes() for p in run.rglob("*") if p.is_file()}
    iv = start(run, "HDS-001", 12, "demo", "demo")
    turn = ask(run, iv["id"], "지금 뭐 하고 있어요?", DemoInterviewer(), "demo", run_embedder(run, run / "no.env"))
    assert turn["a"] and all(r["tick"] <= 12 for r in turn["retrieved"])
    after = {p: p.read_bytes() for p in run.rglob("*") if p.is_file() and "interviews" not in p.parts}
    assert after == before
    assert load(run, iv["id"])["turns"][0]["q"] == "지금 뭐 하고 있어요?"
    assert listing(run, "HDS-001")[0]["questions"] == 1

def test_an_empty_question_is_refused(run):
    iv = start(run, "HDS-001", 3, "demo", "demo")
    with pytest.raises(ValueError):
        ask(run, iv["id"], "   ", DemoInterviewer(), "demo", None)

def test_a_rebuilt_run_marks_its_interviews_stale(run):          # Review Focus 4
    iv = start(run, "HDS-001", 3, "demo", "demo")
    manifest = json.loads((run / "manifest.json").read_text())
    (run / "manifest.json").write_text(json.dumps(manifest | {"token_usage_segments": manifest.get("token_usage_segments", []) + [None]}))
    assert load(run, iv["id"])["stale"] is True
```

  (마지막 테스트는 픽스처를 바꾸므로 `tmp_path` 사본 run에서 한다.)
- [ ] **Step 2–4:** 실패 확인 → 구현 → PASS.
- [ ] **Step 5: 커밋** — `feat(interview): answer from the moment's memories and keep the conversation`

### Task 3: 서버 API

**Files:**
- Modify: `src/conflict_sim/server.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: Task 1–2, 기존 `Server.run_dir`, `settings()`, `has_openai_key()`.
- Produces:
  - `GET /api/runs/<run>/interviews?agent=<id>` → `listing`
  - `GET /api/runs/<run>/interviews/<id>` → `load`
  - `POST /api/runs/<run>/interviews` `{agent, tick}` → `start`(provider·모델 = 설정의 provider, `model_speak`)
  - `POST /api/runs/<run>/interviews/<id>/ask` `{question}` → 턴. 대화 LLM: 설정 provider가 demo면 `DemoInterviewer()`, openai면 키 없을 때 409 "no OpenAI key", 있으면 `OpenAIBackend(create_openai_client(env_file), max_total_tokens=None)`. 임베더 = `run_embedder(run_dir, env_file)`.
  - 409: run 폴더에 `.before-replay`가 있거나 `live.active()`의 그 run 상태가 `replaying`일 때 ask/start; 설정을 읽을 수 없는 run(`ValueError`).
  - 404: 없는 에이전트·인터뷰(`KeyError`).
  - 라우트는 기존 `/api/runs/(?P<run>.+)/people` 앞에 두지 말고, `(?P<run>.+?)/interviews` 비탐욕 패턴으로 run 경로와 구분.
- [ ] **Step 1: 실패 테스트** — 기존 `server` 픽스처(Demo 설정으로 PUT):

```python
def test_an_interview_through_the_api(server):
    base, runs = server
    _call(base, "/api/settings", "PUT", {"provider": "demo"})
    run = "one/s0_smoke/replicate-1"
    status, text = _call(base, f"/api/runs/{run}/interviews", "POST", {"agent": "HDS-001", "tick": 5})
    iv = json.loads(text)
    assert status == 200 and iv["summary"]["name"]
    status, text = _call(base, f"/api/runs/{run}/interviews/{iv['id']}/ask", "POST", {"question": "안녕하세요?"})
    assert status == 200 and json.loads(text)["a"]
    assert json.loads(_call(base, f"/api/runs/{run}/interviews?agent=HDS-001")[1])[0]["questions"] == 1
    assert _call(base, f"/api/runs/{run}/interviews/{iv['id']}/ask", "POST", {"question": " "})[0] == 400   # Focus 3
    assert _call(base, f"/api/runs/{run}/interviews", "POST", {"agent": "NOBODY", "tick": 1})[0] == 404    # Focus 5
    assert _call(base, f"/api/runs/{run}/interviews/..%2Fx")[0] == 404
    (runs / run / ".before-replay").mkdir()
    assert _call(base, f"/api/runs/{run}/interviews/{iv['id']}/ask", "POST", {"question": "?"})[0] == 409

def test_an_openai_interview_without_a_key_is_refused(server, tmp_path):
    # settings provider openai, .env without OPENAI_API_KEY → ask returns 409
```
- [ ] **Step 2–4:** 실패 확인 → 구현 → PASS.
- [ ] **Step 5: 커밋** — `feat(server): interview API`

### Task 4: 뷰어 채팅 패널

**Files:**
- Create: `viz/src/interview.ts`
- Modify: `viz/src/hud.ts`(inspect 패널에 버튼), `viz/view.html`(패널 자리), `viz/src/main.ts`(run 경로를 Hud에 전달), `viz/src/i18n.ts`, `viz/src/style.css`

**Interfaces:**
- Consumes: Task 3 API, `world.frame.tick`, `world.people`.
- Produces:
  - `main.ts`: `hud.runPath = <replay 경로 | /api/live의 run | null>`.
  - `class InterviewPanel { open(agent: string, tick: number): Promise<void>; close(): void }` — `#side` 안에서 inspect 자리를 덮는 sheet. 머리: 이름·역할·스트레스·기분, 배지 `t('interviewWhen', {clock})`, 예전 인터뷰 select(`listing`, 고르면 `load`해서 그 시점·대화를 보여 주고 이어서 질문), stale이면 `t('interviewStale')` 경고. 본문: 안내 `t('interviewNote')`, 말풍선(질문 오른쪽, 답 왼쪽). 아래: `t('interviewCost', {model})`, 입력칸 + 보내기(보내는 중 비활성, 오류는 패널 안에 표시, Enter로 보냄).
  - `hud.ts` inspect 패널 머리에 "💬 인터뷰" 버튼: `runPath`가 null이면 비활성(title = `t('interviewNoRun')`).
  - i18n 키(ko/en): `interview`, `interviewWhen`("{clock}까지의 기억으로 답해요"), `interviewNote`("인터뷰는 run에 영향을 주지 않아요 · run 폴더에 저장돼요"), `interviewCost`("질문 1번에 LLM 1회 + 임베딩 1회 · {model}"), `interviewNew`("새 인터뷰"), `interviewAsk`("{name}에게 물어볼 내용"), `send`, `interviewStale`("이 인터뷰 뒤로 run이 다시 만들어졌어요"), `interviewNoRun`, `interviewBusy`("기록 재생 중이라 지금은 물을 수 없어요").
- [ ] **Step 1:** 구현.
- [ ] **Step 2: 확인** — `npm run check`; `conflict-server` + `npm run dev`(설정 provider demo), 헤드리스 크롬으로 `view.html?replay=<demo run>&tick=12`에서 에이전트를 골라 인터뷰를 열고(필요하면 `&interview=<agent>` 딥링크를 추가해 헤드리스로 열기) 질문·답·저장 후 다시 열기를 확인.
- [ ] **Step 3: 커밋** — `feat(viz): interview an agent from the inspect panel`

### Task 5: 문서와 마무리

**Files:**
- Modify: `README.md`(실시간 보기와 재생 절에 인터뷰 한 단락), `viz/README.md`(interview.ts, API)
- [ ] **Step 1:** 문서 수정.
- [ ] **Step 2: 확인** — 전체 pytest·ruff·`npm run check` PASS.
- [ ] **Step 3: 커밋** — `docs: post-run agent interview`
