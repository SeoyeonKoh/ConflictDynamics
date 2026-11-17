# 조직 구조 선행연구 조사와 비교 구조 제안

작성일: 2026-11-11 · 상태: **문헌 조사 완료, 시나리오 미작성.** 인용 전 원문 대조 필요(§7).
근거 목록: [org_structure_literature_ledger.md](org_structure_literature_ledger.md) (152건, 항목별 검증 판정 포함).
이번 변경은 문서 두 개만 추가한다. 시뮬레이션 코드·설정 변경과 실행은 하지 않았다.

조직 구조에 따라 업무 효율과 갈등이 어떻게 달라지는지 실험할 시나리오를 만들기 전에, 어떤 구조를 비교할지와 각 구조에서 무엇을 예측할 수 있는지를 선행연구에서 찾았다. 본문의 `[T1-07]` 같은 표기는 원장의 항목 ID다.

## 1. 요약

1. **보편적으로 우월한 구조는 없다.** 같은 구조의 효과가 과업 조건(불확실성, 상호의존, 분해 가능성)에 따라 부호까지 바뀐다. 구조만 바꾸는 실험은 해석할 수 없고, 과업 조건과 교차해야 한다.
2. **"구조"는 하나의 변수가 아니다.** 계층 깊이, 결재 권한의 위치, 프로젝트 관리자의 권한, 부서 편성은 서로 독립적으로 움직인다. 묶음으로 바꾸지 말고 하나씩 조작한다.
3. **가장 먼저 볼 것은 결재 권한의 집중과 위임이다.** 근거가 가장 직접적이고, 엔진의 `authorities`와 `Org.signers`가 바로 반응하며, 기존 실행에서 이미 단독 결재자 병목(HDS-001)이 관찰됐다.
4. **갈등은 유형을 나눠서 본다.** 성과를 해치는 것은 과정 갈등(누가 무엇을 하고 누가 승인하는가)과 관계 갈등이다. 과업 갈등은 평균적으로 강하게 해롭지 않다.
5. **LLM 에이전트는 갈등을 덜 만든다.** 긍정성·동조 편향 때문에 구조가 갈등에 미치는 효과가 실제보다 작게 측정될 수 있다. 같은 구조를 반복 실행한 분산을 먼저 재야 한다.

비교를 권하는 구조는 §4의 여섯 묶음이고, 우선순위는 표의 순서다.

## 2. 조사 방법

Sonnet 연구 에이전트가 갈래 10개를 웹 검색으로 조사했고, 갈래마다 별도의 검증 에이전트가 항목별로 서지 실재 여부와 주장 일치를 다시 확인했다. 처음 7개 갈래를 조사한 뒤 누락 영역을 점검해 3개 갈래(G1–G3)를 추가했다.

| 갈래 | 항목 | 확인 | 부분 확인 | 확인 불가 | 오류 |
|---|---:|---:|---:|---:|---:|
| T1 고전 조직설계와 상황이론 | 16 | 9 | 7 | 0 | 0 |
| T2 프로젝트·제품개발 구조 | 17 | 8 | 5 | 4 | 0 |
| T3 조직·팀 갈등 | 14 | 9 | 3 | 2 | 0 |
| T4 통신망 구조와 집단 성과 | 16 | 8 | 7 | 0 | 1 |
| T5 계산 조직이론과 에이전트 기반 모형 | 19 | 8 | 5 | 6 | 0 |
| T6 LLM 다중 에이전트 구조 연구 | 18 | 10 | 7 | 1 | 0 |
| T7 결정권·결재 단계와 한국 기업 맥락 | 15 | 11 | 4 | 0 | 0 |
| G1 시뮬레이션 실험 설계와 타당도 | 18 | 15 | 3 | 0 | 0 |
| G2 팀 규모와 프로세스 손실 | 10 | 2 | 3 | 4 | 1 |
| G3 업무 부하·역할 스트레스·리더십 구조 | 9 | 1 | 6 | 2 | 0 |
| 합계 | 152 | 81 | 50 | 19 | 2 |

"확인"도 대부분 초록이나 2차 요약과 대조한 수준이다. 이 문서는 "확인"과 "부분 확인" 항목만 근거로 쓰고, 부분 확인 항목은 확인된 부분만 서술했다. 확인 불가 항목을 언급할 때는 그 사실을 적었다.

## 3. 문헌이 말하는 것

### 3.1 구조와 효율

**상황 적합.** 안정적인 환경에는 규칙과 계층 중심의 기계적 구조가, 변화가 큰 환경에는 역할이 유연하고 수평 소통이 많은 유기적 구조가 맞는다는 것이 고전적 결론이다(Burns & Stalker 1961 [T1-01], 2차 요약으로만 확인). 부서 간 차이가 클수록 이해 충돌이 늘고, 성공한 조직은 그만큼의 통합 장치를 갖췄다(Lawrence & Lorsch 1967 [T1-02], 2차 요약). Galbraith(1973/1974) [T1-04]는 이를 정보처리 문제로 정리했다. 과업 불확실성이 커질수록 규칙과 계층 의뢰만으로는 부족해지고, 직접 접촉, 연락 역할, 전임 통합자, 매트릭스 순으로 수평 장치가 필요하다. 수평 장치일수록 처리 용량이 크지만 비용도 크다.

