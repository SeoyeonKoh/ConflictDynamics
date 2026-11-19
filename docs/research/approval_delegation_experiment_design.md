# 실험 설계안 — 결재 집중(단일 결재자) vs 범위별 위임 vs 복수·교차 위임

작성 2026-11-19 · 읽기 전용 조사(코드·YAML 수정 없음) · 근거는 모두 저장소 내 file:line

---

## 0. 먼저 짚어 둘 사실 (설계를 바꾸는 발견)

1. **현행 r10 프리셋은 이미 "범위별 위임" 구조다. 단일 결재자 구조가 아니다.**
   `conf/personas/korean_enterprise_10_ko.yaml`의 권한은 다음과 같다.

   | ID | 이름 | 부서/직책 | assign | approve·reject |
   |---|---|---|---|---|
   | HDS-001 | 김민재 | 제품전략 / 통합 제품 리드(team_manager, 최상위) | cross_function | release (+evaluate all_agents) |
   | HDS-002 | 박소연 | 제품전략 / 선임 상품기획자(lead) | product_planning | requirements |
   | HDS-005 | 정태우 | 소프트웨어 / 소프트웨어 리드(lead) | software | architecture (+approve deployment_readiness) |
   | HDS-011 | 송아린 | 제품경험 / 제품 경험 리드(lead) | design | experience_design |
   | HDS-014 | 서동현 | 품질 / 품질 엔지니어링 리드(lead) | quality | quality_signoff |
   | HDS-003, 006, 008, 013, 015 | 팀원 | — | 없음 | 없음 (`titles`가 비어 있어 권한 0, `company_runtime.py:300`) |

2. **r10에서 HDS-001이 병목이 된 것은 "유일한 보유자"라서가 아니라 엔진의 대체 경로 때문이다.**
   `Org.signers`(`src/conflict_sim/environment/org.py:210-232`)의 동작은 다음과 같다.
   - scope 보유자 중 "작업에 가까운 사람"(담당자, 담당자보다 많이 일한 사람)을 뺀다.
   - 남는 결재자가 없으면 담당자의 상위 관리자를 결재자로 추가한다. 반려가 `MAX_RETURNS=2`회(`org.py:8`) 쌓여도 추가한다.
   - scope 보유자가 아무도 없으면 태스크의 `reviewers` 명단이 결재한다.
   - 그래서 **리드가 자기 scope 과업을 직접 맡으면**(T05·T09·T13, 각 프로젝트 리드의 자기 단계) 결재가 모두 HDS-001로 올라간다.
   - 메모리 기록(r10 2026-10-06)과 일치한다. "P1-arch review t11→end, T06 review t23→t28", v6에서 "김민재 6/13 approvals".
   - `docs/research/org_structure_literature_review.md:122`는 "HDS-001 단독 결재자 = 단일 결재자 수준"이라고 썼는데, 이는 **부정확하다**. 실제로는 "부분 위임 + 상위 대체 경로로 생긴 병목"이다.

3. **현행 매핑에는 구멍이 있다(`company_runtime.py:34-48` `TASK_AUTHORITY_SCOPE`).**
   - T10 `deployment_checklist`: 아무도 보유하지 않는다. HDS-005가 가진 것은 `deployment_readiness`라서 이름이 어긋난다. 결과적으로 `reviewers`(HDS-005, HDS-014)가 결재한다.
   - T12 `launch_plan`: 보유자가 없어 `reviewers`(HDS-001, HDS-011)가 결재한다.
   - 프로젝트 단계 scope `"project"`(`company_runtime.py:397`): 보유자가 없다. 프로젝트 리드가 결재하고, 리드 본인의 단계는 리드의 상관(대개 HDS-001)이 결재한다.
   - T01·T02: scope가 없어 검토 없이 바로 done이 된다(`org.py:280`). 모든 조건에서 상수다.

4. **시나리오 YAML만으로는 `authorities`를 바꿀 수 없다.**
   - `C15Scenario`(`company_runtime.py:127-171`)에는 에이전트 권한 필드가 없다.
   - 권한은 프리셋(`conf/company/<preset>.yaml` → `/personas/<preset>`, `/environment/org/<preset>`)에서 온다(`company.py:358`).
   - 따라서 조건마다 **페르소나 파일 1개 + 회사 프리셋 1개 + 시나리오 1개**를 새로 만든다. org·office 파일은 기준선 것을 그대로 참조한다.
   - 제약: evaluate 보유자는 `rules.evaluation_authority`(=[HDS-001])와 같아야 한다(`company.py:276-282`). 그러니 모든 조건에서 HDS-001의 evaluate를 유지한다.

