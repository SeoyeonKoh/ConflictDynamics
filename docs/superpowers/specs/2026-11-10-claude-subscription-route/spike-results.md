# Claude Agent SDK 스파이크 결과

2026-11-11 · `claude-agent-sdk` 0.2.180 (번들 CLI 2.1.321) · macOS · 구독 로그인(`claude auth status`: `authMethod: claude.ai`) · 모델 `claude-haiku-5-5`
스크립트는 저장소 밖 임시 폴더에서 돌렸고 커밋하지 않았다. 호출은 약 60회.

| # | 질문 | 답 | 계획에 반영 |
|---|---|---|---|
| S1 | 구독으로 도는가, 인증 종류를 읽을 수 있는가 | 돈다. 첫 `SystemMessage(subtype="init")`의 `data["apiKeySource"]`가 구독일 때 `"none"`, 키일 때 `"ANTHROPIC_API_KEY"` | 그대로 |
| S2 | API 키를 CLI가 못 보게 | `options.env`에 `{"ANTHROPIC_API_KEY": ""}`를 주면 부모 환경에 키가 있어도 `apiKeySource: "none"`. 반대로 `env`로 키를 주면 CLI가 그 키를 쓴다(잘못된 키 → `ResultMessage(subtype="success", is_error=True, result="Invalid API key …")` 뒤 `ResultError`) | **바뀜**: `os.environ`을 지우지 않고 `env` 덮어쓰기로 막는다 |
| S3 | `tools=[]`로 도구가 꺼지는가 | 꺼진다(init `tools` 0개) | 그대로 |
| S4 | 속도 | 짧은 텍스트 호출 2~5초(대부분 프로세스 기동). 4.3k자 프롬프트 + 스키마: 호출당 3.4~5.1초. 동시 4개로 8회 9.4초, 동시 10개로 20회 10.2초 → 완성 1,500회면 동시 4개 약 30분, 10개 약 13분 | 기본 동시 4 유지 |
| S5 | 구조화 출력 | `strict_schema` 형태의 스키마는 통한다(2턴). `{"type": "object"}`만 주면 **빈 객체 `{}`**가 온다. 스키마 없이 "JSON 객체 하나만" 지시한 텍스트 응답은 1턴에 올바른 JSON | **바뀜**: `json_mode`만 있는 호출은 `output_format` 없이 텍스트를 받아 파싱 |
| S6 | 출력 상한 | 옵션은 없고 환경 변수 `CLAUDE_CODE_MAX_OUTPUT_TOKENS`가 듣는다. 넘으면 `is_error=True`, "exceeded the N output token maximum". 상한에 추론 토큰이 포함된다 | 호출별 상한은 걸지 않는다(OpenAI용 512/384가 추론 토큰 때문에 정상 호출을 끊는다) |
| S7 | 한도 이벤트 | 스트림 중간에 `RateLimitEvent(rate_limit_info=RateLimitInfo(status, rate_limit_type, resets_at, utilization, …))`가 온다(호출마다 `allowed`, `five_hour`, `resets_at`은 유닉스 초). `rejected`는 재현하지 않았다 | 필드 이름 확정 |
| S8 | 동시 실행 | 10개까지 20회 모두 성공. CLI 프로세스 하나에 약 260~310MB(10개 3.1GB) | 기본 4 유지 |
| S9 | 추론 끄기 | `thinking={"type": "disabled"}`는 텍스트 호출에서는 추론 0, **구조화 출력 호출에서는 무시**된다(추론 250~340토큰). `effort="low"`를 함께 주면 77~280 | **바뀜**: `reasoning_effort: none` → `thinking disabled` + `effort="low"` |
| S10 | 큰 입력 | 158k자 프롬프트 2.3초, 96k자 시스템 프롬프트 파일(`{"type": "file", "path"}`) 정상 | 그대로 |

## 문서에 없던 것

1. **CLI가 컨텍스트를 덧붙인다.** 시스템 프롬프트를 문자열로 바꾸고 `setting_sources=[]`, 도구 없음이어도 첫 메시지에 다음이 붙는다: 계정 정보(이메일), 환경 블록(작업 폴더 · 플랫폼 · OS), 다운로드 파일 주의문, 모델 이름, **오늘 날짜**, 남은 토큰 수. 약 500토큰. 끄는 플래그는 찾지 못했다(`--bare`는 구독 로그인을 읽지 않는다). 작업 폴더는 빈 임시 폴더라 저장소 경로는 드러나지 않는다.
2. **사용자 플러그인 · 스킬이 로드된다.** `setting_sources=[]`여도 init에 플러그인 4~5개, 스킬 17개가 보인다. `extra_args`에 `--restricted --disable-slash-commands --strict-mcp-config --no-session-persistence`를 주면 스킬 0개, 모델이 보는 컨텍스트에 훅 · 스킬 문구가 없다(플러그인 목록은 남는다).
3. **세션 기록이 쌓인다.** 기본으로 호출마다 `~/.claude/projects/`에 세션이 저장된다. 실행 하나에 1,500개. `--no-session-persistence`로 막는다.
4. **호출당 토큰이 크다.** 위 4.3k자 스키마 호출의 `model_usage` 합(입력 + 출력 + 캐시 읽기 · 쓰기)이 약 11k. CLI가 붙이는 컨텍스트와 구조화 출력의 두 번째 턴 때문이다. 완성 1,500회면 약 1,600만 토큰으로, 서버 기본 상한 200만이면 약 180회에서 멈춘다.
5. `ResultMessage.usage`와 `model_usage`가 다르다. 텍스트 호출 하나에 `usage` 입력 2 + 캐시 676, `model_usage` 입력 1,179. `model_usage`가 CLI가 보낸 요청 전부를 센다.
6. 스트림을 끝까지 읽지 않고 빠져나오면 `RuntimeError: aclose(): asynchronous generator is already running`. 결과 메시지를 받아도 스트림 끝까지 읽어야 한다.
7. 오류가 두 번 온다: `is_error=True`인 `ResultMessage` 뒤에 `ResultError`(`ProcessError` 하위) 예외.
