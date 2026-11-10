# 시나리오 생성기 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 대화와 미리보기가 한 화면에 있는 작업 화면에서 실험용 시나리오(처음부터 만들거나 기존 시나리오에서 변형, baseline/비교군 짝)를 만들고, 엔진 검증을 통과한 것만 새 파일로 저장해 라이브 목록에 올린다.

**Architecture:**
- **엔진 쪽**
  - 생성된 회사(`generated: true`)에는 느슨한 검증을 적용한다.
  - 회사 파일에 결재 단계(`authority_scope`)를 적을 수 있게 한다.
  - 설정 빌드를 메모리 안의 객체로 할 수 있게 나눈다.
  - 뷰어 프레임이 새 부서를 맵의 빈 부서 자리에 앉힌다.
- **생성기**
  - 초안은 `{company, scenario}` 버전 문서의 묶음이다.
  - LLM은 처음부터 만들 때만 전체 문서를 쓰고, 그 밖에는 JSON 패치(ops)만 낸다. 그래서 비교군이 조용히 달라지는 일을 구조적으로 막는다.
  - 검증은 메모리 안에서 `build_config`로 하고, 실패하면 오류를 LLM에 돌려 ops로 고친다(최대 3회).
- **서버와 화면**
  - `conflict-server`에 초안 API를 더한다.
  - viz에 세 번째 페이지 `create.html`을 더한다.

**Tech Stack:** Python 3.11+ (pydantic, PyYAML, hydra, http.server), pytest, ruff; Vite 8 + TypeScript 7 (no new deps).

**Spec:** `docs/superpowers/specs/2026-11-10-scenario-generator-design.md` (시안 `docs/superpowers/specs/2026-11-10-scenario-generator/layout.html`의 A-2/B). 각 태스크는 spec의 해당 절을 함께 읽는다.

## Global Constraints

**의존성과 보안**
- 새 Python·npm 의존성 없음.
- 서버 보안 규칙은 기존 `_guard`를 그대로 따른다: 로컬 Host/Origin, JSON 본문, OpenAI 키는 브라우저로 가지 않는다.

**LLM 호출**
- 생성 LLM은 settings의 `model_decide`, `reasoning_effort="none"`, temperature `0.4`, `json_mode=True`(strict schema 아님)로 부른다.
- provider가 `demo`면 생성 API는 409 `"scenario generation needs the OpenAI provider"`를 낸다.
- 키가 없으면 409 `"no OpenAI key in the server's .env"`를 낸다.

**인원과 조직 규칙**
- 한 시나리오는 3~20명.
- 생성된 회사의 부서는 최대 6개이고, 맨 위 보고자는 정확히 한 명이다.
- 기존 프리셋(`generated` 없음)의 검증과 동작은 그대로다. 기존 테스트 전부 그대로 통과해야 한다.

**저장**
- 저장은 새 파일만 쓴다.
- 기존 `conf/` 파일을 고치거나 덮어쓰지 않는다. 이름이 겹치면 `-2`, `-3` 접미사를 붙인다.

**생성 결과의 기본값과 id 규칙**
- 기본 언어는 `Korean`, `prompt_style: human`.
- 사람 id는 `P01`… 형식이고, 핵심 업무 id는 `C01`… 형식이다(처음부터 만들 때).

**파일 이름**
- 생성 파일 이름의 접두사는 `gen_`이다.
- 쓰는 파일은 `conf/scenario/company_c15/gen_<slug>.yaml`, `conf/company/gen_<slug>.yaml`, `conf/personas/gen_<slug>.yaml`, `conf/environment/org/gen_<slug>.yaml`이다.

**초안 저장 위치**
- `<settings_path의 폴더>/drafts/<draft id>.json`(기본 `.conflict-sim/drafts/`).

**첨부 크기**
- 첨부 md 파일은 한 개 200 KB, 합계 1 MB까지 받는다.
- UTF-8이 아니면 400 오류를 낸다.

## Review Focus

1. **LLM이 3번 고쳐도 검증을 통과하지 못하는 경우:** 초안에 마지막 버전과 오류를 남긴다. 저장은 막고, 대화창에 오류 목록을 보여 준다. 이 경우를 Task 5에서 테스트한다.
2. **패치가 없는 경로를 가리키거나, 변형 모드에서 baseline을 고치려는 경우:** 그 메시지의 ops는 하나도 적용하지 않는다. 초안은 그대로 두고 이유를 대화창에 적는다. Task 5에서 테스트한다.
3. **같은 초안을 다시 저장하거나 이름이 겹치는 경우:** 기존 파일은 그대로 두고 새 이름으로 쓴다. Task 6에서 테스트한다.
4. **두 탭이 같은 초안에 동시에 메시지를 보내는 경우:** 두 번째 요청은 409 `"the draft is busy"`를 받는다. Task 7에서 테스트한다.
5. **생성 중 토큰 상한에 닿거나 OpenAI 오류가 난 경우:** 초안은 바뀌지 않는다. 대화창에는 실패 한 줄을 적고, API는 502 오류 메시지를 낸다. Task 7에서 테스트한다.

---

## File Structure