5. **에이전트가 권한을 아는 경로는 태스크 뷰의 `can_approve`/`can_reject`뿐이다(`environment/__init__.py:391-400`).**
   - 페르소나 서술(`_agent_spec`, `company_runtime.py:431-465`)에는 authorities가 문장으로 들어가지 않는다.
   - 그래서 조작이 프롬프트의 성격 묘사를 오염시키지 않는다. 장점이다.

이 사실들 때문에 설계를 다음 3수준으로 잡는다.
- **S(단일 집중)**: 새로 만드는 조작 조건.
- **D(범위별 위임)**: 현행 프리셋을 그대로 쓰는 통제 조건이자 r10 병목 재현용.
- **M(복수·교차 위임)**: 대체 경로를 닫는 조건.

---

## 1. 연구 질문과 가설

**RQ.** 승인 권한을 한 사람에게 모을 때와 팀장들에게 범위별 또는 교차로 나눌 때, 같은 일·같은 사람·같은 일정에서 (a) 승인 대기와 처리 속도, (b) 결재자 부하, (c) 결재를 둘러싼 갈등이 어떻게 달라지는가?

**근거 연결.**
- 상급자 과부하일수록 위임의 이익이 커진다(Aghion & Tirole 1997, T7-01).
- 여러 층을 거치는 과업은 대기 지연이 길다(Beggs 2001, T7-08).
- 소수에게 협업 요청이 몰리면 병목이 생긴다(Cross, Rebele & Grant 2016, T4-11, 실무 근거).
- 부하는 평균보다 분산으로 본다(T3-13).
- 관찰 근거: r10에서 HDS-001이 상위 대체 결재자가 되며 P1-arch가 t11부터 끝까지 review, T06이 5틱 대기, P1 0/6을 기록했다.

| | 가설 | 방향 | 주 지표 |
|---|---|---|---|
| **H1 (효율)** | 결재 집중도가 높을수록 승인 대기가 길고 완료가 줄어든다 | waiting_approval·리뷰 대기: **S > D > M**, 코어 완료·기한 준수: **S < D ≤ M** | `idle.counts.waiting_approval`, 리뷰 대기 틱, `tasks.completion_pct`, `on_time` |
| **H2 (부하 편중)** | 집중 구조에서 결재자 스트레스가 오르고 구성원 간 스트레스 분산이 커진다 | HDS-001 최종 stress·전체 분산: **S > D > M** | `stress.agents[HDS-001]`, `stress.std`(또는 max−min) |
| **H3 (갈등)** | 집중 구조에서 결재자를 향한 부정 관계와 불만이 는다. 복수 결재에서는 "누가 승인하나"류 과정 갈등이 상대적으로 는다(경쟁 예측) | 결재자 향 부정 관계·grievance: **S > D > M**. 역할 모호 발화: **M ≥ D** | `relations.conflict_pairs`, `negative_pairs`, `grievances`, `changes`의 HDS-001 향 delta, 역할 모호 발화 수 |

H3의 두 번째 부분은 문헌 근거가 약하다(검토문서 §4 표 6행의 "예측 근거 약함"). 탐색적 가설로 표시한다.

---

## 2. 통제 변수와 조작 변수

### 2.1 베이스라인 선정: **`r10_human` 권장**

| 후보 | 장점 | 단점 | 판단 |
|---|---|---|---|
| **r10_human** | 현재 주력 프롬프트 스타일(human, 이름·업무명). v6에서 self-approval 0, 리뷰 대기 최대 5로 엔진 결함이 정리된 상태. 1일 34틱이라 저렴함(메모리 기준 r10 1회 ≈1.7M in/61k out). HDS-001 병목이 바로 이 시나리오 계열에서 관찰됨 | 하루라 결재 사건 수가 적음(코어 13개 검토 + 프로젝트 단계 23개) | **주 실험** |
| r10_documents_ko | 병목이 처음 관찰된 원본 | engine 프롬프트 스타일(ID 노출)이라 이미 은퇴한 방향. human과 결과 차이가 큼(core 9/15 vs 3~11/15) | 비권장 |
| r10_midweek | 주중 시작, `extra_tasks` 도착 업무로 결재 사건이 더 많음 | extra_tasks의 `assign_scope`를 조건별 매핑과 따로 맞춰야 함. 변동성도 큼 | 2차(견고성) |
| r10_enterprise_weekly | 6일, 주간 운영, 결재 사건 최다 | 911줄 규모라 교란 요인이 많고 1회 비용이 큼 | 3차(외적 타당도), 지금은 보류 |