**구조 차원은 서로 독립적이다.** 공식화, 표준화, 전문화, 분권화, 수직 분화 사이의 상관이 1998년 이후 연구에서는 거의 사라졌다는 메타분석이 있다(Wagner 2025 [T1-07]. 연구 에이전트는 원문을 열어 평균 상관 .24에서 .04로의 하락을 보고했으나, 검증 에이전트는 이 수치를 재확인하지 못했다). Mintzberg의 이상형 구성에 가까울수록 성과가 높다는 가설은 지지되지 않았다(Doty, Glick & Huber 1993 [T1-13]). 구조를 "관료제 묶음"으로 다루지 말고 차원별로 조작할 근거다.

**평탄화는 위임이 아니다.** 계층을 줄이고 관리 폭을 넓힌 미국 대기업에서는 의사결정이 오히려 위로 집중됐고, 최고경영자가 내부 상호작용에 더 많은 시간을 썼다(Wulf 2012 [T7-06]). 계층 깊이와 결재 권한의 위치는 따로 조작해야 한다.

**권한 위임의 이론.** 부하에게 실질 권한을 주면 주도성은 오르고 상급자의 통제력은 줄어든다. 상급자가 과부하일수록 부하의 실질 권한이 커진다(Aghion & Tirole 1997 [T7-01]). 계층은 처리 비용을 낮추지만 여러 층을 올라가야 하는 과업은 대기 지연이 길어진다(Beggs 2001 [T7-08]). 현장 정보가 중요하고 환경이 이질적인 기업일수록 분권화한다(Acemoglu 외 2007 [T7-03]). 아시아 기업은 영미·북유럽 기업보다 덜 분권적이다(Bloom, Sadun & Van Reenen 2012 [T7-04]).

**관리 폭.** 항공 지상 운영에서는 감독 폭이 좁을수록 부하 간 조정 품질이 높고 성과(회전 시간, 품질)가 좋았다(Gittell 2001 [T1-10]). 상호의존이 높고 시간 압박이 큰 업무에 한정된 결과다.

**프로젝트 구조.** 개발 프로젝트 약 540건을 비교한 설문에서 기능조직과 기능 매트릭스는 균형 매트릭스, 프로젝트 매트릭스, 프로젝트팀보다 비용·일정·기술 성과가 낮았다(Larson & Gobeli 1987, 1989 [T2-01, T2-02]). 관리자 인식에 기반한 설문이고 효과 크기는 확인하지 못했다. 현재 엔진의 `functional_matrix_lite`는 이 축에서 성과가 낮다고 보고된 쪽에 있다. 권한이 큰 프로젝트 관리자(heavyweight PM)는 직접 권한보다 목표 명확성과 전략 정렬을 통해 성과에 영향을 준다(Rauniar 외 2008 [T2-07]).

**자기관리 조직.** 관리자–부하 보고 관계를 없앤 조직에 대한 연구는 아직 연구 의제 수준이고 효율·갈등 효과를 비교한 실증은 약하다(Lee & Edmondson 2017 [T2-13]). 전사적 자기관리는 많은 환경에서 성과가 나지 않으며 부분 도입이나 전통 모델과의 혼합이 유용하다는 정리가 있다(Bernstein 외 2016 [T2-14]).

**팀 경계와 과업 의존의 일치(미러링).** 조직의 소통 구조가 과업의 의존 구조와 맞을 때 조정이 덜 든다는 가설이다. 서지는 알려져 있으나 이번 조사에서는 원문 접근에 실패해 수치를 확인하지 못했다(Colfer & Baldwin 2016 [T2-16], MacCormack 외 2012 [T2-15], Cataldo & Herbsleb 2013 [T2-17], 모두 확인 불가).

### 3.2 구조와 갈등

**갈등 유형별 효과.** 116개 연구(8,880개 집단)의 메타분석에서 관계 갈등과 과정 갈등은 집단 성과와 일관되게 부(−)의 관계였고, 과업 갈등은 평균적으로 강한 부정 관계가 아니었다(de Wit, Greer & Jehn 2012 [T3-02]). 앞선 메타분석은 과업 갈등도 부정적이라고 보고했고(De Dreu & Weingart 2003 [T3-01]), 최신 메타분석은 과업·관계·과정·지위 갈등 네 유형 모두 부정적이되 상황 간 이질성이 크다고 보고한다(Yuan, Yin & Sun 2026 [T3-03]). 과업 갈등의 평균 효과는 문헌 안에서 합의되지 않았다.