| 파일 | 역할 |
| --- | --- |
| `src/conflict_sim/company.py` (수정) | `CompanyPreset.generated`, `WorkflowTask.authority_scope`, 생성된 회사의 느슨한 검증 |
| `src/conflict_sim/company_runtime.py` (수정) | `Experiment` 모델과 `C15Scenario.experiment`, `build_config(scenario, preset)` 분리, 결재 단계 우선순위 |
| `src/conflict_sim/frames.py` (수정) | 맵에 없는 부서를 빈 부서 자리로 옮기고, 그 구역 이름표를 새 부서 이름으로 바꾼다 |
| `src/conflict_sim/experiment.py` (수정) | `all_scenarios()` = 고정 목록 + `gen_*` 파일. CLI 선택지 |
| `src/conflict_sim/runs.py` (수정) | 카탈로그가 `all_scenarios()`를 쓴다 |
| `src/conflict_sim/scenario_draft.py` (신규) | 초안 버전 모델, 기존 시나리오 → 버전, 버전 → 프리셋/설정/YAML 파일, 검증, 차이 계산, 패치 적용 |
| `src/conflict_sim/generator.py` (신규) | 초안 저장소, LLM 단계(되묻기·생성·수정·자동 수정), 저장 |
| `src/conflict_sim/server.py` (수정) | `/api/drafts…` 경로 |
| `viz/create.html`, `viz/src/create.ts`, `viz/src/create.css` (신규) | 작업 화면 |
| `viz/src/menu.ts`, `viz/src/i18n.ts`, `viz/vite.config.ts` (수정) | "시나리오 생성" 카드 활성화, 문구, 빌드 입력 |
| 테스트 | `tests/test_company.py`, `tests/test_company_runtime.py`, `tests/test_stream.py`, `tests/test_scenario_draft.py`(신규), `tests/test_generator.py`(신규), `tests/test_runs.py`, `tests/test_server.py` |

---

### Task 1: 생성된 회사의 느슨한 검증과 회사 파일의 결재 단계

**Files:**
- Modify: `src/conflict_sim/company.py:130-137` (`WorkflowTask`), `:192-326` (`CompanyPreset`)
- Modify: `src/conflict_sim/company_runtime.py:222` (`authority_scope=`)
- Test: `tests/test_company.py`, `tests/test_company_runtime.py`

**Interfaces:**
- Produces:
  - `CompanyPreset.generated: bool = False`
  - `CompanyPreset.baseline: Literal["A1B1C1", "generated"]`
  - `WorkflowTask.authority_scope: NonEmptyText | None = None`
  - `MAX_GENERATED_DEPARTMENTS = 6`
  - `GENERATED_AGENTS = (3, 20)`

- [ ] **Step 1: Write the failing tests**

테스트 헬퍼 `_korean_10()`는 `load_company_preset("korean_enterprise_10_ko").model_dump()`를 돌려준다. 테스트는 이 사전을 고쳐 `CompanyPreset.model_validate`에 넣는다.

```python
def test_a_generated_company_may_have_any_size_from_three_to_twenty():
    data = _korean_10(); data["generated"] = True; data["baseline"] = "generated"
    keep = [a for a in data["personas"]["agents"] if a["department"] != "Quality Engineering"]
    # drop the 2 QE people and every reference to them (helper `_drop_people`)
    data = _drop_people(data, {a["id"] for a in data["personas"]["agents"]} - {a["id"] for a in keep})
    preset = CompanyPreset.model_validate(data)
    assert len(preset.personas.agents) == 8

def test_a_generated_company_needs_one_root_but_not_the_project_manager():
    # root = HDS-002 after re-pointing reports_to; project.manager_id stays HDS-001 → still valid
    ...
    assert CompanyPreset.model_validate(data).generated

def test_a_generated_company_keeps_its_bounds():
    # 2 agents → "A generated company has 3 to 20 agents"
    # 7 departments → "A generated company has at most 6 departments"
    # two roots → "A generated company has exactly one reporting root"
    # 0 workflow tasks → "A generated company needs at least one workflow task"

def test_a_generated_company_may_have_no_conflict_events():
    data["environment"]["org"]["conflict_events"] = []  # generated → valid

def test_an_existing_company_keeps_the_locked_rules():
    data = _korean_10(); data["personas"]["agents"] = data["personas"]["agents"][:8]  # not generated
    with pytest.raises(ValidationError, match="20 agents"):
        CompanyPreset.model_validate(data)
```

`tests/test_company_runtime.py`:

```python
def test_a_task_written_scope_wins_over_the_table(monkeypatch):
    # preset whose T05 has authority_scope "design_review", T06 has none
    cfg = build_config(scenario, preset)  # Task 2 name; in this task call build_company_config via a tmp conf
    assert task("T05").authority_scope == "design_review"
    assert task("T06").authority_scope == "architecture"  # from TASK_AUTHORITY_SCOPE
```

