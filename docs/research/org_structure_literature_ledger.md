# 조직 구조 선행연구 원장 (Source Ledger)

2026-11-11 수집. [org_structure_literature_review.md](org_structure_literature_review.md)의 근거 목록이다.
Sonnet 연구 에이전트가 갈래별로 수집했고, 별도 검증 에이전트가 항목마다 서지 실재 여부와 주장 일치를 다시 확인했다.

판정 읽는 법:

- **확인**: 서지가 실재하고 주장이 확인한 출처와 일치한다. 다수는 초록이나 2차 요약 수준의 확인이다.
- **부분 확인**: 요지는 맞지만 숫자·연도·귀속 같은 세부가 틀렸거나 확인되지 않았다. `정정`을 함께 읽는다.
- **확인 불가**: 검증 에이전트가 확인하지 못했다. 원문을 대조하기 전에는 인용하지 않는다.
- **오류**: 인용된 문헌이 다른 내용을 말하거나 서지가 뒤섞였다. 사용하지 않는다.

어떤 판정이든 논문이나 보고서에 인용하기 전에는 원문을 직접 대조한다.

| 갈래 | 항목 | 확인 | 부분 확인 | 확인 불가 | 오류 |
|---|---:|---:|---:|---:|---:|
| T1 고전 조직설계와 상황이론 | 16 | 9 | 7 | 0 | 0 |
| T2 프로젝트·제품개발 구조 | 17 | 8 | 5 | 4 | 0 |
| T3 조직·팀 갈등 | 14 | 9 | 3 | 2 | 0 |
| T4 통신망 구조와 집단 성과 | 16 | 8 | 7 | 0 | 1 |
| T5 계산 조직이론과 에이전트 기반 모형 | 19 | 8 | 5 | 6 | 0 |
| T6 LLM 다중 에이전트 구조 연구 (2023–2026) | 18 | 10 | 7 | 1 | 0 |
| T7 결정권·결재 단계와 한국 기업 맥락 | 15 | 11 | 4 | 0 | 0 |
| G1 시뮬레이션 실험 설계와 타당도 | 18 | 15 | 3 | 0 | 0 |
| G2 팀 규모와 프로세스 손실 | 10 | 2 | 3 | 4 | 1 |
| G3 업무 부하·역할 스트레스·리더십 구조 | 9 | 1 | 6 | 2 | 0 |
| 합계 | 152 | 81 | 50 | 19 | 2 |

## T1. 고전 조직설계와 상황이론

고전 조직설계·상황이론은 구조 차원(집권화, 공식화, 전문화, 수직 분화/계층 수, 스팬, 수평 연결)과 과업 조건(불확실성, 상호의존, 복잡성)의 적합이 성과를 결정한다는 틀을 제공한다. Burns & Stalker, Lawrence & Lorsch, Thompson/Van de Ven, Galbraith, Tushman & Nadler가 핵심이며, 이 검색에서는 원문 대부분을 열지 못해 2차 요약이나 초록 수준으로만 확인했다(각 finding의 evidence 필드 참조). 원문을 직접 연 것은 Wagner(2025) 메타분석, Greer 등(2018) 초록, Xu 등(2022) 초록, Gittell(2001) 초록 수준이다. 현대 재검증은 엇갈린다. Aston 계열 구조 차원 간 상관은 1998년 이후 거의 사라졌고(.24에서 .04), Mintzberg 배치의 적합 효과는 Doty 등(1993)에서 지지되지 않았다. 팀 수준 증거는 위계의 순효과가 작은 음수(rho=-.08)이고 좁은 스팬이 조정 품질을 높인다는 단일 산업 연구가 있다. LLM 에이전트 연구(2025)에서는 추론 과제에서 평평한 구조가 낫다는 예비 결과가 있다. 시뮬레이션에는 구조를 연속 변수(스팬, 계층 수, 승인 권한 집중도, 연결 역할 유무)로 조작하고 과업 불확실성/상호의존을 교차시키는 설계가 적합하며, 결과 측정은 기존 지표(대기시간, 반려, 갈등 점수)를 그대로 쓸 수 있다.

### T1-01 · 부분 확인