**과정 갈등이 출발점이다.** 종단 연구에서 팀 초기의 과정 갈등은 이후 모든 유형의 갈등을 높였고, 초기 과업·관계 갈등에는 그런 효과가 없었다(Greer, Jehn & Mannix 2008 [T3-11]). 신뢰가 높은 팀에서는 과업 갈등이 관계 갈등으로 번지지 않는다(Simons & Peterson 2000 [T3-10]). 비정형 과업에서는 과업 갈등이 해롭지 않았다(Jehn 1995 [T3-09]).

**위계와 갈등.** 54개 연구(13,914개 팀)의 메타분석에서 위계는 팀 성과(−.08)와 팀 존속성(−.11)에 작은 음의 순효과를 보였고, 그 경로는 갈등을 부추기는 상태였다. 위계가 조정을 돕는다는 가설은 대체로 지지되지 않았고, 과업이 모호할 때만 위계가 이로웠다(Greer 외 2018 [T1-11, T3-04]). 정오표에 따라 구성원 이동성의 조절 효과는 더 이상 지지되지 않는다. 지위 갈등은 성과에 부정적이고 과업 갈등의 이점을 없앤다(Bendersky & Hays 2012 [T3-05]).

**매트릭스의 해는 모호성에서 온다.** 역할 모호성은 직무 성과와 부(−)의 관계다(ρ = −.21, Tubre & Collins 2000 [T3-06]). 같은 메타분석에서 역할 갈등은 성과와 거의 무관하다고 인용되지만 이 수치는 확인하지 못했다. 두 상사에게 보고하는 관리자 111명 조사에서는 두 상사와의 관계 질이 불균등할수록 역할 갈등이 컸고, 두 상사 사이의 관계가 좋으면 그 피해가 완충됐다(Sahlmueller 외 2022 [T2-06, G3-01], 실무 요약 글로만 확인). 이중 권한이 갈등과 혼란을 낳는다는 서술은 리뷰에 반복되지만(Ford & Randolph 1992 [T2-03]) 엄밀한 정량 검증은 찾지 못했다.

**목표 구조.** 협력적 목표 상호의존은 열린 토론과 정(+)의 관계이고, 경쟁적·독립적 목표는 열린 토론과 성과 모두에 부(−)다(Tjosvold 외 2022 [T3-12], 114개 연구). 부서별 목표가 충돌하도록 설정하는 것은 구조와 별개의 갈등 원인이다.

**갈등 인식의 비대칭.** 한 사람은 갈등이 크다고 느끼고 다른 사람은 아닐 때 성과가 나빠진다(Jehn 외 2015 [T3-13]). 평균뿐 아니라 구성원 간 분산을 봐야 한다.

### 3.3 통신망과 네트워크

5인 집단 실험의 고전적 결과는 중앙집중망(wheel)이 단순 과업에서 빠르고 조직화가 잘 되지만 주변 구성원의 만족이 낮다는 것이다(Leavitt 1951 [T4-01], 원문 결과는 2차 요약으로만 확인). 과업이 복잡해지면 중앙집중이 문제 해결을 방해할 수 있다(Shaw 1964 [T4-03]). 현대 실험은 최적 구조가 과업에 따라 달라진다는 점을 반복해서 보인다. 조밀한 군집은 정보 탐색을 늘리지만 해법의 다양성은 줄인다(Shore, Bernstein & Lazer 2015 [T4-06]).

실제 업무 집단 182개에서는 리더 주변의 구조적 공백과 핵심–주변 구조가 낮은 성과와 연관됐다(Cummings & Cross 2003 [T4-10]). 팀 내부 연결 밀도가 높고 리더가 네트워크 중심에 있는 팀은 성과가 높았다(Balkundi & Harrison 2006 [T4-09], 37개 연구). 소수의 사람에게 협업 요청이 몰려 병목이 된다는 관찰은 실무 글 수준의 근거다(Cross, Rebele & Grant 2016 [T4-11]).

상시 소통보다 간헐적 소통이 복잡한 문제에서 평균 성과와 최적해 발견을 모두 유지했다는 실험도 있다(Bernstein, Shore & Lazer 2018 [T4-08], 3인 집단).

### 3.4 시뮬레이션 선례

**Virtual Design Team(VDT).** Galbraith의 정보처리 틀을 프로젝트 조직 시뮬레이션으로 옮긴 모형이다. 조직 구조와 과업을 입력받아 행위자별 업무·통신 적체, 예외 처리와 재작업, 프로젝트 기간과 비용을 산출한다고 알려져 있다. 이번 조사에서는 원문을 열지 못해 세부를 확인하지 못했다(Levitt 외 1994 [T5-01], Jin & Levitt 1996 [T5-02], 확인 불가). 우리 지표(승인 대기, 반려, 대화량)와 가장 가까운 선례이므로 원문 확인 가치가 크다.