Task 2 전이라 메모리 빌드가 없으므로, 이 테스트는 `load_company_preset`을 monkeypatch해서 고친 프리셋을 돌려준다.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_company.py tests/test_company_runtime.py -k "generated or scope_wins or locked_rules" -q`

Expected: FAIL. `generated`가 extra 필드라서 실패한다.

- [ ] **Step 3: Implement in `company.py` / `company_runtime.py`**

- **`validate_references`:** `generated`이면 다음 규칙으로 바꾼다.
  - 인원: `3 <= len(agents) <= 20`
  - DISC: 5/5/5/5 고정 대신 `target_counts`와 같은지만 본다.
  - 보고 라인: 뿌리가 정확히 1명이면 된다. 그 사람이 manager가 아니어도 된다.
  - 부서: `len(departments) <= 6`
  - 업무: 1개 이상
  - 갈등 사건: id만 서로 달라야 하고, 개수와 taxonomy는 보지 않는다.
- **공통 검증:** 나머지는 두 쪽 모두 그대로다(순환, 참조 id, 참여, 비순환 업무 그래프, place id). 생성 쪽 오류 문구는 Step 1의 문자열과 정확히 같게 쓴다.
- **`company_runtime.py:222`:** `authority_scope = task.authority_scope if task.authority_scope is not None else TASK_AUTHORITY_SCOPE.get(task.id)`.

- [ ] **Step 4: Run to verify they pass, then the whole suite**

Run: `uv run pytest -q`

Expected: 전부 PASS. 기존 646개 포함.

- [ ] **Step 5: Commit**

`feat(company): looser rules for generated companies; tasks may name their sign-off`

---

### Task 2: 메모리 안에서 설정 빌드, 실험 정보 칸

**Files:**
- Modify: `src/conflict_sim/company_runtime.py:109-152`, `:181-320`
- Test: `tests/test_company_runtime.py`

**Interfaces:**
- Consumes: Task 1의 `CompanyPreset`.
- Produces:
  - `build_config(scenario: C15Scenario, preset: CompanyPreset, *, backend: Literal["demo","openai"] = "demo") -> Config`
  - `build_company_config(name, *, backend)`는 이것을 부르는 얇은 함수가 된다.
  - `class Measure(ValidatedModel)`:
    - `metric: Literal["stress","mood","relation","task_completion","rest_ratio"]`
    - `subject: str` (사람 id, `"all"`, `"partners_of:<id>"`)
    - `toward: str | None = None`
    - `direction: Literal["up","down"]`
  - `class Experiment(ValidatedModel)`:
    - `id: NonEmptyText`
    - `role: Literal["baseline","variant"]`
    - `factor: Literal["structure","work","disposition","event"] | None = None`
    - `hypothesis: str = ""`
    - `measures: list[Measure] = []`
    - `behaviour_checks: list[str] = []`
  - `C15Scenario.experiment: Experiment | None = None`

- [ ] **Step 1: Write the failing tests**

```python
def test_a_config_builds_from_objects_the_same_as_from_files():
    scenario = load_c15_scenario("r10_human")
    preset = load_company_preset(scenario.preset)
    assert build_config(scenario, preset).model_dump() == build_company_config("r10_human").model_dump()

def test_a_scenario_may_carry_its_experiment():
    data = load_c15_scenario("r10_human").model_dump()
    data["experiment"] = {"id": "rude-01", "role": "variant", "factor": "disposition",
                          "hypothesis": "h", "measures": [{"metric": "relation",
                          "subject": "partners_of:HDS-003", "toward": "HDS-003", "direction": "down"}],
                          "behaviour_checks": ["c"]}
    assert C15Scenario.model_validate(data).experiment.measures[0].toward == "HDS-003"
```

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/test_company_runtime.py -q`. Expected: ImportError `build_config`.

- [ ] **Step 3: Implement**

`build_company_config` 본문의 로드 뒤 부분을 `build_config`로 옮긴다. 이름 기반 함수는 로드한 다음 `build_config`를 부른다.

- [ ] **Step 4: Run** — `uv run pytest -q`. Expected: 전부 PASS.

- [ ] **Step 5: Commit**

`refactor(company): build a config from objects; scenarios carry an experiment block`

---

### Task 3: 새 부서를 맵의 빈 부서 자리에

**Files:**
- Modify: `src/conflict_sim/frames.py:8-34`
- Test: `tests/test_stream.py`

**Interfaces:**
- Produces: `Frames.map` is the map with departments re-pointed.
  - 맵에 없는 회사 부서는 아직 쓰이지 않은 맵 부서 자리를 맵에 나온 순서대로 받는다.
  - 그 자리 객체의 `dept` 속성과 구역의 `zone` 이름표는 새 부서의 표시 이름(`AgentSpec.team`)으로 바뀐다.
  - 옮김이 하나라도 있으면, 아무도 쓰지 않는 부서 구역의 `zone` 속성은 지운다.
  - 회사 부서가 모두 맵에 있으면 맵은 그대로다. 기존 run과 같다.
  - 맵 자리보다 부서가 많으면 넘치는 부서는 아무 빈 자리에 앉는다(지금 동작).

- [ ] **Step 1: Write the failing tests**

```python
def test_a_new_department_takes_an_empty_department_area(tmp_path):
    cfg = build_company_config("r10_human")
    # rename every agent's department "Quality Engineering" → "qa" with team "품질팀"
    frames = Frames(cfg_renamed, "r")
    zones = [_props(o).get("zone") for o in _objects(frames.map)]
    assert "품질팀" in zones and "Quality Engineering" not in zones
    assert "Go-to-Market" not in zones  # unused department area loses its label
    seat_depts = set(frames.seat_dept.values())
    assert "qa" in seat_depts

def test_a_company_on_the_map_departments_leaves_the_map_alone():
    cfg = build_company_config("r10_human")
    assert Frames(cfg, "r").map == json.loads(Path(cfg.stream_map).read_text())
```

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/test_stream.py -k department -q`. Expected: FAIL. 구역 이름이 그대로라서 실패한다.

- [ ] **Step 3: Implement in `Frames.__init__`**

맵을 읽은 직후, `seats`/`seat_dept`를 모으기 전에 고쳐 쓴다.
- 구역과 자리는 둘 다 맵의 부서 id(`zone` 이름 = `dept` 값)로 묶여 있다.
- 매핑 `map_dept → company_dept`를 만들어 두 속성에 적용한다.
- 이름표 `zone`에는 `team`을 쓰고, `dept`에는 부서 id를 쓴다.

- [ ] **Step 4: Run** — `uv run pytest tests/test_stream.py -q`. Expected: PASS.

- [ ] **Step 5: Commit**

`feat(frames): seat new departments in the map's free department areas`

---

### Task 4: 초안 버전 모델과 변환·검증·차이·패치 (`scenario_draft.py`)

**Files:**
- Create: `src/conflict_sim/scenario_draft.py`
- Test: `tests/test_scenario_draft.py`

**Interfaces:**
- Consumes: Task 1의 `CompanyPreset`, `WorkflowTask.authority_scope`. Task 2의 `build_config`, `C15Scenario.experiment`.
- Produces:

```python
class Department(ValidatedModel): id: NonEmptyText; name: NonEmptyText
class CompanyDraft(ValidatedModel):
    organization: NonEmptyText          # company name
    project: NonEmptyText               # project name
    departments: list[Department]
    people: list[CompanyAgent]          # company.CompanyAgent as is
    tasks: list[WorkflowTask]           # with authority_scope filled explicitly
    conflict_events: list[ConflictEvent] = []
class Version(ValidatedModel):
    company: CompanyDraft
    scenario: dict                      # C15Scenario fields except id, preset, experiment

def version_from_scenario(name: str) -> Version
def preset_of(company: CompanyDraft, preset_id: str) -> CompanyPreset   # generated=True
def scenario_of(version: Version, scenario_id: str, preset: str, experiment: Experiment | None) -> C15Scenario
def check(version: Version) -> list[str]                 # [] = valid
def config_of(version: Version) -> Config                # raises on invalid
def diff(a: Version, b: Version) -> list[dict]           # [{"path","factor","a","b"}]
def apply_ops(doc: dict, ops: list[dict]) -> dict        # new dict; raises PatchError
def files_of(version: Version, slug: str, *, experiment: Experiment | None,
             reuse_preset: str | None) -> dict[str, str]  # conf-relative path → YAML text
class PatchError(ValueError)
FACTORS = ("structure", "work", "disposition", "event")
```

**`version_from_scenario`**
- 시나리오의 `extends`를 풀고 프리셋을 `CompanyDraft`로 옮긴다.
- 각 업무의 `authority_scope`는 표 값으로 채운다. 그래야 생성 규칙으로 다시 써도 같은 설정이 나온다.

**`preset_of`**
- 사무실은 `conf/environment/office/large_korean_enterprise.yaml`을 읽어 그대로 쓴다.
- 나머지 고정 칸은 기존 프리셋 값을 쓴다:
  - `ProjectDefinition.structure` / `product_type`
  - `OrganizationRules`
  - `task_states` (`korean_enterprise_10_ko` org 파일 값)
  - `engine_handoff`, `evidence_tags`: `["generated"]`
  - `runtime`
- `project.manager_id`는 보고 라인의 뿌리다.
- `evaluation_authority`는 evaluate 권한을 가진 사람들이다.
- `raci`는 `{}`이다.
- `job_families` / `roles`는 사람들에게서 모은다.
- `disc_policy.target_counts`는 실제 개수다. `prohibited_inferences`는 기존 페르소나 파일 값을 쓴다.

**`check`**
- `config_of`를 부르고, 예외 메시지(pydantic이면 오류 줄마다 하나씩)를 목록으로 돌려준다.

**`diff`의 비교 대상과 정렬**
- 두 `config_of(...).model_dump()`를 평탄화해 비교한다.
- 목록은 원소에 `name` 또는 `id`가 있으면 그 값으로 열쇠를 삼는다.
- 무시하는 경로는 `scenario.id`, `scenario.research_question`이다.

**`diff`의 factor 분류 (경로 접두 순서대로 첫 일치)**
- `structure`
  - `agents.<n>.reports_to`, `.authorities`, `.department`, `.team`, `.position`, `.title`
  - `environment.org.departments`
- `disposition`
  - `agents.<n>.persona`, `.communication_style`, `.pressure_response`, `.conflict_style`, `.relationship_notes`, `.work_priority`, `.disc`, `.backstory`
- `event`
  - `scenario.shocks`, `scenario.interventions`
  - `environment.org.tasks.<id>.arrives`
- `work`
  - `environment.org.tasks`, `scenario.meetings`, `weekly_operations`, `environment.weekly_operations`
- 그 밖: `other`

**`apply_ops`**
- 지원하는 op: `add` / `replace` / `remove`. JSON Pointer 경로이고, `add`에서 `-`는 목록 끝이다.
- 경로가 없으면 `PatchError("no such path: <path>")`를 낸다.
- 원본은 바꾸지 않는다.

**`files_of`**
- 기본은 네 파일이다(company / personas / org / scenario). 모두 `gen_<slug>`이고 company 파일은 hydra `defaults`로 셋을 묶는다.
- `reuse_preset`이 주어지면(변형이 회사를 바꾸지 않은 경우) scenario 파일 하나만 쓰고, 그 파일의 `preset`은 `reuse_preset`이다.
- YAML 첫 줄 주석: `# Generated by the scenario generator (<date>); edit through the generator or by hand.`

- [ ] **Step 1: Write the failing tests**

```python
def test_an_existing_scenario_round_trips_to_the_same_config():
    v = version_from_scenario("r10_human")
    assert config_of(v).model_dump(exclude={"scenario"}) == \
        build_company_config("r10_human").model_dump(exclude={"scenario"})

def test_a_broken_version_reports_engine_errors():
    v = version_from_scenario("r10_human")
    v.company.tasks[0].owner = "NOBODY"
    assert any("unknown agents" in e for e in check(v))

def test_diff_names_the_factor_of_each_change():
    a = version_from_scenario("r10_human"); b = a.model_copy(deep=True)
    b.company.people[2].communication_style = "피드백할 때 깎아내리고 비꼬는 말을 쓴다."
    b.company.people[3].reports_to = b.company.people[1].id
    factors = {d["factor"] for d in diff(a, b)}
    assert factors == {"disposition", "structure"}

def test_an_identical_copy_has_no_diff():
    a = version_from_scenario("r10_human"); assert diff(a, a.model_copy(deep=True)) == []

def test_a_patch_to_a_missing_path_changes_nothing():
    doc = {"a": [1]}
    with pytest.raises(PatchError, match="no such path: /b/0"):
        apply_ops(doc, [{"op": "replace", "path": "/b/0", "value": 2}])
    assert doc == {"a": [1]}

def test_written_files_load_through_hydra(tmp_path, monkeypatch):
    # monkeypatch company.CONF_DIR / company_runtime.CONF_DIR to a copy of conf/ under tmp_path
    files = files_of(version_from_scenario("r10_human"), "t1", experiment=None, reuse_preset=None)
    write files under the copy; assert build_company_config("gen_t1").n_agents == 10
```