### 2.2 고정할 것 (Ceteris Paribus)

변형 시나리오는 모두 `extends: r10_human`으로 만든다. 그러면 다음이 기준선과 바이트 단위로 같다.

- **인원**: 10명. `reports_to`·부서·직책·DISC·성향·backstory 모두 기준선 페르소나 그대로. authorities 블록만 바꾼다.
- **태스크·의존성·기한·materials**: `task_runtime`, `unassigned`(T04, T05, T06, T09, T12), projects P1/P3/P4/P12. 모두 상속.
- **태스크 scope**: `TASK_AUTHORITY_SCOPE` 코드 기본값 그대로. org 파일은 기준선 `korean_enterprise_10_ko`를 그대로 참조한다.
- **assign 권한**: 세 조건 모두 동일(위 표). 배정 흐름이 함께 바뀌는 교란을 막으려고 **approve·reject만 조작**한다.
- **회의**: kickoff t1, results_review t26, `rule: everyone`. 상속.
- **쇼크·개입**: `shocks: []`, `interventions: []`. 상속.
- **시드**: 상속값. 단, 실 API에서는 `--pilot`이 `seed_offset=0`으로 고정한다(`experiment.py:496-501`).
- **일수**: `max_days: 1`. `--days`는 지정하지 않는다.
- **prompt_style**: human.
- **모델·백엔드·임베딩 백엔드**: 조건 간 동일하게 고정한다.

주의: `load_c15_scenario`의 `extends`는 **최상위 키 얕은 병합**이다(`company_runtime.py:186-195`).
- 변형 YAML에 `engine:`을 쓰면 회의 블록 전체가 교체된다.
- 그러니 변형에는 `engine`을 **쓰지 않는다**. 상속된 `engine.id`는 `r10_human`으로 남는다.
- 실행 디렉터리 구분은 시나리오 `id`와 `--output-root`로 한다.
- 만약 `engine.id`도 조건별로 달라야 한다면 r10_human의 engine 블록을 통째로 복사한 뒤 id만 바꾼다. 이후 diff로 meetings 동일성을 확인한다.

### 2.3 조작 변수: `authorities` 매핑 초안

새 파일은 세 종류다. 이름은 제안이다.
- `conf/personas/korean_enterprise_10_ko_auth_{single,cross}.yaml`: 기준선 복사본에서 아래 블록만 교체한다.
- `conf/company/korean_enterprise_10_ko_auth_{single,cross}.yaml`: defaults의 `/personas`만 새 파일로 바꾸고, office·org는 기준선을 그대로 쓴다. `preset_id`는 새 값으로 둔다.
- `conf/scenario/company_c15/r10_auth_{single,scoped,cross}.yaml`

**D: 범위별 위임 (통제, 현행 그대로)**. 프리셋 `korean_enterprise_10_ko`를 쓰고 파일 변경은 없다. 시나리오 `r10_auth_scoped`는 r10_human과 id·experiment 블록만 다르다. 사실상 r10_human의 재실행이다.

**S: 단일 결재자 (조작)**. HDS-001이 모든 scope를 승인·반려한다.
- `Org.can`은 `cross_function`/`all_agents`를 모든 scope에 매칭한다(`org.py:176`).
- 그래서 "project" scope까지 HDS-001이 보유하게 된다. 프로젝트 단계의 named reviewer 경로도 닫힌다.

```yaml
# HDS-001
authorities:
- kind: assign
  scope: cross_function
- kind: approve
  scope: cross_function
- kind: reject
  scope: cross_function
- kind: evaluate
  scope: all_agents
# HDS-002
authorities:
- kind: assign
  scope: product_planning
# HDS-005
authorities:
- kind: assign
  scope: software
# HDS-011
authorities:
- kind: assign
  scope: design
# HDS-014
authorities:
- kind: assign
  scope: quality
# 팀원(003/006/008/013/015): authorities: [] (변경 없음)
```

리드에게 assign을 남기면 `grants`가 비지 않는다. 그래서 `titles` 대체 경로를 타지 않고 approve가 확실히 거부된다(`org.py:173-180`).

