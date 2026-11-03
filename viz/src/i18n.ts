// Fixed UI words in Korean and English. What agents wrote (talk, documents, names) is never
// translated. `data-i18n="key"` on an element takes its text from here at boot.
import { getLang } from './prefs';

const words = {
  ko: {
    title: 'Conflict Dynamics', kicker: 'LLM 에이전트 사무실 시뮬레이션',
    tagline: '사람처럼 일하고, 쉬고, 부딪히는 회사를 관찰하세요.',
    live: '라이브 실행', liveDesc: '시나리오를 고르고 새 시뮬레이션을 시작해 실시간으로 봅니다.',
    replay: '리플레이', replayDesc: '지난 run을 골라 처음부터 다시 보고, 장면을 멈춰 살펴봅니다.',
    create: '시나리오 생성', createDesc: '회사와 업무를 설명하면 에이전트가 시나리오 초안을 만들어 줍니다.',
    createFlow: '설명 → YAML 초안 → 자동 검사 → 수정', soon: '준비 중', settings: '환경 설정',
    runningN: '진행 중 {n}개', dayClock: '{day}일차 {clock}', savedRuns: '저장된 run {n}개',
    lastOn: '마지막 {date}', noRuns: '아직 run이 없어요',
    screen: '화면', uiLang: 'UI 언어', theme: '테마', light: '라이트', dark: '다크', system: '시스템',
    provider: 'AI Provider', realApi: '실제 API', demoDesc: '무료 · 규칙 응답', localDesc: 'OpenAI 호환',
    local: '로컬', apiKey: 'API 키', keyFromEnv: '서버 .env에서 읽음', noKey: '서버 .env에 키가 없어요',
    modelDecide: '판단 모델', modelSpeak: '대화 모델', modelEmbed: '임베딩 모델',
    defaultCap: '기본 토큰 상한', cap: '토큰 상한', capped: '상한', unlimited: '무제한',
    costNote: '실제 API 실행은 비용이 들어요. 라이브 실행을 시작할 때 예상 사용량을 한 번 더 보여줘요.',
    demoNote: 'Demo는 API를 부르지 않고 규칙대로 응답해요. 화면과 규칙 확인용이에요.',
    cancel: '취소', save: '저장', back: '뒤로', close: '닫기',
    pickRun: '리플레이할 run 고르기', searchRuns: 'run 이름·시나리오 검색', all: '전체',
    colRun: 'RUN', colState: '상태', colLength: '길이', colModel: '모델', colTokens: '토큰', colDate: '날짜',
    done: '완료', paused: '중단', running: '진행 중', failed: '실패', lengthDays: '{days}일 · {ticks}틱',
    pickHint: 'run을 선택하세요', picked: '선택: {run}', openReplay: '▶ 리플레이 열기', resumeRun: '이어서 실행',
    resumeOld: '하루 끝 저장 지점에서 이어 가며, 일부 상태가 원래 run과 다를 수 있어요.',
    scenario: '시나리오', searchScenario: '시나리오 이름 검색', noScenario: '일치하는 시나리오가 없어요.',
    runSetup: '실행 설정', days: '일수', dayN: '{n}일', scenarioDefault: '시나리오 기본값: {n}일',
    capHint: '상한에 닿으면 그 자리에서 멈추고, 나중에 이어서 돌릴 수 있어요.',
    unlimitedHint: '무제한이면 run이 끝날 때까지 토큰을 계속 써요. 실행 시작 전에 한 번 더 확인해요.',
    estimate: '예상 사용량 약 {tokens} 토큰 · 호출 약 {calls}회', estimateCalls: '예상 호출 약 {calls}회',
    providerLine: 'Provider: {p}', changeInSettings: '환경 설정에서 변경', startRun: '▶ 실행 시작',
    confirmTitle: '실제 API로 실행할까요?', confirmBody: '{estimate}. 상한: {cap}.',
    confirmUnlimited: '토큰 상한이 없어요. run이 끝날 때까지 비용이 계속 들어요.', confirmGo: '실행',
    menu: '← 메인', stop: '정지', stopConfirm: '이 run을 정지할까요? 나중에 리플레이 목록에서 이어서 실행할 수 있어요.',
    replaying: '기록 재생 중 · {tick} / {cut}',
    tasks: '업무', relations: '관계', events: '이벤트', conversations: '대화', pause: '일시정지', resume: '재개',
    step: '한 틱', speed: '속도', liveBadge: '● 라이브', waiting: '첫 틱을 기다리는 중',
    relationships: '관계', reflection: '회고', asOf: '틱 {tick} 기준 · 기억 {n}개 검색', noneYet: '아직 없음',
    convHint: '대화를 고르면 처음부터 끝까지 보여요', thoughtsAll: '속마음 모두 펼치기', thought: '💭 속마음',
    meetingNoThought: '회의 발언은 속마음 기록이 없어요', talk: '대화', meeting: '회의', message: '메시지',
    lines: '{n}마디', noConversations: '아직 대화가 없어요',
    interview: '💬 인터뷰', interviewWhen: '{clock}까지의 기억으로 답해요',
    interviewNote: '인터뷰는 run에 영향을 주지 않아요 · run 폴더에 저장돼요',
    interviewCost: '질문 1번에 LLM 1회 + 임베딩 1회 · {model}', interviewNew: '새 인터뷰',
    interviewAsk: '{name}에게 물어볼 내용', send: '보내기', interviewStale: '이 인터뷰 뒤로 run이 다시 만들어졌어요',
    interviewNoRun: '서버가 띄운 run이나 리플레이에서만 인터뷰할 수 있어요', questionsN: '질문 {n}개',
    stress: '스트레스', mood: '기분',
  },
  en: {
    title: 'Conflict Dynamics', kicker: 'LLM agent office simulation',
    tagline: 'Watch a company that works, rests and clashes like people do.',
    live: 'Live run', liveDesc: 'Pick a scenario, start a new simulation and watch it as it runs.',
    replay: 'Replay', replayDesc: 'Pick a past run, play it from the start and pause on any moment.',
    create: 'Create scenario', createDesc: 'Describe a company and its work; an agent drafts the scenario.',
    createFlow: 'Description → YAML draft → checks → edits', soon: 'Coming soon', settings: 'Settings',
    runningN: '{n} running', dayClock: 'day {day} {clock}', savedRuns: '{n} saved runs',
    lastOn: 'last {date}', noRuns: 'No runs yet',
    screen: 'Display', uiLang: 'Language', theme: 'Theme', light: 'Light', dark: 'Dark', system: 'System',
    provider: 'AI provider', realApi: 'Real API', demoDesc: 'Free · scripted replies', localDesc: 'OpenAI compatible',
    local: 'Local', apiKey: 'API key', keyFromEnv: "Read from the server's .env", noKey: "No key in the server's .env",
    modelDecide: 'Judgement model', modelSpeak: 'Speech model', modelEmbed: 'Embedding model',
    defaultCap: 'Default token cap', cap: 'Token cap', capped: 'Cap', unlimited: 'Unlimited',
    costNote: 'Real API runs cost money. Starting a live run shows the expected use once more.',
    demoNote: 'Demo calls no API and answers by rule. It is for checking the screens and the rules.',
    cancel: 'Cancel', save: 'Save', back: 'Back', close: 'Close',
    pickRun: 'Pick a run to replay', searchRuns: 'Search run or scenario', all: 'All',
    colRun: 'RUN', colState: 'State', colLength: 'Length', colModel: 'Model', colTokens: 'Tokens', colDate: 'Date',
    done: 'Done', paused: 'Stopped', running: 'Running', failed: 'Failed', lengthDays: '{days} d · {ticks} ticks',
    pickHint: 'Pick a run', picked: 'Picked: {run}', openReplay: '▶ Open replay', resumeRun: 'Resume',
    resumeOld: 'Resumes from the last day-end save; some state may differ from the original run.',
    scenario: 'Scenario', searchScenario: 'Search scenario names', noScenario: 'No scenario matches.',
    runSetup: 'Run settings', days: 'Days', dayN: '{n} d', scenarioDefault: 'Scenario default: {n} d',
    capHint: 'At the cap the run stops where it is; you can resume it later.',
    unlimitedHint: 'Unlimited keeps spending tokens until the run ends. You confirm before it starts.',
    estimate: 'Expected about {tokens} tokens · about {calls} calls', estimateCalls: 'About {calls} calls expected',
    providerLine: 'Provider: {p}', changeInSettings: 'Change in settings', startRun: '▶ Start run',
    confirmTitle: 'Run on the real API?', confirmBody: '{estimate}. Cap: {cap}.',
    confirmUnlimited: 'There is no token cap. The run keeps costing until it ends.', confirmGo: 'Run',
    menu: '← Menu', stop: 'Stop', stopConfirm: 'Stop this run? You can resume it later from the replay list.',
    replaying: 'Replaying the record · {tick} / {cut}',
    tasks: 'Tasks', relations: 'Relations', events: 'Events', conversations: 'Talk', pause: 'Pause', resume: 'Resume',
    step: 'Step', speed: 'speed', liveBadge: '● Live', waiting: 'waiting for first tick',
    relationships: 'Relationships', reflection: 'Reflection', asOf: 'as of tick {tick} · {n} memories retrieved',
    noneYet: 'none yet', convHint: 'Pick a conversation to read it whole', thoughtsAll: 'Open all thoughts',
    thought: '💭 Thought', meetingNoThought: 'Meeting turns record no thought', talk: 'Talk', meeting: 'Meeting',
    message: 'Message', lines: '{n} lines', noConversations: 'No conversations yet',
    interview: '💬 Interview', interviewWhen: 'Answers from memories up to {clock}',
    interviewNote: 'Interviews do not change the run · saved in the run folder',
    interviewCost: '1 LLM call + 1 embedding per question · {model}', interviewNew: 'New interview',
    interviewAsk: 'Ask {name} something', send: 'Send', interviewStale: 'The run was rebuilt after this interview',
    interviewNoRun: 'Interviews need a replay or a run the server started', questionsN: '{n} questions',
    stress: 'stress', mood: 'mood',
  },
} as const;

export type Key = keyof typeof words.ko;

export function t(key: Key, vars: Record<string, string | number> = {}): string {
  return words[getLang()][key].replace(/\{(\w+)\}/g, (_, name) => String(vars[name] ?? ''));
}

export function translate(root: ParentNode = document) {
  root.querySelectorAll<HTMLElement>('[data-i18n]').forEach(el => {
    el.textContent = t(el.dataset.i18n as Key);
  });
  root.querySelectorAll<HTMLElement>('[data-i18n-placeholder]').forEach(el => {
    el.setAttribute('placeholder', t(el.dataset.i18nPlaceholder as Key));
  });
  document.documentElement.lang = getLang();
}