- [ ] **Step 2: Run** — `uv run pytest tests/test_scenario_draft.py -q`. Expected: ImportError.
- [ ] **Step 3: Implement `scenario_draft.py`** to the interfaces above.
- [ ] **Step 4: Run** — `uv run pytest tests/test_scenario_draft.py -q && uv run ruff check src tests`. Expected: PASS, clean.
- [ ] **Step 5: Commit**

`feat(generator): draft versions — convert, check, diff by factor, patch, write files`

---

### Task 5: 생성기 — 초안 저장소와 LLM 단계 (`generator.py`)

**Files:**
- Create: `src/conflict_sim/generator.py`
- Test: `tests/test_generator.py`

**Interfaces:**
- Consumes: Task 4 전부. `llm.LanguageModel.complete(...)`.
- Produces:

```python
MAX_FIXES = 3
class DraftBusy(RuntimeError)
class Drafts:                                  # one folder of <id>.json, a lock per draft
    def __init__(self, root: Path)
    def create(self, mode: Literal["scratch","variant"], source: str | None) -> dict
    def load(self, draft_id: str) -> dict      # KeyError when missing
    def listing(self) -> list[dict]            # [{id,title,mode,updated,saved}] newest first
    def busy(self, draft_id: str)              # context manager; DraftBusy if already held
    def write(self, draft: dict) -> None
def view(draft: dict) -> dict                  # draft + {"checks": {...}, "diff": [...], "outside": [...], "files": {...}}
def turn(draft: dict, text: str, attachments: list[dict], llm, model: str) -> dict   # returns new draft
```

**초안 JSON 모양** (`Drafts.create`가 만들고 `turn`이 고친다)

```json
{"id": "d-20261110-1432-ab12", "created": "...", "updated": "...",
 "mode": "scratch", "source": null, "title": "", "pair": false, "factor": null,
 "experiment": null,                       // Experiment fields without role
 "materials": [{"name": "spec.md", "text": "..."}],
 "versions": {"baseline": null, "variant": null},   // Version.model_dump() or null
 "messages": [{"role": "user|ai|check", "text": "...", "tokens": 0}],
 "saved": []}
```

변형 모드의 `create`는 `versions.baseline = version_from_scenario(source)`로 시작한다. 이 baseline은 잠겨 있다.

**`turn`의 흐름** (한 번의 사용자 메시지)

1. **첨부 정리:** 첨부를 `materials`에 붙인다. 크기와 UTF-8 검사는 서버가 한다.
2. **라우터 호출:** 반환은 `{"reply": str, "next": "ask"|"generate"|"edit", "settings": {"title"?, "pair"?, "factor"?, "experiment"?}}`이다. `settings`는 초안에 병합한다.
   - `ask`: AI 메시지 하나를 남기고 끝난다.
3. **`generate`:**
   - **처음부터:** 회사 호출(`CompanyDraft` JSON) → 시나리오 호출(`Version.scenario` JSON) 순서로 부른다. 그다음 `pair`이면 비교군 호출을 한다. 비교군은 baseline에 대한 ops다.
   - **변형:** 비교군 호출만 한다.
4. **`edit`:** 수정 호출을 한다. 반환은 `{"reply", "ops"}`이고, ops 경로는 `/baseline/...` 또는 `/variant/...`로 시작한다.
5. **자동 수정:** 각 생성·수정 뒤 버전마다 `check`를 돌린다. 오류가 있으면 자동 수정 호출(`{"ops"}`, 버전 문서와 오류 목록을 준다)을 최대 `MAX_FIXES`번 한다.
   - 결과는 `check` 메시지 한 줄로 남긴다: `"형식 검사: 오류 {n}개 → 자동 수정 {k}번 → 통과"` 또는 `"… → 통과하지 못함: <첫 오류 3개>"`.
   - 통과하지 못해도 버전은 남긴다(Review Focus 1).
6. **ops 거부:** 다음 경우에는 ops를 하나도 적용하지 않고, AI 메시지로 이유를 적는다(Review Focus 2).
   - `PatchError`가 난다.
   - 변형 모드에서 `/baseline`을 건드린다.
7. **토큰 기록:** 각 AI 메시지에는 그 턴의 토큰 수(`llm.usage` 합)를 `tokens`로 남긴다.

**시스템 프롬프트에 반드시 들어갈 것** (모듈 상수, 문구는 빌더가 쓴다)
- **지침 원문:** `docs/scenario-writing-guide.md` 원문 전체.
- **규칙 (spec §4.1):** 3~20명, 부서 최대 6개, 맨 위 보고자 1명, id 규칙(`P01`/`C01`), 언어 `Korean`, `prompt_style: human`.
- **사무실 장소 id 목록:** 회의·shock의 `place`에 쓴다.
- **성향 규칙 (spec §5.4):**
  - 공격적·비합리적 성향은 사용자가 지목한 사람에게만 넣는다.
  - 행동 묘사로 쓰고 욕설은 쓰지 않는다.
  - 비교 요인이 아닌데 넣으면 reply에 경고한다.
- **비교군 규칙:** 비교군 ops는 고른 요인 밖을 건드리지 않는다.
- **실험 정보 (spec §6):** experiment를 채운다. `measures`의 metric은 5개 값 중에서 고르고, 행동 조작 점검을 반드시 하나 이상 넣는다.
- **md 자료 (spec §7):** 업무의 근거로 쓰고, 해당 업무 id의 `materials`에도 넣는다.
- **출력:** JSON만 낸다.