**위계 대 팀.** 팀은 일반적으로 더 빨리, 더 높게 학습하지만 위계는 이직이 높을 때 성능 저하가 작다. 과업이 분해 불가능할 때 특히 그렇다(Carley 1992 [T5-05]). 조직 설계의 복잡도가 과업 환경의 복잡도와 맞을 때 성과가 좋고, 과업 환경의 특성이 설계보다 성과에 더 큰 영향을 준다(Carley & Lin 1997 [T5-04]).

**설계 요소는 상호작용한다.** 다부서 기업 모형에서 수직 위계, 인센티브, 부서 분해의 효과는 서로 의존하고, 부서장이 가진 권한(정보 보류, 의제 통제, 거부권)에 민감하다(Rivkin & Siggelkow 2003 [T5-09], Siggelkow & Rivkin 2005 [T5-08]). 하위 계층의 처리 능력이 충분하면 오히려 전체 개선이 느려질 수 있다는 반직관적 결과도 있다.

**이중 권한.** 상사 1명, 보고선 없음, 상사 여러 명(매트릭스형)을 과업 복잡도와 분해 정도에 걸쳐 비교한 모형이 있다. 다중 권한 구조에 대한 실증 결과가 상충한다는 문제의식에서 출발한다(Levinthal & Workiewicz 2018 [T5-13], 구조별 결과 방향은 초록에서 확인하지 못함).

### 3.5 LLM 다중 에이전트 연구

**과업이 구조 효과의 부호를 정한다.** 단일 에이전트 대비 중앙집중 구조는 병렬 분해가 가능한 과업에서 +80.8%, 순차 의존 과업에서 −50.3%였다(Kim 외 2025 [T6-01]). 통신 오버헤드는 구조가 복잡할수록 커졌고, 오류 증폭은 검증 지점이 없는 독립 구조(17.2배)가 중앙집중 구조(4.4배)보다 컸다[T6-02]. 위상별 비교에서도 모든 과업에서 이기는 위상은 없었다(Qian 외 2024 [T6-08]).

**계층 대 평면은 결과가 갈린다.** 회사식 3계층 구조가 평면 구조보다 점수가 높고 토큰을 46–80% 덜 썼다는 보고가 있고(Wang 외 2026 [T6-03], 일부 과업에서는 평면이 우세), 소형 모델과 정답형 추론 과업에서는 평면 팀이 평균 5.26점 높았다는 보고가 있다(Muralidharan, Kwak & An 2025 [T6-04], 논문 안에 수치 불일치가 있음). 모델이 강하면 자기조직화가 성공하고 약하면 경직된 구조가 낫다는 보고도 있다(Dochkina 2026 [T6-05], 1인 저자 프리프린트, 초록만 확인).

**반려 권한.** 관리자가 코멘트만 할 수 있는 평면 조건과 초안을 반려할 수 있는 계층 조건을 43쌍으로 비교한 실험에서, 평면 조건이 효용과 글 명료성에서 더 높았고 계층 조건은 헤지 표현이 늘었다. 초안 단계에서는 두 조건이 구별되지 않았고 차이는 수정 단계에서 생겼다(Agachan, van Duijn & Zohrehvand 2026 [T6-06]). 2차 요약이 전하는 토큰·시간 증가 수치는 초록에서 확인되지 않았다.

**LLM 에이전트의 편향.** 다중 에이전트 대화에서 LLM은 사회적 바람직성 편향이 반영된 이상화된 사회를 재현한다(Bian 외 2025 [T6-15]). 토론에서는 과도한 동조가 조기 합의를 낳아 정확도를 낮춘다(Yao 외 2025 [T6-12], Bertalanič & Fortuna 2026 [T6-13]). 에이전트는 과잉 보고하고 지시에 순응하는 경향이 있다(Guo 외 2024 [T6-07]). LLM 사회 시뮬레이션 연구 다수가 타당도 원칙을 위반하며, 엄격한 조건으로 재현하면 효과가 약해지거나 뒤집힌다는 감사 결과가 있다(Zhou 외 2025 [T6-14], 수치는 버전마다 다름).

## 4. 비교할 구조

기준선은 현행 `functional_matrix_lite`다. 엔진의 구조 요인은 `reports_to`, `authorities`, `departments`이고(`src/conflict_sim/scenario_draft.py`의 `STRUCTURE_FIELDS`), 회사는 3–20명, 부서 6개 이하, 최상위 1명, 보고선 순환 없음이라는 제약이 있다(`src/conflict_sim/generator.py`).