**M: 복수·교차 위임 (조작)**. 모든 scope를 리드 2인 이상이 보유하고, 구멍(T10·T12·project)도 메운다.
- 짝은 기존 `reviewers`·RACI의 consulted 관계에서 골랐다. 페르소나 입장에서 그럴듯한 조합이다.
- 리드가 자기 과업을 맡아도 다른 보유자가 남는다. 그래서 상위 대체 경로(HDS-001)가 작동하지 않는다.
- 예외는 HDS-001 본인이 담당하는 T14·T15다. 이 둘은 전 조건에서 자기 결재로 상수다.

```yaml
# HDS-001  (릴리스만 + 평가)
- {kind: assign,   scope: cross_function}
- {kind: approve,  scope: release}
- {kind: reject,   scope: release}
- {kind: evaluate, scope: all_agents}
# HDS-002  요구사항 1차, 경험설계·출시계획 2차, 프로젝트
- {kind: assign,  scope: product_planning}
- {kind: approve, scope: requirements}
- {kind: reject,  scope: requirements}
- {kind: approve, scope: experience_design}
- {kind: reject,  scope: experience_design}
- {kind: approve, scope: launch_plan}
- {kind: reject,  scope: launch_plan}
- {kind: approve, scope: project}
- {kind: reject,  scope: project}
# HDS-005  아키텍처·배포 1차, 품질 2차, 프로젝트
- {kind: assign,  scope: software}
- {kind: approve, scope: architecture}
- {kind: reject,  scope: architecture}
- {kind: approve, scope: deployment_checklist}
- {kind: reject,  scope: deployment_checklist}
- {kind: approve, scope: quality_signoff}
- {kind: reject,  scope: quality_signoff}
- {kind: approve, scope: project}
- {kind: reject,  scope: project}
# HDS-011  경험설계·출시계획 1차, 요구사항 2차, 프로젝트
- {kind: assign,  scope: design}
- {kind: approve, scope: experience_design}
- {kind: reject,  scope: experience_design}
- {kind: approve, scope: launch_plan}
- {kind: reject,  scope: launch_plan}
- {kind: approve, scope: requirements}
- {kind: reject,  scope: requirements}
- {kind: approve, scope: project}
- {kind: reject,  scope: project}
# HDS-014  품질 1차, 아키텍처·배포 2차, 프로젝트
- {kind: assign,  scope: quality}
- {kind: approve, scope: quality_signoff}
- {kind: reject,  scope: quality_signoff}
- {kind: approve, scope: architecture}
- {kind: reject,  scope: architecture}
- {kind: approve, scope: deployment_checklist}
- {kind: reject,  scope: deployment_checklist}
- {kind: approve, scope: project}
- {kind: reject,  scope: project}
```

**과업별 예상 결재자.** 일반 배정(담당자만 작업) 기준이다. ★는 HDS-001로 올라가는 칸이다.

| 과업 (scope) | 일반 담당 | S | D (현행) | M |
|---|---|---|---|---|
| T03 requirements | HDS-003 | ★001 | 002 | 002, 011 |
| T04 experience_design | HDS-013 | ★001 | 011 | 011, 002 |
| T05 architecture | HDS-005 | ★001 | ★001 (리드 본인 → 상위) | 014 |
| T06/T07/T08 architecture | 006/006/008 | ★001 | 005 | 005, 014 |
| T09 quality_signoff | HDS-014 | ★001 | ★001 | 005 |
| T10 deployment_checklist | HDS-008 | ★001 | 005, 014 (reviewers) | 005, 014 |
| T11 quality_signoff | HDS-015 | ★001 | 014 | 014, 005 |
| T12 launch_plan | HDS-002 | ★001 | ★001, 011 (reviewers) | 011 |
| T13 quality_signoff | HDS-014 | ★001 | ★001 | 005 |
| T14/T15 release | HDS-001 | 001 자기결재 | 001 자기결재 | 001 자기결재 |
| P1/P3/P4 단계 (project) | 부서 순번 | ★001 | 프로젝트 리드, 리드 본인 단계는 ★001 | 다른 리드 3~4인 |
| P12 단계 (project) | 제품전략 순번 | ★001 | 003(팀원 리드)·002, 001 단계면 자기결재 | 리드 4인 중 비근접자 |