- [ ] **Step 1: Write the failing tests**

`FakeLLM`은 준비한 응답 문자열을 차례로 돌려주고, 받은 `system`/`prompt`를 기록한다. `usage`는 `{"decide": {"total_tokens": 10}}`이다.

```python
def test_a_vague_request_gets_a_question_and_no_version(tmp_path):
    d = Drafts(tmp_path).create("scratch", None)
    d = turn(d, "실험하고 싶어", [], FakeLLM([router("ask", reply="무엇을 비교할까요?")]), "m")
    assert d["messages"][-1] == {"role": "ai", "text": "무엇을 비교할까요?", "tokens": 10}
    assert d["versions"]["baseline"] is None

def test_scratch_with_a_pair_builds_both_versions_that_pass(tmp_path):
    company, scenario = _r10_as_scratch_json()   # from version_from_scenario("r10_human")
    llm = FakeLLM([router("generate", settings={"pair": True, "factor": "disposition"}),
                   company, scenario, json.dumps({"reply": "ok", "ops": [
                       {"op": "replace", "path": "/variant/company/people/2/communication_style",
                        "value": "피드백할 때 깎아내리고 비꼬는 말을 쓴다."}]})])
    d = turn(Drafts(tmp_path).create("scratch", None), "…", [], llm, "m")
    v = view(d)
    assert v["checks"] == {"baseline": [], "variant": []}
    assert {x["factor"] for x in v["diff"]} == {"disposition"} and v["outside"] == []

def test_engine_errors_go_back_to_the_model_until_fixed(tmp_path): ...
    # scenario JSON with a task owner "NOBODY"; fix call replaces it → check message says 통과

def test_a_version_that_never_passes_is_kept_and_reported(tmp_path): ...
    # 1 + MAX_FIXES failing fixes → last check message contains "통과하지 못함", view()["checks"]["baseline"] != []

def test_a_variant_may_not_touch_its_baseline(tmp_path):
    d = Drafts(tmp_path).create("variant", "r10_human")
    before = d["versions"]["baseline"]
    llm = FakeLLM([router("edit"), json.dumps({"reply": "x", "ops": [
        {"op": "replace", "path": "/baseline/company/organization", "value": "X"}]})])
    d = turn(d, "회사 이름 바꿔줘", [], llm, "m")
    assert d["versions"]["baseline"] == before and "baseline" in d["messages"][-1]["text"]

def test_the_prompt_carries_the_writing_guide_and_the_materials(tmp_path):
    ... assert "갈등은" in llm.calls[0]["system"] or a fixed heading from the guide
    ... assert "spec.md" in llm.calls[1]["prompt"]

def test_a_held_draft_is_busy(tmp_path):
    drafts = Drafts(tmp_path); d = drafts.create("scratch", None)
    with drafts.busy(d["id"]):
        with pytest.raises(DraftBusy):
            with drafts.busy(d["id"]): pass
```

- [ ] **Step 2: Run** — `uv run pytest tests/test_generator.py -q`. Expected: ImportError.
- [ ] **Step 3: Implement `generator.py`** to the interfaces and flow above.
- [ ] **Step 4: Run** — `uv run pytest tests/test_generator.py tests/test_scenario_draft.py -q`. Expected: PASS.
- [ ] **Step 5: Commit**

`feat(generator): drafts and the conversation — ask, generate, edit, auto-fix`

---

### Task 6: 저장과 라이브 목록

**Files:**
- Modify: `src/conflict_sim/generator.py` (`save`)
- Modify: `src/conflict_sim/experiment.py:31-49`, `:404`
- Modify: `src/conflict_sim/runs.py:113-135`
- Test: `tests/test_generator.py`, `tests/test_runs.py`

**Interfaces:**
- Consumes: Task 4의 `files_of`, `check`, `diff`. Task 5의 `Drafts`, `view`.
- Produces:
  - `save(draft: dict, conf_dir: Path, *, accept_outside: bool) -> dict`. 반환은 `saved` 이름 목록이 채워진 새 초안이다.
  - `experiment.all_scenarios() -> tuple[str, ...]`: `SCENARIOS` 뒤에 `conf/scenario/company_c15/gen_*.yaml` 이름을 정렬해 붙인다.
  - 예외: `SaveRefused(ValueError)`

**`save`의 규칙**
- **거부하는 경우** (`SaveRefused`)
  - 어느 버전이든 `check`가 비어 있지 않으면: `"fix the errors first"`
  - `outside`가 있고 `accept_outside`가 아니면: `"the variant differs outside its factor"`
- **이름**
  - `slug`는 `title`을 ASCII 슬러그로 만든 것이다. 비면 초안 id를 쓴다.
  - baseline은 `gen_<slug>_base`, 비교군은 `gen_<slug>_var`이다.
  - 네 파일 중 하나라도 이미 있으면 `-2`, `-3` …를 붙인다. 파일 이름에는 `_2`를 쓴다(hydra·Python 이름에 안전하게).
- **변형 모드**
  - baseline 파일은 쓰지 않는다. `source`가 baseline이다.
  - 비교군의 회사가 원본과 같으면(`company` 동일) `reuse_preset=<원본 preset>`으로 시나리오 파일만 쓴다.
- **실험 정보**
  - 각 시나리오의 `experiment`는 `draft.experiment | {id: draft.experiment.id or slug, role}`이다.
- **기록과 갱신**
  - 쓴 뒤 `draft["saved"]`에 시나리오 이름을 기록한다.
  - 카탈로그 캐시는 `_conf_stamp`가 새 파일을 감지해 다시 만든다.

- [ ] **Step 1: Write the failing tests**

