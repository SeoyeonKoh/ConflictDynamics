# 실제 구독 확인 (Task 9)

2026-11-11 · 브랜치 `feat/claude-subscription-route` · `claude-agent-sdk` 0.2.180, CLI 2.1.321 · `claude-haiku-5-5` · 로컬 임베딩
Claude Code 세션의 환경 변수(`CLAUDE*`)를 지운 셸에서 돌렸다(일반 터미널과 같은 조건).

| 확인 | 결과 |
|---|---|
| 셸에 가짜 `ANTHROPIC_API_KEY`를 둔 채 Claude 실행 | 돈다. 매니페스트 `llm.auth: "subscription"`, 키 오류 없음 |
| `r10_documents_ko` 하루, 상한 100만 토큰 | 틱 8에서 `paused`("Run token budget reached"). 판단 57회 + 발언 6회, 98.8만 + 2.1만 토큰, 임베딩 43회(로컬), 3분 48초 |
| 같은 실행 이어서, 상한 100만 | 테이프로 틱 8까지 재생 뒤 틱 13까지 진행하고 다시 `paused`. 프레임 13개, 중복 0, 세그먼트 2개, 3분 23초 |
| 매니페스트 `llm` | `provider claude, embed_backend local, embed_model paraphrase-multilingual-MiniLM-L12-v2, temperature_sent false, injected_context true, sdk_version 0.2.180, cli_version 2.1.321, auth subscription` |
| `~/.claude/projects`에 세션 기록 | 0개 (`--no-session-persistence`) |
| 서버(워크트리, 포트 8791)로 인터뷰 질문 1개 | 200, 5.8초, 그 시점의 업무를 근거로 답함. 답에 마크다운(굵게 · 목록)이 섞인다 |
| 서버로 생성기 메시지 1개 | 200, 3.4초, 실험 정보를 되묻는 답 |
| 설정 화면 "확인" 버튼 | 실제 호출 1회로 "구독 로그인 확인됨" |

하루를 끝까지 돌리지는 않았다(약 600만 토큰을 쓰므로). 끝까지의 동작(하루 끝 체크포인트, corpus 작성)은
데모 백엔드 테스트가 같은 코드 경로로 다룬다.