| 순위 | 비교 | 조작 필드 | 효율 예측 | 갈등 예측 | 주 근거 |
|---|---|---|---|---|---|
| 1 | 결재 집중 대 위임 | `authorities` | 위임 시 승인 대기 감소 | 결재자 부하 감소, 대기자 불만 감소 | T7-01, T7-08, T4-11 |
| 2 | 계층 깊이 × 결재 위치 | `reports_to`, `authorities` | 평탄+집중 조합의 대기가 가장 김 | 깊은 계층에서 갈등 소폭 증가 | T7-06, T1-11, T1-10 |
| 3 | 프로젝트 관리자 권한 축 | `authorities`, `departments` | 기능·기능 매트릭스가 일정·비용 열세 | 강한 매트릭스에서 역할 모호성 증가 | T2-01, T2-02, T3-06 |
| 4 | 통합 담당자 유무 | 인원 1명, RACI | 부서 간 의존이 높을 때만 대기·반려 감소 | 부서 간 갈등 감소, 담당자 부하 증가 | T1-02, T1-04 |
| 5 | 팀 경계와 과업 의존의 일치 | `departments` 재배치 | 불일치 시 조정 대화량·막힘 증가 | 부서 간 과정 갈등 증가 | T2-16 (확인 불가) |
| 6 | 자기관리형 | `authorities` 동료 분산 | 예측 근거 약함 | 예측 근거 약함 | T2-13, T6-05 |

### 4.1 결재 집중 대 위임

구조는 그대로 두고 승인 권한을 가진 사람 수와 범위만 바꾼다. 세 수준을 권한다.

- 단일 결재자: 모든 과업의 승인 scope를 한 사람이 보유한다.
- 복수 결재자: 같은 scope를 두세 명이 나눠 갖는다.
- 범위별 위임: 일상 과업은 팀장이 종결하고 릴리스 같은 고위험 과업만 상위자가 승인한다.

`Org.signers`(`src/conflict_sim/environment/org.py`)는 scope 보유자 중 작업에 가깝지 않은 사람을 결재자로 삼고, 결재할 사람이 없거나 반려가 누적되면 담당자의 상위 관리자를 추가한다. 따라서 `authorities`만 바꿔도 결재 흐름이 달라진다. 기존 r10 실행에서 HDS-001이 단독 결재자로 병목이 된 것이 단일 결재자 수준에 해당한다.

여기에 반려 권한을 별도 조작으로 더할 수 있다. 승인자가 반려할 수 있는 조건과 코멘트만 할 수 있는 조건의 비교는 LLM 에이전트 선례가 있다[T6-06].

### 4.2 계층 깊이 × 결재 위치

계층 깊이(깊음, 평탄)와 결재 위치(상위 집중, 하위 위임)를 2×2로 조작한다. "평탄하지만 집중된" 조합이 Wulf(2012)가 관찰한 기업에 해당하고, 넓어진 관리 폭 때문에 결재 대기가 가장 길 것으로 예측한다. 20명 제약 안에서는 3단계(팀원–팀장–부서장–대표) 대 1단계(전원이 대표에게 보고)로 구현할 수 있다.

위계의 갈등 효과는 메타분석상 작다(−.08). 갈등 지표에서 큰 차이가 나오지 않더라도 이상한 결과가 아니다.

### 4.3 프로젝트 관리자 권한 축

Larson & Gobeli의 분류를 따라 네 수준을 둔다.

- 순수 기능조직: 프로젝트 관리자에게 승인권이 없고 부서장이 승인한다.
- 기능 매트릭스 lite: 현행 기준선.
- 강한 매트릭스: 프로젝트 관리자가 프로젝트 과업의 승인 scope를 갖고, 부서장은 품질 scope를 유지한다.
- 교차기능 프로젝트팀: 부서를 기능이 아니라 작업 흐름 단위로 편성하고 팀 안에서 승인이 끝난다.

`reports_to`가 단일 값이므로 이중 보고는 직접 표현할 수 없다. 승인 scope를 두 사람에게 주고 RACI의 책임자를 겹치게 두어 근사한다. 매트릭스의 해가 모호성에서 온다는 근거[T3-06]에 맞춰, 권한 경계가 명확한 강한 매트릭스와 모호한 강한 매트릭스를 나눠 보는 것이 좋다.

### 4.4 통합 담당자 유무

승인권이 없고 부서 간 과업에 협의자로 들어가는 조정 역할 한 명을 추가한다. 부서 간 의존이 많은 과업에서만 이득이 있고, 의존이 적으면 대화량만 늘 것으로 예측한다. 담당자에게 요청이 몰리는지를 함께 본다.

### 4.5 팀 경계와 과업 의존의 일치

같은 과업 그래프에서 의존하는 과업이 한 부서 안에 들어가도록 편성한 조건과, 일부러 부서를 가로지르게 편성한 조건을 비교한다. 근거 문헌의 수치를 이번에 확인하지 못했으므로 원문 대조 후 진행한다.

### 4.6 자기관리형