```python
def test_saving_writes_new_files_and_never_overwrites(tmp_conf):   # fixture: copy of conf/ + monkeypatched CONF_DIRs
    d = _passing_pair_draft(title="rude feedback")
    d = save(d, tmp_conf, accept_outside=False)
    assert d["saved"] == ["gen_rude_feedback_base", "gen_rude_feedback_var"]
    d2 = save(d, tmp_conf, accept_outside=False)
    assert d2["saved"][-2:] == ["gen_rude_feedback_base_2", "gen_rude_feedback_var_2"]
    assert build_company_config("gen_rude_feedback_var").scenario  # loads
    assert load_c15_scenario("gen_rude_feedback_var").experiment.role == "variant"

def test_an_invalid_draft_is_not_saved(tmp_conf): ...  # SaveRefused("fix the errors first"), no file written
def test_a_variant_outside_its_factor_needs_consent(tmp_conf): ...
def test_a_work_variant_reuses_the_source_company(tmp_conf):
    # variant of r10_human changing only scenario → one file; its preset == "korean_enterprise_10_ko"
def test_generated_scenarios_appear_in_the_catalog(tmp_conf):   # tests/test_runs.py
    ... assert "gen_rude_feedback_var" in [r["name"] for r in scenario_catalog(runs_root)]
```

- [ ] **Step 2: Run** — `uv run pytest tests/test_generator.py tests/test_runs.py -k "sav or catalog or variant" -q`. Expected: FAIL.
- [ ] **Step 3: Implement**

- `save`는 위 규칙대로 구현한다.
- `all_scenarios`를 만들고, `runs._scenarios`와 `experiment.main`의 `choices`가 이것을 쓰게 한다.
- `_scenarios`에서 생성 시나리오 하나가 빌드에 실패해도(사람이 손으로 고친 경우) 카탈로그 전체가 깨지지 않게 한다. 그 줄만 건너뛴다.

- [ ] **Step 4: Run** — `uv run pytest -q`. Expected: 전부 PASS.
- [ ] **Step 5: Commit**

`feat(generator): save drafts as new scenario files that join the live list`

---

### Task 7: 서버 API

**Files:**
- Modify: `src/conflict_sim/server.py` (routes, handlers, `make_server`)
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: Task 5·6의 `Drafts`, `view`, `turn`, `save`, `DraftBusy`, `SaveRefused`.
- Produces (모두 JSON; 초안 응답은 언제나 `view(draft)`):

| 경로 | 본문 | 응답 / 오류 |
| --- | --- | --- |
| `GET /api/drafts` | — | `Drafts.listing()` |
| `POST /api/drafts` | `{mode, source?}` | 새 초안. `source`가 `all_scenarios()`에 없으면 404 |
| `GET /api/drafts/<id>` | — | 초안. 없으면 404 |
| `POST /api/drafts/<id>/messages` | `{text, files: [{name, text}]}` | 새 초안. 아래 오류 참고 |
| `POST /api/drafts/<id>/save` | `{accept_outside?: bool}` | 새 초안. `SaveRefused` → 409 |

`/messages`의 오류
- demo나 키 없음: 409 (Global Constraints 문구)
- `DraftBusy`: 409 `"the draft is busy"`
- 첨부 크기 초과: 400 `"attachments are limited to 200 KB each, 1 MB in all"`
- `LLMError`나 OpenAI 오류: 502. 초안은 바뀌지 않고, 그 턴의 실패를 `check` 메시지로 적은 초안을 저장한다.

**구현 메모**
- `Server.drafts = Drafts(settings_path.parent / "drafts")`.
- LLM은 다음 설정으로 만든다: `OpenAIBackend(create_openai_client(env_file), max_total_tokens=300_000, reasoning_effort="none", max_tokens_decide=32_000, max_input_chars=400_000)`. 모델은 `settings["model_decide"]`, temperature는 `0.4`다.
- 테스트가 LLM을 바꿔 끼울 수 있게 `Server.generator_llm: Callable[[Server], tuple[llm, model]]`를 둔다.

- [ ] **Step 1: Write the failing tests**

```python
def test_drafts_through_the_api(server, monkeypatch):    # FakeLLM via generator_llm, provider openai
    status, body = _call(base, "/api/drafts", "POST", {"mode": "scratch"}); assert status == 200
    draft_id = json.loads(body)["id"]
    status, body = _call(base, f"/api/drafts/{draft_id}/messages", "POST", {"text": "…", "files": []})
    assert status == 200 and json.loads(body)["messages"][-1]["role"] == "ai"
    assert any(d["id"] == draft_id for d in json.loads(_call(base, "/api/drafts")[1]))

def test_generation_is_refused_on_demo(server): ...          # 409 needs the OpenAI provider
def test_a_busy_draft_answers_409(server, monkeypatch): ...  # hold drafts.busy(id) in the test, POST → 409
def test_an_llm_failure_leaves_the_draft_as_it_was(server, monkeypatch):
    # FakeLLM raises LLMError("Run token budget reached; no further API calls") → 502; versions unchanged; last message role "check"
def test_oversized_attachments_are_refused(server, monkeypatch): ...  # 201 KB file → 400
def test_other_sites_cannot_generate(server): ...            # Origin http://evil.example → 403
```

- [ ] **Step 2: Run** — `uv run pytest tests/test_server.py -k draft -q`. Expected: 404 not found.
- [ ] **Step 3: Implement** the routes and handlers above. `_guard`는 바꾸지 않는다.
- [ ] **Step 4: Run** — `uv run pytest -q && uv run ruff check src tests`. Expected: PASS, clean.
- [ ] **Step 5: Commit**

`feat(server): scenario draft API`

---

### Task 8: 작업 화면 (`create.html`)