**M의 한계(정직하게 기록).** M은 "보유자 수 증가"와 "구멍 메우기(T10 이름 불일치, T12, project)"를 동시에 바꾼다. 두 효과를 분리하려면 선택 조건 **D′(구멍만 메운 범위별 위임)**를 추가한다.
- D′는 D에 `deployment_checklist→005`, `launch_plan→011`, `project→각 리드`만 더한 조건이다.
- 그러면 D→D′는 구멍 효과, D′→M은 복수 보유 효과로 읽을 수 있다.
- 예산이 부족하면 S·D·M 3수준만 돌린다.

### 2.4 변형 시나리오 YAML 초안

```yaml
# r10_auth_single.yaml
extends: r10_human
id: r10_auth_single
preset: korean_enterprise_10_ko_auth_single
research_question: 승인 권한을 한 사람에게 모으면 같은 일에서 승인 대기·결재자 부하·갈등이 어떻게 변하는가? (r10_auth_scoped와 비교)
manipulated_variable: 'authorities: approve·reject를 HDS-001 단일 보유(cross_function)로 집중; assign은 기준선과 동일'
fixed_variables: [personas_except_authorities, reports_to, org_tasks_and_scopes, task_runtime, unassigned, projects, materials, meetings, shocks, seed, max_days, prompt_style, model]
manipulation_check:
- ten agents initialize
- five tasks start unowned
- two everyone-speaks meetings are scheduled
- HDS-001 is the only holder of approve and reject for every task scope
- no lead holds approve or reject; every lead keeps the same assign scope as the baseline
- every task in review lists only HDS-001 as signer (T14/T15 self-signed)
experiment:
  id: auth_delegation
  role: variant
  baseline: r10_auth_scoped
  factor: structure
  hypothesis: 단일 결재 집중 시 승인 대기 휴식과 리뷰 대기가 늘고 완료율이 떨어지며 HDS-001 스트레스와 그를 향한 부정 관계가 오른다.
  measures:
  - {metric: rest_ratio, subject: all, direction: up}
  - {metric: task_completion, subject: all, direction: down}
  - {metric: stress, subject: HDS-001, direction: up}
  - {metric: relation, subject: all, toward: HDS-001, direction: down}
  behaviour_checks:
  - leads ask HDS-001 for sign-off instead of approving themselves
```

`r10_auth_cross.yaml`은 preset·id·manipulated_variable·hypothesis·measures 방향만 반대로 둔다. `r10_auth_scoped.yaml`은 `preset: korean_enterprise_10_ko`, `experiment.role: baseline`, `baseline: r10_auth_scoped`로 둔다. (`Measure` 스키마는 `company_runtime.py:110-114`, `Experiment`는 `:117-124`에 있다.)

---

## 3. Manipulation Check와 측정 지표

### 3.1 Manipulation check (실행 전 결정론 검사 + 실행 후 검사)

**실행 전 (demo 백엔드, 비용 0).**
1. `uv run conflict-company-validate korean_enterprise_10_ko_auth_{single,cross}`: 프리셋 교차참조 검증(evaluate=evaluation_authority, authority kind 유효성).
2. `--dry-run`의 `config.environment.org`에서 에이전트별 authorities를 뽑아 §2.3 표와 대조한다.
3. 세 조건의 resolved config를 diff한다. **에이전트 authorities 외 차이 0**이어야 한다. 허용 차이는 id, preset_id, experiment뿐이다.
4. 작은 스크립트(또는 테스트)로 각 태스크를 review 상태로 두고 `Org.signers`를 호출한다. §2.3 "예상 결재자" 표와 일치하는지 확인한다(담당자 = 기준 owner, worked_by = owner만).
5. demo 백엔드로 3 replicates를 실행해 엔진이 끝까지 도는지, 리뷰 이벤트가 생기는지 확인한다.

**실행 후 (각 실 API 실행).**
- `record.approved_by`(`org.py:303-326`, frames 보드의 task record) 분포에서 HDS-001 승인 비율을 본다.
  - S: T14·T15 포함 ≈100%여야 한다.
  - D: 기존 관찰 ≈ 6/13 수준이다.
  - M: T14·T15 2건만 HDS-001이어야 한다.
  - 기대치에서 크게 벗어나면 그 실행은 조작 실패로 표시한다.
- `rejected` 이벤트의 "may not approve/reject" 거부 수를 본다. S에서 리드가 자기 습관대로 승인을 시도한 흔적이 보이면 조작이 체감됐다는 증거다.
- self-approval 0건(T14·T15 제외)인지 확인한다. v6 수정이 유지되는지 보는 회귀 검사다.