최상위 1명 제약 때문에 전원이 한 사람에게 보고하되 승인 scope를 동료에게 분산하는 방식으로 근사한다. 사람 대상 실증이 약하고 LLM 연구도 프리프린트 수준이라 탐색용으로만 권한다.

### 4.7 이번에는 권하지 않는 비교

- 통신망 위상(wheel, circle 등): 누가 누구에게 말할 수 있는지를 제한하는 필드가 현행 구조 요인에 없다.
- Mintzberg 구성 유형: 이상형 적합 가설이 지지되지 않았다[T1-13].
- 팀 규모: 이번 조사의 근거가 약하고(G2), 인원 수를 바꾸면 과업량과 교란된다.

## 5. 교차 조건과 실험 설계

**과업 조건과 교차한다.** 구조마다 최소 두 조건에서 실행한다.

- 안정 조건: 이벤트가 적고 과업이 순차적으로 이어진다.
- 변동 조건: 이벤트(변경 요청, 긴급 과업)가 많고 과업이 서로 되먹임한다.

시나리오 생성기는 변형이 기준선의 요인 하나만 바꾸도록 제한한다. 따라서 안정 기준선과 변동 기준선을 각각 만들고, 두 기준선에 같은 구조 변형을 붙인다.

**결근·이직 조건.** 위계가 인력 변동에 견고하다는 예측[T5-05]을 보려면 결재자나 관리자의 결근 이벤트를 모든 구조에 똑같이 주입한다.

**반복과 분산.** 일반 에이전트 기반 모형 기준으로, 표준화 효과 크기 0.5를 검정력 80%로 검출하려면 조건당 약 64회, 1.0이면 18–26회가 필요하다(Lee 외 2015 [G1-01]). LLM 실행에는 비현실적인 횟수이므로 큰 효과를 겨냥하고 다음을 지킨다.

- 같은 구조를 시드만 바꿔 반복해 조건 내 분산을 먼저 잰다. 구조 간 차이가 이 분산을 넘는지로 판단한다.
- 페르소나 세트는 모든 구조 조건에서 같은 사람에게 고정한다.
- 단일 실행 비교로 결론 내리지 않는다. 결정적으로 설정한 LLM도 반복 간 정확도가 달라진다(Atil 외 2024 [G1-08]).
- 프롬프트 문구에 대한 민감도를 점검한다(Sclar 외 2023 [G1-06]).

## 6. 측정

**효율.** 기존 지표를 그대로 쓴다. 과업 완료율과 기한 준수율, 승인 대기 시간, 반려(재작업) 횟수, 대화량과 토큰 비용, 휴식 비율.

**휴식의 원인.** 휴식을 "승인 대기 때문에 쉼"과 "할 일이 없어서 쉼"으로 나누면 구조 효과가 드러난다. 결재 집중 구조에서는 전자가 늘 것으로 예측한다.

**갈등 유형.** 대화를 과업 갈등, 관계 갈등, 과정 갈등, 지위 갈등으로 분류한다. 과정 갈등(담당과 승인 권한에 대한 이견)의 비율과 발생 시점을 주 지표로 삼는다. 초기 과정 갈등이 이후 갈등으로 번지는지[T3-11]를 볼 수 있다.

**역할 모호성.** "누가 승인하는가", "누가 담당인가"를 묻는 발화 빈도를 대리 지표로 둔다.

**부하의 분포.** 결재자와 대기자의 스트레스를 따로 집계한다. 평균뿐 아니라 구성원 간 분산을 본다[T3-13].

## 7. 타당도 위협과 조사 한계

**LLM 에이전트의 편향.** 긍정성·동조 편향 때문에 갈등이 덜 발생하고 덜 고조된다. 구조가 갈등에 미치는 효과는 하한으로 해석한다. 권위에 대한 순응이 사람보다 강하면 위계 조건의 결과가 왜곡된다.

**근거 수준.** 152건 중 81건이 확인, 50건이 부분 확인, 19건이 확인 불가, 2건이 오류다. 확인된 항목도 대부분 초록이나 2차 요약 수준이므로, 논문이나 보고서에 인용하기 전에 원문을 대조한다. 검증 에이전트의 정정 중 일부는 검색이 아니라 모델의 기억에 근거한다(원장에 "기억 기반"으로 표시).

**얕게 조사된 영역.**

- 한국 기업 맥락: 팀제 도입, 결재 단계 축소에 관한 국내 연구를 거의 찾지 못했다. 직급 단순화가 보상·승진 경로와 함께 재설계되지 않아 불만이 커진 물류기업 사례 1건[T7-13]과 권력거리와 발언에 관한 설문 1건[T7-14]뿐이다. KCI·RISS·DBpia를 직접 검색해야 한다.
- 팀 규모와 프로세스 손실(G2), 업무 부하와 공유 리더십(G3): 검색 한도가 소진되어 기억 기반 항목이 많다.
- VDT와 미러링 가설: 서지는 알려져 있으나 원문 접근에 실패했다.