**Files:**
- Create: `viz/create.html`, `viz/src/create.ts`, `viz/src/create.css`
- Modify: `viz/vite.config.ts` (`input.create`)
- Modify: `viz/src/menu.ts:147` ("시나리오 생성" 카드 → `/create.html`. meta에 초안 수를 보여 준다)
- Modify: `viz/src/i18n.ts` (ko/en 문구)

**Interfaces:**
- Consumes: Task 7의 API.
- Produces:
  - `create.html?draft=<id>`: 그 초안을 연다.
  - 인자가 없으면 시작 화면을 연다.
    - 새로 만들기: "처음부터" / "기존에서 변형". 변형은 `/api/scenarios`에서 고른다.
    - 이어서 하기: 최근 초안 목록.

**화면** (spec §5.1, 시안 A-2/B)

- **왼쪽 대화**
  - 역할별 말풍선을 쓴다: `user`는 오른쪽, `ai`는 왼쪽, `check`는 회색 한 줄에 ⚙.
  - md 첨부 버튼(`accept=".md,text/markdown"`)이 있다. 붙인 파일은 칩으로 보이고 지울 수 있다.
  - 입력창은 Enter로 보내고, Shift+Enter는 줄바꿈이다.
  - 보내는 동안 입력을 잠그고 "만드는 중…" 표시를 띄운다.
  - AI 메시지 옆에 토큰 수를 작게 표시한다.
- **오른쪽 미리보기**
  - baseline / 비교군 전환. 비교군이 없으면 숨긴다.
  - 탭: 조직도 · 사람·성향 · 업무 · 하루 일정 · 실험 설명 · YAML
    - **조직도:** `reports_to` 트리를 들여쓴 목록으로 보여 준다. 부서 색 점을 붙인다.
    - **사람·성향:** 이름, 부서, 역할, DISC, `communication_style` / `pressure_response` / `conflict_engagement_style`.
    - **업무:** 핵심 업무, 프로젝트, 낮에 들어오는 일. 공수·마감·결재 단계를 보여 준다.
    - **하루 일정:** `engine.meetings`, `shocks`, `weekly_operations.blocks`를 시간순으로 보여 준다. 시각은 9:00 + 15분 × tick.
    - **실험 설명:** 가설, 측정, 행동 조작 점검, 실험 id.
    - **YAML:** `view().files`를 파일별로 보여 준다(읽기 전용, 복사 버튼).
  - 아래 줄: 검사 상태(통과 / 오류 n개)와 **"비교군과 다른 점"**.
    - 의도한 요인만 바뀌었으면 ✓와 요인별 개수를 보여 준다.
    - 요인 밖 차이가 있으면 경고와 경로 목록을 보여 준다.
  - **저장 버튼**
    - 두 버전 모두 오류가 없을 때만 켠다.
    - 요인 밖 차이가 있으면 확인 대화상자를 띄운 뒤 `accept_outside: true`로 저장한다.
    - 저장하면 토스트를 띄우고, "라이브에서 실행" 링크(`/`의 라이브 대화상자)를 보여 준다.
- **Demo 설정·키 없음**
  - 보내기 버튼을 끄고 이유를 한 줄로 보여 준다(`/api/settings`의 `provider`와 `openai_key`).
  - 기존 초안 보기와 저장은 된다.
- **공통**
  - 테마와 프레임은 메뉴 페이지(`menu.css` 토큰, `applyTheme`)를 따른다.
  - 휴대폰 폭에서는 대화와 미리보기를 위아래로 쌓는다.

- [ ] **Step 1: Build**

Run: `cd viz && npm run build`

Expected: tsc 오류 없음. `dist/create.html`이 생긴다.

- [ ] **Step 2: Drive it**

`conflict-server`를 새로 띄우고 FakeLLM 없이 다음을 확인한다.
- 메뉴 → 시나리오 생성 → 변형(`r10_human`) → 초안이 열리고 baseline 미리보기 6개 탭이 그려진다.
- 개발용으로 `/api/drafts` 초안 파일에 손으로 variant를 넣은 경우 "다른 점"이 보인다.
- 폭 1440·390에서 헤드리스 Chrome 스크린샷을 찍는다.

유료 호출은 하지 않는다.

- [ ] **Step 3: Commit**

`feat(viz): scenario generator screen — chat and preview`

---

### Task 9: 실제 한 번 (사용자 확인 후)

유료 호출이므로 사용자에게 먼저 묻고, 승인을 받은 뒤에만 한다.

- [ ] **Step 1:** 서버에서 OpenAI provider로 다음 두 경우를 생성한다. 토큰 수를 기록한다.
  - 변형: `r10_human`, 요인 "성향"(HDS-003을 무례한 피드백으로)
  - 처음부터: 8명, 3개 팀, md 1개
- [ ] **Step 2:** 저장한다. `uv run conflict-company-validate gen_<slug>`와 `ALLOW_PAID_API_EXPERIMENTS=1` 없이 demo 1일 run(`conflict-company-experiment gen_<slug>_var --backend demo --pilot --days 1`)이 끝나는지 본다.
- [ ] **Step 3:** 프롬프트 조정이 필요하면 고친 뒤 커밋한다: `fix(generator): prompt tuning from the first real drafts`

---

## Self-Review 메모

- **spec 대응**
  - §2 두 모드·짝·검토 두 겹은 T5다.
  - §4.1은 T1·T3, §5.3은 T4 `diff`, §5.4는 T5 프롬프트다.
  - §6은 T2·T6, §7은 T5, §8은 T5(초안 저장)·T6(저장)이다.
  - 반목표 "검증 실패가 목록에 나타남"은 T6의 거부와 카탈로그의 건너뛰기로 막는다.
  - 반목표 "유료 호출"은 T7의 demo 거부와 T9 승인으로 막는다.
- **맵 생성은 비목표라 다루지 않는다.** 사무실은 `large_korean_enterprise`로 고정한다.