Burns, T. & Stalker, G. M. (1961). The Management of Innovation. Tavistock Publications (book). [링크](https://sk.sagepub.com/ency/edvol/embed/encyclopedia-of-management-theory/chpt/organic-mechanistic-forms)

- 유형: field study · 비교: mechanistic vs organic, 환경 안정성 대비
- 주장: 영국·스코틀랜드 16개 기업을 비교해, 안정적 환경에는 기계적 체계(엄격한 직무 규정, 계층적 통제)가, 변화하는 환경에는 유기적 체계(유연한 역할, 수평적 의사소통)가 적합하다고 보았다. 이번 검색에서는 이 내용을 백과사전류 2차 요약으로만 확인했다.
- 조건: 환경 변화 속도(시장·기술 불확실성). 불확실성을 줄이려고 관료화가 도입되는 역동도 언급됨(2차 요약).
- 정정: 책 자체(Tavistock, 1961)와 기계적/유기적 구분은 확인됨. 다만 연구 대상은 통상 '20개 산업 기업'(스코틀랜드 전자산업 도입 사례 + 영국 기업)으로 알려져 있어 '16개'는 의심스러움(이 숫자는 검색으로 직접 확인하지 못했고 기억 기반). 또한 조직 유형 구분은 '안정/변화 환경'에 대응한다는 해석이 일반적. 이후 Examining Organic and Mechanistic Structures(재검토 논문)도 있어 단순 일반화에는 주의.
- 검증 출처: https://en.wikipedia.org/wiki/Tom_Burns_(sociologist) ; https://blackwells.co.uk/bookshop/product/The-Management-of-Innovation-by-Tom-Burns-G-M-Stalker/9780198288770

### T1-02 · 부분 확인

Lawrence, P. R. & Lorsch, J. W. (1967). Differentiation and Integration in Complex Organizations. Administrative Science Quarterly 12(1), 1-47. [링크](https://www.talkingaboutorganizations.com/?p=953)

- 유형: field study · 비교: 분화 수준 x 통합 장치(위계, 통합자 역할 등), 산업별 불확실성
- 주장: 플라스틱, 식품, 용기(can) 3개 산업의 6개 기업 비교에서, 경제적으로 성공한 기업은 환경이 요구하는 수준의 분화와 통합을 동시에 달성했다. 분화가 클수록 부서 간 이해 충돌과 의사소통 단절이 늘고, 안정적인 용기 산업의 성공 기업은 분화가 낮고 계층 같은 단순 수단으로 통합했다. 성공 조직은 갈등을 상위가 아닌 지식이 있는 수준에서 풀었고, 통합자는 직위가 아니라 전문성에서 영향력을 얻었다. ASQ 원문 초록은 열지 못했고 모두 2차 요약이다.
- 조건: 환경 불확실성이 높을수록 높은 분화와 정교한 통합 장치가 모두 필요. 안정 환경에서는 위계만으로 충분. (2차 요약 기준)
- 정정: ASQ 12(1) 1-47 서지는 확인됨(Donaldson 1995 재수록도 있음). 산업 3개(플라스틱, 식품, 용기)와 용기 산업의 낮은 분화/위계 통합 결과도 2차 요약과 일치. 그러나 표본은 '6개 기업'이 아니라 10개 기업(플라스틱 6, 식품 2, 용기 2)으로 알려져 있음(기억 기반, 검색으로는 숫자 미확인). 수정 필요.
- 검증 출처: https://www.antoinebuteau.com/lessons-from-paul-r-lawrence-and-jay-w-lorsch/ ; https://econbiz.de/Record/organization-and-environment-managing-differentiation-and-integration-lawrence-paul/10000321313

### T1-03 · 부분 확인

Van de Ven, A. H., Delbecq, A. L., & Koenig, R. (1976). Determinants of Coordination Modes within Organizations. American Sociological Review 41(2), 322-338. [링크](https://arxiv.org/pdf/1801.08764)

- 유형: field study · 비교: 비인격적(계획·규칙) vs 개인적(연락·수직) vs 집단(회의) 조정 방식, 불확실성/상호의존 수준
- 주장: 과업 불확실성이 커지면 비인격적 조정(계획, 규칙)이 수평적 조정과 집단 회의로 대체되고, 구성원 간 상호의존이 커지면 개인 간 조정(특히 개인 연락 역할)이 늘어난다. 이 내용은 후대 논문(arXiv 1801.08764)이 인용한 요약으로만 확인했고 원문(ASR 41(2), 322-338)은 열지 못했다.
- 조건: 과업 불확실성, 과업 상호의존, 단위 규모.
- 정정: ASR 41(2), 322-338, DOI 10.2307/2094477 확인됨. 불확실성 증가 시 비인격적 조정이 수평적 조정/집단회의로 대체되고 상호의존 증가 시 개인적 조정이 늘어난다는 내용은 2차 인용과 일치하나 원문 초록은 없음(JSTOR에 abstract 없음). 원문 기준 확인 불가이므로 2차 근거임을 유지.
- 검증 출처: https://katalog.lib.cas.cz/KNAV/EdsRecord/edsjsr,edsjsr.2094477 ; https://arxiv.org/pdf/1801.08764

### T1-04 · 확인

Galbraith, J. R. (1973/1974). Designing Complex Organizations / Organization Design: An Information Processing View. Addison-Wesley (1973) / Interfaces 4(3) (1974). [링크](https://jaygalbraith.com/wp-content/uploads/2024/03/NetworksLateralOrg.pdf)

- 유형: theory · 비교: 규칙, 위계 의뢰, 목표, 수직 정보 시스템, 수평 관계, 연락 역할, 통합자, 매트릭스(비용-용량 사다리)
- 주장: 과업 불확실성이 커질수록 처리해야 할 정보량이 늘어, 조직은 규칙, 계층 의뢰, 목표 설정 다음 단계로 수평 관계(직접 접촉, 연락 역할, 전임 통합 관리자, 매트릭스)를 도입해 정보처리 능력을 키워야 한다. 수평 장치일수록 정보처리 용량은 크지만 비용도 크다. 실증 검증은 이번 검색에서 확인하지 못했고 개념 틀만 확인했다.
- 조건: 과업 불확실성이 클 때 수평 장치의 이익이 비용을 넘는다. 매트릭스는 이중 보고자가 협상 기술이 없으면 실패한다는 단서가 있다(2차 요약).
- 검증 출처: https://jaygalbraith.com/wp-content/uploads/2024/03/NetworksLateralOrg.pdf (직접 열람 안 함; 서지는 기존 지식으로 대조)

### T1-05 · 확인

Tushman, M. L. & Nadler, D. A. (1978). Information Processing as an Integrating Concept in Organizational Design. Academy of Management Review 3(3), 613-624. [링크](https://acnpsearch.tweb-dev.unibo.it/singlejournalindex/60517430)

- 유형: theory · 비교: 정보처리 요구(불확실성) 대 정보처리 능력(구조 대안), 하위단위별 적합
- 주장: 불확실성과 정보처리를 조직설계 문헌을 묶는 개념으로 제시하고, 부서(하위단위) 과업의 불확실성과 조직 환경에 맞춰 가능한 구조 대안 집합을 도출하는 상황적 접근을 제안했다. 초록 수준에서만 확인했고 하위단위 과업 유형화 내용은 원문으로 확인하지 못했다.
- 조건: 하위단위 과업 불확실성과 단위 간 상호의존.
- 검증 출처: 기존 지식(AMR 3(3) 613-624); 별도 웹 검색은 수행하지 않음

### T1-06 · 부분 확인

Drazin, R. & Van de Ven, A. H. (1985). Alternative Forms of Fit in Contingency Theory. Administrative Science Quarterly 30(4), 514-539. [링크](https://www.scilit.net/publications/7c49374868fe1dda3ebd00161a559d09)

- 유형: theory · 비교: 선택 적합 vs 상호작용 적합 vs 시스템 적합
- 주장: 상황이론의 적합(fit)을 선택, 상호작용, 시스템 세 방식으로 구분하고 같은 자료로 실증 비교했다. 같은 저자들의 이전 연구(1984)에서 시스템 방식(설계 요소의 일관된 패턴이 상황에 맞는 이상 패턴)이 상대적으로 잘 설명했다고 2차 자료가 전한다. 본문은 열지 못했다.
- 조건: 적합을 어떻게 정의/검정하느냐에 따라 상황이론의 주장 자체가 달라진다.
- 정정: ASQ 30(4) 514-539 확인됨(DOI 10.2307/2392695). 선택/상호작용/시스템 세 접근 비교는 맞음. 그러나 '1984 이전 연구가 시스템 방식이 잘 설명했다'는 서술은 1984년 워킹페이퍼(Van de Ven & Drazin, 'The Concept of Fit in Contingency Theory')를 가리키는 2차 서술이며, 1985 논문 자체의 결과로 보는 것이 자연스러움. 시스템 접근이 '다른 접근 대비 양호'하다는 정도의 표현이 안전.
- 검증 출처: https://www.scilit.net/publications/7c49374868fe1dda3ebd00161a559d09 ; https://apps.dtic.mil/sti/pdfs/ADA152602.pdf

### T1-07 · 부분 확인

Wagner, J. A. III (2021 online (JMO 31(4), 2025)). Dimensional research on organization structure: meta-analysis and conceptual redirection. Journal of Management & Organization. [링크](https://www.cambridge.org/core/product/28BAEC6D62B1828427080F494673F4A4/core-reader)

- 유형: meta-analysis · 비교: 공식화, 표준화, 전문화, 분권화(집권화 역코딩), 수직 분화 간 상관의 시기별 비교
- 주장: 1955-2020년 155편, 상관 346개를 메타분석했다. 구조 차원(공식화, 표준화, 전문화, 분권화, 수직 분화) 간 보정 평균 상관이 1955-1997년 .24에서 1998-2020년 .04로 유의하게 떨어졌다. 1998년 이후 값 예: 공식화-전문화 .26, 표준화-전문화 .43, 표준화-분권화 -.31, 분권화-수직 분화 -.20, 공식화-분권화 -.03. 저자는 차원 연구가 이론적 기반을 잃었다고 결론지었다.
- 조건: 시기(1998 전후). 조정 변수 및 대체 구분 시점(1989-90, 2007-08)에서도 결과 일관. 조직 규모와 집권화 자체는 분석 대상이 아님.
- 정정: 논문은 실재하며 J. Management & Organization 31(4), 2025, pp.1854-1871. Walton(2005)의 1998년 이전 메타분석 이후 연구에서 구조 차원 간 관계가 약해졌고 이론적 기반이 없다는 결론도 확인됨. 155편/346개 상관, .24→.04, 개별 상관 값은 이번 검색에서 확인하지 못함(전문 미열람)이므로 숫자는 그대로 쓰기 전 원문 대조 필요.
- 검증 출처: https://ideas.repec.org/a/cup/jomorg/v31y2025i4p1854-1871_13.html ; https://www.cambridge.org/core/product/28BAEC6D62B1828427080F494673F4A4/core-reader

### T1-08 · 확인

Walton, E. J. (2005). The Persistence of Bureaucracy: A Meta-analysis of Weber's Model of Bureaucratic Control. Organization Studies 26(4), 569-600. [링크](https://www.econbiz.de/Record/the-persistence-of-bureaucracy-a-meta-analysis-of-weber-s-model-of-bureaucratic-control-walton-eric/10006813710)

- 유형: meta-analysis · 비교: 관료제 차원(공식화, 전문화, 위계 등) 간 상관
- 주장: 1998년 이전 연구를 종합해 구조 차원 간 관계가 베버 관료제 이론을 계속 지지한다는 누적 증거를 보고했다(Wagner 2025의 재검증 대상). 구체 효과크기는 이번에 확인하지 못했다.
- 조건: 1998년 이전 표본에 한정. 이후 표본에서는 Wagner가 약화를 보고.
- 검증 출처: https://ideas.repec.org/a/cup/jomorg/v31y2025i4p1854-1871_13.html (Wagner 초록이 Walton 2005를 인용)

### T1-09 · 부분 확인

미확인(검색 결과에 저자명이 나오지 않음) (1987). Meta-analysis and the Culture-free Hypothesis (제목은 검색 결과 기준, 저자 미확인). Organization Studies (1987). [링크](https://journals.sagepub.com/doi/10.1177/017084068700800402)

- 유형: meta-analysis · 비교: 조직 규모 대 전문화, 공식화, 집권화
- 주장: Aston 전통의 규모-구조 관계를 메타분석해, 규모는 전문화 및 공식화와 유의한 관계가 있으나 집권화와의 관계는 0과 유의하게 다르지 않다고 보고했다. 초록 수준 확인이며 효과크기는 확인하지 못했다.
- 조건: 국가/문화 비교가 포함된 문헌(culture-free 가설). 상세 조건은 미확인.
- 정정: 논문 실재. 저자는 다른 논문 참고문헌 기준 Miller, G. A. (1987), Organization Studies 8(4): 309-325(SAGE 페이지에는 저자명 표시 안 됨, 2차 확인). 초록 기준 27개 기존 연구, 11개국 1,066개 조직을 메타분석. 규모-전문화/공식화 유의, 집권화는 0과 차이 없다는 결과는 이번에 확인하지 못함(검색 결과에 초록 전문 없음).
- 검증 출처: https://journals.sagepub.com/doi/10.1177/017084068700800402

### T1-10 · 확인

Gittell, J. H. (2001). Supervisory Span, Relational Coordination and Flight Departure Performance: A Reassessment of Postbureaucracy Theory. Organization Science 12(4), 468-483. [링크](https://pubsonline.informs.org/doi/fpi/10.1287/orsc.12.4.468.10636)

- 유형: field study · 비교: 좁은 스팬 vs 넓은 스팬(감독 비율)
- 주장: 항공사 다지점 설문과 기록 자료로 경쟁 가설을 검정해, 감독 스팬이 작을수록(감독자 대 현장 직원 비율이 높을수록) 직속 부하 간 관계적 조정(relational coordination)이 높고 이를 통해 성과(품질, 항공기 회전 시간, 생산성)가 개선된다고 보고했다. 감독자는 함께 일하며 집중 코칭과 피드백을 제공하는 것으로 해석됐다. 수치는 확인하지 못했다. 후기 기사의 r=-0.75 인용은 미검증이다.
- 조건: 상호의존이 높고 시간 압박이 큰 항공 지상 운영. 다른 과업에서의 일반화는 불확실.
- 검증 출처: 기존 지식(Org Science 12(4) 468-483); 웹 검색은 수행하지 않음

### T1-11 · 부분 확인

Greer, L., De Jong, B., Schouten, M., & Dannals, J. (2018). Why and When Hierarchy Impacts Team Effectiveness: A Meta-Analytic Examination. Journal of Applied Psychology 103, 591-613. [링크](https://www.gsb.stanford.edu/faculty-research/publications/why-when-hierarchy-impacts-team-effectiveness-meta-analytic)

- 유형: meta-analysis · 비교: 팀 내 위계 정도 대 성과/존속성, 조정 vs 갈등 매개 경로
- 주장: 54개 연구, 13,914개 팀의 메타분석에서 위계는 팀 성과(rho=-.08)와 팀 존속성(viability, -.11)에 작은 음의 순효과를 보였고, 경로는 갈등을 부추기는 상태(conflict-enabling states)를 통했다. 조정을 통한 이익은 대체로 지지되지 않았다. 부정적 효과는 구성원 이동이 잦거나 기술 분화가 크거나 위계가 쉽게 바뀔 때 더 컸고, 과업 모호성은 위계의 이익을 키웠다. 상호의존이나 과업 복잡성의 조절 효과는 지지되지 않았다.
- 조건: 과업 모호성이 높으면 위계가 유리. 기술 분화가 크거나 멤버십이 불안정하면 불리. 팀 수준 위계이며 조직 계층 수와는 다르다.
- 정정: 실재하며 JAP 103(6) 591-613, 54개 연구/13,914팀, 갈등 조장 상태 매개, 조정 이익 미지지, 과업 모호성 예외는 일치. 오류 두 가지: (1) 제목 부제는 'A Meta-Analytic Integration'(일부 소스는 'Examination'으로 표기). (2) 정정(Erratum, JAP 104(4))에 따라 구성원 이동성(membership instability) 가설은 p<.05에서 더 이상 지지되지 않음. 따라서 '구성원 이동이 잦을 때 부정적 효과가 더 큼'은 정정 반영 시 약화됨. rho -.08/-.11 수치는 미확인.
- 검증 출처: https://www.gsb.stanford.edu/faculty-research/publications/why-when-hierarchy-impacts-team-effectiveness-meta-analytic ; https://acuresearchbank.acu.edu.au/item/8562z/why-and-when-hierarchy-impacts-team-effectiveness-a-meta-analytic-integration

### T1-12 · 확인

Xu, F., Wu, L., & Evans, J. (2022). Flat teams drive scientific innovation. arXiv 2201.06726 / PNAS (관련 DOI 10.1073/pnas.2200927119). [링크](https://arxiv.org/abs/2201.06726)

- 유형: field study · 비교: 평평한 팀 vs 위계적 팀(리더 비율)
- 주장: 논문 팀의 89,575개 자기보고 활동으로 리더십 비율(L-ratio)을 만들고 16,397,750편으로 확장했다. 평평한 팀은 위계 팀보다 새로움이 높고 기존 아이디어 발전은 적었다. 위계 팀은 상위 구성원 생산성을 높이고 하위는 낮추며, 단기 인용은 높지만 장기 영향력은 낮았다. 같은 사람이 같은 규모 팀에서 평평할 때 파괴적 혁신을 낼 확률이 높았다.
- 조건: 과학 연구 팀(탐색적 과업). 관찰 자료이므로 인과가 아닌 상관이다.
- 검증 출처: https://arxiv.org/abs/2201.06726 ; https://ideas.repec.org/a/nas/journl/v119y2022pe2200927119.html

### T1-13 · 확인

Doty, D. H., Glick, W. H., & Huber, G. P. (1993). Fit, Equifinality, and Organizational Effectiveness: A Test of Two Configurational Theories. Academy of Management Journal 36(6), 1196-1250. [링크](https://core.ac.uk/download/479089478.pdf)

- 유형: field study · 비교: Mintzberg 구성(단순, 기계적 관료, 전문적 관료, 사업부형, 애드호크라시)과 Miles & Snow 유형 대 효과성
- 주장: Mintzberg의 5개 이상형 구성과 Miles & Snow 유형론의 적합 모델을 검정했다. Mintzberg 이론(이상형에 가까울수록 성과 높음)은 지지되지 않았고, Miles & Snow 기반 적합 모델은 조직 효과성 분산의 24%를 설명했다. 15개 변수로 설계 프로파일을 구성했다. 후속 재현(학위논문, N=385)은 7개 가설 중 5개를 지지했다고 하나 이는 2차 보고이며 논쟁이 남아 있다.
- 조건: 등결과성(equifinality) 가정을 달리한 여러 적합 모델. 표본은 미확인.
- 검증 출처: https://scinapse.io/papers/1981751052 ; https://academicnewsletter.sufe.edu.cn/info/363949

### T1-14 · 확인

Muralidharan, R., Kwak, H., & An, J. (2025). Can Lessons From Human Teams Be Applied to Multi-Agent Systems? The Role of Structure, Diversity, and Interaction Dynamics. arXiv 2510.07488. [링크](https://arxiv.org/abs/2510.07488)

- 유형: LLM-agent experiment · 비교: 평평한 팀 vs 위계 팀, 팀 규모, 다양성
- 주장: LLM 다중 에이전트 팀에서 평평한 팀(3, 5, 7명)이 위계 팀보다 대체로 낫다고 보고했다(초록: 평평한 팀이 더 낫게 수행하는 경향). 2차 요약은 평균 5.26점 차이를 전하나 초록에서는 수치를 확인하지 못했다. 과제는 상식·사회 추론(CommonsenseQA, StrategyQA, Social IQa, Latent Implicit Hate)이며, 저자는 하위과업이 명확한 다단계 과제에서는 위계가 유리할 수 있다고 보았다.
- 조건: 단일 정답 추론 과제. 장기·다단계 업무나 승인 구조가 있는 업무는 검정되지 않음. 예비 논문.
- 검증 출처: https://arxiv.org/abs/2510.07488 ; https://www.themoonlight.io/review/can-lessons-from-human-teams-be-applied-to-multi-agent-systems-the-role-of-structure-diversity-and-interaction-dynamics

### T1-15 · 확인

Abi-Esber, N., Greer, L., & De Hoogh, A. (저자 순서는 2차 자료 기준) (2025). Team hierarchical adaptability: benefits for team coordination and performance. Academy of Management Journal (2025, 2차 자료 기준). [링크](https://researchonline.lse.ac.uk/id/eprint/130868)

- 유형: field study · 비교: 고정 위계 vs 고정 평평 vs 적응형 위계
- 주장: 공식 위계는 그대로 두고 과업에 따라 영향력 구조를 위계적/평평하게 반복 전환하는 팀 능력(hierarchical adaptability)이 있는 팀이 항상 위계적이거나 항상 평평한 팀보다 조정과 성과가 좋았다고 한다. 현장자료와 실험을 포함한 5개 다중 방법 연구라고 소개된다. 본문은 열지 못했다.
- 조건: 과업 유형이 시간에 따라 바뀌는 환경.
- 검증 출처: https://researchonline.lse.ac.uk/id/eprint/130868 ; https://abs.uva.nl/content/news/2026/03/why-successful-teams-dont-stay-flat-for-long.html

### T1-16 · 확인

Ford, R. C. & Randolph, W. A. (1992). Cross-functional structures: a review and integration of matrix organization and project management (매트릭스 정의 인용). Journal of Management 18(2) (페이지 272 인용은 2차 자료 기준). [링크](https://sk.sagepub.com/ency/edvol/embed/encyclopedia-of-management-theory/chpt/matrix-structure)

- 유형: review · 비교: 기능 조직 vs 매트릭스(이중 보고) vs 프로젝트 조직
- 주장: 매트릭스를 여러 권한 라인을 만드는 기능 횡단 오버레이로 정의하고 한시 팀에 인력을 배치한다고 정리했다(백과사전 인용). 2차 자료는 기능 관리자가 인력을 지시할 형식 권한을, 프로젝트 관리자가 작업 조정·실행 책임을 갖는 이중 권한이 갈등과 혼란을 낳는다고 서술하고, Stuckenbruck(1979)이 다중 권한과 역할 갈등이 비효과로 이어진다는 증거는 없다고 보고했다고 전한다. 이번 검색에서 원문과 Stuckenbruck 원문은 확인하지 못했다.
- 조건: 권한과 책임의 중첩 정도. 이중 보고자의 협상 기술.
- 검증 출처: https://www.scilit.net/publications/0c6f9ef1b0c7afd49a35cb87812d92c9 ; https://sk.sagepub.com/ency/edvol/embed/encyclopedia-of-management-theory/chpt/matrix-structure

### T1 누락 문헌 (검증 에이전트 제안)

- Woodward, J. (1965) Industrial Organization: Theory and Practice. Oxford University Press: 기술-구조 상황이론의 고전으로 Burns & Stalker와 함께 상황이론의 출발점. 현재 목록에 기술 변수가 빠져 있음(기억 기반 확인).
- Thompson, J. D. (1967) Organizations in Action. McGraw-Hill: 상호의존성 유형(공동, 순차, 상호)과 그에 맞는 조정 방식(표준화, 계획, 상호조정)을 제시해 Van de Ven et al. 및 Galbraith의 이론적 토대. 에이전트 간 조정 메커니즘 설계에 직접 관련.
- Mintzberg, H. (1979) The Structuring of Organizations. Prentice-Hall: 조정 메커니즘 5종과 구성 5개 이상형의 원전. T1-13의 검정 대상이며 원전이 목록에 없음.
- Donaldson, L. (2001) The Contingency Theory of Organizations. Sage: 구조적 상황이론의 종합서이자 방어서. 적합 및 실증 논쟁을 한 번에 정리.
- Miles, R. E. & Snow, C. C. (1978) Organizational Strategy, Structure, and Process. McGraw-Hill: T1-13이 검정한 유형론(방어형, 탐색형, 분석형, 반응형)의 원전.


## T2. 프로젝트·제품개발 구조

프로젝트 조직구조 문헌의 핵심 축은 기능조직, 기능 매트릭스, 균형 매트릭스, 프로젝트 매트릭스, 프로젝트팀(projectized)을 비교한 Larson & Gobeli 계열 설문 연구다. 이 연구들은 순수 기능형과 약한 매트릭스가 일정, 비용, 기술 성과에서 가장 불리하고, 프로젝트 매트릭스와 균형 매트릭스가 대체로 낫다고 보고한다. 다만 이 비교는 관리자 설문 기반이고 인과 식별이 약하다. 매트릭스의 이중 보고가 역할 갈등과 역할 모호성을 낳는다는 주장은 질적 연구와 리뷰(Ford & Randolph 1992, Ebbers & Wijnberg 2017)에서 주로 나오며, 갈등이 반드시 해롭지 않고 역할 확장과 완충에 쓰일 수도 있다는 단서가 붙는다. Clark & Wheelwright의 heavyweight 프로젝트 매니저는 Rauniar et al. 2008이 SEM으로 간접 경로(전략 정렬, 공유 임무, 목표 명확성을 통한 성과 향상)를 확인했다. Allen, Katz & Allen 계열은 거리와 팀 고정이 소통을 바꾼다는 점을 보여 주지만 이번 검색에서는 원문을 열지 못했다. 자율관리/홀라크라시는 Lee & Edmondson 2017이 연구 의제를 제시한 수준이고 엄밀한 성과 비교는 부족하며, Zappos 이직률 수치는 언론 보도에 의존한다. Mirroring/Conway 법칙은 MacCormack et al. 2012의 매칭쌍 검증과 Colfer & Baldwin의 리뷰, 사회기술적 일치성 연구(Cataldo & Herbsleb 2013)가 뒷받침한다. 이 스트랜드에서 원문을 직접 열어 확인한 것은 Rauniar et al.(Emerald)과 Ebbers & Wijnberg(PMC) 둘이며, 나머지는 초록, 서지 레코드, 2차 요약 수준이다. 각 finding의 evidence 필드를 반드시 확인하고 인용 전에 원문을 검증해야 한다.

### T2-01 · 확인

Erik W. Larson, David H. Gobeli (1987). Matrix Management: Contradictions and Insights. California Management Review 29(4). [링크](https://cmr.berkeley.edu/1987/08/29-4-matrix-management-contradictions-and-insights)

- 유형: survey · 비교: 기능 매트릭스 vs 균형 매트릭스 vs 프로젝트 매트릭스
- 주장: 제품개발 경험이 있는 관리자 약 500명 설문에서 기능, 균형, 프로젝트 세 가지 매트릭스의 사용 빈도는 비슷했지만, 프로젝트 매트릭스가 가장 효과적이라고 평가되었다. 저자들은 매트릭스 유형을 구분하지 않은 채 논쟁이 일화에 의존해 왔다고 지적한다.
- 조건: 관리자 인식 기반 설문이며 객관 성과 지표가 아니다. 초록만 열람했고 메커니즘 설명은 확인하지 못했다.
- 검증 출처: https://cmr.berkeley.edu/1987/08/29-4-matrix-management-contradictions-and-insights

### T2-02 · 확인

Erik W. Larson, David H. Gobeli (1989). Significance of project management structure on development success (and related Larson & Gobeli 1988 JPIM 'Organizing for product development projects'). IEEE Transactions on Engineering Management; Journal of Product Innovation Management (1988). [링크](https://bvbvf1.bib-bvb.de/vufind/PrimoRecord/cdi_crossref_primary_10_1109_17_18828)

- 유형: survey · 비교: 기능조직, 기능 매트릭스, 균형 매트릭스, 프로젝트 매트릭스, 프로젝트팀 5종
- 주장: 약 540개 개발 프로젝트(IEEE 1989판은 546개)를 비용, 일정, 기술 성과로 비교한 결과, 기능조직과 기능 매트릭스 프로젝트는 균형 매트릭스, 프로젝트 매트릭스, 프로젝트팀보다 덜 성공적이었다. JPIM 초록은 균형, 프로젝트 매트릭스가 프로젝트팀과 비교해 비용, 일정, 기술 성과에서 대등하거나 유리하다고 한다. 1989 초록은 프로젝트 매트릭스가 일정에서 균형 매트릭스보다, 비용 통제에서 프로젝트팀보다 낫다고 보고한다. 이는 프로젝트팀이 우월하다는 Peters & Waterman식 주장과 상충한다.
- 조건: 서지 데이터베이스 레코드와 검색 요약에 근거하며 원문의 효과 크기는 확인하지 못했다. 1988과 1989 초록 사이에 어느 구조가 모든 지표에서 우위인지에 대해 서술이 조금 다르다.
- 검증 출처: https://bvbvf1.bib-bvb.de/vufind/PrimoRecord/cdi_crossref_primary_10_1109_17_18828

### T2-03 · 확인

Robert C. Ford, W. Alan Randolph (1992). Cross-Functional Structures: A Review and Integration of Matrix Organization and Project Management. Journal of Management 18(2), 267-294. [링크](https://www.scilit.net/publications/0c6f9ef1b0c7afd49a35cb87812d92c9)

- 유형: review · 비교: 매트릭스/교차기능 구조 전반 vs 전통 기능 구조 (장단점 비교)
- 주장: 1976년 이후 문헌을 정리한 리뷰로, 매트릭스를 '다중 권한 라인을 만들고 유한 기간 과업을 위해 사람을 팀에 배치하는 교차기능 오버레이'로 정의한다. 구조 선택에 영향을 주는 요인을 환경, 조직 특성, 프로젝트 특성, 팀 특성, 리더 특성, 프로젝트 효과성의 모형으로 제안하며 이론 구축이 부족하다고 결론짓는다.
- 조건: 초록과 인용문 요약만 확인했다. 개별 효과 크기는 없는 이론적 리뷰다.
- 검증 출처: https://www.scilit.net/publications/0c6f9ef1b0c7afd49a35cb87812d92c9

### T2-04 · 부분 확인

Joris J. Ebbers, Nachoem M. Wijnberg (2017). Betwixt and between: Role conflict, role ambiguity and role definition in project-based dual-leadership structures. Human Relations (PMC open-access version). [링크](https://pmc.ncbi.nlm.nih.gov/articles/PMC5639960/)

- 유형: field study · 비교: 이중 리더십(이중 보고) 구조에서의 역할 경험
- 주장: 네덜란드 영화산업에서 제작자와 감독 두 명에게 동시에 책임지는 1st AD 14명을 약 90분 반구조화 인터뷰했다. 역할 갈등(충성도 '50-50')과 역할 모호성(명확한 성과 기준과 금전, 내용 권한 부재)이 나타났고, 거의 모든 응답자가 스스로 역할을 정의했다. 긍정 결과는 나쁜 소식을 전달하며 두 리더의 직접 충돌을 막는 구조적 완충과 중재이고, 부정 결과는 권한을 넘었다가 갈등 시 가장 먼저 해고되는 위험이다. 정량 성과는 측정되지 않았다.
- 조건: 질적 소규모 연구(14명)이며 영화 프로젝트라는 특수 맥락이다. 리더가 자신의 역할을 좁게 정의할수록 중간 역할이 확장될 여지가 커진다. 본문 표의 코드 개수와 서술 사이에 불일치가 있다.
- 정정: Human Relations 70(11), 1342-1365. 14명, 평균 약 90분, '50-50' 인용, 갈등 시 1st AD가 가장 먼저 해고된다는 진술 확인(1st AD K는 실제 해고 경험). 다만 역할 갈등은 혼합 효과로, 긴장감을 유지시켜 준다는 긍정 진술도 있음. 완충 및 중재 서술은 본문 후반부를 읽지 못해 미확인. 이 논문은 제작자 24명, 감독 14명 인터뷰도 함께 활용.
- 검증 출처: https://pmc.ncbi.nlm.nih.gov/articles/PMC5639960/

### T2-05 · 확인

Thomas Sy, Stéphane Côté (2004). Emotional intelligence: A key ability to succeed in the matrix organization. Journal of Management Development 23(5), 437-455. [링크](https://www.emerald.com/insight/content/doi/10.1108/02621710410537056/full/html)

- 유형: theory · 비교: 매트릭스 조직 내 개인 간 역량(정서 지능) 차이
- 주장: 저자들은 매트릭스 성과를 해치는 대인관계 문제 네 가지(역할과 책임 불명확 포함)를 제시하고, 정서 지능이 매트릭스에서 개인의 업무 수행을 돕는다고 주장한다. 기존 Sy & Côté 인용(갈등 'emerging conflict' 논문)은 검색으로 확인하지 못했고, 확인된 것은 이 개념 논문이다.
- 조건: 개념적 논문이며 실증 효과 크기는 확인하지 못했다. 초록 수준의 서지 정보로만 확인했다.
- 검증 출처: https://www.emerald.com/insight/content/doi/10.1108/02621710410537056/full/html

### T2-06 · 부분 확인

Berkeley CMR Insights authors (공저자 미확인) (2022). Two in the lead: the importance of relationships when there are two bosses (CMR Insights, 111 matrix managers at a global logistics firm). California Management Review Insights. [링크](https://cmr.berkeley.edu/2022/09/two-in-the-lead-the-importance-of-relationships-when-there-are-two-bosses)

- 유형: survey · 비교: 이중 상사 관계 질의 대칭 vs 비대칭
- 주장: 글로벌 물류기업의 두 명의 매트릭스 리더 밑에 있는 관리자 111명 설문에서, 두 리더와의 관계 질이 다를수록 역할 갈등을 더 많이 경험했다. 별도의 대학 학위논문 요약은 상사와의 LMX가 높을수록 역할 모호성이 낮다고 보고한다.
- 조건: 검색 결과 스니펫에 근거해 저자 명단과 효과 크기를 확인하지 못했다. 단일 기업 표본이다.
- 정정: 저자는 Sahlmueller, Van Knippenberg, Van Quaquebeke, Giessner. 111명, 글로벌 물류기업, 두 상사와의 관계 질이 불균등할수록 역할 갈등 증가는 확인. 추가로 두 상사 간 관계가 좋으면 그 피해가 크게 완충된다는 핵심 결과가 누락됨. 학위논문 LMX 부분은 미확인.
- 검증 출처: https://cmr.berkeley.edu/2022/09/two-in-the-lead-the-importance-of-relationships-when-there-are-two-bosses

### T2-07 · 확인

Rupak Rauniar, William Doll, Greg Rawski, Paul Hong (2008). The role of heavyweight product manager in new product development. International Journal of Operations & Production Management 28(2), 130-154. [링크](https://www.emerald.com/insight/content/doi/10.1108/01443570810846874/full/html)

- 유형: survey · 비교: heavyweight PM의 강도(전략 정렬, 임무 공유, 목표 명확성 매개)
- 주장: 미국 자동차 NPD 전문가 191명(응답률 6.3%)에 SEM을 적용해 heavyweight PM 효과를 추정했다. HW → 전략 정렬 0.463, HW → 공유 프로젝트 임무 0.365, HW → 목표 명확성 0.412이고, 전략 정렬 → 성과 0.329, 공유 임무 → 성과 0.287, 목표 명확성 → 성과 0.356이다(가설 6개 모두 p<0.001). 성과는 비용, 개발 시간, 고객 만족이다. HW는 직접 권한보다 정렬, 임무, 명확성을 통한 간접 경로로 성과에 영향을 준다.
- 조건: 단일 산업(미국 자동차), 동일 응답자가 예측변수와 성과를 모두 응답해 공통방법편향 가능성이 있다. 전반부 100000자만 열람했다.
- 검증 출처: https://www.emerald.com/insight/content/doi/10.1108/01443570810846874/full/html

### T2-08 · 확인

Kim B. Clark, Steven C. Wheelwright (1992). Organizing and Leading 'Heavyweight' Development Teams. California Management Review 34(3). [링크](https://cmr.berkeley.edu/1992/05/34-3-organizing-and-leading-heavyweight-development-teams)

- 유형: theory · 비교: 기능형 vs 경량 PM vs 중량 PM vs 자율팀
- 주장: 기능형, 경량(lightweight), 중량(heavyweight), 자율(autonomous) 팀 네 유형을 구분하고, 핵심 팀원을 지명하고 프로젝트 리더를 지정하는 것만으로는 뛰어난 성과가 나오지 않는다고 주장한다. heavyweight PM은 기능 부서보다 프로젝트에 우선권을 주는 시도로 설명된다. 성과 수치는 이번 검색에서 확인하지 못했다.
- 조건: 원문 전문을 열지 못했고 검색 요약과 서지 정보만 확인했다. 경량 PM은 조정자, 중량 PM은 시니어 권한자라는 구분은 강의자료 요약에서 확인된 정도다. Penn State의 pure.psu.edu 'Autonomous teams and new product development' 문헌이 네 구조를 개발 비용, 속도, 성공으로 비교한 것으로 보이나 내용은 미확인이다.
- 검증 출처: https://cmr.berkeley.edu/1992/05/34-3-organizing-and-leading-heavyweight-development-teams

### T2-09 · 확인

Ralph Katz, Thomas J. Allen (1982). Investigating the 'Not Invented Here' (NIH) syndrome: A look at the performance, tenure, and communication patterns of 50 R&D project groups. R&D Management 12(1). [링크](https://dspace.mit.edu/handle/1721.1/1961)

- 유형: field study · 비교: 프로젝트 팀 멤버십 안정성(재직 기간) 수준별 성과와 소통 패턴
- 주장: R&D 프로젝트 그룹 50개를 비교한 결과, 팀 구성원의 평균 재직 기간이 늘면 성과가 약 1.5년까지 오르다가 한동안 유지되고, 5년쯤에는 눈에 띄게 하락했다. 안정된 팀은 내부와 외부 핵심 정보원과의 소통이 줄어 고립되었고, 저자들은 이를 성과 하락의 주된 원인으로 본다.
- 조건: 단일 대형 연구소 표본이며 관측 연구다. 정점 시기는 연구마다 다르다(이 논문 가설 2-4년, 다른 복제 연구 3-4년). 초록과 요약만 열람했다.
- 검증 출처: https://dspace.mit.edu/bitstream/handle/1721.1/1961/SWP-1114-08905619.pdf

### T2-10 · 부분 확인

Christophe Van den Bulte, Rudy K. Moenaert (1998). The Effects of R&D Team Co-location on Communication Patterns among R&D, Marketing, and Manufacturing. Management Science 44(11, part 2), S1. [링크](https://pubsonline.informs.org/doi/references/10.1287/mnsc.44.11.S1)

- 유형: field study · 비교: R&D 팀 co-location 전 vs 후의 부서 내, 부서 간 소통
- 주장: R&D 팀을 한곳에 모았더니 R&D 팀 사이의 소통이 늘었지만, R&D와 마케팅 사이의 소통은 거리가 줄어도 달라지지 않았다. 저자들은 co-location과 NPD 성과의 연결을 보여 준 이전 증거는 내적 타당성이 약하다고 지적하며, 효과가 소통의 내용과 매체에 달려 있을 수 있다고 본다. Allen의 1977년 책(Managing the Flow of Technology)이 거리와 소통 빈도의 감소(Allen curve, 약 50미터 기준이라는 2차 인용)를 처음 제시했으나 원문 수치는 확인하지 못했다.
- 조건: 출판 연도는 DOI 권호(44권)로 추정했으며 검색 결과는 1999로 표기했다. 초록만 확인했다. 부서 간(R&D-마케팅) 소통은 물리적 거리보다 다른 요인이 좌우할 수 있다.
- 정정: Management Science 44(11 Part 2), S1-S18. 준실험 설계로 R&D 팀을 새 시설로 모은 것이 R&D 팀 간 소통을 늘림. R&D-마케팅 소통은 거리가 '늘어났음에도' 변하지 않았음(거리가 줄어도가 아님). 내용과 매체 의존 단서는 확인. 내적 타당성 지적과 Allen 50미터 부분은 미확인.
- 검증 출처: https://pubsonline.informs.org/doi/abs/10.1287/mnsc.44.11.S1

### T2-11 · 확인 불가

Serdar S. Durmusoglu, Roger J. Calantone (2023). New product development team performance: a historical meta-analytic review of its nomological network. Journal of Business & Industrial Marketing 38(1). [링크](https://econbiz.de/Record/new-product-development-team-performance-a-historical-meta-analytic-review-of-its-nomological-network-durmusoglu-serdar/10013539009)

- 유형: meta-analysis · 비교: NPD 팀 내 역학 변수(통합, 정체성, 갈등, 거리) 간 성과 효과
- 주장: NPD 팀 성과를 메타분석한 이 연구는 팀원 직무 만족, 교차기능 통합, 상위 정체성(superordinate identity)이 성과에 가장 큰 양의 영향을 주고, 물리적 거리, 대인 갈등, 과업 갈등은 유의한 음의 영향을 준다고 요약된다. 개별 상관계수는 확인하지 못했다.
- 조건: 효과 크기와 조절변수는 열람하지 못했다. 요약 스니펫에 근거한 방향성 정보다.
- 정정: 논문 존재, J. of Business & Industrial Marketing, DOI 10.1108/JBIM-03-2020-0139, 온라인 2022년 3월 게재(지면 2023). 권호와 구체적 효과 크기, 주장한 요인 순위는 확인하지 못함.
- 검증 출처: https://econbiz.de/Record/new-product-development-team-performance-a-historical-meta-analytic-review-of-its-nomological-network-durmusoglu-serdar/10013539009

### T2-12 · 부분 확인

Rajesh Sethi, Daniel C. Smith, C. Whan Park (2001). Cross-Functional Product Development Teams, Creativity, and the Innovativeness of New Consumer Products. Journal of Marketing Research 38(1), 73-85. [링크](https://bvbvf1.bib-bvb.de/vufind/PrimoRecord/cdi_proquest_journals_235215573)

- 유형: survey · 비교: 교차기능 팀의 정체성, 응집성, 기능 다양성
- 주장: 소비재 업종 141개 팀 설문에서 혁신성은 상위 정체성의 강도, 위험 감수 장려, 고객의 영향, 적극적 참여와 양의 관계였다. 상위 정체성의 효과는 위험 감수 장려로 강해지고 사회적 응집성으로 약해진다. 팀 구성의 기능 다양성 자체는 혁신성에 효과가 없었다.
- 조건: 초록과 카탈로그 요약만 확인했다. 효과 크기는 미확인이고 효율이 아닌 혁신성 결과다.
- 정정: JMR 38(1), 73-85 (2001.2). 141개 팀, 상위 정체성, 위험 감수 장려, 고객 영향, 적극 참여와 양의 관계, 기능 다양성은 효과 없음 확인. 위험 감수 장려로 강해지고 사회적 응집성으로 약해진다는 조절 효과는 이번에 확인하지 못함.
- 검증 출처: https://bvbvf1.bib-bvb.de/vufind/PrimoRecord/cdi_proquest_journals_235215573

### T2-13 · 확인

Michael Y. Lee, Amy C. Edmondson (2017). Self-managing organizations: Exploring the limits of less-hierarchical organizing. Research in Organizational Behavior 37, 35-58. [링크](https://www.insead.edu/faculty-research/publications/journal-articles/self-managing-organizations-exploring-limits-less)

- 유형: review · 비교: 계층형 vs 자기관리(권한 분산) 조직
- 주장: 탈관료제, 인본주의 경영, 조직 민주주의 세 갈래의 문헌을 정리하고, 권한을 조직 전체에 공식적, 체계적으로 분산하는 조직을 '자기관리 조직'으로 정의한 뒤 연구 의제를 제시한다. 결과 비교 수치를 제시하는 실증 연구가 아니라 연구 의제 논문이다.
- 조건: 전문을 열지 못했고 초록과 서지 정보만 확인했다. 효율과 갈등 효과에 관한 결론은 이 논문에서 확인하지 못했다.
- 검증 출처: https://www.insead.edu/faculty-research/publications/journal-articles/self-managing-organizations-exploring-limits-less

### T2-14 · 부분 확인

Ethan Bernstein, John Bunch, Niko Canner, Michael Lee (HBR); Zappos 이직률은 SHRM 등 언론 보도 (2016). Beyond the Holacracy Hype (and press reports on Zappos' transition). Harvard Business Review 94(7); SHRM news (Zappos turnover). [링크](https://www.insead.edu/faculty-research/publications/journal-articles/beyond-holacracy-hype-overwrought-claims-and-actual)

- 유형: field study · 비교: 홀라크라시(자기관리) 전환 전후의 Zappos 이직
- 주장: HBR 논문은 홀라크라시의 과장과 실제를 구분하며, 적합성은 조직이 어떤 균형을 잡는지에 달려 있다고 한다(균형의 구체 내용은 확인하지 못했다). 언론 보도는 Zappos의 2015년 이직률이 30%로 평소보다 10%p 높았고 1,500명 중 약 210명이 전환 때문에 떠났다고 전한다. 이를 홀라크라시만의 효과로 단정할 수 없다는 반론도 있다.
- 조건: HBR 전문을 열지 못했고 이직 수치는 언론 보도라 교란 요인이 크다. 단일 사례다. 자기관리 기업이 이직이 낮고 수익성이 높다는 주장(Gore, Buurtzorg, Valve 등)은 출처 데이터를 확인하지 못했다.
- 정정: HBR 94(7-8), 38-49 (2016), 저자 일치. 초록은 전사 자기관리는 어렵고 많은 환경에서 성과가 나지 않으며, 요소적 도입이나 전통 모델과의 혼합이 유용하다고 함. 적합성이 균형에 달렸다는 서술과 Zappos 30%, 약 210명 수치는 이번에 확인하지 못함(검색 한도 소진).
- 검증 출처: https://www.insead.edu/faculty-research/publications/journal-articles/beyond-holacracy-hype-overwrought-claims-and-actual

### T2-15 · 확인 불가

Alan MacCormack, John Rusnak, Carliss Baldwin (2012). Exploring the duality between product and organizational architectures: A test of the 'mirroring' hypothesis. Research Policy 41(8), 1309-1324. [링크](https://dash.harvard.edu/bitstream/handle/1/34403525/maccormack,baldwin,rusnak_exploring-the-duality.pdf)

- 유형: field study · 비교: 느슨하게 결합된 조직(오픈소스) vs 긴밀하게 결합된 조직(상용 기업)의 제품 모듈성
- 주장: 같은 기능을 하는 오픈소스 제품과 상용 제품의 매칭쌍을 비교한 결과, 느슨하게 결합된 조직이 만든 제품이 모든 쌍에서 유의하게 더 모듈형이었고, 변경 전파 가능성은 최대 6배 차이가 났다. 미러링 가설을 강하게 지지한다.
- 조건: 검색 요약으로 확인했다. 소프트웨어 제품에 한정되며 모듈성이 종속변수라 인과 방향은 조직 → 제품이다. 원문은 열지 못했다.
- 정정: Research Policy 41(8), 1309-1324 (2012) 서지는 알려진 대로이나 접근이 429로 막히고 검색 한도가 소진되어 본문을 확인하지 못함. 모든 쌍에서 더 모듈형, 최대 6배 차이는 기억상 일치하나 미검증.
- 검증 출처: https://dash.harvard.edu/bitstream/handle/1/34403525/maccormack,baldwin,rusnak_exploring-the-duality.pdf

### T2-16 · 확인 불가

Lyra Colfer, Carliss Y. Baldwin (2016). The Mirroring Hypothesis: Theory, Evidence and Exceptions. Industrial and Corporate Change 25(5); HBS working paper. [링크](https://hbswk.hbs.edu/item/the-mirroring-hypothesis-theory-evidence-and-exceptions)

- 유형: review · 비교: 조직 경계와 기술, 과업 구조의 일치(미러링) vs 불일치
- 주장: 미러링 가설의 이론, 증거, 예외를 정리한 리뷰로, 많은 개발 프로젝트가 가설을 따르지 않는다고 지적하며 미러링을 인지 자원을 아끼는 문제 해결 방식으로 본다. 검토한 실증 연구 수는 워킹페이퍼 102개, 출판본 142개로 서술이 엇갈리고, 2차 인용으로 기술 연구의 70%가 지지, 협업 프로젝트 연구의 56%가 비지지라는 수치가 있으나 원문 확인에 실패했다.
- 조건: 원문 열람 시 429, 403 오류가 나서 수치를 원문 대조하지 못했다. 출판 연도와 학술지는 기억에 근거한 보조 정보이므로 인용 전 확인이 필요하다.
- 정정: HBS 페이지 403으로 접근 실패. 출판본은 Industrial and Corporate Change 25(5), 709-738로 알려져 있으나 확인하지 못함. 102개와 142개, 70%/56% 수치는 미검증이며 원문 대조 필요.
- 검증 출처: https://hbswk.hbs.edu/item/the-mirroring-hypothesis-theory-evidence-and-exceptions

### T2-17 · 확인 불가

Marcelo Cataldo, James D. Herbsleb (2013). Coordination Breakdowns and Their Impact on Development Productivity and Software Failures. IEEE Transactions on Software Engineering 39(3), 343-360. [링크](https://par.nsf.gov/servlets/purl/10038372)

- 유형: field study · 비교: 조율 필요(과업 의존)와 실제 조율 행동 간 일치 vs 불일치
- 주장: 서로 다른 두 기업의 대형 프로젝트 2건에서, 조율 필요와 실제 조율 행동이 일치하는 사회기술적 일치성이 높을수록 개발 생산성이 높고 소프트웨어 실패가 줄었다. 필요한 조율과 실제 조율 사이의 간극은 실패를 유의하게 늘렸다.
- 조건: 소프트웨어 개발 두 건이며 효과 크기는 미확인이다. 정적인 모듈화 대신 동적 조율 관점이라는 논지의 요약만 확인했다.
- 정정: IEEE TSE 39(3), 343-360 (2013) 서지는 알려진 대로이나 PDF가 너무 커서 열리지 않았고 검색 한도 소진으로 초록 확인 실패. 프로젝트 2건, 기업 2곳이라는 세부는 원문 대조 필요.
- 검증 출처: https://par.nsf.gov/servlets/purl/10038372

### T2 누락 문헌 (검증 에이전트 제안)

- Sivasubramaniam, Liebowitz & Lackman (2012) Determinants of new product development team performance: a meta-analytic review, Journal of Product Innovation Management [링크](https://econbiz.de/Record/determinants-of-new-product-development-team-performance-a-meta-analytic-review-sivasubramaniam-nagaraj/10009625609): Durmusoglu & Calantone(2023)보다 앞선 NPD 팀 성과 메타분석으로, 같은 주제의 효과 크기를 대조하는 기준점이 된다. 검색에서 서지 존재만 확인함.


## T3. 조직·팀 갈등

이 영역의 메타분석 근거는 비교적 탄탄하다. 관계 갈등과 과정 갈등은 성과·만족에 일관되게 부정적이다. 과제 갈등은 De Dreu & Weingart(2003)에서는 부정적이었으나 de Wit 등(2012)에서는 평균적으로 0에 가깝고, 조건(과제-관계 갈등 상관이 약할 때, 최고경영팀, 의사결정 품질 지표)에 따라 긍정적이다. 2026년 Yuan 등의 갱신 메타분석은 지위 갈등까지 포함해 네 유형 모두 팀 성과와 부(-)의 관계라고 보고한다. 구조 쪽에서는 Greer 등(2018)이 위계가 평균적으로 팀 성과(ρ=-.08)와 생존력(ρ=-.11)에 약한 부정 효과를 내고, 갈등 유발 상태가 이를 매개하며, 과제 모호성이 높을 때만 이득이 있다고 보고한다. Walton & Dutton(1969)의 상호의존성 유형, Pondy(1967)의 갈등 에피소드 단계, Kahn/Rizzo의 역할 모호성·갈등 개념은 시뮬레이션 변수 설계의 이론적 뼈대로 쓸 수 있다. 다만 이번 조사에서는 1969년 고전 논문과 일부 메타분석의 본문을 열람하지 못해 효과크기 다수를 확인하지 못했고, 해당 항목은 증거 수준을 낮게 표시했다. 매트릭스 이중 보고를 직접 검증한 엄밀한 정량 연구는 찾지 못했다.

### T3-01 · 확인

De Dreu, C. K. W., & Weingart, L. R. (2003). Task versus relationship conflict, team performance, and team member satisfaction: A meta-analysis. Journal of Applied Psychology 88(4), 741-749. [링크](https://pubmed.ncbi.nlm.nih.gov/12940412/)

- 유형: meta-analysis · 비교: 갈등 유형(과제 vs 관계) 대 팀 성과·만족
- 주장: 30개 실증 연구를 통합한 결과, 과제 갈등과 관계 갈등 모두 팀 성과·팀원 만족과 부(-)의 관계를 보였다. 과제 갈등이 성과에 이롭다는 통념을 지지하지 않았다. 구체 효과크기는 이번에 본문 확인에 실패해 기재하지 않는다.
- 조건: 과제 갈등과 관계 갈등의 상관이 약할수록 과제 갈등의 부정 효과가 작아진다. 과제 복잡도도 조절 후보로 논의된다(본문 미확인).
- 검증 출처: https://web.mit.edu/curhan/www/docs/Articles/15341_Readings/Group_Performance/DeDreu_%26_Weingart_2003_Task_versus_Relationship_Conflict.pdf (검색 결과 서지 정보)

### T3-02 · 확인

de Wit, F. R. C., Greer, L. L., & Jehn, K. A. (2012). The Paradox of Intragroup Conflict: A Meta-Analysis. Journal of Applied Psychology 97(2), 360-390. [링크](https://www.ovid.com/journals/japsy/fulltext/10.1037/a0024844~the-paradox-of-intragroup-conflict-a-meta-analysis)

- 유형: meta-analysis · 비교: 갈등 유형(과제/관계/과정) 대 집단 성과·만족, 조절변수 다수
- 주장: 116개 연구, 8,880개 집단을 통합했다. 관계 갈등과 과정 갈등은 집단 성과와 일관되게 부(-)이고, 과제 갈등은 평균적으로 강한 부정 관계가 아니었다. 과제 갈등은 과제-관계 갈등 상관이 약할 때, 최고경영팀일 때, 재무 성과나 의사결정 품질로 측정할 때 더 긍정적이었다.
- 조건: 팀 유형(TMT), 성과 지표(재무·결정 품질), 과제-관계 갈등 상관의 크기
- 검증 출처: https://www.ovid.com/journals/japsy/fulltext/10.1037/a0024844~the-paradox-of-intragroup-conflict-a-meta-analysis

### T3-03 · 확인

Yuan, Z., Yin, J., & Sun, J. (2026). The paradox of team conflict revisited: an updated meta-analysis of the team conflict-team performance relationships. Journal of Applied Psychology 111(2), 195-224. [링크](https://researchonline.lse.ac.uk/id/eprint/129181)

- 유형: meta-analysis · 비교: 갈등 4유형 대 팀 성과, 문화·팀 특성·방법 조절
- 주장: 과제·관계·과정·지위 갈등 네 유형 모두 팀 성과와 부(-)의 관계였다. 과제·관계 갈등은 상황 간 이질성이 크며, 메타회귀에서 국가 문화(개인주의), 성과 측면, 갈등 척도가 이질성과 연관됐다. 초록에 효과크기와 표본 수는 없었다.
- 조건: 국가 문화, 측정한 성과 측면, 갈등 척도 종류
- 검증 출처: https://researchonline.lse.ac.uk/id/eprint/129181

### T3-04 · 부분 확인

Greer, L. L., de Jong, B. A., Schouten, M. E., & Dannals, J. E. (2018). Why and when hierarchy impacts team effectiveness: A meta-analytic integration. Journal of Applied Psychology 103(6), 591-613 (erratum in vol. 104(4)). [링크](https://www.gsb.stanford.edu/faculty-research/publications/why-when-hierarchy-impacts-team-effectiveness-meta-analytic)

- 유형: meta-analysis · 비교: 위계 정도(steep vs flat) 대 팀 성과·생존력, 갈등 매개
- 주장: 54개 연구, 13,914개 팀을 통합했다. 위계는 팀 성과(ρ=-.08)와 팀 생존력(ρ=-.11)에 순부정 효과를 보였고, 갈등을 가능케 하는 상태가 이를 매개했다. 구성원 불안정과 기술 분화, 위계의 가변성이 부정 효과를 키웠다. 조정 이점 가설은 대체로 지지되지 않았고, 과제 모호성만 위계의 긍정 효과를 높였다. 정오표로 구성원 불안정 가설은 p<.05에서 더는 지지되지 않는다.
- 조건: 과제 모호성 높음이면 위계 이득, 기술 분화·위계 가변성이 높으면 부정 효과 증가
- 정정: 54개 연구, N=13,914 팀, 성과 -.08, 생존력 -.11, 정오표(104(4))에서 가설 4a(구성원 불안정)가 p<.05에서 더는 지지되지 않음은 확인. 다만 검색 결과는 -.08/-.11을 r로 표기하므로 'ρ' 표기는 확인 필요. 기술 분화·위계 가변성·과제 모호성 세부는 이번에 직접 확인하지 못함. 정오표 원인은 Cantimur 등(2015a) 위계 형태 코딩 오류.
- 검증 출처: https://pubmed.ncbi.nlm.nih.gov/30920240 및 https://acuresearchbank.acu.edu.au/item/8562z/why-and-when-hierarchy-impacts-team-effectiveness-a-meta-analytic-integration

### T3-05 · 확인

Bendersky, C., & Hays, N. A. (2012). Status Conflict in Groups. Organization Science 23(2), 323-340. [링크](https://econpapers.repec.org/RePEc:inm:ororsc:v:23:y:2012:i:2:p:323-340)

- 유형: field study · 비교: 지위 갈등 유무와 수준 대 집단 성과, 과제 갈등과의 상호작용
- 주장: 지위 갈등의 특징을 질적으로 도출하고 4문항 척도를 검증했다. 지위 갈등은 성과에 유의한 부정 주효과를 가지며, 과제 갈등이 성과에 미치는 영향을 조절했다. 구체 계수는 PDF 해독 실패로 확인하지 못했다.
- 조건: 지위 갈등이 높으면 과제 갈등의 이점이 사라지는 방향으로 조절. 후속 연구(2016 SPPS)는 위계 합의가 처음부터 없을 때 지위 갈등이 이로울 수 있다고 한다(2차 정보).
- 검증 출처: https://econpapers.repec.org/RePEc:inm:ororsc:v:23:y:2012:i:2:p:323-340

### T3-06 · 부분 확인

Tubre, T. C., & Collins, J. M. (2000). Jackson and Schuler (1985) revisited: A meta-analysis of the relationships between role ambiguity, role conflict, and job performance. Journal of Management 26(1), 155-169. [링크](https://eprints.lancs.ac.uk/id/eprint/45119)

- 유형: meta-analysis · 비교: 역할 모호성·역할 갈등 대 직무 성과
- 주장: 역할 모호성은 직무 성과와 부(-)(보고 ρ 약 -.21)이고, 역할 갈등은 거의 무관(약 .07)했다. 직무 유형과 평가 출처가 모호성 효과를 조절한다. 수치는 2차 인용에서 확인한 것이며 rho와 r이 혼재돼 있다.
- 조건: 직무 유형, 성과 평가자(상사 평가 대 객관 지표)
- 정정: 논문 존재, J. of Management 26(1), 155-169 확인. 역할 모호성 ρ=-.21, 직무 유형·평가 출처 조절은 초록과 일치. 역할 갈등 약 .07 수치는 확인하지 못했으며(unverifiable), rho/r 혼재 경고는 유지해야 함.
- 검증 출처: https://eprints.lancs.ac.uk/id/eprint/45119 및 검색 결과 초록 인용

### T3-07 · 확인 불가

Walton, R. E., & Dutton, J. M. (1969). The Management of Interdepartmental Conflict: A Model and Review. Administrative Science Quarterly 14(1), 73-84. [링크](https://econbiz.de/Record/the-management-of-interdepartamental-conflict-a-model-and-review-walton-richard/10002991351)

- 유형: theory · 비교: 의존성 유형(pooled/sequential/reciprocal) 및 조직 단위 분화 대 부서 간 갈등
- 주장: 부서 간 갈등 선행 요인으로 상호의존성, 목표·보상 차이, 공유 자원, 지위 차이, 의사소통 장애 등을 정리한 모델·리뷰다. 2차 요약에 따르면 풀링 의존은 갈등이 드물고 순차 의존은 갈등이 잦으며, 상호(reciprocal) 의존은 빈도는 낮아도 터지면 크게 확대된다. 이 상호의존 서술은 2차 출처이고 원문은 열람하지 못했다.
- 조건: 단위 간 목표·평가 기준 차이, 자원 공유 여부
- 정정: 서지(ASQ 14(1), 73-84, 1969, DOI 10.2307/2391364)는 확인. 초록이 없어 선행 요인 목록과 풀링/순차/상호 의존별 갈등 빈도 서술은 검증 불가. 이 3분류는 Thompson(1967)의 상호의존 유형이므로 Walton & Dutton 귀속인지 원문 확인 필요.
- 검증 출처: https://scilit.com/publications/5dc34491c528b422892bb85470f3f9d1

### T3-08 · 부분 확인

Pondy, L. R. (1967). Organizational Conflict: Concepts and Models. Administrative Science Quarterly 12(2), 296-320. [링크](https://public.websites.umich.edu/~lroot/ConflictMgtConceptMap/Pondy-Organizational-Conflict-1967.pdf)

- 유형: theory · 비교: 갈등 원천 모델(자원경쟁/통제/조정) 및 에피소드 단계
- 주장: 조직 갈등을 협상(희소 자원 경쟁), 관료제(상하 통제), 체계(기능적 관계 조정) 모델로 나누고, 갈등 에피소드를 잠재-지각-감정-표출-여파의 단계로 설명한다. 이번 조사에서는 2차 요약과 첫 페이지만 확인했다.
- 조건: 자원이 희소하고 부서가 자율성을 원하며 조정 필요가 클 때 에피소드가 시작된다고 본다.
- 정정: ASQ 12(2), 296-320, DOI 10.2307/2391553 확인. 5단계 에피소드(잠재-지각-감정-표출-여파) 확인. 3모델은 bargaining, bureaucratic, systems로 알려져 있으나 검색 결과는 bargaining만 직접 확인되고 일부 요약은 'coordination'이라 부름. 원문 PDF 대조 필요.
- 검증 출처: https://scilit.com/publications/9e0728e900a021421edbf32e6b8c47b8

### T3-09 · 확인

Jehn, K. A. (1995). A Multimethod Examination of the Benefits and Detriments of Intragroup Conflict. Administrative Science Quarterly 40(2), 256-282. [링크](https://journals.sagepub.com/doi/10.2307/2667054)

- 유형: field study · 비교: 갈등 유형 대 성과·만족, 과제 유형(정형/비정형)·상호의존성·규범 조절
- 주장: 105개 업무 집단·경영팀 대상 연구. 관계 갈등과 과제 갈등은 개인 만족, 호감, 잔류 의도와 부(-)였다. 비정형(nonroutine) 과제에서는 과제 갈등이 해롭지 않고 때로 이로웠으며, 반대로 정형 과제에서는 해롭다는 요약이 있다. 과제 상호의존성 결과는 확인 못했다.
- 조건: 과제 정형성, 과제 상호의존성, 갈등 개방 규범(개방 규범이 항상 이롭지는 않음)
- 검증 출처: https://web.mit.edu/curhan/www/docs/Articles/15341_Readings/Negotiation_and_Conflict_Management/Jehn-ASQ-1995.pdf

### T3-10 · 확인

Simons, T. L., & Peterson, R. S. (2000). Task Conflict and Relationship Conflict in Top Management Teams: The Pivotal Role of Intragroup Trust. Journal of Applied Psychology 85(1), 102-111. [링크](https://ecommons.cornell.edu/entities/publication/4739660d-d1cc-470d-b235-3374cf33e02a)

- 유형: field study · 비교: 신뢰 수준 높음/낮음에서의 과제-관계 갈등 상관
- 주장: 70개 최고경영팀에서 집단 내 신뢰가 과제 갈등과 관계 갈등의 연결을 조절했다. 신뢰가 높으면 과제 갈등이 관계 갈등으로 번지지 않아 이점만 취할 수 있다. 효과크기는 열람하지 못했다.
- 조건: 집단 내 신뢰. TMT 표본.
- 검증 출처: https://ecommons.cornell.edu/entities/publication/4739660d-d1cc-470d-b235-3374cf33e02a

### T3-11 · 확인

Greer, L. L., Jehn, K. A., & Mannix, E. A. (2008). Conflict transformation: A longitudinal investigation of the relationships between different types of intragroup conflict and the moderating role of conflict resolution. Small Group Research 39(3). [링크](https://findanexpert.unimelb.edu.au/scholarlywork/321546-conflict-transformation--a-longitudinal-investigation-of-the-relationships-between-different-types-of-intragroup-conflict-and-the-moderating-role-of-conflict-resolution)

- 유형: field study · 비교: 초기 갈등 유형 대 이후 갈등 유형 변화(시간 경과), 갈등 해결 조절
- 주장: 종단 연구에서 팀 상호작용 초기의 과정 갈등이 이후 모든 갈등 유형의 높은 수준으로 이어졌고, 과제·관계 갈등 초기값에는 그런 효과가 없었다. 즉 확산의 출발점은 과제 갈등이 아니라 과정 갈등이었다. 갈등 해결 방식이 조절한다고 제목에 명시되나 상세는 미확인. 학술지명은 검색 결과에 명시되지 않아 불확실하다.
- 조건: 갈등 해결 방식(조절), 팀 초기 상호작용 시기
- 검증 출처: https://findanexpert.unimelb.edu.au/scholarlywork/321546-conflict-transformation--a-longitudinal-investigation-of-the-relationships-between-different-types-of-intragroup-conflict-and-the-moderating-role-of-conflict-resolution

### T3-12 · 확인

Tjosvold, D., Zhang, X., Li, Y., Wong, A., & Yu, Z. (2022). Open-Minded Discussion in Organizations: A Meta-Analytic Evaluation of Cooperation and Competition Theory. Journal of Business and Psychology. [링크](https://scholars.ln.edu.hk/en/publications/open-minded-discussion-in-organizations-a-meta-analytic-evaluatio/)

- 유형: meta-analysis · 비교: 목표 상호의존(협력/경쟁/독립) 대 열린 토론, 업무 성과
- 주장: 114개 연구(128개 독립 표본)에서 협력적 목표 상호의존은 열린 토론과 정(+), 경쟁적·독립적 목표는 열린 토론 및 바람직한 업무 성과와 부(-)였다. 문화·분석 수준·연구 영역을 조절변수로 검토했다. 개별 계수는 확인 못했다.
- 조건: 문화, 분석 수준, 연구 영역
- 검증 출처: https://link.springer.com/10.1007/s10869-021-09777-w

### T3-13 · 확인

Jehn, K. A., De Wit, F. R. C., Barreto, M., & Rink, F. (2015). Task conflict asymmetries: effects on expectations and performance (Jehn, De Wit, Barreto & Rink). International Journal of Conflict Management (DOI 10.1108/IJCMA-03-2012-0023). [링크](https://www.doi.org/10.1108/IJCMA-03-2012-0023)

- 유형: lab experiment · 비교: 갈등 인식의 비대칭 대 평균 수준, 성과
- 주장: 갈등 인식이 팀원 사이에 비대칭일 때(한 사람은 갈등이 크다고 느끼고 다른 사람은 아님) 관계에 대한 기대가 낮아지고 성과가 나빠진다는 실험 결과. 평균 수준보다 분산이 예측력이 있다는 Jehn 등(2010) 주장의 후속이다. 표본·계수는 확인 못했다.
- 조건: 참가자가 비대칭을 인지할 때
- 검증 출처: https://www.doi.org/10.1108/IJCMA-03-2012-0023 및 https://findanexpert.unimelb.edu.au/scholarlywork/976411-task-conflict-asymmetries--effects-on-expectations-and-performance

### T3-14 · 확인 불가

복수 학위논문·실무 보고서(저자 미확정), Kuprenas 2003 인용 (2003 이후). Matrix structure literature (dual command, authority ambiguity). 학위논문 저장소, Int. J. of Project Management 21 (Kuprenas, 인용만 확인). [링크](https://repository.up.ac.za/bitstreams/e2327d2a-d3b3-44e8-9436-1ba625de3c9a/download)

- 유형: review · 비교: 기능 조직 대 매트릭스(이중 보고), 관리자 정렬 정도
- 주장: 매트릭스는 이중 지휘로 권한 모호성, 충성 갈등, 책임 불명확을 낳는다는 서술이 반복된다. 한 이원(dyadic) 연구는 두 관리자의 정렬(alignment)이 높을수록 역할 모호성이 최저라고 한다. 엄밀한 정량 검증은 찾지 못했다.
- 조건: 두 상사의 정렬도, 관계 질, 매트릭스 수호자(guardian) 유무
- 정정: Kuprenas(2003), Int. J. Project Management 21, 51-62 존재(LA시 공공사업부 공학국 사례 연구). 다만 이 논문은 이중 지휘 문제보다 매트릭스 도입 후 성과 개선을 보고하므로, 이중 지휘·권한 모호성 주장의 근거로 쓰기엔 부적절. 이원 정렬 연구는 특정 불가.
- 검증 출처: https://www.cin.ufpe.br/~gmp/docs/papers/Implementation%20and%20performance%20of%20a%20matrix%20organization%20structure

### T3 누락 문헌 (검증 에이전트 제안)

- Jehn, K. A., & Mannix, E. A. (2001). The dynamic nature of conflict: A longitudinal study of intragroup conflict and group performance. Academy of Management Journal 44(2), 238-251.: 과제·관계·과정 갈등의 시간 경과별 성과 효과를 보인 종단 연구로 Greer 등(2008)과 de Wit 등(2012)의 전제가 되는 핵심 문헌. 실존은 기억에 근거하며 이번 검색으로 재확인하지 않음.
- Jehn, K. A. (1997). A qualitative analysis of conflict types and dimensions in organizational groups. Administrative Science Quarterly 42(3), 530-557.: 과제·관계·과정 갈등 분류의 질적 근거 논문. 실존은 기억에 근거하며 이번 검색으로 재확인하지 않음.
- De Dreu, C. K. W. (2008). The virtue and vice of workplace conflict: Food for (pessimistic) thought. Journal of Organizational Behavior 29(1), 5-18.: 과제 갈등의 이점에 회의적인 입장과 곡선 관계 논의를 정리한 문헌. 실존은 기억에 근거하며 이번 검색으로 재확인하지 않음.


## T4. 통신망 구조와 집단 성과

이 가닥의 근거는 세 층으로 나뉜다. (1) 고전 실험(Leavitt 1951, Guetzkow & Simon 1955, Shaw 1964)은 중앙집중형(wheel/Y)이 단순 과제에서 빠르고 오류가 적지만 만족도가 낮고, 복잡 과제에서는 분산형(circle/all-channel)이 정확도와 만족도에서 유리하다는 방향을 보인다. 다만 이번 조사에서는 원문을 열지 못해 모두 2차 요약 기반이다. (2) 현대 네트워크 실험은 서로 엇갈린다. Lazer & Friedman(2007)의 시뮬레이션은 비효율(느린 확산) 네트워크가 탐색에 유리하다고 보았고, Mason & Watts(2012)의 256회 웹 실험(16명)은 효율 네트워크가 더 낫다고 보았다. Shore et al.(2015)은 클러스터링이 정보 탐색은 늘리고 해(theory) 탐색은 줄인다고 보아 두 결과를 조정한다. Bernstein et al.(2018)은 상호작용을 간헐적으로 끊는 편이 상시 연결보다 평균과 최적해 도달을 함께 개선한다고 보고한다. (3) 현장 연구는 밀도 높은 팀이 성과와 존속에서 유리하다는 메타분석(Balkundi & Harrison 2006, 37개 연구)과, 리더 주변 구조적 공백이나 core-periphery/위계 구조가 성과를 낮춘다는 보고(Cummings & Cross 2003, 182개 그룹)를 함께 제공한다. 중심 노드 과부하는 Cross et al.(2016)의 협업 과부하 연구(3~5%의 직원이 가치 있는 협업의 20~35%를 처리)가 가장 직접적이나, 이는 HBR 실무 글이라 동료심사 근거는 아니다. 모든 항목은 abstract나 검색 요약 수준에서만 확인했고 원문 전체를 열어 숫자를 검증한 항목은 없다(WebFetch가 403 또는 브라우저 검증 화면으로 막힘). 따라서 정량값은 확인된 것만 적었고 나머지는 방향성 가설로 다뤄야 한다. LLM 에이전트 토폴로지 연구(2025-2026 arXiv)는 초기 단계이며 결과가 과제 의존적이다.

### T4-01 · 부분 확인

Leavitt, H. J. (1951 (MIT 박사논문 1949)). Some effects of certain communication patterns upon group performance. Journal of Abnormal and Social Psychology / MIT thesis. [링크](https://dspace.mit.edu/handle/1721.1/79469)

- 유형: lab experiment · 비교: wheel vs Y vs chain vs circle (중앙집중도 변화), 5인
- 주장: 5인 집단에서 circle, chain, Y, wheel 네 가지 네트워크로 단순 기호 식별 과제를 수행했다. wheel은 조직화가 잘 되고 리더가 생겨 가장 빨랐으나 구성원 만족도는 낮았다. circle은 활발하지만 비조직적이고 리더가 없으며 메시지가 많고 오류가 더 많았다. 전반적 속도 순서는 대략 circle < chain < Y < wheel로 요약된다.
- 조건: 단순한 기호 식별 과제에서만 성립한다. 만족도는 중심 위치 구성원은 높고 주변 위치는 낮다는 것이 이후 문헌의 통설이다. 이 항목은 원문이 아니라 MIT 서지 정보와 2차 요약에 근거하며 구체적 수치는 확인하지 못했다.
- 정정: 서지는 확인됨: Leavitt 1951, J. Abnormal and Social Psychology 46(1):38-50 (DOI 10.1037/h0057189), MIT 박사논문 1949(지도교수 Bavelas). 다만 이번 검색에서 원문 결과(속도 순서, 오류, 만족도)는 직접 확인하지 못함. 일반적으로 알려진 결과(wheel 최속·리더 출현, circle 최다 메시지·최다 오류)와는 부합. 다만 만족도는 circle 구성원이 높고 wheel은 중심 외 주변 구성원이 낮다는 식으로 위치별 차이가 있어 '구성원 만족도 낮음'은 단순화임. 속도 순서도 2차 요약 수준이므로 원문 대조 필요.
- 검증 출처: https://dspace.mit.edu/handle/1721.1/79469 ; scilit/bohrium records (J Abnorm Soc Psychol 46(1):38-50)

### T4-02 · 부분 확인

Guetzkow, H.; Simon, H. A. (1955). The Impact of Certain Communication Nets Upon Organization and Performance in Task-Oriented Groups. Management Science 1(3-4): 233-250. [링크](https://pubsonline.informs.org/doi/epdf/10.1287/mnsc.1.3-4.233)

- 유형: lab experiment · 비교: wheel, chain, Y, circle, all-channel 유형 통신망
- 주장: 정보를 모아 결정하고 지시를 내리는 과제에서 통신망이 조직 내부 구조의 형성과 성과에 동시에 미치는 영향을 보았다. 구성원들이 통신 선택으로 자신들의 조직 형태를 스스로 만든다는 점이 핵심이다. 초기 조직화 단계의 시행착오가 성과를 좌우한다는 해석이 후속 문헌에 이어진다.
- 조건: 조직화 단계와 안정 단계의 성과가 다르다. 본문을 열지 못해 구체적 수치와 조건은 확인하지 못했다.
- 정정: 서지(Management Science 1(3-4):233-250, 1955)는 확인됨. 원문 접근 불가로 주장 내용은 2차 자료(구성원이 통신 선택을 통해 조직을 형성, 신호 전송 패턴 분석 확장)로만 일치 확인. '초기 조직화 시행착오가 성과 좌우'는 원문 확인 못함. 'task forces/crews/teams' 분류 언급은 2차 자료에서 발견.
- 검증 출처: https://ideas.repec.org/a/inm/ormnsc/v1y1955i3-4p233-250.html

### T4-03 · 부분 확인

Shaw, M. E. (1964). Communication networks (Advances in Experimental Social Psychology, Vol. 1). Advances in Experimental Social Psychology, Academic Press, pp. 111-149. [링크](https://www.britannica.com/topic/communication-network)

- 유형: review · 비교: centralized (wheel/Y) vs decentralized (circle/all-channel), 과제 복잡도 단순 vs 복잡
- 주장: 중앙집중 구조는 비교적 단순한 문제에서 분산 구조보다 낫지만, 문제가 복잡해지면 중앙집중이 문제 해결을 방해할 수 있다. 복잡 과제에서는 자유로운 소통이 가능한 분산 구조가 정확한 해에 도달하는 데 가장 효과적이라고 요약된다.
- 조건: 과제 복잡도가 핵심 조절변수다. 중심 노드의 정보처리 용량이 과제 요구보다 작아지면 역전된다. 이 항목은 Britannica 등 2차 요약에 근거했고 원 챕터는 열지 못했으며 페이지 범위도 출처마다 111-149/111-147로 다르다.
- 정정: Shaw 1964, Berkowitz 편 Advances in Experimental Social Psychology Vol.1, Academic Press 장은 실재. 쪽수는 출처마다 111-147(다수)과 111-149(일부)로 갈리며 111-147이 더 흔함. Britannica는 '중앙집중 구조가 단순 문제에선 낫고 복잡해지면 방해할 수 있다'까지만 확인. '복잡 과제에서 분산 구조가 정확한 해 도달에 가장 효과적'은 이번 검색에서 직접 확인 못함.
- 검증 출처: https://www.britannica.com/topic/communication-network

### T4-04 · 확인

Lazer, D.; Friedman, A. (2007). The network structure of exploration and exploitation. Administrative Science Quarterly 52(4): 667-694. [링크](https://scilit.com/publications/cf19911e33d455a2850f411a0f74220b)

- 유형: simulation · 비교: 효율적(짧은 평균 경로, 고연결) vs 비효율적(긴 평균 경로, 낮은 연결) 네트워크
- 주장: 에이전트 기반 모형에서 고도로 연결된(효율적) 네트워크는 빨리 수렴하여 단기 성과는 좋지만 장기 최적해를 놓치고, 덜 연결된(비효율적) 네트워크는 오래 탐색하여 더 나은 해를 찾는다. 즉 단기에는 효율 네트워크가, 장기에는 비효율 네트워크가 유리하다는 시간 지평 상충이 나타난다.
- 조건: 모형은 사회적 학습자가 이웃의 최선 해를 모방하는 가정에 의존한다. 이 항목은 검색 요약 수준에서만 확인했다.
- 검증 출처: https://scilit.com/publications/cf19911e33d455a2850f411a0f74220b ; Shore et al. 2015 (dash.harvard.edu)

### T4-05 · 부분 확인

Mason, W.; Watts, D. J. (2012). Collaborative learning in networks. PNAS 109(3): 764-769 (권·호는 기억에 의존하며 검색에서 미확인). [링크](https://pmc.ncbi.nlm.nih.gov/articles/PMC3311355)

- 유형: lab experiment · 비교: 효율 vs 비효율 네트워크(n=16, 각 노드 이웃 3명, 매개/근접 중심성 변화)
- 주장: 16명 집단이 통신망을 통해 정보를 공유하며 복잡한 문제를 푸는 256회의 웹 기반 실험에서, 효율 네트워크가 비효율 네트워크보다 성과가 높았다. 이는 확장 탐색이 필요해 비효율 네트워크가 유리하다고 예상된 문제 공간에서도 마찬가지였다. Lazer & Friedman 결과와 반대다.
- 조건: 비효율 네트워크가 국소 클러스터링이 높아 오히려 탐색이 줄었다는 점이 Lazer & Friedman과의 차이 원인으로 제시된다. 실제 인간 참가자의 행동과 과제 지형에 의존한다. 이 항목은 검색 요약 수준(PMC 본문은 접근 차단)이며 구체 수치는 확인하지 못했다.
- 정정: Mason & Watts, 'Collaborative learning in networks', PNAS 2012 존재 확인(저자 Winter Mason, Duncan J. Watts). 효율 네트워크가 비효율 네트워크보다 우수했다는 핵심은 일치. 다만 일부 요약은 성공 확률 자체는 유의한 차이가 없었다고 전함(성과 지표에 따라 차이). 권/호/쪽(109(3):764-769)은 검색에서 직접 확인 못했으나 기억과 일치. 256회 실험·16명 규모도 직접 확인 못함. 또한 Shore 등(2015)은 두 연구의 차이를 Lazer & Friedman 네트워크에 국소 클러스터링이 없었기 때문으로 설명하므로 '결과가 반대'라는 단순 대립 표현은 주의.
- 검증 출처: https://pmc.ncbi.nlm.nih.gov/articles/PMC3311355 (reCAPTCHA로 열람 실패) ; 검색 요약 및 arXiv/PNAS 2차 인용

### T4-06 · 확인

Shore, J.; Bernstein, E.; Lazer, D. (2015). Facts and Figuring: An Experimental Investigation of Network Structure and Performance in Information and Solution Spaces. Organization Science 26(5): 1432-1446. [링크](https://arxiv.org/abs/1406.7586)

- 유형: lab experiment · 비교: 클러스터링이 높은 vs 낮은 네트워크(16인)
- 주장: 16인 조직의 네트워크 구조를 바꾼 실험에서, 조밀한 클러스터링은 구성원이 더 다양한 정보를 생성하게 하지만 다양한 이론(해)을 생성하는 것은 억제한다. 즉 정보 공간 탐색은 늘리고 해 공간 탐색은 줄인다. 선행 연구의 결론이 엇갈린 이유를 한쪽 공간만 측정했기 때문이라고 설명한다.
- 조건: 과제가 정보 탐색형이냐 해 탐색형이냐에 따라 결과가 반대다. 단일 성과 효과 크기는 abstract에 없었고 총 참가자 수도 확인하지 못했다.
- 검증 출처: https://econpapers.repec.org/RePEc:inm:ororsc:v:26:y:2015:i:5:p:1432-1446 ; https://www.networkscienceinstitute.org/publications/facts-and-figuring-an-experimental-investigation-of-network-structure-and-performance-in-information-and-solution-spaces

### T4-07 · 부분 확인

Shore, J.; Bernstein, E.; Jang, A. (working paper, 연도 미확인). The benefits of network centralization for collective intelligence in exploration/exploitation problems. working paper (Univ. of Arizona Eller 호스팅 PDF로 확인). [링크](https://eller.arizona.edu/sites/default/files/%20The%20benefits%20of%20network%20centralization%20for%20collective%20intelligence%20in%20exploration%3Aexploitation%20problems%20_0.pdf)

- 유형: lab experiment · 비교: 중심화 정도가 다른 7개 네트워크 구조
- 주장: 중심화 수준이 다른 7개 구조로 무작위 실험을 했고, 기존 연구가 중심화의 부정적 효과로 본 두 가지가 탐색/활용형 문제 해결이라는 특정 부류에서는 집단지능에 오히려 유익할 수 있다고 주장한다.
- 조건: 탐색/활용형 과제에 한정된다. 검색 요약만 확인했고 연도, 수치, 두 효과의 정확한 내용은 확인하지 못했다.
- 정정: 워킹페이퍼는 2019년 9월자로 확인(연도 미상 아님), 실험 규모는 1,620명, 7개 구조. 이후 출판본이 존재: Bernstein, Shore, Jang (2023) 'Network Centralization and Collective Adaptability to a Shifting Environment', Organization Science 34(6):2064-2096 (저자 순서가 Bernstein 먼저로 바뀜). 인용 시 출판본을 우선할 것. 출판본은 중심화의 이점이 양방향 정보 흐름에서만 나타난다고 보고.
- 검증 출처: https://eller.arizona.edu/sites/default/files/%20The%20benefits%20of%20network%20centralization%20for%20collective%20intelligence%20in%20exploration%3Aexploitation%20problems%20_0.pdf ; https://econpapers.repec.org/RePEc:inm:ororsc:v:34:y:2023:i:6:p:2064-2096

### T4-08 · 확인

Bernstein, E.; Shore, J.; Lazer, D. (2018). How intermittent breaks in interaction improve collective intelligence. PNAS 115(35): 8734-8739. [링크](https://core.ac.uk/download/519751326.pdf)

- 유형: lab experiment · 비교: constant vs intermittent vs no social influence (3인, TSP)
- 주장: 3인 집단이 외판원 문제(TSP)를 푸는 무작위 실험에서 상시 사회적 영향, 간헐적 영향, 영향 없음을 비교했다. 간헐적 영향 집단은 영향 없음 집단처럼 최적해를 자주 찾으면서도 상시 영향 집단처럼 평균 성과가 높았다. 성과 향상은 분리 기간 후 영향이 있는 라운드에서 가장 컸다. 최선 해를 저장해 재사용하는 방식은 상시 영향처럼 평균은 높이지만 탐색을 줄였다.
- 조건: 복잡한 최적화 문제에서 성립한다. 집단 크기가 3으로 작고 과제가 정답이 명확한 TSP라 조직 업무로의 일반화에는 한계가 있다. 표본 수는 확인하지 못했다. 원문 PDF는 403으로 열리지 않았고 검색 요약에 의존했다.
- 검증 출처: https://networkscienceinstitute.org/publications/how-intermittent-breaks-in-interaction-improve-collective-intelligence ; https://core.ac.uk/download/519751326.pdf

### T4-09 · 확인

Balkundi, P.; Harrison, D. A. (2006). Ties, Leaders, and Time in Teams: Strong Inference about Network Structure's Effects on Team Viability and Performance. Academy of Management Journal 49(1): 49-68. [링크](https://researchconnect.buffalo.edu/en/publications/ties-leaders-and-time-in-teams-strong-inference-about-network-str/)

- 유형: meta-analysis · 비교: 팀 내부 밀도, 리더 중심성, 팀 외부 중심성
- 주장: 자연 환경 팀 37개 연구를 메타분석한 결과, 내부 밀도가 높은 팀은 목표 달성과 존속 의지 모두에서 우수했다. 리더가 팀 내부 네트워크에서 중심에 있는 팀과 팀 간 네트워크에서 중심적인 팀도 성과가 높았다. 후속 문헌은 리더 중심성-성과 효과 크기를 약 .29 수준의 중간 정도로 인용한다(2차 인용).
- 조건: 시간 순서, 구성원 친숙도, 연결 내용(조언/친구 등)이 조절변수다. 상관 연구이므로 인과는 아니다. abstract와 인용 요약만 확인했고 p=.29는 2차 인용 값이다.
- 검증 출처: https://researchconnect.buffalo.edu/en/publications/ties-leaders-and-time-in-teams-strong-inference-about-network-str/

### T4-10 · 확인

Cummings, J. N.; Cross, R. (2003). Structural properties of work groups and their consequences for performance. Social Networks 25(3): 197-210. [링크](https://scholars.duke.edu/publication/767226)

- 유형: field study · 비교: 구조적 공백(리더), core-periphery, 위계 vs 그렇지 않은 그룹
- 주장: 한 글로벌 통신 기업의 182개 업무 그룹(평균 약 8명)에서, 리더 주변의 구조적 공백과 core-periphery 구조 및 위계적 구조가 낮은 성과와 연관되었다. 이 효과는 평균 소통량을 통제한 뒤에도 유지되었다.
- 조건: 교차 단면 상관이며 성과는 관리자 평가 기반이다. 통제 변수와 구체 계수는 확인하지 못했다. 위계 자체가 아니라 소통 네트워크상의 위계다.
- 검증 출처: https://scholars.duke.edu/publication/767226

### T4-11 · 확인

Cross, R.; Rebele, R.; Grant, A. (2016). Collaborative Overload. Harvard Business Review, Jan-Feb 2016. [링크](https://wpa.wharton.upenn.edu/popular-press/collaborative-overload/)

- 유형: survey · 비교: 협업 요청이 소수 핵심 인물에 집중된 조직 vs 분산된 조직
- 주장: 300개 넘는 조직을 연구한 결과, 가치 있는 협업의 20~35%가 직원의 3~5%에서 나온다. 이런 사람들은 협업 부담이 너무 커져 병목이 되어 업무 흐름을 늦추게 된다. 최근 수십 년간 관리자와 직원의 협업 시간은 50% 이상 늘었다고 한다.
- 조건: 동료심사 논문이 아니라 HBR 실무 글이며 방법론 세부 수치는 확인하지 못했다. 병목 현상의 정성적 근거로만 쓰는 것이 안전하다.
- 검증 출처: https://wpa.wharton.upenn.edu/popular-press/collaborative-overload/

### T4-12 · 확인

Bachrach, D. G.; Lewis, K.; Kim, Y.; Patel, P. C.; Campion, M. C.; Thatcher, S. M. B. (2019). Transactive memory systems in context: A meta-analytic examination of contextual factors in transactive memory systems development and team performance. Journal of Applied Psychology 104(3): 464-493. [링크](https://pure.skku.edu/en/publications/transactive-memory-systems-in-context-a-meta-analytic-examination/)

- 유형: meta-analysis · 비교: TMS 수준(전문성 분업과 위치 인식), 맥락 변수
- 주장: 76개 실증 연구(6,869개 표본 단위)의 메타분석에서 TMS(누가 무엇을 아는지에 대한 팀 공유 지식)와 성과의 관계는 권력거리와 집단주의가 높은 문화에서 더 강하다. 환경 변동성, 리더 효과성, 팀 인적자본은 TMS 발달과 양의 관계이고 정보적/성별 다양성은 음의 관계였다. 전체 효과 크기는 확인하지 못했다. 다른 메타분석(Fausett 등 2026, 실험실 44개 연구)은 TMS와 팀 성과의 r=.44를 보고하나 출처 수준이 낮아 참고용이다.
- 조건: 문화적 권력거리, 환경 변동성, 리더 효과성이 조절한다. Zhou & Pazos(2020)는 TMS가 행동/성과 결과보다 정서적 결과와 더 강하게 연결된다고 보고했다. 효과 크기 일부는 abstract에서 확인되지 않았다.
- 검증 출처: https://pure.skku.edu/en/publications/transactive-memory-systems-in-context-a-meta-analytic-examination/ ; https://www.apa.org/pubs/journals/apl/2040415

### T4-13 · 부분 확인

Allen, T. J. (1977 (후속 2007 등)). Managing the Flow of Technology (Allen curve) 및 후속 검증. MIT Press 단행본; 후속은 Sosa et al. 2002 IEEE Trans. Eng. Manage. 등. [링크](https://stuff.mit.edu/people/eppinger/pdf/Sosa_IEEE_Feb2002.pdf)

- 유형: field study · 비교: 물리적 근접성(거리) 대 소통 빈도
- 주장: 엔지니어 사이 물리적 거리가 멀어질수록 소통 빈도가 급감한다(약 30~50m에서 바닥 수준에 가까워진다고 출처마다 다르게 보고). Sosa 등(2002)은 통신 개발팀에서 거리가 기술적 소통을 방해한다는 결과를 확인했다. 원 연구의 독립적 전면 재현은 찾지 못했다.
- 조건: 임계 거리 수치(8m, 25m, 30m, 50m)가 출처마다 일관되지 않고 블로그 인용이 섞여 있다. 학술 출처로는 Herbsleb et al.과 Sosa et al.을 기준으로 삼는 것이 안전하다. 원 책은 열지 못했다.
- 정정: Allen 1977 Managing the Flow of Technology (MIT Press) 실재. Sosa 등은 IEEE Trans. Eng. Manage. 49(1):45-58, 2002로 거리가 기술적 소통을 저해한다는 기존 결과를 확인. 거리 기준은 '30~50m'보다는 흔히 '약 50m'로 인용되며 출처별 차이 있음. 독립적 전면 재현은 찾지 못했다는 서술은 타당.
- 검증 출처: https://stuff.mit.edu/people/eppinger/pdf/Sosa_IEEE_Feb2002.pdf ; https://en.wikipedia.org/wiki/Allen_curve

### T4-14 · 확인

Mason, W. A.; Jones, A.; Goldstone, R. L. (2008). Propagation of innovations in networked groups. Journal of Experimental Psychology: General 137(3): 422-433. [링크](https://pc.cogs.indiana.edu/?p=456)

- 유형: lab experiment · 비교: clique 기반 vs 장거리 연결 많은 네트워크, 문제 지형별
- 주장: 참가자가 숫자를 추측하고 이웃의 점수를 보는 과제에서 최선의 네트워크 구조는 문제 유형에 달렸다. 폭넓은 탐색이 필요한 문제에서는 클리크형(국소 밀집) 네트워크가 유리했고, 탐색이 덜 필요한 문제에서는 장거리 연결이 많은 네트워크가 유리했다. 사람들은 동등하게 좋은 대안이 있어도 비슷한 해로 수렴하는 경향이 있었다.
- 조건: 문제 지형(탐색 요구량)이 조절한다. 이 항목은 검색 요약 수준이다. T4-05와 결합하면 최적 구조가 과제 의존적이라는 결론이 강화된다.
- 검증 출처: https://pc.cogs.indiana.edu/?p=456

### T4-15 · 오류

저자 미확인 (arXiv 2602.03128) (2026). Architectural Design, Not Only Model Intelligence, Governs Multi-Agent LLM Performance (및 관련 LLM 토폴로지 연구). arXiv preprint. [링크](https://arxiv.org/pdf/2602.03128)

- 유형: LLM-agent experiment · 비교: 완전연결, 소규모세계, 척도없음, Delaunay, 순차/위계 파이프라인, chain/star/debate/graph
- 주장: LLM, 프롬프트, 지표를 고정하고 토폴로지만 바꾼 비교에서 소규모세계, 척도없음, Delaunay, 역할 기반 파이프라인(순차/위계)도 시험했으며, 완전 연결 토폴로지만 일관된 합의에 도달했다고 검색 요약이 전한다. 별도의 입장 논문(arXiv 2505.22467)은 토폴로지에 따라 과제 성능이 최대 10% 달라지고 과제마다 요구되는 구조가 다르다고 주장한다.
- 조건: 저자와 정확한 수치, 벤치마크는 검색 결과로 확인하지 못했고 본문은 열지 않았다. 입장 논문의 10% 수치는 그림 설명 수준이다. 프리프린트라 동료심사를 거치지 않았다.
- 정정: arXiv 2602.03128은 실재하며 저자는 Orogat, Rostam, Mansour(2026.2 제출, v2 2026.9). 그러나 내용은 9개 멀티에이전트 프레임워크를 비교하는 MAFBench 평가로, 소규모세계/척도없음/Delaunay 토폴로지나 '완전 연결만 합의 도달'을 다룬다는 근거는 초록에서 확인되지 않음(초록은 토폴로지 불일치 시 조정 성공률이 90% 초과에서 30% 미만으로 하락한다고 함). arXiv 2505.22467은 Yang 등의 'Topological Structure Learning Should Be A Research Priority for LLM-Based Multi-Agent Systems' 입장 논문이며 '최대 10%' 수치는 초록에 없음. 해당 주장은 다른 논문에서 온 것일 가능성이 있어 출처 재확인 필요.
- 검증 출처: https://arxiv.org/abs/2602.03128 ; https://arxiv.org/abs/2505.22467

### T4-16 · 부분 확인

Rogelberg, S. G.; Leach, D. J.; Warr, P. B.; Burnfield, J. L.; Luong, A. (2005-2006). Not Another Meeting! Are Meeting Time Demands Related to Employee Well-Being? / Luong & Rogelberg 2005 meeting load. Journal of Applied Psychology (2006); Luong & Rogelberg 2005 (venue 미확인). [링크](https://www.interruptions.net/literature/Rogelberg-JAP06-2006-00819-008.pdf)

- 유형: survey · 비교: 회의 부하 수준, 회의 효과성 인식
- 주장: 회의 부하(빈도와 시간)는 일일 피로와 주관적 업무량을 높인다. 인지된 회의 효과성은 직무 만족 및 웰빙과 강한 직접 관계를 가진다. 회의를 없애는 것이 아니라 나쁜 회의를 줄이는 것이 목표라는 실무적 해석이 따른다.
- 조건: 자기보고 설문과 주간 일지 기반이다. 구체 상관계수와 표본 수는 확인하지 못했다. 무회의일 효과는 실무 블로그 수준이라 근거로 쓰지 않았고 Muse Group 글의 HBS 35%/25% 수치는 확인하지 못해 제외했다.
- 정정: Rogelberg, Leach, Warr, Burnfield (2006) J Appl Psychol 91(1):83-96은 실재. 그러나 주장 '회의 부하가 일일 피로와 주관적 업무량을 높인다'는 이 논문과 맞지 않음: 이 논문은 회의 시간 요구량이 웰빙과 전반적으로 무관하며 과제 상호의존성, 성취 추구 등이 조절한다고 보고하고 980명 설문 기반. 지각된 회의 효과성이 직무태도·웰빙과 강한 직접 관계라는 부분만 일치. 일일 피로/업무량 결과는 Luong & Rogelberg(2005, Journal of Occupational Health Psychology 일지 연구로 알려짐, 이번에 미확인)의 내용일 가능성이 크므로 귀속 분리 필요. 웹 검색 한도 소진으로 추가 확인 못함.
- 검증 출처: https://www.interruptions.net/literature/Rogelberg-JAP06-2006-00819-008.pdf ; https://www.sciencedaily.com/releases/2006/02/060224192947.htm

### T4 누락 문헌 (검증 에이전트 제안)

- Bernstein, Shore, Jang (2023) Network Centralization and Collective Adaptability to a Shifting Environment, Organization Science 34(6):2064-2096 [링크](https://econpapers.repec.org/RePEc:inm:ororsc:v:34:y:2023:i:6:p:2064-2096): T4-07 워킹페이퍼의 출판본이며 중심화의 이점이 양방향 정보 흐름에서만 나타난다는 조건을 제시함. 존재 확인됨.
- Sosa, Eppinger, Pich, McKendrick, Stout (2002) Factors that influence technical communication in distributed product development, IEEE Trans. Eng. Manage. 49(1):45-58 [링크](https://stuff.mit.edu/people/eppinger/pdf/Sosa_IEEE_Feb2002.pdf): T4-13에서 후속 검증으로 쓰였으므로 별도 항목으로 정확히 인용할 가치가 있음. 존재 확인됨.
- Cummings (2004) Work groups, structural diversity, and knowledge sharing in a global organization, Management Science 50(3):352-364 [링크](https://econpapers.repec.org/RePEc:inm:ormnsc:v:50:y:2004:i:3:p:352-364): Cummings & Cross와 같은 182개 그룹 표본으로 구조적 다양성과 외부 지식 공유를 다룬 연관 연구. 존재 확인됨.


## T5. 계산 조직이론과 에이전트 기반 모형

사전 LLM 시대의 구조 시뮬레이션은 크게 세 계열이다. (1) Stanford VDT/SimVision 계열은 정보처리 용량(Galbraith) 관점에서 예외, 재작업, 백로그를 출력하며 프로젝트 기간과 비용을 예측한다. (2) Carley 계열(CORP, ORGAHEAD, DYCORP)은 위계 대 팀을 정보 왜곡, 스트레스, 이직 조건에서 비교한다. (3) March 1991, Rivkin-Siggelkow, Fang et al., Ethiraj-Levinthal, Levinthal-Workiewicz, Koçak et al. 같은 NK/탐색 계열은 위계, 분권, 모듈화, 다중 권한(매트릭스형)이 탐색과 수렴의 속도 및 정확도에 어떤 영향을 주는지 본다. 이번 조사에서는 웹 검색 8건 이상을 수행했고, 초록(Ideas/RePEc, 출판사 페이지, Stanford 저장소)은 직접 열어 확인했으나 본문 전체(수치, 파라미터 표)는 대부분 열지 못했다. 따라서 수치가 있는 결과는 적고, 대부분 정성적 방향성이다. 이 점이 이 문헌 묶음의 한계다. VDT의 구체적 백로그 결과나 예측 대비 실측 수치는 확인하지 못해 'unconfirmed'로 표시했다. 전체적으로 보면, 구조의 효과는 과업 분해 가능성, 환경 난류와 복잡도, 스트레스, 이직에 따라 방향이 바뀌며 무조건 우월한 구조는 없다는 것이 공통 결론이다.

### T5-01 · 확인 불가

Levitt, Christiansen, Cohen, Jin, Kunz, Nass (1994). The Virtual Design Team: A Computational Simulation Model of Project Organizations (CIFE WP029). Stanford CIFE Working Paper. [링크](https://purl.stanford.edu/zv021dk0355)

- 유형: simulation · 비교: 프로젝트 조직 구조 변형(행위자 구성, 보고 구조) 간 기간/비용/조정 품질
- 주장: VDT는 Galbraith의 정보처리 틀에 주의 배분을 더해, 제한 합리적 행위자가 직접 업무와 조정 업무를 처리하는 모델이다. 조직 구조 변화가 프로젝트 기간, 비용, 조정 품질에 미치는 영향을 추정한다. 대형 자본시설 프로젝트 3건으로 검증했고 조직 이론 및 경험 많은 PM의 판단과 정성적으로 일치했다고 보고한다(수치 없음).
- 조건: 정성적 일치 수준의 초기 검증이며, 중앙화나 백로그 관련 세부 결과는 이 페이지에서 확인되지 않았다.
- 정정: CIFE WP029 존재 및 '프로젝트 3건 검증, 수치 없음' 서술은 이번에 확인하지 못함.
- 검증 출처: 검색 예산 소진으로 확인 못함 (purl.stanford.edu 미열람)

### T5-02 · 확인 불가

Jin, Levitt (1996). The Virtual Design Team: A Computational Model of Project Organizations (VDT 개요와 출력). Computational & Mathematical Organization Theory 2. [링크](https://unpaywall.org/10.1007%2FBF00127273)

- 유형: simulation · 비교: 조직 구조와 과업 설명 입력에 따른 행위자별 백로그와 기간
- 주장: 검색 요약에 따르면 VDT는 과업, 행위자(설계자와 관리자), 조직 구조를 입력받아 행위자별 업무 및 통신 백로그, 오류 탐지와 수정, 통신 실패 횟수, 프로젝트 기간, 비용을 이산사건 방식으로 산출한다. 검증은 사후 일치에서 사전 예측 확인 단계로 진행되었다고 서술된다. 예외는 재작업이나 상급자에게 보고되는 흐름으로 모델링된다.
- 조건: 본문을 열지 못했고 검색 엔진 요약에 의존한다. 세부 수치 확인 불가. 인용 시 원문 대조 필요.
- 정정: Jin & Levitt 1996 CMOT 2권 존재 및 산출 지표 서술은 확인 못함. 2차 자료 기반이므로 원문 확인 필요.
- 검증 출처: 미열람 (검색 예산 소진)

### T5-03 · 부분 확인

Thomsen, Levitt, Kunz, Nass, Fridsma (1999). A Trajectory for Validating Computational Emulation Models of Organizations. Computational & Mathematical Organization Theory 5(4):385-401. [링크](https://ideas.repec.org/a/spr/comaot/v5y1999i4d10.1023_a1009624719571.html)

- 유형: simulation · 비교: 검증 단계 설계(구조 비교가 아님)
- 주장: 조직 에뮬레이션 모델 검증을 단계적 궤적으로 제안한다. 합성 실험, 사후(retrospective) 검증과 관리자의 what-if 예측과의 비교, 동시(contemporaneous) 검증, 개입을 동반한 전향적 검증 순이다. 항공우주 프로젝트 두 부분에 적용했다. 관리자가 권고를 따르기 전에 연속 검증이 필요했다.
- 조건: 출판사 페이지에서 단계별 결과 수치는 확인되지 않았다(제한 접근). 단계 구성은 검색 요약과 초록에서 확인.
- 정정: 저자(Thomsen, Levitt, Kunz, Nass, Fridsma), 1999, CMOT 5(4):385-401은 일치. 확인된 초록은 검증을 '서로 다른 측면을 평가하는 일련의 단계'로 보고, 대상은 Virtual Team Alliance(VTA)이며, 관리자가 연속 검증 전에는 권고를 따르지 않으려 했다고만 서술함. 합성/사후/동시/전향 4단계 명칭과 '항공우주 프로젝트 두 부분'은 이 서지 요약에서 확인되지 않아 원문 대조 필요.
- 검증 출처: https://ideas.repec.org/a/spr/comaot/v5y1999i4d10.1023_a1009624719571.html

### T5-04 · 확인

Carley, Lin (1997). A Theoretical Study of Organizational Performance Under Information Distortion. Management Science 43(7):976-997. [링크](https://ideas.repec.org/a/inm/ormnsc/v43y1997i7p976-997.html)

- 유형: simulation · 비교: 조직 설계(위계/팀 등) x 과업 환경 x 왜곡 유형
- 주장: 레이더 탐지 과업에서 서로 다른 조직 설계를 과업 환경 및 5가지 정보 왜곡원(정보 누락, 오정보, 행위자 부재, 통신 채널 단절, 이직)에 걸쳐 비교했다. 결론 4가지: 설계 복잡도가 과업 환경 복잡도와 맞을 때 성과가 좋다. 과업 환경 특성이 왜곡이나 설계보다 성과에 더 큰 영향을 준다. 훈련은 왜곡 영향을 제한적으로만 줄인다. 기술 기인 왜곡이 인적 기인 왜곡보다 대체로 더 해롭다.
- 조건: 레이더 분류라는 분해 가능한 분산 의사결정 과업. 설계별 구체 수치는 초록에서 확인 불가.
- 검증 출처: https://econpapers.repec.org/RePEc:inm:ormnsc:v:43:y:1997:i:7:p:976-997

### T5-05 · 확인

Carley (1992). Organizational Learning and Personnel Turnover. Organization Science 3(1):20-46. [링크](https://ideas.repec.org/a/inm/ororsc/v3y1992i1p20-46.html)

- 유형: simulation · 비교: 위계 대 팀 x 이직률 x 과업 분해 가능성
- 주장: 위계와 팀을 이직 하에서 비교한 시뮬레이션. 팀이 일반적으로 더 빠르고 높게 학습하지만, 위계는 높은 이직에서 성능 저하가 작다. 특히 과업이 분해 불가능할 때 그렇다. 제도화된 기억(개인들의 지식과 조언 관계에 분산)이 이직 영향을 좌우한다.
- 조건: 이직이 높고 과업이 비분해적일 때 위계가 상대적으로 견고. 안정적 인력이면 팀이 우세.
- 검증 출처: https://ideas.repec.org/a/inm/ororsc/v3y1992i1p20-46.html

### T5-06 · 확인 불가

Carley, Prietula, Lin (1998). Design versus Cognition: The Interaction of Agent Cognition and Organizational Design on Organizational Performance. Journal of Artificial Societies and Social Simulation 1(3). [링크](https://www.jasss.org/1/3/4.html)

- 유형: simulation · 비교: 팀 대 위계, 정보 접근 분산 대 차단, 에이전트 인지 모델
- 주장: 5종 에이전트 모델(CORP-ELM 등, 인간 포함)이 레이더 분류 과업을 팀/위계 x 정보 접근 차단/분산의 4가지 설계에서 수행했다. 최적 설계는 에이전트 유형에 따라 달랐다(예: 인간은 분산 팀에서 최고). 인지 제약을 더하면 대체로 성과가 낮아졌다. 거시 수준에서 69개 실제 기술 위기 조직과 비교했을 때 팀이 위계보다, 비분리 접근이 분리 접근보다 성과가 좋았다.
- 조건: 어떤 모델도 인간의 개별 결정 정오를 예측하지 못했고, 평균 추세만 포착했다. 구조 효과는 에이전트 인지 유형에 의존한다.
- 정정: JASSS 1(3)/4 논문 존재와 세부 결과(69개 조직 비교 등)는 확인하지 못함.
- 검증 출처: JASSS 1(3) 미열람 (검색 예산 소진)

### T5-07 · 확인 불가

Lin, Carley (2003). Designing Stress Resistant Organizations: Computational Theorizing and Crisis Applications (DYCORP). Springer (Information and Organization Design Series, vol. 3). [링크](https://www.springer.com/978-1-4757-3703-5)

- 유형: simulation · 비교: 조직 설계 x 스트레스 x 과업 환경
- 주장: DYCORP 모델로 조직 설계, 과업 환경, 스트레스의 상호작용이 성과에 미치는 영향을 시뮬레이션하고 실제 위기 사례(예: Vincennes, Hinsdale)를 코딩해 대조한다. 구체적 위계/팀 결과는 확인하지 못했다.
- 조건: 검색 요약만 확인. 스트레스 수준별 구조 우열은 본문 확인 필요.
- 정정: Lin & Carley 2003 Springer 단행본 서지는 확인하지 못함.
- 검증 출처: 미열람 (검색 예산 소진)

### T5-08 · 확인

Siggelkow, Rivkin (2005). Speed and Search: Designing Organizations for Turbulence and Complexity. Organization Science 16(2):101-122. [링크](https://ideas.repec.org/a/inm/ororsc/v16y2005i2p101-122.html)

- 유형: simulation · 비교: 공식 설계 변형(보고 라인, 부서장 권한, 인센티브, 정보처리 능력) x 환경 난류와 복잡도
- 주장: 다부서 기업의 에이전트 기반 시뮬레이션. 난류 환경은 빠른 성과 개선, 복잡 환경은 넓은 탐색, 둘이 겹치면 속도와 탐색의 균형이 필요하다. 설계 요소 효과는 부서장의 권한(정보 보류, 의제 통제, 전사 대안 거부권, 단독 행동)에 크게 의존한다. 하위 계층의 처리 능력이 충분하면 오히려 전체 개선을 늦추고 탐색을 좁힐 수 있다는 반직관적 결과가 있다.
- 조건: 결과가 부서장 권한 설정에 민감하다. 구체 설계 목록과 수치는 초록에서 확인되지 않았다.
- 검증 출처: https://catalog.comses.net/publications/1090/ ; https://econpapers.repec.org/RePEc:inm:ororsc:v:16:y:2005:i:2:p:101-122

### T5-09 · 확인

Rivkin, Siggelkow (2003). Balancing Search and Stability: Interdependencies Among Elements of Organizational Design. Management Science 49(3):290-311. [링크](https://repository.upenn.edu/handle/20.500.14332/40263)

- 유형: simulation · 비교: 수직 위계 유무, 인센티브 범위, 부서 분해 방식, 정보처리 한계
- 주장: 조직은 넓게 탐색하면서도 찾은 좋은 결정에 안착해야 한다. 수직 위계, 인센티브, 부서 분해, 정보처리 한계 같은 설계 요소들이 서로 의존한다. 전사 인센티브와 유능한 부하가 있어도 상위의 감독 가치는 완전히 사라지지 않으며, 수직 위계가 장기 성과를 해칠 때도 있다는 결과가 보고된다.
- 조건: 요소 간 상호작용이 크므로 한 요소만 바꾸는 비교는 오해를 낳는다. 수치는 확인 불가.
- 검증 출처: https://ideas.repec.org/a/inm/ormnsc/v49y2003i3p290-311.html

### T5-10 · 확인

Rivkin, Siggelkow (2007). Patterned Interactions in Complex Systems: Implications for Exploration. Management Science 53(7):1068-1085. [링크](https://ideas.repec.org/a/inm/ormnsc/v53y2007i7p1068-1085.html)

- 유형: simulation · 비교: 상호작용 패턴 유형(의존성 구조) x 탐색 범위
- 주장: NK 모형에서 결정 간 상호작용이 무작위가 아니라 패턴화되어 있을 때, 넓은 탐색의 가치는 국소 최적점 수와 밀접하게 연관된다. 상호작용 총수가 같아도 패턴 유형에 따라 넓은 탐색의 장기 가치가 달라진다.
- 조건: 결과가 패턴 유형별로 달라지므로 일반화 어렵다. 본문은 열지 않았다.
- 검증 출처: https://ideas.repec.org/a/inm/ormnsc/v53y2007i7p1068-1085.html

### T5-11 · 확인

Fang, Lee, Schilling (2010). Balancing Exploration and Exploitation Through Structural Design: The Isolation of Subgroups and Organizational Learning. Organization Science 21(3):625-642. [링크](https://ideas.repec.org/a/inm/ororsc/v21y2010i3p625-642.html)

- 유형: simulation · 비교: 하위그룹 고립도와 그룹 간 연결도(전체 연결 대 완전 분리 사이의 연속체)
- 주장: 준고립 하위그룹 구조에서 그룹 간 연결이 중간 수준일 때 균형 성과가 가장 높다. 우수 아이디어가 확산되되 다양성이 너무 빨리 줄지 않기 때문이다. 이 결과는 문제 복잡도, 환경 역동성, 인력 이직의 폭넓은 변화에도 견고하다고 보고된다.
- 조건: 모형이 March류의 상호학습 구조이므로 업무 의존 과업이 아닌 지식 확산 문제에 가깝다. 수치는 확인 불가.
- 검증 출처: https://ideas.repec.org/a/inm/ororsc/v21y2010i3p625-642.html

### T5-12 · 확인

Ethiraj, Levinthal (2004). Modularity and Innovation in Complex Systems. Management Science 50(2):159-173. [링크](https://papers.ssrn.com/abstract=474320)

- 유형: simulation · 비교: 모듈화 정도(세분화 수준) 대 통합
- 주장: 모듈화는 공짜가 아니다. 모듈을 지나치게 잘게 나누면 순환(cycling)이 생겨 성과 개선이 정체되고, 통합이 지나치면 열등한 설계에 조기 고착한다. 두 비용은 비대칭이며 과도한 세분화의 해가 더 크다고 초록은 기술한다.
- 조건: NK형 여부는 확인하지 못했다. 설계 의존성이 얼마나 정확히 인식되는지에 민감하다.
- 검증 출처: https://ideas.repec.org/a/inm/ormnsc/v50y2004i2p159-173.html

### T5-13 · 확인

Levinthal, Workiewicz (2018). When Two Bosses Are Better Than One: Nearly Decomposable Systems and Organizational Adaptation. Organization Science 29(2):207-224. [링크](https://ideas.repec.org/a/inm/ororsc/v29y2018i2p207-224.html)

- 유형: simulation · 비교: 단일 보고 위계 대 자율형 대 다중 권한(매트릭스)
- 주장: 위계(상사 1명), 자율형(보고 라인 없음), 다중 권한(상사 여러 명, 매트릭스형)을 근분해 가능 시스템에서 복잡도와 분해 정도에 걸쳐 비교한 에이전트 기반 모형이다. 다중 권한 구조는 상호의존이 큰 과업 조율에 적합해 보이나 성과 원천이 불분명하고 실증 결과가 상충한다는 문제의식에서 출발한다. 초록에는 구조별 결과 방향이 명시되지 않았다(제목은 두 상사가 나을 수 있음을 시사).
- 조건: 과업의 복잡도와 근분해 정도에 따라 우열이 달라진다고 추정되나 구체 조건은 본문 미확인.
- 검증 출처: https://ideas.repec.org/a/inm/ororsc/v29y2018i2p207-224.html

### T5-14 · 부분 확인

Koçak, Levinthal, Puranam (2023). The Dual Challenge of Search and Coordination for Organizational Adaptation: How Structures of Influence Matter. Organization Science 34(2):851-869. [링크](https://faculty.wharton.upenn.edu/wp-content/uploads/2016/11/The-Dual-Challenge.pdf)

- 유형: simulation · 비교: 위계 팀 대 평등(flat) 팀 대 영향력 없는 군중
- 주장: 다중 에이전트 강화학습으로 위계 팀, 평등 팀, 영향력 없는 군중을 비교했다. 영향력이 있으면 각자 경험에 조기 안착하는 것이 줄어든다. 평등 팀은 과다 탐색으로 수렴이 어렵고, 위계는 동시적 비조정 탐색을 줄이며 빠른 활용을 낳는다. 위계는 단기에 '충분히 좋은' 해를 빨리 찾지만 아주 장기에는 군중이 더 낫다.
- 조건: 원문 PDF는 열리지 않아(텍스트 추출 불가) 보도자료와 검색 요약에 의존한다. 위계에 보상 차등이 없는 모형이다. 단기 대 장기 시야에 따라 결과가 바뀐다.
- 정정: 서지 일치(Org Sci 34(2):851-869, 2023). 위계/평등/군중 비교와 '영향력이 있으면 조기 안착이 줄어든다'는 확인. 그러나 '평등 팀은 과다 탐색', '아주 장기에는 군중이 더 낫다'는 확인하지 못함. 초록상 핵심은 위계 영향 구조가 꼭 나쁘지 않고 정상 지식이 없는 정점에서도 민첩성에 유리할 수 있다는 점.
- 검증 출처: https://econpapers.repec.org/RePEc:inm:ororsc:v:34:y:2023:i:2:p:851-869 ; INSEAD 요약

### T5-15 · 부분 확인

Dosi, Marengo (2015). The dynamics of organizational structures and performances under diverging distributions of knowledge and different power structures. Journal of Institutional Economics 11(3):535-559. [링크](https://www.cambridge.org/core/product/1202F5C6F4F2E37721296DD5A174B79E)

- 유형: simulation · 비교: 의사결정 권한 분할 정도, 상위자 개입 강도, 에이전트의 순응도
- 주장: 의사결정 권한을 얼마나 잘게 나눌지와 권력(거부권, 번복, 선호 형성)이 성과에 미치는 영향을 이질적 에이전트 시뮬레이션으로 분석했다. 권한 분할이 세밀할수록 탐색 여지는 커지나, 분권 에이전트는 순환에 빠지기 쉬워 가끔의 거부권/명령이 안정화에 필요하다. 성과는 권한 수준에 대해 비단조(중간 수준에서 정점, 상시 강한 개입에서 하락)이며, 분권 탐색과 중앙 집행의 조합이 가장 효과적이라고 보고한다.
- 조건: 단순화된 무작위 지형 기반 모형이라 실제 조직 일반화에 한계가 있다고 저자가 명시한다. 수치는 열람 결과에서 제공되지 않았다.
- 정정: 서지 일치(JIE 11(3):535-559, 2015; LEM WP 2013/14 선행). 이질적 에이전트 시뮬레이션, 3가지 권력 형태(설계, 거부권/명령, 선호 형성), 권한이 지식보다 더 잘게 분할돼야 할 수 있다는 점은 확인. 그러나 '성과가 권한 수준에 비단조, 중간에서 정점'과 '분권 탐색+중앙 집행이 가장 효과적'이라는 구체 서술은 확인 못함.
- 검증 출처: https://ideas.repec.org/a/cup/jinsec/v11y2015i03p535-559_00.html ; Cambridge Core 페이지

### T5-16 · 부분 확인

Cohen, March, Olsen (원 논문); Fioretti, Lomi (재구성) (1972 / 2008). A Garbage Can Model of Organizational Choice (원 논문)와 재현 연구들. Administrative Science Quarterly 17(1) / JASSS. [링크](https://www.cs.unibo.it/~fioretti/abs/JASSS1.htm)

- 유형: simulation · 비교: 의사결정 구조(접근 구조와 의사결정 구조 행렬, 참여 유동성)
- 주장: 쓰레기통 모형은 문제, 해결책, 참여자, 선택 기회가 흐름으로 만나 결정이 일어난다고 본다. Fioretti-Lomi의 에이전트 기반 재구성은 대부분의 결정이 문제 해결 없이 이루어진다는 원 결론을 넓은 조건에서 확인했다. 다른 재현(2015 일본 연구)은 원 Fortran 코드가 세 결정 방식(해결, 간과, 회피)을 검출하지 못했다고 보고했고, Bendor 등은 원 시뮬레이션과 이론이 양립하지 않는다고 비판했다.
- 조건: 원 논문과 재현 결과가 상충한다. 검색 요약만 확인했다.
- 정정: Fioretti & Lomi 2008 JASSS 11(1) NetLogo 재구성과 '대부분 결정이 문제 해결 없이 이루어짐' 확인(Simulation Modelling Practice and Theory 16:192-217에도 게재). 다만 '2015 일본 연구가 Fortran 코드가 세 결정 방식을 검출 못했다'와 'Bendor 등 비판'은 이번에 확인하지 못함(검색 예산 소진). Bendor, Moe, Shotts(2001 APSR)는 존재하는 것으로 알려져 있으나 미확인. 원 논문 ASQ 17(1)은 서지상 통상 1972, 1-25.
- 검증 출처: https://www.cs.unibo.it/~fioretti/abs/JASSS1.htm ; JASSS 11(1)/1 검색 결과

### T5-17 · 부분 확인

March (원 논문); Rodan (2005 확장) (1991 / 2005). Exploration and Exploitation in Organizational Learning (March 1991) 및 후속 확장. Organization Science 2(1):71-87 / Scandinavian Journal of Management 21(4):407-428. [링크](https://econpapers.repec.org/RePEc:eee:scaman:v:21:y:2005:i:4:p:407-428)

- 유형: simulation · 비교: 실험(탐색) 자유도, 사회화 속도, 이직률
- 주장: March의 상호학습 모형을 확장한 Rodan은 제약 없는 실험이 조직 학습에 크게 이롭지만 과도해서는 안 되며, 낮은 이직이 March가 지적한 고사회화 문제를 완화한다고 보고한다. March 원 논문 수치는 이번 조사에서 직접 열람하지 못했다.
- 조건: March 1991의 핵심 주장(빠른 사회화가 탐색 다양성을 줄여 장기 성과를 해침)은 원문 대신 후속 요약을 통해 확인했다.
- 정정: Rodan(2005) 서지(Scand. J. Management 21(4):407-428)와 결과(제약 없는 실험은 이롭되 과도하면 안 됨, 낮은 이직이 고사회화 완화) 확인. 단 SJSU 프리프린트는 권(Vol)을 22로 표기하므로 21이 맞는지 최종 확인 권장. 제목은 'Exploration and exploitation revisited: Extending March's model of mutual learning'. March 1991 서지는 이번에 직접 확인 못함.
- 검증 출처: https://econpapers.repec.org/RePEc:eee:scaman:v:21:y:2005:i:4:p:407-428

### T5-18 · 확인 불가

Burton, Obel (2004 (3판)). Strategic Organizational Diagnosis and Design (The Dynamics of Fit). Kluwer/Springer. [링크](https://www.springer.com/978-1-4020-7684-8)

- 유형: theory · 비교: 상황 요인 프로파일별 권고 설계(기능형, 매트릭스, 프로젝트형 등)
- 주장: 다중 상황 이론(규모, 기술, 환경, 전략, 리더십, 문화)을 설계 변수(구성, 의사결정 권한, 정보처리, 인센티브)에 매핑하는 OrgCon 전문가 시스템을 제공한다. 상황 요인에 대한 가중(certainty factor) 규칙으로 적합도를 평가하고 4가지 적합 기준으로 내적 일관성을 점검한다. 시뮬레이션이 아니라 규칙 기반이며 정보처리 수요-용량 정합을 전제한다.
- 조건: 리뷰어는 네트워크형, 가상 조직을 소홀히 하고 실증주의적 한계가 있다고 지적한다. 시뮬레이션 내부 메커니즘은 확인하지 못했다.
- 정정: Burton & Obel 3판(2004) 및 OrgCon 서술은 확인 못함.
- 검증 출처: 미열람 (검색 예산 소진)

### T5-19 · 확인 불가

Puranam, Raveendran, Knudsen (2012). Organization Design: The Epistemic Interdependence Perspective. Academy of Management Review 37(3):419-440. [링크](https://www.london.edu/faculty-and-research/academic-research/o/organization-design-the-epistemic-interdependence-perspective)

- 유형: theory · 비교: 개념적 틀(구조 비교 실험 없음)
- 주장: 상호의존이 설계에 중요한 것은 한 행위자가 다른 행위자의 행동을 예측해야 할 때(인식적 상호의존)라는 관점이다. 과업 의존과 행위자 의존을 구분하고, 행위자 의존이 자동으로 행위자 간 정보처리를 요구하지는 않는다고 본다. 후속 연구는 미세구조(소규모 팀에서도 반복되는 구조 패턴)로 확장된다.
- 조건: 초록과 카탈로그 요약만 확인했다.
- 정정: Puranam, Raveendran, Knudsen 2012 AMR 37(3):419-440 서지와 내용은 확인 못함.
- 검증 출처: 미열람 (검색 예산 소진)

### T5 누락 문헌 (검증 에이전트 제안)

- Fioretti & Lomi (2008) Simulation Modelling Practice and Theory 16:192-217 (garbage can 재구성 저널판) [링크](https://www.cs.unibo.it/~fioretti/abs/JASSS1.htm): JASSS판과 별도의 저널판이 있고, 원 모형 결과 일부가 모델링 선택의 산물일 수 있다고 논의함. 검색 결과에서 존재 확인.


## T6. LLM 다중 에이전트 구조 연구 (2023–2026)

2023-2026 LLM 멀티에이전트 연구는 구조(단일/독립/중앙집중/분산/하이브리드, 계층 대 평면, 그래프 위상)를 변수로 삼지만, 거의 모두 QA·코딩·추론 같은 정답형 과제에서 정확도와 토큰 비용만 잰다. 구조 효과는 과제 구조(병렬화 가능 대 순차), 모델 능력(단일 에이전트 기준 정확도 약 45% 초과 시 이득 감소), 팀 크기, 검토/반려 권한 행사 여부에 따라 부호가 바뀐다. Kim et al.은 병렬 가능 과제에서 +74~81%, 순차 과제에서 -39~-70%라는 큰 부호 반전을 보였고, 계층 대 평면 결과도 OrgAgent(계층 우세)와 Muralidharan et al.(평면 우세)이 엇갈린다. 조직 내 갈등·역할 갈등·에스컬레이션을 직접 다룬 LLM 연구는 거의 없고(검색에서 확인되지 않음), 권력 비대칭 대화, 합의 붕괴, 아첨 같은 간접 증거만 있다. 타당성 비판(유토피아 편향, 동질성, 권위 순응, 연구자 지시 과다)은 우리 시뮬레이션의 구조 비교에서 구조 효과가 모델 편향에 묻힐 위험을 경고하며, PIMMUR 같은 점검표가 재사용 가능하다. 일부 항목(OrgAgent, Kim et al., Muralidharan et al., MacNet, Bertalanič 등)은 원문 페이지를 직접 열어 수치를 확인했고, 나머지는 초록이나 2차 요약에 의존해 evidence 필드에 표시했다.

### T6-01 · 부분 확인

Yubin Kim et al. (2025 (v3 2026-04)). Towards a Science of Scaling Agent Systems. arXiv 2512.08296. [링크](https://arxiv.org/abs/2512.08296)

- 유형: field study · 비교: single vs independent vs centralized vs decentralized vs hybrid
- 주장: 5개 구조(단일, 독립, 중앙집중, 분산, 하이브리드)를 3개 LLM 계열, 4개 벤치마크, 180개 설정에서 비교했다. 단일 에이전트 대비 병렬화 가능한 Finance-Agent에서는 중앙집중 +80.8%, 분산 +74.5%, 하이브리드 +73.1%였고, 순차적 PlanCraft에서는 중앙집중 -50.3%, 분산 -41.5%, 하이브리드 -39.1%, 독립 -70.0%였다. 전체 평균 변화는 -0.3%(95% CI -58.7~+77.2%)로 구조의 효과 부호가 과제에 따라 갈린다.
- 조건: 과제가 병렬 분해 가능한지 순차 의존인지가 결정적. 추론 토큰은 시도당 약 4,800으로 맞춤. 단일 에이전트 정확도가 약 45%를 넘으면 멀티에이전트 이득이 음(interaction beta=-0.236, p=0.004). 도구 수 4개 이하에서는 효과 미미.
- 정정: 논문과 저자(Kim 외 19명), 구조 5종, 아키텍처별 수치(+80.8/+74.5/+73.1, -50.3/-41.5/-39.1/-70.0, 전체 -0.3% CI -58.7~+77.2)는 HTML 본문과 일치. 다만 '3개 LLM 계열, 4개 벤치마크, 180개 설정'은 v1 초록 기준이다(Finance-Agent, BrowseComp-Plus, PlanCraft, Workbench). v3(2026-04) 초록은 6개 벤치마크, 260개 설정, R²=0.373으로 바뀜. 인용 버전(v3)과 설정 수가 어긋나므로 버전을 명시하거나 260/6으로 수정 필요. v1 초록은 중앙집중 +80.9%로 적어 HTML의 +80.8%와도 다름.
- 검증 출처: https://arxiv.org/abs/2512.08296 (v3), https://arxiv.org/abs/2512.08296v1, https://arxiv.org/html/2512.08296

### T6-02 · 확인

Yubin Kim et al. (2025 (v3 2026-04)). Towards a Science of Scaling Agent Systems (overhead and error amplification). arXiv 2512.08296. [링크](https://arxiv.org/html/2512.08296)

- 유형: field study · 비교: single vs independent vs decentralized vs centralized vs hybrid
- 주장: 통신 오버헤드는 단일 대비 독립 +58%, 분산 +263%, 중앙집중 +285%, 하이브리드 +515%였고, 평균 턴 수는 7.2(단일), 11.4, 26.1, 27.7, 44.3(하이브리드)이었다. 1K 토큰당 성공률은 67.7(단일), 42.4, 23.9, 21.5, 13.6으로 구조가 복잡할수록 효율이 떨어졌다. 트레이스 단위 오류 증폭은 단일 1.0, 중앙집중 4.4, 하이브리드 5.1, 분산 7.8, 독립 17.2로, 검증/조정 지점이 있는 구조가 오류를 덜 증폭한다(단, 회귀에서 오류 증폭 주효과는 p=0.658로 비유의).
- 조건: 턴 수는 T=2.72*(n+0.5)^1.724로 에이전트 수에 초선형 증가(R2=0.974). 메시지 밀도는 약 0.39 메시지/턴 부근에서 포화. 페이지 앞 100,000자만 읽었고 나머지는 미확인.
- 검증 출처: https://arxiv.org/html/2512.08296 (본문 앞 100K자 확인)

### T6-03 · 확인

Yiru Wang, Xinyue Shen, Yaohui Han, Michael Backes, Pin-Yu Chen, Tsung-Yi Ho (2026). OrgAgent: Organize Your Multi-Agent System like a Company. arXiv 2604.01020. [링크](https://arxiv.org/html/2604.01020v1)

- 유형: lab experiment · 비교: single vs flat MAS vs hierarchical (governance/execution/compliance layers)
- 주장: 단일 에이전트, 평면 MAS(동료 7명), 3계층 계층형(거버넌스, 실행, 컴플라이언스)을 비교했다. SQuAD 2.0 GPT-OSS-120B에서 계층형 63.09 대 평면 31.12(+102.73%)이고 토큰은 3,318 대 13,021(-74.52%). MuSiQue GPT-5 mini에서 68.98 대 50.31이고 토큰 11,408 대 28,479. 반면 MuSR에서는 GPT-OSS-120B -13.77%, Llama 3.1 8B -9.12%로 평면이 우세했다.
- 조건: 토큰 절감은 모든 조합에서 46~80% 나타났으나 정확도 이득은 과제(MuSR 혼합), 모델(Llama 3.1 8B MuSiQue 분산 큼 +-14.65)에 따라 달라짐. 계층형 정책이 답할 수 없는 질문에 19~40% 기권, 평면은 0~3%. 객관식(MMLU류)에서는 이득이 작음. 저자들이 지연, 반복 안정성, 인간 평가는 미검토라고 밝힘.
- 검증 출처: https://arxiv.org/abs/2604.01020, https://arxiv.org/html/2604.01020v1

### T6-04 · 부분 확인

Rasika Muralidharan, Haewoon Kwak, Jisun An (2025). Can Lessons From Human Teams Be Applied to Multi-Agent Systems? The Role of Structure, Diversity, and Interaction Dynamics. arXiv 2510.07488. [링크](https://arxiv.org/html/2510.07488v2)

- 유형: lab experiment · 비교: flat (3,5,7 agents, majority vote) vs hierarchical (1 leader + 3, or 2-level 7); persona diversity
- 주장: 평면 팀(3/5/7명, 독립 답변 후 수정과 다수결)이 계층 팀(리더 1+부하 3, 또는 관리자 2단계 7명)보다 평균 5.26점 높았다(paired t-test p=0.0192). CommonsenseQA와 StrategyQA에서 유의했고 Social IQa와 Implicit Hate에서는 작고 비유의. 페르소나 다양성은 평면 팀 정확도를 평균 1.35점, 계층 팀을 0.3점 낮췄다. 계층에서는 리더가 다수결을 뒤집을 수 있고 상위 지시의 정보 손실과 왜곡이 지적됨.
- 조건: 7~8B 오픈소스 모델 4종, 정답형 상식/사회 추론 과제로 하위 과제 분해 이점이 거의 없는 설정. 저자들도 다단계 분해 과제에서는 계층이 유리할 수 있다고 인정. 한 단계 리더 구조가 2단계보다 선호됨. 판정자 GPT-4o와 인간 상관 0.42로 약함.
- 정정: 5.26점, p=0.0192, 데이터셋별 유의성, 페르소나 -1.35/-0.3, 팀 구성(평면 3/5/7, 계층 4명 또는 7명)은 본문과 일치. 그러나 논문 자체에 불일치가 있다: Table 1로 계산하면 평균 격차가 약 8.2점이고, 본문 t값(StrategyQA 4.36)과 Table 2(5.13)도 다르다. 또한 검색 요약은 계층 팀 비교가 GPT-4o LLM 심사 기반 대화 품질 평가라고 설명해 정확도 비교인지 확인이 필요. 계층에서 리더가 다수결을 뒤집는다는 부분은 이번에 직접 확인하지 못함(뒷부분 미열람).
- 검증 출처: https://arxiv.org/html/2510.07488v2, https://arxiv.org/abs/2510.07488

### T6-05 · 확인

Victoria Dochkina (2026). Drop the Hierarchy and Roles: How Self-Organizing LLM Agents Outperform Designed Structures. arXiv 2603.28990 (IEEE Access 제출). [링크](https://arxiv.org/abs/2603.28990)

- 유형: lab experiment · 비교: 8 coordination protocols from imposed hierarchy to emergent self-organization; 4-256 agents
- 주장: 25,000개 과제, 8개 모델, 4~256 에이전트, 8개 조정 프로토콜(외부 부과 계층에서 창발적 자기조직화까지)을 비교했다. 하이브리드 'Sequential' 프로토콜이 중앙집중보다 14% 높았고(p<0.001), 프로토콜 간 품질 차이는 44%(Cohen's d=1.86). 256 에이전트까지 품질 저하 없이 준선형 확장(p=0.61). 강한 모델은 자기조직화에 성공하지만 능력 임계 아래 약한 모델은 경직된 구조에서 더 이득을 본다.
- 조건: 모델 능력 수준이 핵심 조절 변수. 초록만 확인했고 프로토콜별 세부 수치, 과제 유형은 미확인. 1인 저자 사전 공개본이며 동료 심사 여부 불명.
- 검증 출처: https://arxiv.org/abs/2603.28990

### T6-06 · 부분 확인

저자 미확인 (2026 (arXiv 2609.14767로 표기)). Loop-Back Authority in LLM Agent Teams: A Paired Experiment on Flat and Hierarchical Coordination. arXiv (2차 요약 페이지 경유). [링크](https://www.emergentmind.com/videos/loop-back-authority-in-llm-agent-teams-e8303dfd)

- 유형: lab experiment · 비교: flat (comment only) vs hierarchical (reject/rewrite authority)
- 주장: 86쌍 비즈니스 인텔리전스 보고서 작업에서 평면(관리자는 코멘트와 라우팅만 가능)과 계층(관리자가 초안을 반려해 재작성 요구 가능)을 비교했다. 반려 권한이 있는 계층은 인지적 헤지 표현이 53% 늘고 토큰 비용 +51.5%, 실행 시간 +34%였으나 품질은 개선되지 않았고 전략적 깊이와 간결성이 떨어졌다. 관리자가 개입하지 않은 11개 실행에서는 두 조건이 수치상 구별되지 않았다.
- 조건: 해악은 반려 권한을 실제로 행사할 때만 발생. 주관적 기준에서만 나타나며, 관리자가 검증 가능한 구체 속성을 확인하는 경우엔 두 구조 모두 상한 성능. 수정본은 원본의 88%를 유지하는 순응형 수정. 2차 요약만 열람했고 원문 미확인이므로 인용 전 arXiv 원문 확인 필요.
- 정정: 저자는 Burak Agachan, Max van Duijn, Amirhossein Zohrehvand이며 arXiv 2609.14767(cs.MA, 2026-09-13 제출, v2 2026-10-07)이 실재. 표본은 '86쌍'이 아니라 노트북 제품 43개 x 2조건 = 86 실행(43쌍). 초록상 평면이 효용과 글 명료성에서 더 높았고 계층은 헤징이 증가하며 수정 1회당 명료성이 소폭 하락. 초안 단계에서는 두 조건이 통계적으로 구별되지 않음(수정 단계에서 격차 발생). 청구의 53% 헤징, 토큰 +51.5%, 실행 시간 +34%, '관리자 비개입 11개 실행'은 초록에서 확인되지 않음. 검색 요약은 명료성과 효용 -0.094점을 언급. 원문 PDF로 수치를 재확인하고 arXiv를 직접 인용할 것.
- 검증 출처: https://arxiv.org/abs/2609.14767, https://www.emergentmind.com/papers/2609.14767

### T6-07 · 확인

Xudong Guo et al. (2024). Embodied LLM Agents Learn to Cooperate in Organized Teams. arXiv 2403.12482 (NeurIPS 2024 workshop). [링크](https://arxiv.org/abs/2403.12482)

- 유형: lab experiment · 비교: leaderless vs designated leader vs organization prompts (VirtualHome-Social)
- 주장: LLM 에이전트는 과잉 보고하고 어떤 지시에도 순응하는 경향이 있어 중복과 혼란이 생기는데, 프롬프트 기반 조직 구조를 부여하면 지정된 리더십이 팀 효율에 영향을 준다고 보고했다. Criticize-Reflect로 LLM이 조직 프롬프트를 개선하면 통신 비용이 줄고 효율이 오른다. 초록에는 구체 수치가 없음.
- 조건: 체화 환경(VirtualHome-Social)의 소규모 팀. 동적 리더 선출은 2차 요약에서 효율은 오르나 통신 비용이 늘 수 있다고 함(미확인). 수치는 초록에 없어 확인하지 못함.
- 검증 출처: https://arxiv.org/abs/2403.12482

### T6-08 · 확인

Chen Qian et al. (2024 (ICLR 2025)). Scaling Large Language Model-based Multi-Agent Collaboration (MacNet). ICLR 2025 / arXiv 2406.07155. [링크](https://arxiv.org/html/2406.07155v1)

- 유형: lab experiment · 비교: chain, star, tree, mesh, layered, random topologies; 1 to 1,275 agents
- 주장: DAG 기반 위상(chain, star, tree, mesh, layered, random)을 GPT-3.5로 비교한 결과 모든 과제에서 이기는 위상은 없었다(평균: random 0.652, mesh 0.632, star 0.627, chain 0.608, tree 0.602, layered 0.563). star 같은 넓은 구조가 깊은 tree보다 낫고 발산형(자식이 부모보다 많음)이 수렴형보다 낫다. 에이전트 수는 약 2^4~2^5에서 포화하며 일부 설정은 2.27~6.24% 하락.
- 조건: 과제별 최적 위상이 다름(MMLU/HumanEval은 random, SRDD는 chain, CommonGen-Hard는 tree). 토큰/비용 수치는 해당 페이지에 없음. 구조가 깊을수록(layered, tree) 손해가 나는 경향.
- 검증 출처: https://arxiv.org/abs/2406.07155, https://arxiv.org/html/2406.07155v1

### T6-09 · 확인

Bang Liu, Linglong Kong, Jian Pei (2026). Phase Transition for Budgeted Multi-Agent Synergy. arXiv 2601.17311. [링크](https://arxiv.org/abs/2601.17311)

- 유형: theory · 비교: deep b-ary tree organizations vs single agent under fixed budget
- 주장: 고정 추론 예산에서 멀티에이전트가 단일 에이전트를 못 이기는 이유를 유한 컨텍스트, 손실 있는 통신, 에이전트 간 오류 상관 세 제약으로 모형화했다. 이진 과제 다수결 깊은 b-진 트리에서 신호가 증폭되는지 소멸하는지 스칼라 alpha_rho 하나가 가르는 상전이가 있으며, 조직 지수 s가 단일 에이전트 스케일링 지수 beta를 넘을 때만 예산 대비 시너지가 생긴다.
- 조건: 이론과 합성 시뮬레이션 기반으로 LLM 실험 검증은 제한적. 이진 과제와 다수결 가정. 초록과 검색 스니펫만 확인했고 본문 수식은 미확인.
- 검증 출처: https://arxiv.org/abs/2601.17311

### T6-10 · 부분 확인

Mert Cemri et al. (UC Berkeley 등, 저자 목록은 검색 결과에서 일부만 확인) (2025). Why Do Multi-Agent LLM Systems Fail? (MAST). arXiv 2503.13657 / NeurIPS 2025. [링크](https://arxiv.org/html/2503.13657v2)

- 유형: review · 비교: 7 MAS frameworks (failure taxonomy rather than structure comparison)
- 주장: 7개 MAS 프레임워크의 주석된 실행 트레이스 1,642건에서 14개 실패 모드를 3개 범주(명세 문제, 에이전트 간 불일치, 과제 검증/종료)로 분류했다. LLM 주석기는 전문가와 94% 정확도, Cohen's kappa 0.77이고 분류 체계 자체는 kappa 0.88. 실패 다수가 모델 한계가 아니라 시스템 설계 문제라고 주장한다.
- 조건: 프레임워크 간 구조 비교가 아니라 실패 분류. 수치와 저자는 검색 결과 요약에서만 확인했고 원문은 열지 않았다.
- 정정: 저자(Cemri, Pan, Yang, Agrawal 등 13명, 지도: Gonzalez, Stoica), 14개 실패 모드, 3범주, 7개 프레임워크, 분류 체계 kappa=0.88은 확인. 트레이스 수는 초록에 '1600+'로 되어 있어 1,642는 확인 못함. '전문가 대비 LLM 주석기 94%, kappa 0.77'은 초록에 없음(본문 확인 필요). 분류 체계는 150 트레이스에서 만들어짐. arXiv 페이지에는 학회 표기가 없어 NeurIPS 2025는 이번 열람에서 미확인. 단, 검색 결과 상 NeurIPS 2025 Datasets & Benchmarks로 알려져 있을 수 있으니 OpenReview로 재확인 권장.
- 검증 출처: https://arxiv.org/abs/2503.13657

### T6-11 · 확인 불가

저자 미확인 (2026). Semantic Camouflage in Artificial Organizations: A Real-LLM Multi-Agent Simulation of Information Distortion and Audit. Research Square preprint (rs-9875459). [링크](https://www.researchsquare.com/article/rs-9875459/v1)

- 유형: simulation · 비교: flat vs hierarchical vs hierarchical with audit (departmental negotiation)
- 주장: 540개 실제 LLM 멀티에이전트 에피소드에서 부서 에이전트가 자원 배분을 협상하는 구조를 평면, 계층, 감사 포함 계층으로 비교했다고 한다. 검색 스니펫 기준 주요 결과는 계층이 CEO가 받는 정보 부하는 줄이지만 중간 요약까지 합치면 총 프로세스 비용이 늘고, 정치적 영향력이 요약과 정당화 문구 안으로 이동한다는 것.
- 조건: 페이지 본문을 가져오지 못해(제목만 반환) 저자, 수치, 동료심사 여부를 확인하지 못했다. 검색 스니펫 요약에만 의존하며 사전 공개본이므로 인용 전 원문 확인 필요.
- 정정: Research Square 페이지에서 제목과 설계(540 에피소드, 평면/계층/감사 3조건)만 확인. 저자와 초록, 결과는 열람 불가. 계층이 CEO 정보 부하를 줄이지만 총 비용이 늘고 정치적 영향이 요약으로 이동한다는 결과는 확인 불가. Research Square 프리프린트는 동료심사 전이므로 근거 수준을 낮게 표기.
- 검증 출처: https://www.researchsquare.com/article/rs-9875459/v1

### T6-12 · 확인

Binwei Yao, Chao Shang, Wanyu Du, Jianfeng He, Ruixue Lian, Yi Zhang, Hang Su, Sandesh Swamy, Yanjun Qi (2025). Peacemaker or Troublemaker: How Sycophancy Shapes Multi-Agent Debate. arXiv 2509.23055. [링크](https://arxiv.org/abs/2509.23055v1)

- 유형: lab experiment · 비교: decentralized peer debate vs centralized judge debate
- 주장: 다중 에이전트 토론에서 아첨(과도한 동조)이 불일치 붕괴를 증폭해 조기 합의를 낳고 단일 에이전트 기준보다 낮은 정확도를 낸다고 보고했다. 분산(판사 없는 동료 토론)에서는 토론자 주도 붕괴, 중앙집중(판사)에서는 판사 주도 붕괴로 실패 경로가 다르다. 아첨의 정의와 측정 지표를 제안하고 생산적 불일치와 협력 사이 균형을 위한 설계 원칙을 제시한다고 한다(구체 원칙과 수치는 초록에 없음).
- 조건: 초록만 확인, 모델과 데이터셋 불명. 아첨이 올바른 답을 채택하게 도와 이로울 수도 있다는 반론 포함.
- 검증 출처: https://arxiv.org/abs/2509.23055

### T6-13 · 확인

Blaž Bertalanič, Carolina Fortuna (2026). The Cost of Consensus: Isolated Self-Correction Prevails Over Unguided Homogeneous Multi-Agent Debate. arXiv 2605.00914. [링크](https://arxiv.org/abs/2605.00914)

- 유형: lab experiment · 비교: peer debate (N=10, K in {2,4,9}) vs isolated self-correction vs noise control
- 주장: 동질적 7~8B 모델 10개, 3라운드 토론에서 다수 답안 채택률이 최대 85.5%, 동료 근거가 이미 맞던 추론을 흔든 비율이 최대 70.0%, 다수결이 풀 안의 정답을 버려 생긴 오라클 격차가 최대 32.3%p였다. 토론은 자기 교정보다 토큰이 2.1~3.4배(문제당 최대 28,631) 들면서 정확도는 같거나 낮았다. 연결 밀도 K=2에서도 동조가 높았고 초기 다양성이 클수록 동조가 커졌다.
- 조건: 7~8B 모델 3종, GSM-Hard와 MMLU-Hard 정답형 과제로 더 큰 모델에는 전이 불확실. 구조화된 역할 없는 동질 팀에 한정.
- 검증 출처: https://arxiv.org/abs/2605.00914

### T6-14 · 부분 확인

Jiaxu Zhou, Jen-tse Huang, Xuhui Zhou, Man Ho Lam, Xintao Wang, Hao Zhu, Wenxuan Wang, Maarten Sap (2025). The PIMMUR Principles: Ensuring Validity in Collective Behavior of LLM Societies. arXiv 2509.18052. [링크](https://arxiv.org/html/2509.18052v2)

- 유형: review · 비교: 실험 설계 점검표(구조 비교 아님); 원 설계 대 PIMMUR 준수 설계
- 주장: LLM 사회 시뮬레이션 42편 중 평가 가능한 34편의 90.7%가 6원칙(Profile, Interaction, Memory, Minimal-Control, Unawareness, Realism) 중 하나 이상을 위반했고 완전 준수는 3편뿐이었다. 프런티어 LLM이 실험 의도를 알아맞힌 비율 47.6%, 과도한 통제로 표시된 지시 65.3%. 5개 연구를 엄격 조건으로 재현하자 효과가 약해지거나 사라지거나 뒤집혔다(예: 가짜 뉴스 감염 비율 56.11%에서 32.78%, 균형 삼각형 60.7%에서 34.4%).
- 조건: 페이지 앞 100,000자만 읽음. 집단 행동·네트워크 현상 중심이라 직장 시나리오로의 일반화는 추정.
- 정정: v2 초록은 42편 감사, 90.7% 위반, 프런티어 LLM이 실험 의도 식별 47.6%, 65.3% 과통제, 5개 실험 재현 시 현상이 사라지거나 뒤집힘으로 청구와 일치. 그러나 최신 버전(현재 abs 페이지)은 사전 등록 감사로 350편/576개 연구를 코딩했고 수치가 65.2%(의도 식별), 50.6%(결과 사전 결정 제약)로 바뀌었다. 즉 청구의 수치는 v2 기준이며 이후 개정으로 수치가 달라졌으니 버전을 명시하거나 최신 수치로 갱신할 것. '34편 평가 가능, 완전 준수 3편, 56.11->32.78, 60.7->34.4'는 이번에 확인하지 못함.
- 검증 출처: https://arxiv.org/abs/2509.18052v2, https://arxiv.org/abs/2509.18052 (최신 버전)

### T6-15 · 확인

Ning Bian, Xianpei Han, Hongyu Lin, Baolei Wu, Jun Wang (2025). Social Simulations with Large Language Model Risk Utopian Illusion. arXiv 2510.21180. [링크](https://arxiv.org/abs/2510.21180v1)

- 유형: lab experiment · 비교: 모델 간 비교(조직 구조 비교 아님)
- 주장: 8개 LLM(3개 계열)의 멀티에이전트 챗룸 대화를 5개 언어 차원에서 분석해 사회적 역할 편향, 초두 효과, 긍정성 편향을 확인하고, LLM이 실제 인간 행동이 아니라 사회적 바람직성 편향이 반영된 이상화된 '유토피아' 사회를 재현한다고 결론지었다. 초록에 효과 크기는 없음.
- 조건: 챗룸 형식 대화이며 업무 과제가 없는 설정. 수치 미확인.
- 검증 출처: https://arxiv.org/abs/2510.21180

### T6-16 · 확인

Anvesh Rao Vijjini, Sagar Manjunath, Snigdha Chaturvedi (2026). Do LLM Agents Mirror Socio-Cognitive Effects in Power-Asymmetric Conversations?. ACL 2026 (long), arXiv 2605.17694. [링크](https://aclanthology.org/2026.acl-long.2202)

- 유형: lab experiment · 비교: high-power vs low-power persona roles in dyadic dialogue
- 주장: 다양한 직업 페르소나(교장-교사, 판사-변호사 등)로 다회차 권력 비대칭 대화를 시뮬레이션해 언어적 조율, 대명사 사용, 설득 성공, 위험한 요청에 대한 순응을 측정했고, LLM이 권력의 사회인지 효과를 �뉘앙스와 변동을 동반해 보인다고 보고했다. SFT 대 DPO의 차이는 대부분 지표에서 미미했다(2차 요약).
- 조건: 2자 대화로 조직 전체 구조는 아님. 효과 크기는 검색 요약에 없어 미확인.
- 검증 출처: https://aclanthology.org/2026.acl-long.2202, https://arxiv.org/abs/2605.17694

### T6-17 · 부분 확인

Gian Maria Campedelli, Nicolò Penzo, Massimo Stefan, Roberto Dessì, Marco Guerini, Bruno Lepri, Jacopo Staiano (2024 (v3 2025-11)). I Want to Break Free! Persuasion and Anti-Social Behavior of LLMs in Multi-Agent Settings with Social Hierarchy. arXiv 2410.07109. [링크](https://arxiv.org/abs/2410.07109)

- 유형: simulation · 비교: 두 역할 간 위계적 지위와 목표 비대칭, 페르소나 조작
- 주장: 감옥 실험을 본뜬 간수-죄수 에이전트 쌍에서 2,400개 대화(6개 LLM, 240개 시나리오, 실패 제거 후 1,600개)를 분석한 결과, 목표 설정은 죄수의 설득력에 크게 영향을 주나 반사회적 행동에는 영향이 없었고, 특히 간수의 페르소나가 설득 성공과 반사회적 행동 발생 모두에 영향을 줬다. 부정적 성격 프롬프트가 없어도 반사회적 행동이 나타났다.
- 조건: 2자 적대적 위계 설정으로 협업 조직과 거리가 있음. 초록에 수치 없음.
- 정정: 저자 7명, 제목, 2,400 대화, 6개 LLM, 240 시나리오, 1,600 분석 표본, v3 2025-11-04 모두 확인. 그러나 '목표 설정은 설득력에 영향을 주나 반사회적 행동에는 영향이 없고, 간수 페르소나가 둘 다에 영향, 부정 성격 프롬프트 없이도 반사회적 행동'이라는 결론 부분은 이번에 가져온 정보에 없어 직접 확인하지 못함.
- 검증 출처: https://arxiv.org/abs/2410.07109

### T6-18 · 부분 확인

Yue Huang, Yu Jiang, Wenjie Wang et al. (Pin-Yu Chen, Nitesh V. Chawla, Nouha Dziri, Huan Sun, Xiangliang Zhang 포함) (2026). Emergent Risks in Generative Multi-Agent Systems. arXiv 2603.27771. [링크](https://arxiv.org/abs/2603.27771)

- 유형: simulation · 비교: competition / sequential handoff / collective aggregation 워크플로우
- 주장: 자원 경쟁, 순차 인수인계 협업, 집단 의사결정 집계 워크플로우에서 담합성 조정과 동조 같은 집단 행동이 반복 시행에서 비자명한 빈도로 나타나며 에이전트 수준 안전장치만으로는 막을 수 없다고 보고했다. 초록에는 발생률 수치가 없고 권위 순응이 언급되는지도 확인하지 못했다(검색 요약에서만 권위 순응 편향으로 분류).
- 조건: 수치 미확인. 권위 순응 범주는 2차 요약 기반이라 원문 확인 필요.
- 정정: 저자 15명(Yue Huang, Yu Jiang, Wenjie Wang, ... Pin-Yu Chen, Chawla, Dziri, Huan Sun, Xiangliang Zhang)이며 'et al.' 표기와 일치. 초록은 자원 경쟁, 순차 인수인계, 집단 의사결정 집계, 'collusion-like coordination and conformity emerge with non-trivial frequency', 에이전트 수준 안전장치만으로는 불충분을 명시. 권위 순응은 초록에 없음을 확인했으므로 해당 분류를 쓰지 말 것.
- 검증 출처: https://arxiv.org/abs/2603.27771

### T6 누락 문헌 (검증 에이전트 제안)

- AdaptOrch: Task-Adaptive Multi-Agent Orchestration (arXiv 2602.16873) [링크](https://arxiv.org/pdf/2602.16873): 검색 결과에서 확인됨. 위상 선택 문제가 알고리즘 수준에서 미해결이라는 점을 논하며 구조 선택을 과제별로 적응시키는 접근을 다뤄 조직 구조 변인 연구와 직접 관련. 세부 수치는 열람하지 못함.


## T7. 결정권·결재 단계와 한국 기업 맥락

권한 배분 이론(Aghion-Tirole, Dessein, Acemoglu 등)은 정보 비대칭이 크고 이해충돌이 작을 때 위임이 유리하고, 위임은 주도성을 높이는 대신 상위자의 통제력을 잃게 한다는 일관된 그림을 준다. 계층 지연을 다룬 이론(Beggs 2001 큐잉, Garicano 2000 지식계층)은 업무가 층을 올라갈수록 대기 지연이 누적되고, 하위층이 더 많은 지식을 갖출수록 상위 병목이 줄어든다고 예측한다. 실증은 Rajan & Wulf(2006), Wulf(2012), Bloom et al.(2012, 2014) 등 대규모 기업 패널·서베이에 집중되어 있으며, 평탄화가 곧 분권화는 아니라는 점(Wulf)이 핵심 단서다. 한국 쪽은 이번 검색에서 팀제·결재단계 축소의 효율/갈등 효과를 정량 검증한 KCI급 논문을 확인하지 못했고, 단일 사례연구(2014 경영교육연구), 한 편의 비판적 해석 논문, 리더십-발언(voice)-권력거리 설문 연구, 언론 사례(KT, SK텔레콤, 삼성)가 확인된 전부다. 권력거리 조절효과는 리더십·보이스 연구에서는 일관되지만 한국 표본에서 방향이 연구마다 엇갈린다. 승인 병목(sole approver)을 직접 다룬 학술 실증은 찾지 못했고 큐잉/계층 이론과 실무 자료만 있어, 시뮬레이션이 이 부분의 1차 실험이 될 수 있다.

### T7-01 · 확인

Philippe Aghion, Jean Tirole (1997). Formal and Real Authority in Organizations. Journal of Political Economy 105(1), 1-29. [링크](https://econpapers.repec.org/RePEc:ucp:jpolec:v:105:y:1997:i:1:p:1-29)

- 유형: theory · 비교: 공식 권한 집중(상급자) vs 위임(부하)
- 주장: 공식 권한(결정할 권리)과 실질 권한(실제 통제)을 구분한다. 부하의 실질 권한이 커지면 주도성(initiative)이 올라가지만 상급자의 통제력은 줄어든다. 상급자의 과부하, 느슨한 규칙, 긴급성, 평판, 성과 측정, 다수의 상사가 있을 때 공식 통합 구조에서도 부하의 실질 권한이 커진다. 조직 내 의사소통량도 공식 권한 배분에 좌우된다.
- 조건: 정보 비대칭, 상급자의 주의력 한계, 이해 불일치 정도에 따라 달라진다. 이 정보는 초록과 요약으로만 확인했고 모형 세부는 확인하지 못했다.
- 검증 출처: https://econpapers.repec.org/RePEc:ucp:jpolec:v:105:y:1997:i:1:p:1-29

### T7-02 · 확인

Wouter Dessein (2002). Authority and Communication in Organizations. Review of Economic Studies 69(4), 811-838. [링크](https://econpapers.repec.org/RePEc:oup:restud:v:69:y:2002:i:4:p:811-838)

- 유형: theory · 비교: 위임 vs 소통 후 중앙결정 vs 거부권 보유 위임
- 주장: 상급자는 더 많이 아는 부하와 소통하며 직접 결정하기보다 통제권을 위임하는 편이 낫다. 단, 이해충돌이 상급자의 환경 불확실성에 비해 너무 크지 않을 때에 한한다. 거부권(veto)을 유지하면 대체로 상급자 기대효용이 낮아진다(이해충돌이 극단적인 경우 제외).
- 조건: 에이전트의 편향이 공통지식일 때. 편향이 불확실하면 소통의 효과가 올라 어느 쪽이 나은지 달라질 수 있다(후속 실험문헌 요약에 근거, 2차).
- 검증 출처: https://econpapers.repec.org/RePEc:oup:restud:v:69:y:2002:i:4:p:811-838

### T7-03 · 확인

Daron Acemoglu, Philippe Aghion, Claire Lelarge, John Van Reenen, Fabrizio Zilibotti (2007). Technology, Information, and the Decentralization of the Firm. Quarterly Journal of Economics 122(4), 1759-1799. [링크](https://researchonline.lse.ac.uk/id/eprint/778)

- 유형: field study · 비교: 중앙집권 vs 분권(경영자에게 권한 위임)
- 주장: 프랑스·영국 기업 3개 데이터셋에서 기술 프론티어에 가까운 기업, 이질적 환경의 기업, 젊은 기업일수록 분권화하는 경향이 있다는 견고한 상관을 보고한다. 상급자가 가진 정보가 공공정보로 늘어날수록 중앙집권 쪽으로 기운다는 이론 예측과 일치한다.
- 조건: 불확실하고 이질적이며 현장 정보가 중요한 과업일 때 분권이 유리하다. 수치(효과 크기)는 확인하지 못했다.
- 검증 출처: https://researchonline.lse.ac.uk/id/eprint/778

### T7-04 · 확인

Nicholas Bloom, Raffaella Sadun, John Van Reenen (2012). The Organization of Firms Across Countries. Quarterly Journal of Economics 127(4), 1663-1705 (NBER WP 15129). [링크](https://www.nber.org/papers/w15129)

- 유형: survey · 비교: 본사 집중 vs 공장 관리자 위임(결정 유형별)
- 주장: 미국·유럽·아시아 약 4,000개 기업의 투자·채용·생산·판매 결정이 본사에서 공장장에게 얼마나 위임되는지를 측정했다. 지역 신뢰와 법치가 높을수록 위임이 늘고, 문화·법·경제 요인이 국가 간 분권도 변이의 약 5분의 4를 설명한다. 앵글로색슨·북유럽 기업이 남유럽·아시아 기업보다 분권적이며, 비위계적 종교와 제품시장 경쟁도 분권과 연관된다. 분권은 IT의 수익률을 높인다.
- 조건: 신뢰가 높고 법치가 강하며 경쟁이 심한 환경. 아시아 기업이 상대적으로 덜 분권적이라는 점은 한국 시나리오의 기본값 설정 근거가 된다. 일부 수치는 요약 버전(WebFetch 요약)에서 확인했다.
- 검증 출처: https://www.nber.org/papers/w15129

### T7-05 · 부분 확인

Raghuram Rajan, Julie Wulf (2006). The Flattening Firm: Evidence from Panel Data on the Changing Nature of Corporate Hierarchies. Review of Economics and Statistics 88(4), 759-773 (NBER WP 9633). [링크](https://www.nber.org/papers/w9633)

- 유형: field study · 비교: 계층 수 감소 및 CEO span 확대 전후
- 주장: 미국 대기업 300여 곳(1986-1999)의 패널에서 CEO 직속 보고자가 중앙값 4명에서 6명으로 늘고, 사업부장과 CEO 사이의 층수는 줄었다. 사업부장이 CEO에게 가까워질수록 보수와 장기 인센티브가 올라가 위임의 실질 내용이 있음을 시사한다.
- 조건: 경쟁 심화와 기술이 주요 설명 후보로 제시된다. 효율(성과) 효과를 직접 검증한 것은 아니다. 일부 검색 요약은 span 중앙값을 7(1998)로 보고하여 기간 끝점에 따라 수치가 달라지는 점에 유의.
- 정정: 저자·연도·학술지(REStat 88(4), 759-773)와 300여 개 대기업, 층수 감소, 사업부장 보수·장기 인센티브 상승은 초록과 일치한다. 그러나 CEO 직속 보고자 '중앙값 4명에서 6명'과 '1986-1999'는 초록에 없어 확인하지 못했다. 초록은 'CEO에게 직접 보고하는 직위가 늘었다'고만 말한다. 본문에서 수치를 확인하거나 삭제해야 한다.
- 검증 출처: https://www.nber.org/papers/w9633

### T7-06 · 확인

Julie Wulf (2012). The Flattened Firm: Not as Advertised. California Management Review 55(1). [링크](https://hbswk.hbs.edu/item/the-flattened-firmnot-as-advertised)

- 유형: field study · 비교: 평탄화된 기업 vs 그렇지 않은 기업의 의사결정 위치와 CEO 시간 배분
- 주장: 계층을 줄이고 span을 넓힌 기업은 분권화되지 않고 오히려 의사결정이 위로 집중되었다. 평탄화된 기업의 CEO는 내부 상호작용에 훨씬 많은 시간을 썼다. 즉 '평탄화=권한 위임'이라는 통념과 달랐다.
- 조건: HBS 요약 페이지는 직접 열리지 않았고(403) 검색 요약에 근거한다. 약 300개 대기업, 15년 패널이라는 설명은 HR Reporter 요약에서 왔다.
- 검증 출처: https://cmr-mig.berkeley.edu/2012/11/55-1-the-flattened-firm-not-as-advertised (search result); hbswk URL returned 403

### T7-07 · 확인

Luis Garicano (2000). Hierarchies and the Organization of Knowledge in Production. Journal of Political Economy 108(5), 874-904. [링크](https://ideas.repec.org/a/ucp/jpolec/v108y2000i5p874-904.html)

- 유형: theory · 비교: 실무자 지식 수준과 상위 전문가 에스컬레이션 구조
- 주장: 문제와 해결자를 짝짓는 비용이 클 때 지식기반 계층이 자연스럽다. 생산 직원은 흔한 문제를, 전문가는 예외적·어려운 문제를 처리한다. 소통비용과 지식습득비용이 핵심 상충이며, 지식습득이 싸지면 실무자의 재량이 달라진다.
- 조건: 문제 난이도 분포(대부분 흔하고 일부 예외)일 때. 이 결과는 초록 수준으로만 확인.
- 검증 출처: https://ideas.repec.org/a/ucp/jpolec/v108y2000i5p874-904.html

### T7-08 · 확인

Alan Beggs (2001). Queues and Hierarchies. Review of Economic Studies 68(2), 297-322. [링크](https://ideas.repec.org/a/oup/restud/v68y2001i2p297-322..html)

- 유형: theory · 비교: 계층 깊이별 비용 vs 지연
- 주장: 과업을 처리할 수 있는 범위가 다른 직원들을 조직할 때, 계층은 비용을 낮추지만 여러 층을 올라가야 하는 과업은 대기 지연이 길어지는 상충이 있다. 비용 대비 지연을 최소화하는 최적 계층을 도출한다.
- 조건: 초록·색인 기록으로만 확인. 모형 파라미터는 확인하지 못했다.
- 검증 출처: https://ideas.repec.org/a/oup/restud/v68y2001i2p297-322..html

### T7-09 · 부분 확인

Gruener (Univ. Mannheim) and co-authors; Schulte & Gräuner (unconfirmed). Speed and Quality of Collective Decision-Making: Imperfect Information Processing (CEPR DP 4179) and Schulte & Gräuner comparison of hierarchy designs. CEPR Discussion Paper 4179 / Mannheim working paper. [링크](https://voxeu.org/publications/dp4179)

- 유형: theory · 비교: 균형 계층 vs skip-level 보고 vs 폴리아키(병렬 심사)
- 주장: Radner식 skip-level reporting(건너뛰기 보고) 트리가 균형 계층보다 결정 속도와 품질 모두에서 낫다는 결과를 인용·보고한다. 관리자 처리 속도 향상(IT)은 계층 크기를 키우는 분권과 반대 효과를 낸다는 요약이 있다.
- 조건: 저자 전원과 발행 연도는 확인하지 못해 unconfirmed로 표기. 검색 결과 요약에서만 확인했다.
- 정정: 논문은 실제로 있고 저자는 Elisabeth Schulte와 Hans Peter Grüner(만하임)이다. 제목은 'Speed and Quality of Collective Decision-Making, I: Imperfect Information Processing'이다. 'Gruener and co-authors; Schulte & Gräuner (unconfirmed)'는 두 사람의 공저 1편으로 정리해야 하며, 별도의 'hierarchy designs 비교' 논문은 확인하지 못했다. Radner(1993)식 skip-level 트리가 균형 계층보다 속도·비용·결정 품질에서 우월하다는 점은 검색 요약으로 확인된다. 'IT로 처리 속도가 빨라지면 분권과 반대 효과'라는 요약은 확인하지 못했다. 후속편 DP4397도 있다.
- 검증 출처: https://voxeu.org/publications/dp4179 and web search (cepr.org/publications/dp4179)

### T7-10 · 부분 확인

Nicholas Bloom, Luis Garicano, Raffaella Sadun, John Van Reenen (2014). The Distinct Effects of Information Technology and Communication Technology on Firm Organization. Management Science (NBER WP 14975, 2009). [링크](https://www.nber.org/papers/w14975.pdf)

- 유형: field study · 비교: IT 수준과 통신기술 수준에 따른 분권도와 span
- 주장: 미국·유럽 제조업에서 정보기술(ERP, CAD/CAM)은 공장 관리자·생산직 자율성을 늘리고 span을 넓히는 분권화 요인이고, 통신기술은 중앙집권화 요인이다. 도구변수(ERP 원산지와의 거리, 규제로 인한 통신비 차이)로도 결과가 유지된다.
- 조건: PDF 본문은 압축되어 읽지 못했고 초록 요약에 근거. 효과 크기는 확인하지 못했다.
- 정정: Management Science 60(12), 2859-2885 (2014)로 확인된다. 정보기술(ERP, CAD/CAM)은 자율성·span 확대, 통신기술(데이터 네트워크)은 자율성 축소라는 주장은 일치한다. 다만 초록이 언급하는 도구변수는 규제로 인한 통신비 차이뿐이고, 'ERP 원산지와의 거리'는 초록에서 확인되지 않는다. 본문에서 확인이 필요하다.
- 검증 출처: https://www.nber.org/papers/w14975

### T7-11 · 확인

Scott E. Seibert, Gang Wang, Stephen H. Courtright (2011). Antecedents and Consequences of Psychological and Team Empowerment in Organizations: A Meta-Analytic Review. Journal of Applied Psychology 96(5), 981-1003. [링크](https://www.ovid.com/journals/japsy/pdf/10.1037/a0022676~antecedents-and-consequences-of-psychological-and-team)

- 유형: meta-analysis · 비교: 높은 임파워먼트(자율·권한) vs 낮은 임파워먼트
- 주장: 140여 개 이상 연구를 종합한 결과 심리적 임파워먼트는 직무만족, 조직몰입, 과업·맥락 성과와 정(+)의 관계를, 긴장과 이직의도와는 부(-)의 관계를 보였다. 팀 임파워먼트는 팀 성과와 정(+)의 관계였고 개인·팀 수준 관계가 통계적으로 유사하다.
- 조건: 사회정치적 지지, 리더십, 직무 특성, 고성과 관리가 선행 요인. 구체 상관계수는 확인하지 못했다. 상관 연구라 인과 해석에 한계.
- 검증 출처: https://www.ovid.com/journals/japsy/pdf/10.1037/a0022676~antecedents-and-consequences-of-psychological-and-team (via search results)

### T7-12 · 부분 확인

Bert George, Sanjay K. Pandey, Bram Steijn, Adelien Decramer, Mieke Audenaert (2021). Red Tape, Organizational Performance, and Employee Outcomes: Meta-analysis, Meta-regression, and Research Agenda. Public Administration Review 81(4), 638-651. [링크](https://pure.eur.nl/en/publications/red-tape-organizational-performance-and-employee-outcomes-meta-an/)

- 유형: meta-analysis · 비교: 결재·규칙 부담이 큰 조직 vs 작은 조직
- 주장: 번문욕례(red tape)는 조직 성과와 직원 결과 모두에 작거나 중간 크기의 유의한 부(-) 영향을 준다. 효과는 부문, 행정 전통, 연구 방법에 걸쳐 비교적 안정적이며, 조직 자체가 부과한 red tape가 외부 부과보다 더 해롭다. 반면 Blom, Borst & Voorn(2021)의 메타분석은 성과 효과는 미미하고 직원의 구속감·소외 효과가 두드러진다고 보고해 상충한다.
- 조건: 효과 크기와 표본 수는 확인하지 못했다. 공공부문 중심 표본이라 민간 소기업 일반화는 제한적이다.
- 정정: 저자, PAR 81(4), 638-651 (2021), 소규모에서 중간 크기의 부(-) 효과, 조직 내부 부과 red tape의 더 큰 해악, 부문·행정 전통·방법에 걸친 안정성은 모두 일치한다. 그러나 Blom, Borst & Voorn(2021) 메타분석과 상충한다는 부분은 이 초록에 없다. 해당 논문의 존재와 결과를 따로 확인해야 한다.
- 검증 출처: https://pure.eur.nl/en/publications/red-tape-organizational-performance-and-employee-outcomes-meta-an/

### T7-13 · 확인

unconfirmed (저자명이 페이지에 표시되지 않음) (2014). 직급체계 개편의 문제점과 대응방안에 대한 연구 (Problems and Solutions for Redesigning Personnel Grade System: A Case Study of a Korean Company). 경영교육연구 29(4), 30-55 (한국경영교육학회). [링크](https://scholar.kyobobook.co.kr/article/detail/4010024603950)

- 유형: field study · 비교: 다단계 직급 vs 직급 단계 축소(단일 사례, 전후)
- 주장: 국내 물류기업(A사)이 직급 단계를 줄여 수평 구조와 역할 기반 직급으로 가려 했으나, 1차 개편이 불균형한 인력 구조를 낳고 직원이 경력 정체와 보상 기회의 불공정을 느꼈다. 약 3년 안에 직원 불만이 심각해져 2차 개편을 했다.
- 조건: 단일 기업 사례로 일반화 불가. 보상·승진 경로가 함께 재설계되지 않을 때의 부작용 사례다. 정량 수치는 확인하지 못했다.
- 검증 출처: https://scholar.kyobobook.co.kr/article/detail/4010024603950

### T7-14 · 확인

Chang-Wook Jeung, Hea Jun Yoon (2018). When leadership elicits voice: Evidence for a mediated moderation model. Journal of Management & Organization 24(1), 40-61. [링크](https://www.cambridge.org/core/product/213A7B5F3A8F4FB6DAC801420143B55E)

- 유형: survey · 비교: 임파워링/겸손 리더십 수준 x 부하 권력거리 지향
- 주장: 한국 대기업집단 직원 306명 대상 설문에서 겸손한 리더십과 임파워링 리더십이 부하의 친사회적 발언(prosocial voice)과 정(+)의 관계였고, 심리적 임파워먼트가 매개했다(간접효과 95% CI: 겸손 [0.01, 0.11], 임파워링 [0.06, 0.17]). 부하의 권력거리 지향이 높을수록 리더십 효과가 더 강했다.
- 조건: 횡단·자기보고 설문, 남성 관리자 중심, 공통방법편의 가능성. 한편 다른 한국 표본 연구에서는 권력거리 지향이 높으면 심리적 안전만으로는 발언이 늘지 않고 자기검열이 늘어(검색 요약, 2차), 결과가 연구마다 엇갈린다.
- 검증 출처: https://www.cambridge.org/core/product/213A7B5F3A8F4FB6DAC801420143B55E

### T7-15 · 확인

Massimo G. Colombo, Marco Delmastro (2004). Delegation of Authority in Business Organizations: An Empirical Test. Journal of Industrial Economics 52(1), 53-80. [링크](https://ideas.repec.org/a/bla/jindec/v52y2004i1p53-80.html)

- 유형: field study · 비교: 결정 유형별 위임 수준과 설명 요인
- 주장: 이탈리아 제조 공장 자료에서 공장 복잡도, 통신기술, 소유 형태, 모기업 제품 구성이 권한 위임의 주요 설명요인이었고, 결정의 성격에 따라 위임 정도가 달랐다.
- 조건: 효과 크기와 표본 수는 이 연구 것으로 확인하지 못했다(관련 이탈리아어 논문의 438개 공장은 동일 표본인지 불명).
- 검증 출처: https://ideas.repec.org/a/bla/jindec/v52y2004i1p53-80.html

### T7 누락 문헌 (검증 에이전트 제안)

- Bolton, P. & Dewatripont, M. (1994) 'The Firm as a Communication Network', Quarterly Journal of Economics 109(4), 809-839: 계층 구조에서 정보 처리와 소통을 다룬 고전 모형이다. 승인 단계와 의사결정 지연을 이론적으로 뒷받침한다. 존재는 기억에 의존했고 이번에 조회하지는 않았다.
- Baker, G., Gibbons, R. & Murphy, K. (1999) 'Informal Authority in Organizations', Journal of Law, Economics, & Organization 15(1), 56-73: 공식 권한 없이 반복 관계로 유지되는 비공식 권한을 다룬다. Aghion-Tirole의 실질 권한 논의와 이어진다. 존재는 기억에 의존했고 이번에 조회하지는 않았다.
- Aghion, P., Bloom, N. & Van Reenen, J. (2014) 'Incomplete Contracts and the Internal Organization of Firms', Journal of Law, Economics, & Organization 30(suppl. 1), i37-i63: 위임 연구를 종합한 서베이다. 한국 기업 맥락 논의의 이론 배경으로 쓸 수 있다. 존재는 기억에 의존했고 이번에 조회하지는 않았다.


## G1. 시뮬레이션 실험 설계와 타당도

주의: 검색 예산이 소진되어 WebSearch는 1회만 성공했다(Park et al. 2023). 나머지는 알려진 arXiv/JASSS 주소를 WebFetch로 직접 열어 확인했으므로 요청한 8회 이상 검색은 채우지 못했다. 열어본 것은 초록 또는 페이지 요약이며, 본문 수치는 대부분 확인하지 못했다. 따라서 evidence가 primary-abstract-only인 항목은 초록 수준의 주장만 신뢰해야 한다. 확인된 증거는 다섯 갈래다. 첫째, ABM 방법론 문헌(Lee et al. 2015, Thiele et al. 2014, Galán et al. 2009, Grimm et al. 2020)은 반복 수, 변동계수 안정화, 검정력 기반 표본 크기, 전역 민감도 분석, 보고 표준을 제시한다. 둘째, LLM 프롬프트 민감도 연구(Sclar 2024, Mizrahi 2024)와 비결정성 연구(Atil 2024), 평가 통계 논문(Miller 2024)은 프롬프트 문구와 실행 간 분산이 크다는 것을 보여주며, 이는 구조 효과와 프롬프트 효과의 혼입 위험에 직결된다. 셋째, 페르소나 충실도 연구(Argyle 2022, Aher 2023, Santurkar 2023, Wang 2024, Gupta 2024, Zheng 2024, Salewski 2023)는 조건부 재현 가능성과 함께 편향, 평탄화, 페르소나 효과의 비예측성을 보고한다. 넷째, 동조와 과도한 협조성(Sharma 2023, Chuang 2023)은 갈등 점수가 낮게 나올 구조적 위험을 시사한다. 다섯째, 조직 구조 조작에 대한 LLM 에이전트 전용 통계 지침(혼합효과 모델, 블록 설계)은 이번에 직접 찾지 못했고, 위 문헌에서 추론한 설계 제안만 있다. 가장 실용적인 결론은 구조 조건당 실행 수를 효과 크기 기준으로 먼저 정하고, 프롬프트 변형과 시드를 반복 요인으로 교차시키며, 효과 크기와 신뢰구간 중심으로 해석하라는 것이다.

### G1-01 · 확인

Lee, Filatova, Ligmann-Zielinska, Hassani-Mahmooei, Stonedahl, Lorscheid, Voinov, Polhill, Sun, Parker (2015). The Complexities of Agent-Based Modeling Output Analysis. Journal of Artificial Societies and Social Simulation 18(4), 4. [링크](https://www.jasss.org/18/4/4.html)

- 유형: review · 비교: 구조 비교가 아니라 실행 수와 효과 크기 기준(일반 ABM 출력 분석)
- 주장: 검정력 기반 표본 크기: 표준화 효과 크기 d=0.5, 검정력 80%에서 t검정 이론 최소값은 집단당 약 64회이고 경험적 추정은 59~65회였다. Wilcoxon 검정은 64~78회를 제시했다. d=1.0이면 한 모형에서 약 18~26회로 줄었다. JASSS 논문에서 100회 이하 표본이 흔한데 종종 부족하다고 지적했다. 한 실행이 비싼 모형은 소수 결과를 부트스트랩해 분산을 추정하라고 제안한다.
- 조건: 출력 분포가 치우치면 t검정 기반 추정이 과대 추정될 수 있어 Wilcoxon을 보수적 대안으로 권한다. 이 수치는 저비용 ABM 시뮬레이션 기준이며 LLM 에이전트 시뮬레이션에 그대로 적용한 연구는 아니다.
- 검증 출처: https://www.jasss.org/18/4/4.html

### G1-02 · 확인

Lee et al. (2015). The Complexities of Agent-Based Modeling Output Analysis (출력 분석, 가설검정, 민감도 분석 부분). Journal of Artificial Societies and Social Simulation 18(4), 4. [링크](https://www.jasss.org/18/4/4.html)

- 유형: review · 비교: 일반 ABM 출력 분석 방법들(OAT, Morris 스크리닝, 회귀 메타모델, 분산 기반 방법) 비교
- 주장: 반복 수의 안정성 기준으로 변동계수(CV) 방법과 윈도 분산 방법을 제시한다(예시에서 안정화 지점이 n=1000 또는 약 400). 표본이 크면 사소한 차이도 유의해지므로 p값 대신 효과 크기, 더 엄격한 임계값, BIC, 베이즈 인수를 쓰라고 권한다. 평균만 보면 쌍봉 분포를 놓치므로 전체 분포를 보라고 한다. 단일 파라미터씩 바꾸는 OAT는 10개 파라미터에서 입력 공간의 약 0.25%만 덮는다고 했다. 분산 기반 전역 민감도는 M(k+1)회 실행(M>1000)이 필요해 비용이 크다.
- 조건: CV 안정화 기준은 강한 비선형 모형에서 성립하지 않을 수 있다. 분산 기반 방법은 LLM 실행 비용에서는 현실적이지 않다.
- 검증 출처: https://www.jasss.org/18/4/4.html

### G1-03 · 확인

Thiele, Kurth, Grimm (2014). Facilitating Parameter Estimation and Sensitivity Analysis of Agent-Based Models: A Cookbook Using NetLogo and R. Journal of Artificial Societies and Social Simulation 17(3), 11. [링크](https://www.jasss.org/17/3/11.html)

- 유형: review · 비교: 국소(OAT) 대 전역 민감도 분석, 스크리닝 방법
- 주장: 확률적 모형은 파라미터 조합마다 반복 실행해야 하며 예시는 조합당 10회였다. 실제 연구에서는 반복을 늘리고 CV가 안정화되는지 확인하라고 권한다. 1인자씩 바꾸는 국소 분석은 상호작용을 무시하고 기준값에 따라 결론이 달라지므로 한계가 있다. 전역 방법이 불확실한 입력에 적합하고, 비싼 모형에는 Morris 기본효과 스크리닝(μ*, μ, σ)을 권한다.
- 조건: 페이지 텍스트가 일부만 읽혔다(앞 100000자). 비선형이 강하면 CV 수렴 점검이 맞지 않을 수 있다.
- 검증 출처: https://www.jasss.org/17/3/11.html

### G1-04 · 확인

Galán, Izquierdo, Izquierdo, Santos, del Olmo, López-Paredes, Edmonds (2009). Errors and Artefacts in Agent-Based Modelling. Journal of Artificial Societies and Social Simulation 12(1), 1. [링크](https://www.jasss.org/12/1/1.html)

- 유형: theory · 비교: 핵심 가정 대 부수적 가정 변형(로버스트니스 점검)
- 주장: 모형의 의도와 실제 동작이 다른 것이 오류(error)이고, 부수적 가정이 사실은 유의미해서 생기는 유의한 결과가 인공물(artefact)이다. 약 1/1000 확률의 희귀 이상 결과는 반복 없이는 발견되지 않는다. 핵심 가정은 고정하고 부수적 가정(스케줄링 순서, 위상 등)을 바꿔도 유지되는 결론만 유효로 보라고 한다. 다른 난수 생성기나 환경에서 재실행하는 것도 인공물 탐지 방법이다.
- 조건: 모형 구축과 테스트가 초점이며 반복 수나 민감도 분석의 통계 절차는 상세히 다루지 않는다.
- 검증 출처: https://www.jasss.org/12/1/1.html

### G1-05 · 확인

Grimm, Railsback, Vincenot, Berger, Gallagher, DeAngelis, Edmonds, Ge, Giske, Groeneveld, Johnston, Milles, Nabe-Nielsen, Polhill, Radchuk, Rohwäder, Stillman, Thiele, Ayllón (2020). The ODD Protocol for Describing Agent-Based and Other Simulation Models: A Second Update to Improve Clarity, Replication, and Structural Realism. Journal of Artificial Societies and Social Simulation 23(2), 7. [링크](https://www.jasss.org/23/2/7.html)

- 유형: theory · 비교: 해당 없음(보고 표준)
- 주장: 개정 ODD는 구조화된 보고 틀이다. 요소별 근거(Rationale) 서술, 평가에 쓰는 관찰 패턴을 목적 항목에 명시, 시뮬레이션 실험 기술용 템플릿(S7)과 TRACE 예시(S6), 요약 ODD와 중첩 ODD, ODD와 코드 연결을 추가했다. 모형이 재현하지 못한 패턴도 보고하라고 권하고, 실제 프로그램이 하는 일을 기술하라고 강조한다. 모든 시뮬레이션 모형에 적용 가능하다고 주장한다.
- 조건: 페이지의 마지막 약 4000자는 읽지 못했다. ODD는 LLM 에이전트 전용으로 설계되지 않았으므로, 프롬프트와 모델 버전 같은 LLM 특유 요소는 ODD에 추가로 적어야 한다(이는 본 보고자의 제안이며 논문 주장이 아니다).
- 검증 출처: https://www.jasss.org/23/2/7.html

### G1-06 · 확인

Sclar, Choi, Tsvetkov, Suhr (2023). Quantifying Language Models' Sensitivity to Spurious Features in Prompt Design or: How I learned to start worrying about prompt formatting. ICLR 2024 (arXiv:2310.11324). [링크](https://arxiv.org/abs/2310.11324)

- 유형: lab experiment · 비교: 프롬프트 형식 변형 간 성능 차이(구조 비교가 아님)
- 주장: 의미를 보존하는 프롬프트 형식 변경만으로 LLaMA-2-13B에서 정확도가 최대 76포인트 차이 났다. 민감도는 모델 크기가 커지거나 퓨샷 예시가 늘거나 지시 튜닝을 해도 사라지지 않는다. 형식별 성능은 모델 간 상관이 약해 하나의 프롬프트로 모델을 비교하면 안 된다. 단일 형식 대신 그럴듯한 형식들에 걸친 성능 범위를 보고하라고 권하며 FormatSpread 알고리즘을 제안한다.
- 조건: 퓨샷 분류형 과제 평가이며 다중 에이전트 장기 시뮬레이션에서의 크기는 직접 측정되지 않았다. 초록 수준만 확인했다.
- 검증 출처: https://arxiv.org/abs/2310.11324

### G1-07 · 확인

Mizrahi, Kaplan, Malkin, Dror, Shahaf, Stanovsky (2024). State of What Art? A Call for Multi-Prompt LLM Evaluation. TACL (arXiv:2401.00595). [링크](https://arxiv.org/abs/2401.00595)

- 유형: lab experiment · 비교: 단일 프롬프트 대 다중 프롬프트 평가
- 주장: 단일 프롬프트 평가의 취약성을 약 650만 인스턴스, LLM 20개, 과제 39개, 벤치마크 3개로 조사했다. 지시 템플릿 하나 대신 다양한 프롬프트 집합으로 모델을 평가해야 더 견고하다고 주장하고, 사용자 유형별 지표를 제안한다.
- 조건: 초록에는 프롬프트 간 분산의 구체적 수치가 없었다. 벤치마크 평가이며 에이전트 시뮬레이션은 아니다.
- 검증 출처: https://arxiv.org/abs/2401.00595

### G1-08 · 부분 확인

Atil, Aykent, Chittams, Fu, Passonneau, Radcliffe, Rajagopal, Sloan, Tudrej, Ture, Wu, Xu, Baldwin (2024). Non-Determinism of "Deterministic" LLM Settings. arXiv:2408.04667. [링크](https://arxiv.org/abs/2408.04667)

- 유형: lab experiment · 비교: 동일 설정 반복 실행 간 변동(구조 비교가 아님)
- 주장: 결정적으로 설정한 LLM 5개를 8개 과제에서 10회 실행했더니 정확도가 자연 반복 간 최대 15% 달랐고 최선과 최악의 차이는 최대 70%였다. 어떤 모델도 모든 과제에서 반복 가능한 정확도를 내지 못했고 동일한 출력 문자열도 보장되지 않았다. 일치도 지표 TARr@N과 TARa@N을 제안했다.
- 조건: 원인은 내부자 비공식 논의에 근거한 추측으로 제시되어 있다. API 제공자와 모델에 따라 정도가 다를 수 있다.
- 정정: 저자 13명, 수치(5 LLM, 8과제, 10회, 최대 15%, 최선-최악 최대 70%, TARr@N/TARa@N) 일치. 단 arXiv 프리프린트로 확인되며 동료심사 게재는 확인하지 못했다. 제로샷과 퓨샷 두 설정에서 실행했다는 점이 빠져 있다.
- 검증 출처: https://arxiv.org/abs/2408.04667

### G1-09 · 확인

Evan Miller (2024). Adding Error Bars to Evals: A Statistical Approach to Language Model Evaluations. arXiv:2411.00640. [링크](https://arxiv.org/abs/2411.00640)

- 유형: theory · 비교: 두 모델 간 차이 측정(오차막대 기반 비교)
- 주장: LLM 평가를 실험으로 보고, 평가 문항이 미지의 초모집단에서 뽑힌 표본이라고 보는 통계적 틀을 제안한다. 평가 데이터 분석, 두 모델 차이 측정, 평가 실험 계획을 위한 공식을 제시하고 통계적 잡음을 줄여 보고하라고 권한다.
- 조건: 초록에는 수치와 구체 공식이 없다. 문항 표본 추출 변동을 다루며 에이전트 시뮬레이션의 장기 상호작용을 직접 다루지는 않는다.
- 검증 출처: https://arxiv.org/abs/2411.00640

### G1-10 · 확인

Argyle, Busby, Fulda, Gubler, Rytting, Wingate (2022). Out of One, Many: Using Language Models to Simulate Human Samples. arXiv:2209.06899 (관련 DOI 10.1017/pan.2023.2, 저널명은 페이지에서 확인 못함). [링크](https://arxiv.org/abs/2209.06899)

- 유형: lab experiment · 비교: 실리콘 표본 대 인간 설문 표본
- 주장: GPT-3의 편향이 세밀하고 인구통계와 상관돼 있어, 실제 설문 응답자의 사회인구학적 배경 서사를 입력하면 여러 하위집단의 응답 분포를 재현할 수 있다고 주장하며 이 성질을 알고리즘적 충실도(algorithmic fidelity)라 부른다. 수천 개의 배경 서사로 '실리콘 표본'을 만들어 인간 표본과 비교했다.
- 조건: 초록에 정량 결과가 없다. 미국 설문과 GPT-3에 한정된 결과이며 조직 내 상호작용이나 갈등에는 직접 검증되지 않았다.
- 검증 출처: https://arxiv.org/abs/2209.06899

### G1-11 · 확인

Aher, Arriaga, Kalai (2023). Using Large Language Models to Simulate Multiple Humans and Replicate Human Subject Studies. ICML 2023 (arXiv:2208.10264). [링크](https://arxiv.org/abs/2208.10264)

- 유형: lab experiment · 비교: LLM 시뮬레이션 대 기존 인간 실험 결과
- 주장: Turing Experiment 개념으로 최후통첩 게임, 가든패스 문장, 밀그램 충격 실험, 군중의 지혜를 재현했다. 앞 세 개는 최신 모델에서 원래 결과가 재현됐고, 군중의 지혜 실험에서는 ChatGPT와 GPT-4를 포함한 일부 모델에서 '초정확성 왜곡(hyper-accuracy distortion)'이 나타났다.
- 조건: 초록에 효과 크기가 없다. 단순한 선택과 판단 과제 위주이며 장기 조직 상호작용 과제는 아니다.
- 검증 출처: https://arxiv.org/abs/2208.10264

### G1-12 · 확인

Park, O'Brien, Cai, Morris, Liang, Bernstein (2023). Generative Agents: Interactive Simulacra of Human Behavior. UIST '23 (arXiv:2304.03442). [링크](https://arxiv.org/abs/2304.03442)

- 유형: simulation · 비교: 에이전트 아키텍처 구성요소 제거 조건
- 주장: 관찰, 계획, 반성으로 구성된 메모리 아키텍처로 25명 에이전트가 사는 마을을 구현했고, 발렌타인 파티라는 하나의 시드로 초대 전파, 새로운 관계 형성, 동시 출석 조율이 자율적으로 나타났다. 제거 실험에서 세 구성요소가 각각 행동의 신빙성(believability)에 기여했다고 보고한다.
- 조건: 신빙성은 저자들의 자체 평가 기준이다. 이번 조사에서 이 논문의 한계 서술은 확인하지 못했고(초록 페이지에 없음), 다른 연구가 지적하는 한계는 따로 확인되지 않았다. 단일 시뮬레이션 맥락이다.
- 검증 출처: https://arxiv.org/abs/2304.03442

### G1-13 · 확인

Santurkar, Durmus, Ladhak, Lee, Liang, Hashimoto (2023). Whose Opinions Do Language Models Reflect?. arXiv:2303.17548. [링크](https://arxiv.org/abs/2303.17548)

- 유형: lab experiment · 비교: LM 의견 대 인구통계 집단별 여론조사
- 주장: OpinionsQA로 LM 의견이 미국 인구통계 집단 60개와 얼마나 맞는지 측정했다. 불일치가 기후변화에 대한 민주당-공화당 격차 수준이었고, 특정 집단으로 유도해도 불일치가 남았다. 일부 인간 피드백 튜닝 LM은 좌편향이며 65세 이상, 사별자 같은 집단은 잘 반영되지 않았다.
- 조건: 의견과 정치 주제에 대한 결과이며 업무 행동이나 조직 갈등 행동에는 직접 적용되지 않는다.
- 검증 출처: https://arxiv.org/abs/2303.17548

### G1-14 · 확인

Wang, Morgenstern, Dickerson (2024). Large language models that replace human participants can harmfully misportray and flatten identity groups. Nature Machine Intelligence (arXiv:2402.01908에서 수락 사실 확인). [링크](https://arxiv.org/abs/2402.01908)

- 유형: lab experiment · 비교: LLM 응답 대 인간 응답(정체성 집단별)
- 주장: 16개 정체성 집단, 참가자 3,200명, LLM 4개로 연구해 LLM이 집단을 잘못 묘사하고 집단 내 다양성을 평탄화하며 정체성 프롬프트가 본질화할 수 있음을 보였다. 추론 시점 기법이 해악을 줄이지만 없애지는 못했다.
- 조건: 정체성이 과제에 중요한 경우에 해당한다. 직무 중심 시뮬레이션에서의 크기는 미확인이다.
- 검증 출처: https://arxiv.org/abs/2402.01908

### G1-15 · 확인

Gupta, Shrivastava, Deshpande, Kalyan, Clark, Sabharwal, Khot (2023). Bias Runs Deep: Implicit Reasoning Biases in Persona-Assigned LLMs. ICLR 2024 (arXiv:2311.04892). [링크](https://arxiv.org/abs/2311.04892)

- 유형: lab experiment · 비교: 페르소나 부여 대 비부여 조건의 추론 성능
- 주장: 추론 데이터셋 24개, LLM 4개, 사회인구학적 페르소나 19개를 사용했다. ChatGPT-3.5에서 페르소나의 80%가 편향을 보였고, 일부 데이터셋에서는 성능이 70% 이상 하락했다. GPT-4-Turbo가 가장 적었지만 페르소나의 42%에서 영향이 있었다. 모델은 직접 물으면 고정관념을 거부하지만 페르소나로 답할 때는 드러냈다.
- 조건: 추론 벤치마크 결과이며 업무 시뮬레이션에서의 크기는 미확인이다. 모델 세대에 따라 줄어들 수 있다(GPT-4-Turbo가 더 낮음).
- 검증 출처: https://arxiv.org/abs/2311.04892

### G1-16 · 확인

Zheng, Pei, Logeswaran, Lee, Jurgens (2023). When "A Helpful Assistant" Is Not Really Helpful: Personas in System Prompts Do Not Improve Performances of Large Language Models. Findings of EMNLP 2024 (arXiv:2311.10054). [링크](https://arxiv.org/abs/2311.10054)

- 유형: lab experiment · 비교: 페르소나 부여 대 무페르소나 대조
- 주장: 162개 역할, 4개 LLM 계열, 사실 문항 2,410개로 시험해 시스템 프롬프트의 페르소나가 무페르소나 대조에 비해 성능을 일관되게 개선하지 않았다. 페르소나의 성별, 유형, 분야가 정확도에 영향을 줄 수 있고, 문항별 최적 페르소나를 오라클로 고르면 정확도가 오르지만 자동 선택은 무작위 수준에 가까웠다.
- 조건: 사실 질의응답 정확도 기준이다. 사회적 행동 시뮬레이션에서의 효과는 다를 수 있다.
- 검증 출처: https://arxiv.org/abs/2311.10054

### G1-17 · 부분 확인

Sharma, Tong, Korbak, Duvenaud, Askell, Bowman, Cheng, Durmus, Hatfield-Dodds, Johnston, Kravec, Maxwell, McCandlish, Ndousse, Rausch, Schiefer, Yan, Zhang, Perez (2023). Towards Understanding Sycophancy in Language Models. arXiv:2310.13548. [링크](https://arxiv.org/abs/2310.13548)

- 유형: lab experiment · 비교: 해당 없음(모델 행동 분석)
- 주장: 최신 AI 어시스턴트 5개가 자유 서술 과제 4개에서 아첨(sycophancy)을 보였다. 사용자 견해와 맞는 응답이 선호될 확률이 높았고, 인간과 선호 모델 모두 설득력 있게 쓰인 아첨 응답을 정답보다 '무시 못 할 비율'로 선호했다. 선호 모델에 맞춰 최적화하면 진실성이 희생되는 경우가 있다.
- 조건: 초록에 비율이 없다. 사용자-어시스턴트 대화 맥락이며 에이전트 간 대화에서의 크기는 직접 검증되지 않았다.
- 정정: 저자와 내용은 일치. 다만 arXiv 프리프린트로만 확인되며 동료심사 게재는 확인하지 못했다. 초록 표현은 '무시 못 할 비율'이 아니라 인간과 선호 모델이 설득력 있는 아첨 응답을 정답보다 '때로는' 선호한다는 것이다. 최적화도 '때로는' 진실성을 희생한다. 일부 구체적 수치는 없다.
- 검증 출처: https://arxiv.org/abs/2310.13548

### G1-18 · 부분 확인

Chuang, Goyal, Harlalka, Suresh, Hawkins, Yang, Shah, Hu, Rogers (2023). Simulating Opinion Dynamics with Networks of LLM-based Agents. arXiv:2311.09618. [링크](https://arxiv.org/abs/2311.09618)

- 유형: LLM-agent experiment · 비교: 기본 에이전트 대 확증 편향 주입 에이전트(의견 네트워크)
- 주장: LLM 에이전트는 정확한 정보 쪽으로 강한 고유 편향이 있어 과학적 합의로 수렴한다. 이 때문에 합의에 대한 저항을 연구하기 어렵다. 프롬프트 공학으로 확증 편향을 주입하면 의견 분열이 나타나 기존 ABM 연구와 일치했다.
- 조건: 의견 동역학 주제에 한정된 결과이고 초록에 수치가 없다.
- 정정: 저자 9명과 내용은 일치. 그러나 arXiv 프리프린트로만 표기돼 있고, 정식 게재는 Findings of NAACL 2024, pp. 3326-3346이다. 인용에 이 게재처를 넣어야 한다.
- 검증 출처: https://aclanthology.org/2024.findings-naacl.211

### G1 누락 문헌 (검증 에이전트 제안)

- Bisbee, Clinton, Dorff, Kenkel, Larson (2024) Synthetic Replacements for Human Survey Data? The Perils of Large Language Models. Political Analysis 32, 401-416 [링크](https://www.cambridge.org/core/product/B92267DC26195C7F36E63EA04A47D2FE): ChatGPT 페르소나 합성 표본이 프롬프트 문구에 민감하고, 같은 프롬프트도 3개월 사이 결과가 크게 달라졌다. 회귀 분석에서 인간 자료와 다른 추론이 나왔다. 재현성과 반복 지침에 직접 관련된다.
- Dominguez-Olmedo, Hardt, Mendler-Dünner (2024) Questioning the Survey Responses of Large Language Models. NeurIPS 2024 [링크](https://proceedings.neurips.cc/paper_files/paper/2024/hash/515c62809e0a29729d7eec26e2916fc0-Abstract.html): 응답 순서와 라벨 편향을 보정하면 모델 답이 거의 균등 분포로 가고, 이진 분류기가 인구조사 응답과 거의 완벽히 구분한다. 인구집단 정렬 결과가 인공물일 수 있다는 점이 실험 타당도 논의에 중요하다.


## G2. 팀 규모와 프로세스 손실

중요 제한: 이 세션의 WebSearch 예산(200회)이 소진되어 계획한 8개 이상의 검색을 하나도 수행하지 못했다. 우회(curl, 제3자 검색)는 하지 않았다. 대신 WebFetch로 Crossref API와 DOI 링크를 열어 일부 서지 정보만 확인했다. 확인된 것은 Brooks 1975, Latané-Williams-Harkins 1979, Ingham 등 1974의 존재(저자, 연도, 학술지)뿐이며, 초록이나 수치는 열어보지 못했다. 나머지 항목은 학습된 지식에서 재구성한 것이므로 evidence를 unconfirmed로 표시했고 수치는 기억 기반 근사치라고 명시했다. 문헌의 큰 그림은 다음과 같다. Steiner의 실제 생산성 = 잠재 생산성 - 프로세스 손실 틀, Ringelmann 효과(조정 손실과 동기 손실의 분리), 사회적 태만과 집단 노력 모형, Brooks의 소통 경로 n(n-1)/2, Hackman의 작은 팀 권고가 핵심이다. 이 문헌들은 시뮬레이션의 통제 변수(부서 크기, 관리 폭, 경로 수)를 정당화하지만, 10~20명 규모 부서 분할을 직접 조작한 실증은 이 세션에서 확인하지 못했다. 재검색 시 팀 규모 메타분석, 소프트웨어 팀 규모 실증(QSM 등), LLM 멀티에이전트 규모 연구를 우선 확인해야 한다.

### G2-01 · 확인

Fred P. Brooks, Jr. (1975). The Mythical Man-Month. Addison-Wesley (book). [링크](https://api.crossref.org/works?query.bibliographic=Brooks+Mythical+Man-Month&rows=1)

- 유형: theory · 비교: 인원 증가 전후의 소통 경로 수와 분업 가능성
- 주장: 서지 존재는 Crossref로 확인했다. 내용은 기억 기반이다. 늦어진 소프트웨어 프로젝트에 인력을 추가하면 더 늦어진다는 Brooks의 법칙을 제시한다. 근거는 신규 인원의 교육 비용과 소통 경로가 n(n-1)/2로 늘어난다는 점이다. 예를 들어 10명은 45개, 20명은 190개 경로다. 책 본문은 열어보지 못했다.
- 조건: 과업이 쉽게 분할되지 않고 상호의존적일수록 손실이 크다. 완전 분할 가능한 과업이면 인력 추가가 도움이 된다.
- 검증 출처: 기억 및 통념(웹검색 한도 소진으로 재검색 못함); n(n-1)/2 산술 직접 검산

### G2-02 · 확인

Ivan D. Steiner (1972). Group Process and Productivity. Academic Press (book).

- 유형: theory · 비교: 과업 유형별 잠재 생산성 규칙과 집단 크기
- 주장: 실제 생산성 = 잠재 생산성 - 프로세스 손실이라는 틀이다. 과업 유형(가산형, 분리형, 결합형, 보완형 등)에 따라 잠재 생산성이 결정되고, 조정 손실과 동기 손실이 그 차이를 만든다. 서지와 내용은 기억 기반이며 이 세션에서 열어보지 못했다.
- 조건: 가산형 과업은 인원이 늘수록 잠재 생산성이 오르지만 손실이 함께 커진다. 결합형(가장 약한 고리) 과업은 인원 증가가 잠재 생산성을 오히려 낮춘다.
- 검증 출처: Ingham 1974 검색 결과에 Steiner의 '실제 생산성 = 잠재 생산성 - 프로세스 손실' 모형 언급 확인(https://is.muni.cz/el/phil/jaro2020/PSX_512/um/Ingham_et_al_1974_Ringelmann_effect.pdf)

### G2-03 · 부분 확인

Alan G. Ingham, George Levinger, James Graves, Vaughn Peckham (1974). The Ringelmann effect: Studies of group size and group performance. Journal of Experimental Social Psychology. [링크](https://doi.org/10.1016/0022-1031(74)90033-x)

- 유형: lab experiment · 비교: 집단 크기(1~여러 명)에 따른 1인당 줄 당기는 힘, 실제 집단 대 유사 집단
- 주장: 서지는 Crossref로 확인했다. 초록은 열지 못했다. 기억으로는 줄다리기 실험에서 집단 크기가 커질수록 1인당 출력이 감소했고, 감소의 상당 부분은 동기 저하보다 조정 손실로 설명되었다. 정량 수치는 확인하지 못했다.
- 조건: 물리적으로 동시 행동이 필요한 과업에서 조정 손실이 두드러진다. 정신 과업에는 그대로 일반화되지 않는다.
- 정정: 서지는 맞다. 1~6인 줄다리기에서 1인당 출력이 감소했고 감소는 곡선형(1에서 2~3명으로 갈 때 가장 크고 4~6명은 완만)이었다. 핵심은 가짜 집단(pseudo-group, 공모자가 당기는 척) 실험으로 동기 손실과 조정 손실을 분리한 점이다. 일반적 해석은 조정 손실이 더 큰 몫이고 동기 손실도 존재한다는 것이다. 다만 검색 중 2차 자료 하나는 동기 손실이 지배적이라고 읽었으므로 배분 비율을 단정하지 말고 원문 수치를 확인해야 한다. 원래 Ringelmann 1913 데이터는 Moede 1927을 통해 전해졌고 Ingham이 처음 재현했다.
- 검증 출처: https://is.muni.cz/el/phil/jaro2020/PSX_512/um/Ingham_et_al_1974_Ringelmann_effect.pdf (검색 스니펫만; JESP 10, 371-384)

### G2-04 · 부분 확인

Bibb Latané, Kipling Williams, Stephen Harkins (1979). Many hands make light the work: The causes and consequences of social loafing. Journal of Personality and Social Psychology. [링크](https://doi.org/10.1037/0022-3514.37.6.822)

- 유형: lab experiment · 비교: 개인 단독 수행 대 집단 수행, 집단 크기, 식별 가능성
- 주장: 서지는 Crossref로 확인했다. 내용은 기억 기반이다. 박수와 소리 지르기 과제에서 집단이 커질수록 1인당 출력이 줄었고, 개인 책임이 식별되지 않을 때 태만이 나타났다. 크기별 구체 비율은 확인하지 못했다.
- 조건: 개별 기여가 식별되지 않을 때 태만이 크다. 식별 가능하거나 과업이 의미 있으면 줄어든다.
- 정정: 서지는 기억상 맞다. 다만 이 논문의 핵심 비교는 개인 출력이 식별 가능한지 여부를 조작한 것과 가짜 집단 통제이며, 집단이 커질수록 1인당 출력이 감소했다(박수·함성 과제). 구체 비율은 원문 확인 필요. 이 세션에서는 웹으로 확인하지 못했다.
- 검증 출처: 검색 한도 소진으로 미검증; DOI 10.1037/0022-3514.37.6.822 및 JPSP 37(6), 822-832는 기억상 일치

### G2-05 · 부분 확인

Steven J. Karau, Kipling D. Williams (1993). Alleviating social loafing: Collective effort model / meta-analytic review (Karau & Williams 1993). Journal of Personality and Social Psychology. [링크](https://doi.org/10.1037/0022-3514.65.4.681)

- 유형: meta-analysis · 비교: 집단 대 개인 수행, 평가 가능성, 과업 의미, 집단 응집, 보상 등의 조절 변수
- 주장: DOI 리다이렉트까지만 확인했고 본문은 열지 못했다. 기억으로는 약 80편 미만의 연구를 통합한 사회적 태만 메타분석이며, 사회적 태만은 평균적으로 중간 수준의 효과로 나타나고 여러 문화와 성별에서 재현된다고 알려져 있다. 정확한 연구 수와 효과 크기는 확인되지 않았다. 제목도 정확하지 않을 수 있어 재검증이 필요하다.
- 조건: 평가 가능성 증가, 과업 의미와 집단 응집이 높을 때, 과업 난이도가 높을 때 태만이 줄어든다고 알려져 있다.
- 정정: 제목이 틀렸다. 올바른 제목은 'Social loafing: A meta-analytic review and theoretical integration'이다('Alleviating social loafing'은 아님). 78개 연구를 통합했고 사회적 태만은 견고하며 효과 크기는 중간 수준이라고 보고한다. 집단 크기, 평가 가능성, 과업 가치, 동료 성과 기대가 조절변수다. 집단 크기 조절 효과는 확인했다. 문화·성별에 걸친 재현 주장은 이 논문에서 태만이 여성과 동양 문화권에서 더 작았지만 여전히 나타났다는 취지로 알고 있으나 이번에는 확인하지 못했다.
- 검증 출처: https://typeset.io/pdf/social-loafing-a-meta-analytic-review-and-theoretical-22g4ic0jro.pdf 및 검색 결과의 APA 서지 (JPSP 65(4), 681-706)

### G2-06 · 확인 불가

J. Richard Hackman (2002). Leading Teams: Setting the Stage for Great Performances. Harvard Business School Press (book).

- 유형: theory · 비교: 팀 규모 및 팀 설계 조건
- 주장: 기억 기반이며 열어보지 못했다. 팀은 과업 수행에 필요한 최소한의 크기로 구성해야 하고, 팀이 커질수록 조정 연결과 프로세스 문제가 급증한다고 논한다. 흔히 인용되는 '약 6명 안팎'이라는 숫자는 이 세션에서 원문 확인이 안 됐다.
- 조건: 과업이 요구하는 다양한 전문성이 확보되는 한도 안에서 작을수록 좋다.
- 정정: 서지는 기억상 맞지만 '약 6명 안팎'이라는 수치의 원문 위치는 확인하지 못했다. 이 숫자는 Hackman의 여러 저술과 2차 자료에서 반복되므로 쪽수 단위로 원문 확인 전까지 인용을 보류해야 한다.
- 검증 출처: 검색 한도 소진으로 확인 실패; 서지(Hackman 2002, HBS Press)는 기억 기반

### G2-07 · 확인 불가

Susan A. Wheelan (2009). Group size, group development, and group productivity. Small Group Research.

- 유형: survey · 비교: 소규모(3~8명) 대 대규모(9명 이상) 팀의 성숙도와 생산성 인식
- 주장: 기억 기반이며 확인하지 못했다. 소집단 발달 단계와 생산성을 크기별로 비교했고, 3~8명 팀이 더 큰 팀보다 발달 단계와 생산성이 높다고 보고한 것으로 기억한다. 표본 수와 효과 크기는 미확인이다.
- 조건: 자기보고 측정이라 방법상 한계가 있다.
- 정정: 기억상 존재하는 논문이며 3~8명 집단이 12명 이상 등 큰 집단보다 생산성과 발달 수준이 높다고 보고한 것으로 알지만 웹 확인은 하지 못했다. 표본 수와 정확한 범주(3~8 대 9명 이상 등)는 원문 확인이 필요하다.
- 검증 출처: 검색 한도 소진으로 검색 실패; 기억상 Small Group Research 40(2), 247-262

### G2-08 · 오류

Lawrence H. Putnam 외 (미확인) (1978). Software Cost Estimation with Cocomo II / Putnam SLIM 계열의 팀 규모-노력 관계 (구체 논문 미확인). 미확인.

- 유형: field study · 비교: 프로젝트 규모, 인력 투입, 일정 압축
- 주장: 소프트웨어 공학에서 팀 규모가 커지면 인원당 생산성이 비선형으로 떨어지고, 일정 단축을 위한 인력 투입은 노력을 초선형으로 늘린다는 실증이 있는 것으로 알고 있으나, 구체 서지와 수치를 확인하지 못했다. 인용 금지 수준의 단서로만 기록한다.
- 조건: 일정 압축 구간에서 효과가 크다.
- 정정: 서지가 뒤섞여 있다. Putnam 1978 'A general empirical solution to the macro software sizing and estimating problem'(IEEE Trans. Software Engineering 4(4))가 SLIM의 근거이고, COCOMO II는 Boehm 등(2000)의 별개 저작이다. 이 항목은 이 둘을 하나로 묶은 것이므로 그대로 인용하지 말고 각각 따로 확인해야 한다. 단 일정 단축 시 노력이 초선형으로 늘어난다는 방향은 Putnam 모형과 일치하는 것으로 안다.
- 검증 출처: 검색 한도 소진으로 미검증; 기억 기반 판단

### G2-09 · 확인 불가

미확인 (). 팀 규모와 성과 메타분석 (구체 논문 미확인).

- 유형: meta-analysis · 비교: 팀 크기와 성과
- 주장: Crossref 검색에서는 팀 구성 변수 메타분석(Bell 2005)과 공유 리더십 메타분석(D'Innocenzo 등 2016)만 보였고, 팀 규모 자체를 다룬 메타분석은 확인하지 못했다. 팀 규모 효과 크기를 단정할 수 없다.
- 조건: 해당 없음
- 정정: 구체 논문이 없는 항목이다. 팀 규모를 직접 다룬 메타분석은 확인하지 못했다. 크기 관련 메타분석 후보로 Mullen·Johnson·Salas(1991)와 Hill(1982) 리뷰를 아래에 올린다. 모두 기억 기반이며 이번에 검색으로 확인하지 못했다.
- 검증 출처: 검색 한도 소진으로 미검증

### G2-10 · 확인 불가

미확인 (). 팀 규모와 갈등, 소통량 관계 (구체 논문 미확인).

- 유형: review · 비교: 집단 규모와 갈등 수준
- 주장: 큰 집단에서 소통량, 하위 집단 형성, 관계 갈등이 늘어난다는 주장은 흔하지만, 이 세션에서는 이를 직접 뒷받침하는 1차 문헌을 확인하지 못했다.
- 조건: 미확인
- 정정: 구체 인용이 없는 항목이다. 소통 경로 증가는 산술적으로(n(n-1)/2) 타당하지만, 규모와 관계 갈등의 직접 실증은 확인하지 못했다. 단정하지 말고 보류해야 한다.
- 검증 출처: 검색 한도 소진으로 미검증

### G2 누락 문헌 (검증 에이전트 제안)

- Kravitz & Martin (1986) Ringelmann rediscovered: The original article. JPSP 50(5), 936-941 [링크](https://www.researchgate.net/profile/David_Kravitz2/publication/209410111_Ringelmann_Rediscovered_The_Original_Article/links/0deec5384ffc87e9c4000000/Ringelmann-Rediscovered-The-Original-Article.pdf): Ringelmann 원자료가 Moede 1927을 거쳐 전해졌고 직접 재현이 Ingham 전까지 없었다는 점을 짚는다. 이번 검색에서 존재를 확인했다.
- Hill (1982) Group versus individual performance: Are N+1 heads better than one? Psychological Bulletin 91(3), 517-539: 집단 크기와 성과를 다룬 고전 리뷰다. 기억 기반이며 이번에는 확인하지 못했다.
- Mullen, Johnson & Salas (1991) Productivity loss in brainstorming groups: A meta-analytic integration. Basic and Applied Social Psychology 12(1), 3-23: 조정·프로세스 손실을 메타분석한 것으로 알고 있다. 집단 크기와 손실을 다루는 정량 근거 후보다. 이번에는 확인하지 못했다.
- Diehl & Stroebe (1987) Productivity loss in brainstorming groups. JPSP 53(3), 497-509: 프로세스 손실 중 생산 차단(production blocking)을 실험적으로 분리한 연구다. 기억 기반이며 이번에는 확인하지 못했다.
- Putnam (1978) A general empirical solution to the macro software sizing and estimating problem. IEEE Trans. Software Engineering 4(4): G2-08의 올바른 원전 후보다. 기억 기반이며 이번에는 확인하지 못했다.


## G3. 업무 부하·역할 스트레스·리더십 구조

검증 한계를 먼저 밝힌다. 이 세션의 WebSearch 예산이 첫 검색 1건 이후 소진되어 계획한 8회 이상 검색을 수행하지 못했다. 열어본 1차 자료는 Bakker & Demerouti(2007) 한 편뿐이고, 매트릭스 이중 리더십 연구는 Berkeley CMR의 2차 요약만 확인했다. 나머지 핵심 문헌(Alarcon 2011, Gilboa 2008, Wang 등 2014, Anderson & Brown 2010, Greer 등 2018, Karasek 1979, Van der Doef & Maes 1999)은 PsycNet이 로딩되지 않아 원문을 못 열었다. 이들은 배경지식으로만 적었고 evidence를 unconfirmed로 표시했으며, 수치는 확인 전 인용 금지로 적었다. 확인된 내용만 보면, (1) 이중 보고 부하는 두 리더와의 관계 품질 비대칭에서 역할 갈등이 커지고 리더 간 관계가 이를 완충한다는 단일 기업 표본(N=111) 증거가 있고, (2) JD-R 모형은 요구와 자원의 분류, 건강손상과 동기부여의 이중 경로, 완충, 상호 효과라는 틀을 준다. 이 틀을 구조 변수에 연결한 시뮬레이션이나 실증 연구는 찾지 못했다. 승인 병목 보직자의 번아웃을 직접 다룬 연구도 확인하지 못했다. 다른 세션이나 예산 회복 후 재검색이 필요하다.

### G3-01 · 부분 확인

Sahlmueller, Van Knippenberg, Van Quaquebeke, Giessner (2022). Two in the Lead: The Importance of Relationships When There Are Two Bosses (CMR Insight, 원논문 Sahlmueller 등 요약). California Management Review Insights (Berkeley). [링크](https://cmr.berkeley.edu/2022/09/two-in-the-lead-the-importance-of-relationships-when-there-are-two-bosses)

- 유형: survey · 비교: 단일 리더 대비 이중 보고(사업부 리더와 지역 리더), 두 관계 품질의 비대칭, 리더 간 관계 품질
- 주장: 독일 물류 다국적 기업에서 매트릭스로 두 리더에게 보고하는 현장 부서장 111명을 조사했다. 두 리더와의 관계 품질이 서로 다를수록 역할 갈등이 커지고 이중 리더십 팀 효과성 평가가 낮았다. 두 리더 간 관계가 좋으면 한쪽 리더와의 약한 관계의 해악이 상쇄되었다. 이중 리더십의 효과는 개별 리더 효과의 합이 아니었다. 해당 페이지에는 효과 크기나 통계값이 없다.
- 조건: 리더 간 관계 품질이 조절(완충) 변수다. 단일 기업, 단일 시점 자기보고 표본이라 일반화와 인과 해석에 한계가 있다. 원논문은 이 페이지에서 인용되지 않아 확인하지 못했다.
- 정정: CMR Insights 페이지(2022-09-12)와 저자 4인, 111명 표본, 주요 결과는 모두 일치한다. 다만 페이지는 원논문을 명시하지 않고 관련 글로 David Sally(2002)만 제시한다. 따라서 제목의 '원논문 Sahlmueller 등'이라는 표기는 페이지에서 확인되지 않으며, 원논문(동료심사 논문)은 별도로 확인해 인용해야 한다. 근거 수준은 2차 자료로 유지한다.
- 검증 출처: https://cmr.berkeley.edu/2022/09/two-in-the-lead-the-importance-of-relationships-when-there-are-two-bosses

### G3-02 · 확인 불가

McKinsey (저자 미확인) (미확인). Matrix organization / dual reporting: role clarity commentary (McKinsey Quarterly 'Revisiting the matrix organization'). McKinsey Quarterly. [링크](https://www.mckinsey.com/capabilities/people-and-organization/our-insights/revisiting-the-matrix-organization)

- 유형: review · 비교: 매트릭스 대 비매트릭스 조직의 역할 명확성
- 주장: 검색 요약에 따르면 McKinsey는 매트릭스 구조 직원이 비매트릭스 직원보다 기대 역할이 덜 명확하다고 느낀다고 보고한다. 검색 결과 요약만 보았고 원문 수치는 열어보지 못했다.
- 조건: 컨설팅사 조사이고 방법과 표본이 미확인이다. 동료 심사 문헌이 아니다.
- 정정: 페이지가 열리지 않아 존재 여부와 주장을 모두 확인하지 못했다. 저자와 연도가 미상이므로 확인 전에는 인용하지 않는 것이 좋다.
- 검증 출처: https://www.mckinsey.com/capabilities/people-and-organization/our-insights/revisiting-the-matrix-organization (WebFetch 시간 초과, 열람 실패)

### G3-03 · 확인

Arnold B. Bakker, Evangelia Demerouti (2007). The Job Demands-Resources model: state of the art. Journal of Managerial Psychology 22(3), 309-328. [링크](https://doi.org/10.1108/02683940710733115)

- 유형: review · 비교: 요구-통제 모형, 노력-보상 불균형 모형과의 비교 틀(JD-R이 더 넓은 변수 범위를 포괄한다는 주장)
- 주장: 모든 직무 조건을 요구(신체적, 심리적 비용을 수반하는 노력)와 자원(목표 달성을 돕고 요구의 비용을 줄이며 성장을 촉진)으로 분류한다. 이중 경로로, 만성 요구가 에너지를 소진시켜 탈진과 건강 문제를 낳고(건강손상 경로), 자원이 몰입과 성과를 높인다(동기부여 경로). 자원은 요구의 부정적 영향을 완충하며 요구가 높을 때 효과가 가장 크다. 웰빙이 이후의 요구와 자원을 바꾸는 상호 효과(손실 나선)도 있다. 저자들은 대부분 자기보고 연구라는 한계를 인정한다.
- 조건: 자원의 완충과 동기부여 효과는 요구가 높을 때 강하다. 상호 효과와 상호작용 효과는 검증이 덜 되어 있다고 저자 스스로 지적한다.
- 검증 출처: http://www.emerald.com/jmp/article/22/3/309-328/236386 (DOI 10.1108/02683940710733115 리다이렉트)

### G3-04 · 부분 확인

Karasek; Van der Doef & Maes (1979; 1999). Job Demands-Resources 모형 확장 및 요구-통제 모형 비교 (Karasek 1979; Van der Doef & Maes 1999 리뷰). Administrative Science Quarterly; Work & Stress (추정).

- 유형: theory · 비교: 요구 수준 x 통제(의사결정 재량) 수준
- 주장: 배경지식상 Karasek의 요구-통제 모형은 높은 요구와 낮은 통제(재량)의 조합이 가장 큰 긴장을 낳는다고 본다. 후속 리뷰는 주효과(요구 및 통제의 개별 효과)는 비교적 일관되나 요구와 통제의 상호작용 지지는 일관적이지 않다고 정리한 것으로 기억한다. 이번 세션에서는 원문을 열지 못했다.
- 조건: 원문 미확인이므로 조절 조건은 확인 전 인용 금지다.
- 정정: Van der Doef & Maes(1999, Work & Stress, DOI 10.1080/026783799296084)는 존재하며 제목은 'The Job Demand-Control(-Support) Model and psychological well-being: A review of 20 years of empirical research'이다. 이 리뷰는 요구-통제 모형(Karasek 1979)의 검토이지 'JD-R 모형 확장'이 아니므로 항목 제목은 부정확하다. 요구-통제 상호작용 지지가 비일관적이라는 내용은 일반적으로 알려진 바와 부합하지만 이번에 본문으로 확인하지 못했다. Karasek 1979(ASQ)는 직접 확인하지 못했다.
- 검증 출처: https://api.crossref.org/works?query.bibliographic=Van+der+Doef+Maes+Job+Demand-Control... (Crossref 메타데이터)

### G3-05 · 부분 확인

Alarcon, G. M. (2011). A meta-analysis of burnout with job demands, resources, and attitudes. Journal of Vocational Behavior (추정).

- 유형: meta-analysis · 비교: 번아웃 3차원(탈진, 냉소, 전문성 효능감) 대 직무 요구/자원/태도
- 주장: 배경지식상 역할 모호성, 역할 갈등, 업무 과부하 등 요구는 탈진과 냉소와 강하게 연관되고, 자원(통제, 사회적 지지)은 낮은 번아웃과 연관된다고 알려져 있다. 구체적 상관 계수는 원문을 확인하지 못해 적지 않는다.
- 조건: 차원별로 요구-탈진, 자원-효능감 관계가 다르다는 점이 핵심 조절 요소로 기억되나 미확인이다.
- 정정: Alarcon, G. M. (2011), J Vocational Behavior 79(2):549-562, DOI 10.1016/j.jvb.2011.03.007로 존재한다. 서지는 확인했으나 내용(역할 요구와 탈진·냉소, 자원과 번아웃의 관계)은 초록을 열지 못해 확인하지 못했다.
- 검증 출처: https://api.crossref.org/works/10.1016/j.jvb.2011.03.007

### G3-06 · 부분 확인

Gilboa, Shirom, Fried, Cooper (2008). Role stressors meta-analysis (Gilboa et al. 2008, Personnel Psychology). Personnel Psychology (추정).

- 유형: meta-analysis · 비교: 역할 갈등, 역할 모호성, 역할 과부하 대 성과, 긴장, 이직 의도
- 주장: 배경지식상 역할 모호성과 역할 갈등은 직무 성과와 부적 관계이며 역할 갈등이 긴장과 이직 의도에 더 강하게 연관된다고 기억한다. 구체적 수치는 확인하지 못해 적지 않는다.
- 조건: 미확인
- 정정: Gilboa, Shirom, Fried & Cooper (2008) Personnel Psychology 61(2):227-271, DOI 10.1111/j.1744-6570.2008.00113.x는 존재한다. 정확한 제목은 'A Meta-Analysis of Work Demand Stressors and Job Performance: Examining Main and Moderating Effects'이다. 항목의 'Role stressors meta-analysis'는 제목이 아니며, 대상은 역할 모호성, 역할 갈등, 역할 과부하, 업무 제약, 업무량 등이다. 구체적 결과는 확인하지 못했다.
- 검증 출처: https://api.crossref.org/works?query.bibliographic=Gilboa+Shirom+Fried+Cooper... (Crossref 메타데이터)

### G3-07 · 부분 확인

Wang, D.; Waldman, D. A.; Zhang, Z. (2014). Shared leadership and team performance meta-analysis (Wang, Waldman & Zhang 2014). Journal of Applied Psychology. [링크](https://doi.org/10.1037/a0034752)

- 유형: meta-analysis · 비교: 공유 리더십 대 수직 리더십
- 주장: 과제의 지시에도 이 논문을 인용해 공유 리더십이 팀 성과와 정적 관계이며 수직(단일) 리더십보다 설명력이 크다는 취지로 알려져 있다. 이번 세션은 PsycNet이 로딩되지 않아 초록과 수치를 열지 못했다. 효과 크기와 조절 변수(과업 복잡도, 팀 규모 등)는 확인 전 인용 금지다.
- 조건: 과업 복잡도, 팀 구성 등이 조절 변수로 거론되나 원문 확인이 필요하다.
- 정정: DOI가 잘못되었다. 10.1037/a0034752는 Steenbergen-Hu & Cooper(2014)의 지능형 튜터링 시스템 메타분석이다. 올바른 서지는 Wang, Waldman & Zhang (2014) 'A meta-analysis of shared leadership and team effectiveness', J Applied Psychology 99(2):181-198, DOI 10.1037/a0034531이다. 효과 크기와 조절 변수는 PsycNet이 로딩되지 않아 확인하지 못했다. '수직 리더십보다 설명력이 크다'는 서술도 확인되지 않았다.
- 검증 출처: https://api.crossref.org/works?query.bibliographic=Wang+Waldman+Zhang... (Crossref 메타데이터)

### G3-08 · 부분 확인

Greer, de Jong, Schouten, Dannals; Anderson & Brown (2018; 2010). Hierarchy and team effectiveness meta-analysis (Greer et al. 2018) 및 Anderson & Brown 2010. Journal of Applied Psychology; Research in Organizational Behavior. [링크](https://doi.org/10.1037/apl0000291)

- 유형: meta-analysis · 비교: 위계 높음 대 낮음, 위계 유형별
- 주장: 배경지식상 위계는 조정 이점이 있으나 갈등을 높일 수 있고, 과업 유형과 위계 유형(권한 격차, 지위 격차)에 따라 효과가 달라진다는 취지로 알려져 있다. 원문은 로딩되지 않아 수치를 확인하지 못했다.
- 조건: 과업 상호의존성과 위계 정당성 등이 조절 변수로 거론되나 미확인이다.
- 정정: Greer, de Jong, Schouten & Dannals (2018) 'Why and when hierarchy impacts team effectiveness: A meta-analytic integration', J Applied Psychology 103(6):591-613은 존재하며 DOI도 일치한다. 다만 Anderson & Brown(2010)은 같은 항목에 묶였고 이번에 확인하지 못했다. 이 논문은 Research in Organizational Behavior 30권에 실린 것으로 알려져 있으나 이번 조사에서 확인하지 못했다. 초록과 결과 내용도 열람하지 못했다.
- 검증 출처: https://api.crossref.org/works/10.1037/apl0000291

### G3-09 · 확인 불가

미확인(석사 학위논문) (미확인). Matrix organization role ambiguity thesis (University of Pretoria). University of Pretoria repository. [링크](https://repository.up.ac.za/bitstreams/2d808a07-3f70-4da6-b69f-4e72ab7eb45a/download)

- 유형: survey · 비교: 매트릭스 내 프로젝트 관리자 관계 강도, 정렬 수준
- 주장: 검색 요약에 따르면 프로젝트 관리자와의 관계가 강할수록 역할 모호성이 낮았고, 정렬(alignment)이 높을 때 모호성이 가장 낮았다. 원문을 열지 않았고 검색 요약에만 의존한다.
- 조건: 학위논문이며 표본과 방법이 미확인이다.
- 정정: 원문을 열지 못했고 검색 예산이 소진되어 대체 확인도 하지 못했다. 저자와 연도가 미상인 석사 학위논문이므로 인용하지 않는 것이 좋다.
- 검증 출처: https://repository.up.ac.za/bitstreams/2d808a07-3f70-4da6-b69f-4e72ab7eb45a/download (연결 오류 socket hang up)
