# Simulator Core Implementation Plan

**Goal:** 설계 문서 9절의 1~2단계를 실행 가능한 Python 패키지로 구현한다.

**Architecture:** dataclass 모델, 순차 틱 루프, 단일 LLM 인터페이스를 사용한다.
생성과 측정을 분리하며, 설정과 결정 기록을 ConvoKit corpus 옆에 저장한다.

**Tech Stack:** Python 3.11+, uv, PyYAML, 선택적 OpenAI SDK, pytest.

**Spec:** ../../conflict-sim-design.md

## 범위와 결정

- 참여자 3~6명, 기본 max_ticks=12, silence_limit=2.
- 예제는 영어 합성 시드이며 실제 CGA 데이터로 표시하지 않는다.
- `last_seen`은 틱이 아닌 읽은 발화 수다. 초기 시드와 같은 틱의 새 발화를 놓치지 않는다.
- round_robin은 고정 순서 평가, random은 틱마다 셔플한다. 둘 다 확률적 침묵을 허용한다.
- bidding은 동일한 대화 상태에서 urge를 비교하고, 최고 입찰자 한 명만 확률 게이트를 거친다.
  동점은 seeded RNG로 선택하며 availability=0인 에이전트는 입찰에서 제외한다.
- event_driven은 새 답글이나 정확한 @호명에 반응한다. 첫 틱에는 모두 시드를 읽는다.
- 같은 틱에 여러 게시물이 가능하다. bidding만 최대 한 개로 제한한다.
- reply_to=null은 기존 루트에 대한 답글로 정규화해 단일 트리를 유지한다.
- max_ticks는 발화 수 상한이 아니다. 종료 틱과 실제 생성 발화 수를 별도로 기록한다.
- 오류는 침묵으로 바꾸지 않는다. 잘못된 결정/답글/API 오류는 실행 실패다.
- CRAFT, CGA 추출, 반복 ablation 실험은 이번 단계에 포함하지 않는다.

## 구현 및 검증

- [x] 모델·엔진: `models.py`, `engine.py`, `config.py`를 구현한다.
  먼저 seed tick=0 읽기, 같은 틱의 뒤늦은 답글, 침묵 종료, bidding의 승자/동점,
  event_driven의 호명, random 재현성, 잘못된 트리 거부를 테스트로 고정한다.
  `uv run pytest tests/test_engine.py tests/test_models.py`로 확인한다.
- [x] 에이전트·LLM: `agent.py`, `llm.py`를 구현한다.
  JSON urge 범위, reply_to 존재 여부, 생성 모델 분리, 실패 시 중단을 테스트한다.
  외부 HTTP 경계에서 응답을 대체하고 내부 파싱과 프롬프트는 실제 코드를 실행한다.
  `uv run pytest tests/test_agent.py tests/test_llm.py`로 확인한다.
- [x] CLI·저장: `cli.py`, `storage.py`, `config.yaml`, 합성 시드와 README를 작성한다.
  config 상대 경로, 참여자 검증, 데모 실행, 로그 재로딩, 출력 덮어쓰기 방지를 확인한다.
  `uv run conflict-sim --config config.yaml --output runs/demo`를 실행한다.
- [x] 전체 pytest, Ruff, wheel 빌드를 확인하고 실제 API/CRAFT 미검증 범위를 명시한다.

작업은 현재 세션에서 순서대로 수행하며, 유료 API 요청은 검증에 사용하지 않는다.

## 검증 결과

- pytest 65개 통과. 네 가지 규칙의 실제 CLI 실행을 포함한다.
- Ruff lint 및 format 확인, sdist/wheel 빌드, 별도 환경 wheel CLI 실행을 확인했다.
- 코드 검토에서 발견한 작은 context_size의 미열람 본문 누락은 재현 테스트 후 수정했다.
- 예제 난수 시드는 생성 흐름 확인을 위해 42로 설정했다. `runs/demo-example`은
  발화 2개를 생성하고 4틱 후 침묵 종료한 합성 데모다.
- 실제 유료 LLM 요청, ConvoKit 런타임 로딩, CRAFT/CGA 검증은 수행하지 않았다.
