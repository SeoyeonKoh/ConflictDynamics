# Intervention Framework Proposal

작성일: 2026-10-05 · 상태: **회의 검토용 최종 구조(안), 구현·효과 검증 전**
검토 기준: 로컬 HEAD `a410ec0` 및 현재 C14–C16 코드·설정.
이번 변경은 이 문서만 추가한다. simulation code/config 변경, API 호출, token optimization, CRAFT 실행, intervention experiment는 하지 않았다.

## 1. 추천 framework

**ICMS를 조직 시스템의 상위 원칙, DSD를 절차 배치·평가의 설계 원칙, Interests–Rights–Power(IRP)를 개입 mechanism의 분류로 사용한다.** 그 위에 프로젝트의 Preventive / Early / Post 단계를 교차해 3×3 design space를 만든다.

**이 3×3은 선행문헌의 공식 단일 모델이 아니다.** ICMS의 조직 통합 원칙, DSD의 설계 원칙, IRP의 해결 방식 분류를 ConflictDynamics 실험에 맞게 결합한 operational framework다. 시간 단계, 특정 actor·tick·threshold·측정 지표는 프로젝트 제안이다.

문서의 근거 표기:

- **[L] Literature-supported**: 출처가 직접 지지하는 개념·절차.
- **[O] Project operationalization**: 코드에 맞춘 분류·설계·측정 정의.
- **[H] Proposed hypothesis**: 효과가 아직 검증되지 않은 예상.

### 1.1 ICMS — 시스템 전체를 보는 원칙 [L]

SPIDR(2001), 인쇄 pp. 9–14에서 다음을 확인했다.

1. **Broad scope**: 직급·분쟁 종류에 관계없이 문제를 제기할 수 있는 선택지.
2. **Culture / early resolution**: 선의의 이견을 허용하고, 가능한 낮은 수준에서 직접 협상·조기 해결을 지원.
3. **Multiple access points**: 믿고 접근할 수 있는 여러 지원 경로.
4. **Multiple options**: Interests와 Rights 절차를 제공하고 필요하면 두 경로 사이를 이동.
5. **Support structures**: 교육·조정·관리 체계로 갈등관리를 일상 운영에 통합.