### 3.2 핵심 지표 (`src/conflict_sim/run_summary.py`가 바로 주는 것)

| 구분 | 필드 | 위치 | 가설 |
|---|---|---|---|
| 승인 대기 휴식 | `idle.counts.waiting_approval`, `idle.share_of_idle.waiting_approval`, `idle.per_agent[*].waiting_approval` | `idle_summary` `:342-385`, 분류 `classify_rest` `:286-310` | H1 |
| 기타 휴식 | `idle.counts.no_workable / other_idle`, `idle.idle_pct` | 같음 | 대조(구조 효과가 승인 대기에만 실리는지) |
| 완료·기한 | `tasks.completion_pct`, `done`, `on_time`, `late`, `overdue_open`, `mean_progress_pct` | `task_summary` `:180-219` | H1 |
| 스트레스 | `stress.mean/max/…`(`stats` `:104-115`), `stress.agents[HDS-001]`, `stress.timeline` | `stress_summary` `:406-437` | H2 |
| 관계·갈등 | `relations.conflict_pairs`(≤−0.2), `negative_pairs`, `mutual_negative_pairs`, `grievances`, `changes` | `relation_summary` `:448-500` | H3 |

### 3.3 추가 지표 (run_summary에 없음, events/frames에서 계산)

- **리뷰 대기 틱**: 과업별 `done_tick − review_tick`과 미완료 review의 `last_tick − review_tick`. 평균, 최대, 결재자별로 본다. H1의 가장 직접적인 지표다.
- **결재 집중도**: approved_by의 HDS-001 비율과 허핀달 지수. 조작 확인 겸 매개변수다.
- **크리티컬 패스 도달**: 코어 T01~T15 중 done 수(기존 "core n/15"), T15 도달 여부.
- **반려 수**: `record.rejections` 길이 합. M에서 결재자 간 기준 불일치로 늘어날 수 있다.
- **결재자 측 유휴**: run_summary docstring이 밝히듯 대기하는 쪽만 집계한다. 결재자가 쉬는 동안 리뷰가 쌓인 틱 수를 따로 센다(review 상태 과업이 있는데 signer가 rest한 틱).
- **스트레스 분산**: `stress.agents`로 표준편차를 계산한다. 결재자 대 대기자(리뷰 중인 과업의 팀원)로 나눈 평균도 본다(T3-13).
- **역할 모호 발화**: 발화 중 "누가 승인/결재/사인", "누구한테 올려" 같은 패턴 빈도. 검토문서 §6의 대리 지표다.
- **결재자를 향한 대화량**: HDS-001을 대상으로 한 talk·chase 수(`chase_counts`).
- **비용**: 입·출력 토큰과 act 호출 수. 조건 간 비용 차이 자체도 결과다.

---

## 4. 실행 계획과 타당도 위협

### 4.1 일수·반복 수

- **days = 1**(시나리오 기본값). r10은 모든 due가 34틱 이하인 압축 하루라서 `--days`를 늘려도 새 일이 생기지 않는다. 휴식만 부풀어 waiting_approval 비율을 왜곡한다.
- **반복**:
  - 엔진 제약상 실 API(`openai`/`claude`)는 `--pilot` 단일 실행만 허용된다(`experiment.py:478-481`). 그래서 반복은 **조건별로 `--output-root`를 달리한 별도 호출**로 쌓는다.
  - 시드는 고정이고 변동은 LLM 샘플링에서만 온다. 이것이 측정할 "조건 내 분산"이다.
  - 1단계(파일럿): 조건당 1회 × 3조건으로 조작 확인과 효과 방향을 본다.
  - 2단계(본실험): **조건당 5회**를 권장한다. 최소 3회다. 검토문서 §5 기준으로 d=1.0 검출에 18~26회가 필요하므로, 이 규모는 큰 효과만 겨냥한다.
  - 판단 규칙은 "조건 간 차이 > 조건 내 범위(min~max)"다. 단일 실행 비교로 결론 내리지 않는다.
- **순서**: S→D→M을 한 묶음으로 섞어(interleave) 돌린다. API 쪽 시간대 변동이 한 조건에 몰리지 않게 하려는 것이다.
- **D 조건은 반드시 새로 돌린다.** 기존 r10_human v6 결과를 재사용하면 커밋, 모델 버전, 날짜가 달라져 교란된다.