**일반화.** 사람 조직 연구의 효과가 LLM 에이전트에서 같은 방향으로 나타난다는 보장은 없다. 이 문서의 예측은 검증할 가설이다.

## 8. 핵심 참고문헌

판정 표기: ✓ 확인, △ 부분 확인, ? 확인 불가. 전체 목록과 정정 내용은 원장에 있다.

**구조와 효율**

- ✓ Galbraith (1973/1974). Organization Design: An Information Processing View. [링크](https://jaygalbraith.com/wp-content/uploads/2024/03/NetworksLateralOrg.pdf) [T1-04]
- △ Wagner (2025). Dimensional research on organization structure: meta-analysis and conceptual redirection. *Journal of Management & Organization* 31(4). [링크](https://www.cambridge.org/core/product/28BAEC6D62B1828427080F494673F4A4/core-reader) [T1-07]
- ✓ Doty, Glick & Huber (1993). Fit, Equifinality, and Organizational Effectiveness. *Academy of Management Journal* 36(6). [링크](https://core.ac.uk/download/479089478.pdf) [T1-13]
- ✓ Gittell (2001). Supervisory Span, Relational Coordination and Flight Departure Performance. *Organization Science* 12(4). [링크](https://pubsonline.informs.org/doi/fpi/10.1287/orsc.12.4.468.10636) [T1-10]
- ✓ Wulf (2012). The Flattened Firm: Not as Advertised. *California Management Review* 55(1). [링크](https://hbswk.hbs.edu/item/the-flattened-firmnot-as-advertised) [T7-06]
- ✓ Aghion & Tirole (1997). Formal and Real Authority in Organizations. *Journal of Political Economy* 105(1). [링크](https://econpapers.repec.org/RePEc:ucp:jpolec:v:105:y:1997:i:1:p:1-29) [T7-01]
- ✓ Beggs (2001). Queues and Hierarchies. *Review of Economic Studies* 68(2). [링크](https://ideas.repec.org/a/oup/restud/v68y2001i2p297-322..html) [T7-08]
- ✓ Larson & Gobeli (1987). Matrix Management: Contradictions and Insights. *California Management Review* 29(4). [링크](https://cmr.berkeley.edu/1987/08/29-4-matrix-management-contradictions-and-insights) [T2-01]
- ✓ Larson & Gobeli (1989). Significance of project management structure on development success. *IEEE Transactions on Engineering Management*. [링크](https://bvbvf1.bib-bvb.de/vufind/PrimoRecord/cdi_crossref_primary_10_1109_17_18828) [T2-02]
- ✓ Rauniar, Doll, Rawski & Hong (2008). The role of heavyweight product manager in new product development. *IJOPM*. [링크](https://www.emerald.com/insight/content/doi/10.1108/01443570810846874/full/html) [T2-07]
- ✓ Lee & Edmondson (2017). Self-managing organizations. *Research in Organizational Behavior* 37. [링크](https://www.insead.edu/faculty-research/publications/journal-articles/self-managing-organizations-exploring-limits-less) [T2-13]
- ? Colfer & Baldwin (2016). The Mirroring Hypothesis: Theory, Evidence and Exceptions. *Industrial and Corporate Change* 25(5). [링크](https://hbswk.hbs.edu/item/the-mirroring-hypothesis-theory-evidence-and-exceptions) [T2-16]

**구조와 갈등**

- ✓ de Wit, Greer & Jehn (2012). The Paradox of Intragroup Conflict: A Meta-Analysis. *Journal of Applied Psychology* 97(2). [링크](https://www.ovid.com/journals/japsy/fulltext/10.1037/a0024844~the-paradox-of-intragroup-conflict-a-meta-analysis) [T3-02]
- ✓ Yuan, Yin & Sun (2026). The paradox of team conflict revisited. *Journal of Applied Psychology* 111(2). [링크](https://researchonline.lse.ac.uk/id/eprint/129181) [T3-03]
- △ Greer, de Jong, Schouten & Dannals (2018). Why and when hierarchy impacts team effectiveness: A meta-analytic integration. *Journal of Applied Psychology* 103(6). [링크](https://www.gsb.stanford.edu/faculty-research/publications/why-when-hierarchy-impacts-team-effectiveness-meta-analytic) [T1-11]
- ✓ Greer, Jehn & Mannix (2008). Conflict transformation. *Small Group Research* 39(3). [링크](https://findanexpert.unimelb.edu.au/scholarlywork/321546-conflict-transformation--a-longitudinal-investigation-of-the-relationships-between-different-types-of-intragroup-conflict-and-the-moderating-role-of-conflict-resolution) [T3-11]
- ✓ Bendersky & Hays (2012). Status Conflict in Groups. *Organization Science* 23(2). [링크](https://econpapers.repec.org/RePEc:inm:ororsc:v:23:y:2012:i:2:p:323-340) [T3-05]
- △ Tubre & Collins (2000). Jackson and Schuler (1985) revisited. *Journal of Management* 26(1). [링크](https://eprints.lancs.ac.uk/id/eprint/45119) [T3-06]
- ✓ Jehn (1995). A Multimethod Examination of the Benefits and Detriments of Intragroup Conflict. *Administrative Science Quarterly* 40(2). [링크](https://journals.sagepub.com/doi/10.2307/2667054) [T3-09]
- △ Sahlmueller, Van Knippenberg, Van Quaquebeke & Giessner (2022). Two in the Lead. *CMR Insights*. [링크](https://cmr.berkeley.edu/2022/09/two-in-the-lead-the-importance-of-relationships-when-there-are-two-bosses) [T2-06]

**시뮬레이션 선례**

- ✓ Carley (1992). Organizational Learning and Personnel Turnover. *Organization Science* 3(1). [링크](https://ideas.repec.org/a/inm/ororsc/v3y1992i1p20-46.html) [T5-05]
- ✓ Carley & Lin (1997). A Theoretical Study of Organizational Performance Under Information Distortion. *Management Science* 43(7). [링크](https://ideas.repec.org/a/inm/ormnsc/v43y1997i7p976-997.html) [T5-04]
- ✓ Siggelkow & Rivkin (2005). Speed and Search. *Organization Science* 16(2). [링크](https://ideas.repec.org/a/inm/ororsc/v16y2005i2p101-122.html) [T5-08]
- ✓ Levinthal & Workiewicz (2018). When Two Bosses Are Better Than One. *Organization Science* 29(2). [링크](https://ideas.repec.org/a/inm/ororsc/v29y2018i2p207-224.html) [T5-13]
- ? Jin & Levitt (1996). The Virtual Design Team. *Computational & Mathematical Organization Theory* 2. [링크](https://unpaywall.org/10.1007%2FBF00127273) [T5-02]

**LLM 다중 에이전트**

- △ Kim 외 (2025). Towards a Science of Scaling Agent Systems. [arXiv 2512.08296](https://arxiv.org/abs/2512.08296) [T6-01, T6-02]
- ✓ Wang 외 (2026). OrgAgent: Organize Your Multi-Agent System like a Company. [arXiv 2604.01020](https://arxiv.org/html/2604.01020v1) [T6-03]
- △ Muralidharan, Kwak & An (2025). Can Lessons From Human Teams Be Applied to Multi-Agent Systems? [arXiv 2510.07488](https://arxiv.org/html/2510.07488v2) [T6-04]
- ✓ Dochkina (2026). Drop the Hierarchy and Roles. [arXiv 2603.28990](https://arxiv.org/abs/2603.28990) [T6-05]
- △ Agachan, van Duijn & Zohrehvand (2026). Loop-Back Authority in LLM Agent Teams. arXiv 2609.14767 [T6-06]
- ✓ Qian 외 (2024). Scaling Large Language Model-based Multi-Agent Collaboration. [arXiv 2406.07155](https://arxiv.org/html/2406.07155v1) [T6-08]
- ✓ Bian 외 (2025). Social Simulations with Large Language Model Risk Utopian Illusion. [arXiv 2510.21180](https://arxiv.org/abs/2510.21180v1) [T6-15]
- ✓ Yao 외 (2025). Peacemaker or Troublemaker: How Sycophancy Shapes Multi-Agent Debate. [arXiv 2509.23055](https://arxiv.org/abs/2509.23055v1) [T6-12]
- △ Zhou 외 (2025). The PIMMUR Principles. [arXiv 2509.18052](https://arxiv.org/html/2509.18052v2) [T6-14]

**실험 설계**

- ✓ Lee 외 (2015). The Complexities of Agent-Based Modeling Output Analysis. *JASSS* 18(4). [링크](https://www.jasss.org/18/4/4.html) [G1-01]
- ✓ Galán 외 (2009). Errors and Artefacts in Agent-Based Modelling. *JASSS* 12(1). [링크](https://www.jasss.org/12/1/1.html) [G1-04]
- ✓ Sclar, Choi, Tsvetkov & Suhr (2023). Quantifying Language Models' Sensitivity to Spurious Features in Prompt Design. [arXiv 2310.11324](https://arxiv.org/abs/2310.11324) [G1-06]
- △ Atil 외 (2024). Non-Determinism of "Deterministic" LLM Settings. [arXiv 2408.04667](https://arxiv.org/abs/2408.04667) [G1-08]

**한국 맥락**

- ✓ 직급체계 개편의 문제점과 대응방안에 대한 연구 (2014). 경영교육연구 29(4). [링크](https://scholar.kyobobook.co.kr/article/detail/4010024603950) [T7-13]
- ✓ Jeung & Yoon (2018). When leadership elicits voice. *Journal of Management & Organization* 24(1). [T7-14]