예방·문제 식별·해결을 연결한다는 해석은 원문과 부합한다. 그러나 일률적인 단계 통과를 요구하는 사다리나 “갈등은 항상 informal부터 처리”라는 규칙으로 해석하지 않는다. 원문은 자발성, 중립성, 권리 보호도 다룬다. 현재 simulation은 이러한 ICMS 전체를 구현한 조직이 아니라 일부 업무 갈등 개입을 실험하는 모델이다. [SPIDR 원문 PDF](https://mitsloan.mit.edu/shared/ods/documents/?DocumentID=3981), [서지·초록](https://dspace.mit.edu/entities/publication/9cb47107-1c9a-478b-866d-70aaa31c018f)

### 1.2 DSD — 진단·설계·운영·평가 [L]

Harvard PON은 Diagnose → Design → Implement → Evaluate를 설명하며, 조직에 맞는 저비용·덜 침습적인 접근을 먼저 고려하고 결과 만족·재발·관계를 평가한다. 이는 조직 시스템을 만드는 과정이다. **개별 사건이 반드시 이 네 단계를 밟는다는 뜻은 아니다.** [PON, What is DSD?](https://www.pon.harvard.edu/daily/dispute-resolution/what-is-dispute-system-design/)

Ury·Brett·Goldberg(1988), ch. 3, pp. 41–64의 설계 원칙은 Interests에 초점, 협상으로의 loop-back, 저비용 Rights/Power backup, 사전 협의·사후 feedback, 낮은 비용부터의 절차 배치, 동기·기술·자원이다. direct conversation → facilitation → mediation → formal review는 이를 적용한 **예시 경로**이며, 유일한 canonical 순서는 아니다. 더 강한 절차 뒤에도 협상으로 돌아올 수 있다. [원 논문 서지](https://doi.org/10.1111/j.1571-9979.1988.tb00484.x), [동일 저작 ch. 3 공개 열람본](https://fliphtml5.com/fzqli/dqct/Getting_Disputes_Resolved_-_William_l._Ury/)

### 1.3 IRP — 작동 mechanism과 trade-off [L/O]

| Mechanism | 원문 개념 [L] | 기업 업무 갈등에 적용 [O] | trade-off |
| --- | --- | --- | --- |
| Interests | 당사자의 underlying needs·concerns를 조정 | constraints·우선순위 논의, 공동 문제 해결, mediation | 관계·수용·재발 측면의 이점 가능. 시간·참여와 합의 가능성 필요 |
| Rights | 법·계약·규칙·정당한 기준으로 판단 | owner/reviewer/approval authority 확인, 절차 적용 | 기준 명확화 가능. 실제 needs가 해결되지 않거나 승패 구도가 생길 수 있음 |
| Power | 상대에게 의지를 관철할 능력을 통해 해결 | manager의 자원·due·담당자 결정 | 직접 실행 가능. 수용·공정성·관계 비용을 같이 평가해야 함 |

Ury 등은 transaction costs, satisfaction, relationship, recurrence의 네 기준을 사용한다. Interests가 대체로 저비용이라는 논지이지 항상 우월하다는 주장은 아니다. Rights/Power가 필요하거나 바람직한 경우도 있다. [1988 원문 ch. 1의 허가 재수록본, Reading 1.1, 인쇄 pp. 1–10 / PDF pp. 12–21](https://library.uniq.edu.iq/storage/books/file/Negotiation/1668074651neg.pdf#page=12)

**Manager의 모든 행위를 Power로 분류하지 않는다.** 합의를 도우면 Interests, 기존 기준을 설명하면 Rights, 배분·기한을 일방적으로 변경하면 프로젝트의 administrative Power다. 원문의 power contest와 정당한 관리권 행사도 동일 개념으로 단정하지 않는다. primary mechanism은 직접 작동 경로, secondary는 부수 경로로 기록한다.

### 1.4 Acas / CIPD 실무 근거와 범위 [L]

Acas의 33명 인터뷰 기반 연구와 연구자 해설은 early, voluntary dialogue, active listening, 안전한 문제 제기, manager skill을 강조한다. 이는 qualitative 실무 근거이며 causal effectiveness estimate가 아니다. 연구 보고서의 견해는 Acas의 공식 지침과도 구분한다. [Acas 연구 소개](https://www.acas.org.uk/research-and-commentary/workplace-conflict/defining-and-enabling-informal-workplace-conflict-resolution), [연구자 해설, 2025-06-30](https://www.acas.org.uk/the-power-of-informal-conflict-resolution-at-work)

CIPD(2025-09-24)는 mediation을 자발적·중립적 제3자 과정으로 설명하며, communication·관계 문제에 조기 또는 formal dispute 이후 활용할 수 있다고 한다. 심각한 allegation, 공식 investigation 요청, 옳고 그름의 판단이 필요한 경우는 부적합할 수 있다. **모든 harassment에 mediation이 금지된다는 식으로 확대하지 않는다.** 이 프로젝트는 serious HR/legal 사건을 핵심 실험에서 제외한다. [CIPD mediation factsheet](https://www.cipd.org/uk/knowledge/factsheets/mediation-factsheet/)

## 2. 현재 저장소 진단 [O: 코드 확인]

### 2.1 시나리오와 taxonomy

| Scenario | 실제 조작 | 주의점 / intervention 적합성 |
| --- | --- | --- |
| S0 | structural shock 없음, 20명·15-task DAG·2일 | shock control과 구분. 전체 갈등이 없다는 뜻은 아님 |
| S1 | day 0 tick 2, T01 forced_block_until=10 | dependency recovery의 coordination 비용. 정보 개입으로 강제 잠금은 못 해제 |
| S2 | tick 4, T14 due를 12 줄임 | due=62→50; scope/effort 동일. I2에서 +6이면 56 |
| S3 | tick 10, meeting_room capacity 10→4; tick 12 회의 | 현재 specialist/test resource 경쟁이 아니라 **회의 공간** 조작 |
| S4 | evaluation season=true, promotion_slots=1; tick 4 announcement | flag는 초기 config부터 true. announcement가 season의 최초 시작이라고 단정 불가 |

근거: `docs/research/C15_scenario_design.md`; `conf/scenario/company_c15/s0_baseline.yaml`, `s1_dependency_failure.yaml`, `s2_deadline_pressure.yaml`, `s3_resource_competition.yaml`, `s4_evaluation_season.yaml`; `environment/__init__.py:353–383`.

| Event | 선언된 conflict source | 현재 해석 |
| --- | --- | --- |
| E01 | task_dependency_failure | S1의 직접 조작 |
| E02 | deadline_compression | S2의 직접 조작 |
| E03 | scarce_resource_competition | S3에서는 room capacity로 축소 구현 |
| E04 | priority_disagreement | IRP 비교 후보; 이 이름의 자동 탐지기가 있다는 뜻은 아님 |
| E05 | role_ambiguity_or_overlap | P1의 이론적 target. 현재 S1은 잘못된 owner를 주입하지 않음 |
| E06 | unequal_workload_allocation | P2 target 후보. 현재 S2는 workload 불평등을 직접 조작하지 않음 |
| E07 | evaluation_or_promotion_salience | S4 조작; credit withholding의 자동 발생은 보장 안 됨 |
| E08 | information_delay_or_missing_handoff | P1/P3의 coordination target 후보 |
| E09 | public_criticism_or_face_threat | 대화 human coding 후보; 비판을 강제로 주입하지 않음 |
| E10 | ignored_or_refused_request | unanswered/outcome 기록과 연결 가능; 모든 rejection을 동일시하지 않음 |

E01–E10은 `conf/environment/org/large_korean_enterprise.yaml:220–270`의 design taxonomy다. 모든 event ID가 자동으로 검출·emit되는 runtime taxonomy라고 주장하지 않는다. 자연스러운 task prerequisite blocking은 tick 0부터 생길 수 있어 “blocked=true” 하나로 shock-induced conflict를 판정하지 않는다.

### 2.2 구현상 주요 제한

- `InterventionSpec`(`models.py:282–297`)는 day/tick/actor/task/target/amount 기반 fixed schedule이다. state trigger predicate, consent, mediator 역할, 발송할 clarification 본문 필드가 없다.
- `loop.py:442–483`는 tick-start에 schedule을 처리하고 그 뒤 environment.advance·perceive·act를 수행한다.
- `company_runtime.py:133–142`는 scenario 상속에서 **top-level shallow update**를 한다. 자식의 engine은 부모 engine 전체를 교체한다. 실제로 S1/S2/S4의 meetings=[]는 S0의 day-0 회의를 유지하지 않는다. 현재 S0–S4를 “shock 하나만 다른 모든 조건”으로 그대로 비교하면 meeting confound가 있다. 미래 비교는 각 S1 treatment/control의 완성된 resolved config를 대조해야 한다.
- I1/I3는 S1 seed와 task_runtime을 상속하고 I2는 S2를 상속한다. 서로 다른 S1과 S2를 같은 충격에 대한 mechanism 비교로 사용할 수 없다.
- `conf/experiments/c16/manifest.yaml`은 S0–S4 5조건 + intervention pair 3개, 조건당 3반복의 계획이다. pilot 실패 상태이며 real API attempt 3은 tick 5·503,945 tokens에서 중단됐다. 완성된 개입 효과 결과가 있는 것으로 취급하지 않는다.
- 조직은 HDS라는 synthetic organization이다. 특정 실제 한국 기업의 갈등 행동을 재현했다고 주장하지 않는다.

## 3. Final 3×3 intervention matrix [O]

행은 **사건의 진행 단계**, 열은 **개입의 primary mechanism**이다. 동일한 절차도 실행 시점에 따라 다른 행에 놓인다. Post가 항상 더 강한 개입이라는 뜻은 아니다. corporate example은 원리의 참고 사례이며 아래 cell의 개입을 그 기업이 그대로 시행했다는 주장이 아니다.

| Stage | Interests | Rights | Power |
| --- | --- | --- | --- |
| A Preventive | **P3 Dependency alignment**: 시작 전 constraints·expectation 논의. Primary I / secondary R 가능. CCE TALK를 직접 대화의 참고로 사용; 예방 시점은 프로젝트 설계. 기존 meeting primitive 활용 가능, agenda·수신 범위 설계 필요 | **P1 Role/handoff brief**: owner·review·approval·handoff 기준 재확인. Primary R / manager authority는 secondary P 가능. Alcoa의 여러 resolution option을 참고; RACI 사용의 직접 사례 근거는 아님. 현재 I1은 전송 기능 추가 필요 | **P2 Anticipatory allocation**: workload/resource 충돌 전에 배분. Primary P / 기준 공시는 secondary R. 선택 사례가 이 예방 배분을 직접 입증하지는 않음. 기존 workload/resource adjustment primitive가 있으나 권한·불변식·scope 점검 필요 |
| B Early / Informal | **Early check-in / joint problem solving**: objective sign 이후 관점·needs 확인. Primary I / manager P 가능. CCE TALK·SUPPORT, Acas. I3 primitive를 활용할 수 있으나 invitation·bounded session·당사자 선정 필요 | **Early role/process brief**: blocked/누락 요청 이후 기존 기준 확인. Primary R / secondary P 가능. Alcoa option 원리를 참고, 이 cell의 책임 확인 사례는 미확인. I1을 agent-visible briefing으로 수정해야 의미 있는 treatment | **Priority / temporary allocation decision**: constraint에 대응하는 권한 결정. Primary P / secondary R. 직접 corporate case는 확인하지 못함. I2 due +6, resource_adjustment 사용 가능 |
| C Post / Escalated | **Repair conversation / genuine mediation**: unresolved interaction 이후 관계·협의 복구. Primary I / impartial mediator면 P 최소화. CCE MEDIATION, CIPD. I3는 manager check-in까지 가능; genuine mediation은 2당사자+중립 actor·consent·confidentiality 설계가 추가로 필요 | **Neutral operational review**: 기록·규칙에 근거한 책임·절차 판단. Primary R / secondary I 가능. CCE arbitration은 formal backup 원리만 참고, simulation은 비법률 업무 review로 제한. neutral evaluator와 evidentiary protocol 미구현 | **Recovery reallocation / due decision**: 해결되지 않은 업무 병목을 권한으로 조정. Primary P / secondary R. 선택 사례는 특정 재배치/기한 변경 효과의 직접 근거가 아님. 기존 primitive는 있으나 owner 변경은 lifecycle=ready까지 바꿔 treatment 강도 주의 |

### Cell 검토 결론

- 9 cell은 이론과 양립하는 **design space**다. 직접 기업 evidence가 부족한 배분·RACI cell을 검증된 기업 프로그램으로 포장하지 않는다.
- A-R/B-R/C-R은 다른 세 개 mechanism이 아니라 **같은 역할·절차 명확화의 timing variant**로 묶는 것이 효율적이다.
- A-I/B-I/C-I의 overlap도 크다. mediation 명칭은 자발성·중립성·당사자 과정이 있을 때만 사용한다.
- 기존 Power primitive는 state를 직접 바꾸므로 정보·대화 treatment와 intensity를 같다고 볼 수 없다.
- multiple access points·manager training·ombuds는 framework layer의 원칙으로 남긴다. 이번 실험을 위해 새 HR actor나 vector DB 등을 만들지 않는다.

## 4. I1 / I2 / I3 재분류 [O]

| 기존 ID | 실제 작동과 위치 | Primary / Secondary | 제안 |
| --- | --- | --- | --- |
| I1 Manager Clarification | S1, tick 6. Early를 의도하지만 충돌 상태 기반 판정은 없음. `_apply_intervention`은 clarification=true만 반환하고 `_log`에 저장 | **현재는 mechanism 미구현**. 의도는 Rights; 실제 directive가 추가되면 Power | **Scheduled clarification marker**로 현재 능력을 표기. 후속 구현에서 agent-visible RoleBrief를 전달한 뒤 responsibility/process clarification로 명명 |
| I2 Deadline Adjustment | S2 tick 4 compression 뒤 tick 10 T14 due +6. scheduled structural response; Early 의도, Post 증거 없음 | **Power**, secondary Rights는 기준·이유가 실제 전달될 때만 | 유지 가능. lateness 비교는 original due=62 / compressed due=50 / adjusted due=56을 각각 구분 |
| I3 Private Mediation | S1 tick 8, HDS-001(manager)+HDS-005(software lead), 2인 private turn-taking. phase 전환까지 keep_open | **Interests-oriented 의도**, secondary Power(권한자 주도·강제 이동). genuine mediation 성립은 미확인 | **Manager–employee private clarification/check-in**으로 명칭 수정 제안. 기존 ID는 호환용 alias로 남길 수 있음 |

I1 근거: `loop.py:470–512`, `loop.py:833–835`는 log만 append한다. `_view:330–360`, `Agent.perceive:404–453`에는 intervention event를 agent 정보·memory로 전달하는 경로가 없다. 따라서 I1이 actual agent behavior를 바꾸는 책임 명확화라고 전제할 수 없다.

I3 근거: `loop.py:555–588`, `conversation.py:88–96`의 PRIVATE는 generic work conversation이다. 중립 third-party, 두 갈등 당사자의 관점 조정, consent, 합의 기록이 보장되지 않는다. T01 owner는 HDS-002이고 직접 handoff recipient는 HDS-012이다. HDS-005와 manager의 세션을 product–software 당사자 mediation이라고 자동 해석할 수 없다.

추가로 I3는 busy/공간 부족 시 조용히 return하지만 상위 함수는 private_session=true를 반환한다. **로그의 성공 flag 대신 실제 session 생성·참여·turn 수를 manipulation check**로 써야 한다. 이번에는 수정하지 않았다.

## 5. Missing interventions와 선택 우선순위 [O/H]

1. **P1 Preventive role/handoff brief — 최우선**: E01에 동반할 수 있는 책임·handoff 불확실성에 대응. E05를 S1에서 별도로 조작하지 않으므로 “role ambiguity 제거 실험”이라는 주장은 제한한다. 현재 task 정보가 이미 충분하면 효과가 없을 수 있다는 null도 유효하다.
2. **P2 Preventive workload/resource adjustment — 후속**: S2의 deadline 변경과 workload 재배분을 함께 넣으면 두 조작이 된다. S3에서도 room allocation과 specialist 경쟁을 혼동하지 않는다.
3. **P3 Preventive alignment conversation — 후속**: S1이 우선 후보. S3 coordination에는 타당하지만 session의 시간·token cost가 추가된다. S4는 공정한 기준과 정보 공개 범위가 먼저 확정돼야 한다.

P2/P3는 missing 영역을 설명하는 후보이며 이번 권장 실험에 동시에 넣지 않는다. 9 cell 전부를 실험하거나 S1–S4 전체를 cross product로 늘리지 않는다.

## 6. Corporate examples — 3개만 유지 [L]

### 6.1 Coca-Cola Enterprises SOLUTIONS

PON의 역사적 사례는 TALK(직접 대화), SUPPORT(HR 등 내부 지원), MEDIATION(훈련된 내부 조정), legal claim의 외부 ADR/arbitration 경로를 설명한다. 단계·지원·선택지의 연결을 참고한다. 이를 현재 모든 Coca-Cola 계열사의 동일 제도로 주장하지 않는다. [PON, 2020; originally 2008](https://www.pon.harvard.edu/daily/dispute-resolution/employee-grievances-and-litigation/)

별도 Brown v. CCE 기록은 당시 brochure의 Talk/Support/Mediation/Arbitration 네 옵션과 법률 청구의 mandatory arbitration을 확인한다. PON의 설명과 법원 기록은 분쟁 종류·사업부·시기의 차이를 고려해야 한다. **모든 경로가 voluntary이거나 반드시 네 단계를 순차 통과했다는 근거로 쓰지 않는다.** CCE와 The Coca-Cola Company의 유사 이름 프로그램도 구분한다. [미 연방법원 공개 기록, PDF pp. 3–4 확인](https://www.govinfo.gov/content/pkg/USCOURTS-nyed-2_08-cv-03231/pdf/USCOURTS-nyed-2_08-cv-03231-0.pdf)

### 6.2 Alcoa Resolve It

Lipsky·Seeber·Hall의 field research는 multiple access points/options, voluntary participation, representation, anti-retaliation, training을 기록한다. “많은 채널·절차를 조직 지원과 함께 제공”하는 ICMS 예시다. 임의의 RACI/deadline 개입의 효과 근거는 아니다. [Cornell 저자 원고, 인쇄 p. 26](https://ecommons.cornell.edu/server/api/core/bitstreams/81e1ba62-ba81-46cc-bf40-676ce14d47a1/content)

### 6.3 Chevron

동일 연구는 Alcoa와 유사한 comprehensive program에 ombudsperson 접근 경로가 더해진 사례를 제시한다. manager 외의 접근점을 두는 의미를 보여준다. 현재 simulation에 독립 ombuds가 있다는 주장은 하지 않는다. 연구는 당시 system의 정량적 비용·편익을 확정하지 못한다고 밝힌다. [Cornell 저자 원고, 인쇄 pp. 27–28](https://ecommons.cornell.edu/server/api/core/bitstreams/81e1ba62-ba81-46cc-bf40-676ce14d47a1/content)

GE/Nestlé/J&J/Prudential/PECO/Raytheon의 이름 목록은 최종 근거에서 제외한다. 위 사례는 역사적 미국 조직 사례이며 한국 대기업 적용 가능성이나 simulation 인과 효과를 직접 증명하지 않는다.

## 7. 실제 실험에 사용할 set — 4 arms / 3 timing interventions [O]

**최종 추천: Design A, Timing-focused. S1만 고정하고 동일한 Rights-oriented RoleBrief의 전달 시점만 바꾼다.**
C0 + P1-R + E1-R + L1-R의 4조건이다. 신규 개입을 세 가지 mechanism으로 늘리는 대신 작은 하나의 정보 개입을 세 시점에 배치한다. 아래 ID는 제안용이며 현재 YAML에 구현된 이름이 아니다.

### 7.1 공통 treatment 정의

**RoleBrief RB-v1**: 기존 config의 T01 owner(HDS-002), reviewer 목록, 실제 task authority_scope의 승인 규칙, T01→T02/HDS-012 handoff 사실을 동일한 deterministic 본문으로 설명한다. 실제 grant와 reviewers를 대조해 정당한 approval actor를 지정하며, manager만 모든 task를 승인한다고 새 규칙을 만들지 않는다.

Actor HDS-001, 수신자 HDS-002/HDS-012, 단 1회 전달, 동일 경로·본문·recipient·visibility·길이 제한. 새 owner, reviewer, due, effort, shock duration, instruction authority, SLA, 인력 배분을 만들지 않는다. 미래의 실패를 알리는 문장, blame, 평가, 새로운 task priority 지시는 넣지 않는다. 사용 중인 회사 세계 prompt 원칙에 맞게 English 본문을 동결한다.

현재 resolved S1의 T01/T02는 authority_scope=None이다. reviewer 명단은 존재하지만 `Org.work`의 review gate 조건을 충족하지 않아, 이를 필수 승인 절차라고 새로 설명하면 현 runtime과 충돌한다. RB-v1은 이 사실도 유지하고 reviewer 명단·조언 경로와 실행상 승인 gate를 구분한다. 근거: `environment/org.py:240–265`와 config-load 확인.

이미 알고 있던 사실의 **재확인과 salience**를 조작한다. 따라서 이것은 광범위한 mediation이나 ICMS 전체의 효과 실험이 아니다. 수신 memory에 기록하고 실제 prompt 노출 여부도 확인해야 한다. 기존 I1의 marker만으로 대체하지 않는다.

전송은 기존 inbox/observation memory 경로를 활용하도록 후속 설계한다. schedule tick에 발송하면 읽는 것은 다음 tick이므로 **send tick과 exposure tick을 분리**한다. 세 treatment 모두 같은 경로를 적용해 실제 노출을 맞춘다. 이번 문서는 구현하지 않는다.

| Field | C0 Control | P1-R Preventive brief | E1-R Early brief | L1-R Late brief |
| --- | --- | --- | --- | --- |
| Intervention ID | C0-S1 | P1-R | E1-R | L1-R |
| Stage | 없음 | A, shock 전 | B의 fixed proxy | C의 late proxy; observed escalation 보장 안 됨 |
| Mechanism | 없음 | Rights-oriented | 동일 Rights-oriented | 동일 Rights-oriented |
| Target conflict | E01 dependency coordination | E01 + E08 가능 경로 | 동일 | 동일 |
| Trigger | 없음 | fixed, day 0 tick 0 발송→1 노출 | shock+3, tick 5 발송→6 노출 | shock+5, tick 7 발송→8 노출 |
| Actor | 없음 | HDS-001 | 동일 | 동일 |
| Actual action | 추가 briefing 없음 | RB-v1, 동일 2 recipient에 1회 | 동일 | 동일 |
| State changed | 자연 진행 | inbox→memory/info salience | 동일 | 동일 |
| Variables held fixed | 공통 S1 resolved config | 충격2–10, seed, persona, authority, DAG, effort/due, recipients/body, route, cache/model/memory/retry 설정 | 동일; 시점만 차이 | 동일; 시점만 차이 |
| Expected mechanism [H] | benchmark | 문제 전 역할 인지·handoff 이해 | coordination 혼선 조기 확인 | 누적 혼선 후 기준 재확인 |
| Primary outcome | T01→T02 coordination latency | 동일 | 동일 | 동일 |

**Primary outcome 정의**: T01 완료(done)로 prerequisite가 실제 해소된 tick부터 T02의 첫 유효 work tick까지의 지연. 단순 shock expiry=10은 T01 완료를 뜻하지 않는다. T02 시작/선행 완료가 horizon 내 없으면 0이나 임의 큰 값으로 채우지 않고 right-censored로 표시한다. censoring·완료율을 함께 보고한다.

보조 결과는 shock 이후 누적 blocked-task ticks, relevant repeated/ignored requests, dyad relationship delta, stress AUC다. 특정 차단 최소 시간 자체는 변경할 수 없으므로 정보 개입이 T01의 강제 불가 기간을 줄였다는 가설은 세우지 않는다.

### 7.2 A / B / C 비교와 선택 이유

| Design | 장점 | 현재 위험 | 결론 |
| --- | --- | --- | --- |
| A Timing | 같은 mechanism·actor·강도 유지 가능, 4조건 | fixed late가 실제 post-conflict인지 별도 확인 필요 | **권장**, 저비용 RB-v1 하나의 timing을 식별 |
| B Mechanism | IRP 효과 비교가 직접적 | I1 marker/I2 구조 변경/I3 대화의 강도·scenario·visibility가 모두 다름 | 현재 보류; 같은 source에서 절차 강도를 먼저 정의해야 함 |
| C Limited mixed | 기업 대표 policy package 비교에 자연스러움 | timing와 mechanism confounding. “왜 효과가 났는지” 분리 불가 | policy package 연구라면 후속 가능; 현재 timing RQ에는 A가 명확 |

RQ: **동일한 dependency shock에서 동일한 역할·handoff 정보의 전달 시점이 후속 업무 coordination 지연과 사회적 비용에 어떤 차이를 만드는가?**

IRP 세 방식 중 무엇이 가장 우월한지, 예방이 모든 경우에 더 좋은지, ICMS 전체가 성공하는지는 이 연구가 답하지 않는다. Interests 중심 시스템이라는 문헌 권고와 연구상 저비용 Rights 정보 조작 선택도 구분한다.

### 7.3 반복·비용·비교 단위

- 기본 S1을 그대로 사용: **20 agents, 2일, day span=34, 총 68 ticks**, 같은 15-task DAG. 32-tick s0_smoke는 engine 검증용이지 동일한 research condition이 아니다.
- 4조건 × 같은 3개 seed(1501/1502/1503) = **12개 run의 설계**. 숫자 1502/1503을 쓴다고 S2/S3 scenario를 실행하는 것은 아니다. 모두 S1 내용 + seed offset이다.
- agent 20명이나 대화 turn을 독립 replicate로 세지 않는다. **run/seed가 반복 단위**다.
- small-n exploratory comparison이다. paired effect와 trajectory·censoring을 보여주되, 3seed로 강한 통계적 유의성·일반화를 주장하지 않는다.
- C16 기존 8조건×3회=24회보다 run 수를 절반으로 좁힌다. 절감률은 condition count 기준이지 token cost의 50% 감소 보장은 아니다.
- 68-tick real API run의 비용을 아직 모른다. 먼저 문서·공통 payload·state visibility를 demo/fake로 검증하고, 비용 승인을 받은 단일 full-horizon pilot이 완주·usage gate를 통과한 뒤 반복을 판단한다. **지금 12회 실행 승인을 요청하거나 실행하지 않는다.**
- API seed는 provider가 보장하는 deterministic simulation seed와 동일하지 않다. 모델·temperature·버전·cache warm-up·budget을 고정 기록하고, 흔들리는 출력은 반복과 human sample로 평가한다.
- 예산 중단은 개입 효과가 아니다. 누락 run을 조용히 제외하거나 다른 seed로 자동 교체하지 말고 중단·completion status를 함께 보고한다.

## 8. Scenario × Intervention mapping [O]

| Scenario | 이론적으로 타당한 pair | 이번 선택 |
| --- | --- | --- |
| S1 | P1/E1/L1 동일 role/handoff brief; P3 alignment; I3의 정확한 당사자 check-in | **주 실험 C0/P1-R/E1-R/L1-R만** |
| S2 | 기존 I2 due adjustment; 필요 시 P2 workload와 분리 | framework 후속, 현재 주 실험 제외 |
| S3 | 사전 room allocation 또는 early resource adjustment; bounded cross-team coordination | 후속; generic specialist allocation을 현 S3에 적용하지 않음 |
| S4 | 평가 criteria/evidence process clarification(R), expectation alignment(I) | 후속; 승진 slot 증가를 관계 회복과 동일시하지 않음 |
| S0 | manipulation/정보 개입 자체의 효과를 보는 별도 control 가능 | 주 실험 조건을 늘리지 않음 |

P1을 S1에 쓰는 것은 E05가 이미 존재한다는 주장과 다르다. S1의 objective blockage에 대한 coordination salience를 먼저 검증한다. S0를 추가하면 meeting schedule 차이를 해결한 뒤 별도 design으로 등록해야 한다.

## 9. Trigger 및 evaluation protocol [O]

### 9.1 Fixed / state-based 구분

주 실험은 위 fixed exposure 1/6/8로 preregister한다. 모든 treatment는 결과를 보지 않고 한 번만 배정·전달한다.

실제 workflow 도입을 위한 후속 state trigger 예시는 다음과 같다. **threshold는 문헌이 제공한 숫자가 아니라 제안**이며 현재 runtime에 구현되지 않았다.

- Early: shock-linked T01의 unavailable duration ≥2 또는 T01→T02 dyad의 정해진 no_reply_ticks에 따른 ignored request.
- Post proxy: 같은 task/dyad의 미해결 objective request episode가 2개 이상이면서 shock-linked blockage가 4ticks 이상 지속. 동일 요청의 매 tick 재출력을 서로 다른 episode로 세지 않는다.
- mood/stress 또는 relationship은 엔진 내부에 존재해도 manager에게 자동 공개된 정보는 아니다. actor access policy를 정의하기 전 trigger에 쓰지 않는다.
- CRAFT p(t)는 trigger, agent prompt, manager decision에 넣지 않는다.
- tick-start schedule 전에 판단하면 직전 tick까지의 상태만 사용한다. 자연 DAG blocked_since=0 대신 shock id·relevant task·해당 window를 연결한다.
- 한 run 한 개입, fired/eligible/send/delivered/observed ticks와 근거 state를 별도로 기록한다.
- 적격 조건이 없으면 미실시로 기록하고 intention-to-treat 비교에 남긴다. trigger 후 busy/공간 때문에 실패한 세션도 success로 세지 않는다.

State trigger 자체를 arm별로 다르게 쓰면 eligibility population과 노출 시간이 달라진다. 주 timing trial에서는 fixed로 유지하고, 후속에서는 같은 pre-treatment eligibility 기준으로 policy assignment를 비교한다. treated outcome을 보고 post-conflict run만 골라 효과를 추정하지 않는다.

### 9.2 지표 — 네 영역과 비용

| 영역 | 지표·정의 | 현재 자료와 필요한 구분 |
| --- | --- | --- |
| Task | primary T01→T02 latency; horizon 완료 비율; shock 이후 task×tick blocked 합; time overdue; workload/overtime | frames/checkpoint/task snapshot에서 산출. overdue는 한 번 켜지는 flag만 세지 않고 per-tick due/status로 재구성 |
| Social | task/dyad 관련 distinct request/ignored episodes; help/work contribution; session·utterance 수; directed relationship delta; grievance 기록 | events/threads/agent state. env-invalid action retry와 interpersonal refusal 분리 |
| Individual | stress AUC·peak·종료값, mood trajectory, workload burden | 같은 68ticks 비교. 20명 전체와 target dyad를 사전 지정해 별도 보고 |
| Observer | CRAFT trajectory·peak·threshold crossing; coded blame/needs/role references | **보조 observer만**. 기업 대화 validity 미확인, 인간 코딩과 함께 해석 |
| Intervention cost | added calls/tokens, recipient observations, time away from work, delivery/compliance | policy 비용. task improvement가 단순 추가 활동량 때문인지 함께 확인 |

Latency가 censor되는 run은 완료율과 restricted follow-up 정보를 함께 제시한다. blocked time은 task×tick이며 agent×tick과 혼용하지 않는다. 관계는 A→B/B→A가 다를 수 있어 평균 하나만 제시하지 않는다.

Social refusal은 실제 Outcome.refused/ignored 및 원인을 사용한다. grievance list는 memory ID가 누적된 기록이며 “미해결 grievance 수”를 자동 측정한다고 볼 수 없다. 현재 removal/resolution semantics가 확인되지 않았으므로 생성·누적 수와 human-coded unresolved status를 구분한다.

Human coding 제안: 같은 사전 지정 window(ticks 2–10, 10–18)에서 관련 모든 세션을 후보로 잡고, 없는 세션도 0개로 기록한다. cost가 크면 arm/seed 균형 표본을 정한다. 두 coder가 condition을 가능한 한 가린 대화에서 blame, role/authority reference, needs/constraints, refusal rationale, agreed next action을 코딩하고 disagreement/adjudication을 보고한다. 추가 LLM judge는 이번 설계에 필수로 넣지 않는다.

CRAFT threshold·human codebook·outcome 방향은 결과를 본 뒤 바꾸지 않는다. **대화가 적어지거나 grievance 신고가 줄어드는 것만으로 성공을 판정하지 않는다.** 문제 제기가 쉬워지면서 관측량이 늘 수도 있다. task recovery와 사회·개인 비용의 trade-off를 함께 보여준다.

## 10. 근거·operationalization·hypothesis를 분리한 claim ledger

| Claim | 유형 | 근거/한계 |
| --- | --- | --- |
| ICMS의 다섯 특성과 여러 경로의 통합 | L | SPIDR pp. 9–14; 공식 3-stage timing 모델은 아님 |
| DSD 진단·설계·운영·평가, 저비용 절차·loop-back | L | PON 및 Ury 등 ch. 3 |
| IRP의 서로 다른 처리 logic와 비용 비교 | L | Ury 등 ch. 1; Interests 항상 승리 아님 |
| Preventive/Early/Post × IRP 3×3 | O | 본 프로젝트 조합; canonical theory 아님 |
| manager due change를 administrative Power로 분류 | O | 코드의 unilateral structural change를 operationalize |
| 동일 RB-v1을 1/6/8에 노출 | O | 통제 가능한 timing 비교를 위한 설계 |
| 예방 brief가 coordination/social cost를 줄일 것 | H | 정보가 이미 충분하면 null 가능, hard block 제거 불가 |
| mediation/private check-in이 관계 회복을 보장 | **채택 안 함** | 현재 I3는 mediation fidelity 부족, 효과 미검증 |
| 4arm이면 비용상 반드시 완주 가능 | **채택 안 함** | historical paid pilot 미완주, full-run cost 미확인 |

### Source hierarchy / 검증 상태

| Tier | 문헌 | 실제 확인 범위 |
| --- | --- | --- |
| 1 | SPIDR ADR in the Workplace Committee (2001), Designing Integrated Conflict Management Systems, Cornell Studies No.4 | Mary Rowe/MIT 공식 링크 PDF를 직접 읽음. 인쇄 pp.9–14 / PDF pp.12–17, 원문 5특성 확인. MIT/Cornell repository endpoint는 일부 405였으나 faculty-linked PDF 확보 |
| 1 | Ury, Brett & Goldberg (1988), Getting Disputes Resolved, ch.1 pp.3–19 | 저작의 허가 재수록 Reading 1.1을 대학 제공 PDF에서 직접 확인. 재수록의 pagination과 원 저작 pagination 구분 |
| 1 | Ury et al. (1988), Designing an Effective Dispute Resolution System, Negotiation Journal 4:413–431 | DOI 서지 확인. publisher 본문은 열리지 않아 동일 저작 ch.3 공개 scan/text의 설계 원칙을 확인. publisher article 전체를 읽었다고 주장하지 않음 |
| 2 | Harvard PON, What is DSD? (2026-07-14) | 4-step design/evaluation 및 least invasive principle 직접 확인 |
| 2 | Acas 연구 소개·2025 연구자 해설 | 33 interviews 및 early/voluntary/skill 내용 확인. full interview dataset 미확인 |
| 2 | CIPD Mediation at work (2025-09-24) | 공개 factsheet의 definition·process·scope·boundary 확인 |
| 3 | PON CCE 역사적 case + Brown v. CCE 법원 원문 | 단계 설명과 당시 arbitration policy 분리. 제도의 현재 운영 여부·효과 미검증 |
| 3 | Lipsky, Seeber & Hall, An Uncertain Destination: On the Development of Conflict Management Systems in U.S. Corporations | Cornell 저자 원고 pp.26–28, Alcoa/Chevron 및 효과 정량화 한계 확인. repository 업로드 시각을 fieldwork 연도로 쓰지 않음 |

블로그·일반 HR 사이트는 핵심 근거로 쓰지 않았다. PON article은 전문기관의 교육 해설로 Tier2이며 Tier1 원 연구와 구분한다. FlipHTML5는 원 저작의 열람 mirror로만 사용했으며 그 사이트의 별도 해설을 근거로 쓰지 않았다. 최종 연구 제출 전 도서관 제공 원 판본으로 ch.3 scan의 판본·page를 다시 대조하는 것이 좋다.

## 11. 아직 결정해야 할 사항 / 구현 전 gate

1. **RQ 승인**: 동일 Rights brief의 timing RQ로 좁힐지. IRP mechanism ranking이 목표라면 Design B로 재설계해야 한다.
2. **RB-v1 확정**: 실제 승인 grant·reviewer 충돌 없이 기존 사실만 전달할 것. 이미 prompt에 동일 사실이 있다는 null 가능성도 명시.
3. **I1 후속 기능**: marker가 아닌 실제 전달·memory 기록·prompt 노출과 manipulation check. 이번에는 미구현.
4. **stage 명칭**: 주 trial의 fixed tick 8을 Late로 표기할지, Post-conflict는 objective escalation qualification을 충족한 경우에만 사용할지. 추천은 **Late**.
5. **primary latency/censoring 정의**: T01 done 기준, T02 첫 work 식별, time horizon, human sample/codebook 동결.
6. **pilot 비용 gate**: full-horizon 20-agent run의 cap·중단 처리·반복 승인. cache policy·model version·warm-up을 모든 arm에 동일 적용.
7. **I3 명칭/충실도**: alias 유지와 실제 mediation 신설은 별도 후속 결정. 독립 neutral을 추가하면 20-agent fixed composition이 바뀌므로 지금 넣지 않음.

이번 작업의 검증은 code/config/source reading, 8개 scenario의 config-only loading, 문서 정합성 점검이다. 20 agents·68ticks, seed·meetings·intervention timing, T01/T02 owner/handoff/authority_scope를 확인했으며 `git diff --check`가 통과했다. 테스트·simulation·CRAFT·API를 새로 실행하지 않았으며 기존 519-pass 결과를 이 연구 설계의 효과 검증으로 인용하지 않는다.

---

## Recommended Final Structure — 회의용 1페이지 요약

**목표**: 구조적 dependency failure 이후 coordination·사회적 비용을 줄이는 데 **같은 개입의 시점**이 영향을 주는지 평가한다.

**Framework**: ICMS(조직 통합 원칙) + DSD(저비용 절차·loop-back·평가) + IRP(mechanism). **Preventive/Early/Post × IRP는 프로젝트의 3×3 operational design space**이며 공식 단일 이론은 아니다.

**현재 진단**: I1=agent에게 전달되지 않는 clarification marker. I2=due +6의 administrative Power. I3=manager–employee private check-in으로 genuine mediation 아님. I3 success flag와 실제 session 생성도 분리해야 한다.

**주 실험 선택**: **Design A / Timing-focused**, S1 하나만 고정. **C0 no intervention / P1-R preventive / E1-R early / L1-R late**. 세 treatment는 똑같은 RoleBrief RB-v1을 HDS-001→HDS-002/HDS-012에 한 번 전달하며 실제 exposure tick만 **1 / 6 / 8**로 바꾼다. Tick 8의 실제 관계 갈등은 보장되지 않으므로 “Post 효과”로 단정하지 않는다.

**고정 조건**: 20명, 기존 S1 15-task DAG·effort/due·authority/persona, shock tick 2–10, 68ticks, 같은 3seed, model/cache/retry/memory 설정. treatment body·recipient·길이·경로 동일. 정보·memory 변화만 허용하고 hard block·due·owner는 그대로다.

**규모**: 4조건×3seed=12run의 계획. 비용상 실행 가능성을 아직 보장하지 않는다. 후속 demo/fake fidelity 확인과 별도 비용 승인 single full-run pilot 뒤 반복을 결정한다. **이번에는 실행하지 않음.**

**Primary**: T01 실제 완료 이후 T02 첫 유효 work까지 coordination latency, 미완료는 censored. **Secondary**: blocked task×ticks, completion/overdue, relevant requests/help, 관계·grievance 기록, stress/mood. CRAFT는 observer만 사용하고 human-coded sample과 대조한다. 간단한 단일 갈등 점수로 성공을 판정하지 않는다.

**Corporate support**: CCE=직접 대화·내부 지원·mediation·formal backup 연결, Alcoa=여러 접근점/옵션·training·anti-retaliation, Chevron=ombuds 경로. 역사적 원리 사례이며 특정 RACI/deadline 조작의 효과 증거는 아니다.

**회의에서 결정할 3가지**: (1) timing RQ 채택, (2) RB-v1의 내용·전달 fidelity와 Late 명칭, (3) primary latency·pilot budget gate. **P2/P3와 IRP mechanism 비교는 후속으로 남긴다.**