### 4.2 비용과 백엔드 주의점

- r10 1회 ≈ 1.7M in / 61k out(메모리, r10_documents_ko 기준). human 스타일은 비슷하거나 약간 많다.
  - 3조건 × 5회 ≈ 26M 입력 토큰.
  - 파일럿 3회 ≈ 5M.
- 유료 실행에는 `ALLOW_PAID_API_EXPERIMENTS=1`과 `--max-total-tokens 3000000`이 필요하다. 기본 500k 상한이면 t13 근처에서 멈춘다(메모리 기록).
- **OpenAI**:
  - `--model-decide`/`--model-speak`/`--model-embed`를 명시해 세 조건 모두 같은 모델 ID로 고정한다.
  - retrieval cache는 조건 간 같은 설정(기본 on)으로 둔다.
- **Claude(구독 경로, Agent SDK)**:
  - `--claude-max-concurrent`를 조건 간 같은 값으로 고정한다. 동시성은 틱 내 판단 순서와 타임아웃에 영향을 줄 수 있다.
  - 임베딩은 `--embed-backend`(openai 또는 local)를 명시해 고정한다. 커밋 a2f9acf 이후 openai 임베딩의 기본 모델명이 바뀌었다.
  - 구독 한도에 걸려 중단되면 `--resume`으로 이어 간다. 이어 간 실행은 표시해 두고, 민감도 분석에서 제외해 본다.
- OpenAI와 Claude 결과를 한 조건 안에서 섞지 않는다. 백엔드는 블록 요인으로 따로 분석한다.

### 4.3 타당도 위협

| 위협 | 내용 | 대응 |
|---|---|---|
| 조작 혼입(M) | M은 보유자 수와 구멍 메우기를 함께 바꿈 | 선택 조건 D′ 추가로 분해(§2.3) |
| 기준선 정의 | 문헌 검토의 "r10 = 단일 결재자" 서술이 사실과 다름 | 보고서·노트에 "D = 부분 위임 + 상위 대체"로 정정 표기 |
| 배정 교란 | 권한이 바뀌면 kickoff 배정(unassigned 5건)이 달라져 "누가 담당이냐"가 조건마다 달라짐 | assign 고정. 실제 owner 분포를 공변량으로 기록하고, 조건 간 배정이 크게 다르면 층화해 비교 |
| 천장·바닥 | 하루 34틱에 크리티컬 패스 16틱이라 S에서 바닥 효과(코어 2~3/15) 가능 | 리뷰 대기 틱처럼 연속 지표를 주 지표로. 필요하면 2차로 r10_midweek 반복 |
| 결재자 측 유휴 미집계 | run_summary는 대기 측만 봄 | §3.3 결재자 유휴 지표를 별도 계산 |
| LLM 긍정·순응 편향 | 갈등이 덜 나고 위계에 과순응 → H3 효과 과소 | 갈등 효과는 하한으로 해석(검토문서 §7) |
| 비결정성 | 같은 시드·설정도 실행마다 다름(Atil 외 2024) | 조건당 5회, 범위 비교 |
| 프롬프트 민감도 | can_approve 표시 방식이 행동을 좌우할 수 있음 | 조건 간 프롬프트 템플릿 동일 유지. 결재 거부 메시지 수를 기록 |
| 상수 자기결재 | T14·T15는 전 조건 HDS-001 자기결재 | 상수이므로 비교에서 빼고 보고 |
| 코드 변화 | 실행 사이 커밋이 바뀌면 교란 | 실험 전 커밋을 고정(태그)하고 manifest의 커밋 해시 확인 |
| 얕은 extends 병합 | 변형에 engine을 쓰면 회의가 통째로 바뀔 위험 | 변형에서 engine 생략. resolved config diff로 검증(§3.1-3) |

### 4.4 실행 순서 요약

1. 프리셋 2개, 페르소나 2개, 시나리오 3개를 작성한다. (D′는 선택)
2. validate, dry-run diff, signers 단위 검사, demo ×3을 돌린다.
3. 실 API 파일럿을 S·D·M 각 1회 돌리고 조작 확인을 통과시킨다.
4. 본실험을 조건당 4회 추가해 총 5회로 interleave 실행한다.
5. run_summary 지표와 §3.3 추가 지표로 집계하고, 조건 간 차이를 조건 내 범위와 대조한다.
