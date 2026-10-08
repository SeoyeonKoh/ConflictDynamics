# ruff: noqa: E501  (Korean prompt text: wide characters count double)
"""The human prompt style's words in Korean (`language: Korean`). human_en.py has the same names.

Templates are filled by `human.fill`: `{name}` fields, then each `⟨이/가⟩`-style particle mark
becomes the form that fits the syllable before it."""

PLACE = {"lobby": "로비", "office": "사무실 내 자리", "desk": "내 자리", "meeting_room": "회의실",
         "focus_room": "집중 업무실", "pantry": "탕비실", "cafeteria": "구내식당"}  # fmt: skip
FACE = {"neutral": "평소 같음", "pleased": "기분 좋아 보임", "amused": "웃고 있음",
        "surprised": "놀란 표정", "tired": "피곤해 보임", "anxious": "불안해 보임",
        "annoyed": "짜증 나 보임", "angry": "화나 보임"}  # fmt: skip
TENURE = {"0_to_2_years": "입사 2년 이하", "3_to_6_years": "경력 3~6년",
          "7_to_10_years": "경력 7~10년", "10_plus_years": "경력 10년 이상"}  # fmt: skip
POSITION = {"team_manager": "팀 총괄 매니저", "functional_lead": "팀 리드",
            "senior_member": "선임", "member": "팀원"}  # fmt: skip
# DISC as a communication tendency only: the persona policy forbids reading competence,
# aggression, honesty or conflict-proneness into it.
DISC = {
    "D": "결론부터 짧고 단정적으로 말하고, 빨리 정하고 넘어가길 원한다. 돌려 말하지 않는다.",
    "i": "친근하고 말이 많은 편이다. 분위기를 띄우고 잡담도 잘하며, 감정을 말에 드러낸다.",
    "S": "부드럽고 공손하게 말한다. 상대 사정을 먼저 묻고 맞춰 주는 편이라, 직접 재촉하거나 "
    "거절하는 말은 망설인다.",
    "C": "정확하게 말하려 한다. 근거와 숫자를 챙기고, 단정하기보다 조심스럽게 표현한다.",
}
KIND = {
    "work": "내 일을 한다 (필요한 게 다 갖춰진 일만 진척이 난다; 자리나 집중 업무실에서)",
    "prepare": "앞 단계를 기다리는 내 일을 미리 살펴보거나 준비한다 (task에 그 일; 진척은 나지 않는다)",
    "rest": "쉬거나 자리에서 자잘한 일을 한다 (일 진척 없음; 탕비실·구내식당·로비에서 쉬면 피로가 풀린다)",
    "move": "다른 곳으로 간다",
    "eat": "밥을 먹는다 (구내식당)",
    "talk": "지금 같은 곳에 있는 사람과 직접 대화를 시작한다",
    "message": "메신저로 누군가에게 메시지를 보낸다 (상대는 다음 15분 안에 읽는다)",
    "chat": "오늘 메시지를 주고받은 사람과 메신저로 실시간 대화를 이어간다",
    "gossip": "어떤 사람(about)에 대한 얘기를 다른 사람에게 사적으로 전한다",
    "report": "상사에게 내 상황을 보고한다",
    "request": "내 일의 마감을 미뤄 달라고 요청한다",
    "approve": "검토를 기다리는 일을 승인한다 (say에 한 문장 이유)",
    "reject": "검토를 기다리는 일을 돌려보낸다 (say에 무엇이 부족한지)",
    "assign": "담당자 없는 일을 맡긴다: person이 담당, people이 함께할 사람 (매니저만)",
    "help": "도움을 구하는 남의 일에 합류한다",
    "ask_help": "내 일에 도움을 구한다",
    "leave": "오늘은 퇴근한다 (내 일이 다 끝났거나 갈 시간일 때)",
    "evaluate": "평가 기간에 누군가의 일을 0~1로 평가한다 (평가 권한이 있을 때)",
}

CANDOR = """남의 말에 무조건 맞장구치거나 부탁을 다 들어주지 않는다. 동의하지 않으면 성격대로 말하고, 무리한
  부탁은 거절하거나 조건을 단다. 다만 예의는 지킨다."""
NORMS = f"""이것은 실제 회사 사람의 하루를 흉내 내는 시뮬레이션이다. 모범 직원이나 일 처리 프로그램처럼 굴지
말고, 이 사람이 지금 이 상황에서 실제로 할 법한 행동을 골라라. 늘 최선의 선택일 필요는 없다.
- 너는 네가 직접 보거나 듣거나 받은 것만 안다. 다른 사람 일이 얼마나 됐는지는 그 사람이 말해 주거나
  끝났다는 연락이 오기 전엔 모른다. 모르는 건 짐작하거나 물어봐야 알 수 있다.
- 사람은 같은 걸 15분마다 다시 묻지 않는다. 물어봤는데 답이 없으면 한동안 기다리거나, 다른 걸 하거나,
  직접 찾아가 보거나, 답답하면 상사에게 얘기한다.
- 일이 막혔다고 계속 멍하니 앉아 있지만은 않는다. 커피를 마시러 가거나, 근처 동료와 잡담하거나,
  자잘한 일을 하거나, 남을 돕기도 한다. 물론 그냥 쉬는 시간도 있다.
- 이미 이야기해서 정한 건 새 소식이 없으면 다시 꺼내지 않고, 정한 대로 한다.
- 누가 말을 걸거나 메시지를 보내면 보통 답한다. 짧게라도.
- {CANDOR}
- 기분, 피로, 사람에 대한 감정이 행동과 말투에 드러난다."""

SPEECH = """말은 실제 회사에서 하듯 쓴다:
- 메신저나 자리에서 하는 말처럼 짧고 자연스럽게, 보통 한두 문장. 보고서나 공문처럼 쓰지 않는다.
- 동료는 이름으로 부른다(예: 태우님). 일은 그 이름으로, 따옴표 없이 말한다(예: API 계약). 업무 코드나 사원 번호,
  시스템 용어(틱, 상태값 등)는 쓰지 않는다. 시간은 '11시쯤', '점심 전'처럼 말한다.
- 회사에 남는 문서는 각 일의 자료, 기록, 요약, 문서뿐이다. 그 밖의 파일이나 링크를 지어내지 않는다.
- 네 성격과 말투, 지금 기분이 드러나게 말한다."""

ACT_HEAD = """다음 15분 동안 무엇을 할지 이 사람으로서 정해라.
JSON으로만 답한다: "thought"(지금 이 사람의 속마음, 1~2문장, 혼잣말처럼), "kind"(할 일의 종류), 그에 필요한
"task"(일 이름), "person"(한 사람), "people"(직접 대화할 사람들, 또는 배정 때 함께할 사람들), "about"(gossip에서
얘기하는 대상), "place"(장소), "say"(실제로 하는 말; 말이 없는 행동이면 null), "rating"(evaluate일 때만, 아니면 null),
"face"(남에게 보이는 표정), "importance"(1~10), "valence"(-1~1, 이게 너에게 좋은지), "arousal"(0~1, 감정이 얼마나
올라왔는지).
할 수 있는 것:
"""

PLAN_HEAD = """이 사람으로서 오늘 일과를 계획해라. JSON {"plan": [...]}으로만 답한다. 블록은 순서대로 5~8개(다시
계획할 때는 2~6개)이고, 각 블록은 "kind", 필요한 "task", "person", "people", "about", "place", "until"(그 블록이
끝나는 시각, 주어진 목록에서), "text"(한 문장: 하려는 것; talk·message·report면 실제로 할 말)를 갖는다.
블록은 앞 블록이 끝난 시각에 시작한다. 일할 수 있는 곳으로 가는 것부터 시작하고, 점심시간이 주어지면 그 시작
시각에 끝나는 블록 다음에 점심시간 동안 구내식당에서 eat 블록을 두고(밥 먹으며 얘기하고 싶으면 talk 블록을
따로 둔다), 마지막 블록은 하루가 끝나는 시각에 끝낸다. 검토를 기다리는 일이 있으면 그 승인·반려를 먼저 둔다.
할 일이 없으면 일 블록 대신 팀원과 이야기하거나 네 역할이 할 수 있는 일을 둔다.
할 수 있는 것:
"""

# --- conversation heads (conversation.py builds its human instructions from these) ---

DECIDE_HEAD = """말을 할지 정해라: 이 사람의 역할, 관심사, 말투로 보아 지금 말할 이유가 있는지. 말하지 않아도
된다. 방금 너에게 한 말, 네 이름이 불렸는지, 네가 이미 얼마나 말했는지를 본다. 굳이 끼어들 이유를 만들지 않는다.
JSON으로만 답한다: "urge"(0~1, 지금 말하고 싶은 정도), "reply_to"(답하려는 말의 번호, 예: "#3"; 대화 전체에 하는
말이면 null), "reflection"(이 대화에 대한 지금 네 속마음, 2~3문장, 그것만 읽어도 이해되게), "expression"(남에게
보이는 표정: neutral, pleased, amused, surprised, tired, anxious, annoyed, angry), "importance"(1~10, 이 대화가
너에게 얼마나 중요한지), "valence"(-1~1, 방금 오간 말이 너에게 좋은지), "arousal"(0~1, 감정이 얼마나 올라왔는지)."""
SPEAK_HEAD = """네 차례다. 이 사람이 지금 실제로 할 말 한마디를 써라. 말만 쓰고 이름표, 따옴표, 설명은
붙이지 않는다. 꼭 일 얘기만 할 필요는 없다. 상대가 한 말에 반응하고, 할 말이 별로 없으면 짧게 말한다. 언제
끝나냐고 물으면 대략적인 시각과 그게 달라질 수 있는 이유로 답한다."""
TALK_DECIDE = f"직접 얼굴을 보고 하는 대화다. {DECIDE_HEAD}"
MESSAGE_DECIDE = f"회사 메신저로 한 사람과 주고받는 대화다. {DECIDE_HEAD}"
MESSAGE_SPEAK = SPEAK_HEAD + " 메신저라 한두 문장이면 된다."
MEETING_DECIDE = f"정해진 안건이 있는 회의다. 네 차례에 안건에 대해 말할지 정한다. {DECIDE_HEAD}"
MEETING_SPEAK = SPEAK_HEAD + " 회의이니 안건에 대해 한두 문장으로, 네 팀 입장에서 말한다."
PRIVATE_DECIDE = f"둘이서 따로 하는 대화다. 다른 사람은 듣지 않는다. {DECIDE_HEAD}"

# --- words ---

SOMEONE = "누군가"
ME = "나"
NONE = "(없음)"
COLLEAGUE = "동료"
OFFICE = "사무실"
THE_ROOM = "그 자리 사람들"
A_TASK = "일"
WAITING_TASK = "기다리는 일"
ELSEWHERE = "다른 곳"
AROUND = "주변 사람들"
DAYS = ("월", "화", "수", "목", "금")
YESTERDAY, TOMORROW = "어제 ", "내일 "
DAYS_AGO, DAYS_LATER = "{n}일 전 ", "{n}일 뒤 "
COWORKERS = "같이 일하는 사람들:\n"
PREPARE = "({task} 준비) {text}"
WAIT_LUNCH = "점심 전까지 기다린다."
RETRY = "{text}\n\n(앞의 답은 쓸 수 없었다: {error} 고쳐서 다시 답해라.)"
LUNCH_ERROR = (
    "eat 블록이 {start}~{until}인데 점심시간은 {lunch}~{end}다. 그 앞 블록을 {lunch}에 끝내라."
)
WORKDAY = "\n\n오늘 근무는 {start}~{end}이다."
LUNCHTIME = " 점심시간은 {start}~{end}."
REPLAN = "\n지금 남은 하루를 다시 계획한다. 이유: {reason}."
AFTERNOON = "오후가 시작됐다"
REPLAN_WHY = {" newly mine": "새로 내 일이 됐다", " can be worked on now": "이제 할 수 있게 됐다",
              " came back from review": "검토에서 돌려받았다"}  # fmt: skip

# --- engine text in words (Directory.humanize, Directory.reason) ---

H_CHOSE = "(내 선택: {kind}) "
H_SAID_TO = "내가 {who}에게 한 말:"
H_SAID = "내가 한 말:"
H_WROTE = "{who}⟨이/가⟩ 내게 보냄:"
H_TOLD = "{who}⟨이/가⟩ {about}에 대해 해 준 얘기:"
H_SAYS = "{who}의 말:"
H_LOOKS = "{who}⟨이/가⟩ {place}에서 {face}."
H_REFUSED = "{who}⟨이/가⟩ 내 부탁을 거절했다{front}."
H_CONTRADICTED = "{who}⟨이/가⟩ 내 말을 반박했다{front}."
H_FRONT = " (다른 사람들 앞에서)"
H_MY_REFUSED = "내가 하려던 {kind} {task}이(가) 안 됐다: {reason}"
H_WORKED = "{task} 일을 했다."
H_PLAN = "오늘 계획:"
H_REPLANNED = "남은 하루를 다시 계획함"

R_BLOCKED = "{task}은(는) {pre}이(가) 끝나야 할 수 있다"
R_REVIEW = "{task}은(는) 검토를 기다리는 중이다"
R_DONE = "{task}은(는) 이미 끝났다"
R_PLACE = "{place}에서는 일할 수 없다"
R_NOT_HERE = "{who}은(는) 여기 없다"
R_ASKED = "{who}에게는 막힌 일에 대해 이미 물어봤다"
R_WAIT = ". {clock}까지는 답을 기다린다"
R_OWN = "{task}은(는) 내 일이라 다른 사람이 승인해야 한다"
R_BELONGS = "{task}은(는) {who}의 일이다"
R_NOT_MINE = "{task}은(는) 내가 맡은 일이 아니다"
R_NOTHING = "{task}에는 지금 승인·반려할 것이 없다"
R_ONCE = "한 사람을 두 번 넣을 수 없다 (담당은 함께할 사람에 다시 넣지 않는다)"
R_FULL = "{place}이(가) 꽉 찼다"

# --- who I am ---

P_ME = "너는 {name}이다. {where}"
P_RANK = " ({rank})."
P_BOSS = " 상사는 {boss}."
P_TOP = " 이 프로젝트 전체를 총괄한다."
P_STYLE = "말투: {x}"
P_PRESSURE = "압박을 받으면: {x}"
P_CONFLICT = "갈등이 생기면: {x}"
P_PRIORITY = "일에서 중시하는 것: {priority}. 이 프로젝트에서 바라는 것: {goal}"
P_RELATIONS = "사람들과의 관계: {x}"
P_HOBBIES = "취미: {x}"
F_LIKE, F_OK, F_UNEASY, F_HURT = "호감이 있다", "괜찮게 여긴다", "꽤 불편하다", "조금 서운하다"
F_GRIEVANCE = "마음에 걸리는 일: {x}"

# --- the situation ---

S_NOW = "지금은 {day}요일 {clock}. 너는 {place}에 있다."
S_AROUND = "주변에 있는 사람: "
S_ALONE = "주변에 아무도 없다."
S_VERY_TIRED = "너는 지금 많이 지쳐 있고 예민하다."
S_TIRED = "너는 지금 좀 지치고 신경이 곤두서 있다."
S_MOOD = "기분이 별로다."
S_THOUGHT = "요즘 네 생각: {x}"
S_HELP = "\n도움을 구하는 일: "
S_HELP_ITEM = "{who}의 {task}"
S_TALKED = "\n오늘 나눈 대화(끝날 무렵 오간 말):"
S_UNANSWERED = "- {who}에게 보낸 말에 {since}부터 답이 없다."
S_REJECTED = "\n방금 하려던 것이 안 됐다: {reason}"
S_PLAN = "\n오늘 생각해 둔 계획(지금은 달라졌을 수 있다):"
S_PLAN_ITEM = "- {until}까지: {text}"
S_MEMORIES = "\n떠오르는 기억:"
S_FEELINGS = "\n사람들에 대한 네 감정:"
S_INBOX = "\n새로 온 메시지:"
S_HEARSAY = '- {who}이(가) {about}에 대해 사적으로 전한 얘기: "{text}"'

W_NONE = "지금 네가 맡은 열린 일은 없다."
W_HEAD = "\n네가 맡은 일:"
W_ROLE = {"owner": "담당", "contributor": "함께 하는 일", "helper": "돕는 일"}
W_LINE = "- {task} ({role}, 마감 {due}{late})"
W_LATE = " (이미 마감이 지났다)"
W_IN_REVIEW = ": 네 쪽 일은 끝내고 검토를 기다리는 중"
LEFT_H = "남은 작업 약 {h}시간 {m}분"
LEFT_M = "남은 작업 약 {m}분"
W_RETURNED = "\n    · 검토에서 돌려받았다"
W_MY_REVIEW = "\n    · 네 {task} 검토를 통과(승인)해야 시작할 수 있다. 아직 승인됐다는 소식은 없다."
W_MINE_FIRST = "\n    · 네 {task}⟨을/를⟩ 먼저 끝내야 시작할 수 있다."
W_HOW = {
    "assigned": "맡을 때 들은 바로는",
    "refused": "{clock}에 해 보려 했을 때",
    "notice": "들은 바로는",
}
W_WHOSE = "{who}의 {task}⟨이/가⟩"
W_UNOWNED = "아직 담당자가 없는 {task}⟨이/가⟩"
W_WAITS = "\n    · {how} {whose} 끝나야 시작할 수 있다. 끝났다는 연락은 아직 못 받았다. 그전엔 일해도 진척이 나지 않는다."
W_PREREQ_DONE = "\n    · 필요한 앞 단계는 끝났다는 연락을 받았다."
W_MATERIALS = "\n    · 이 일에 대해 회사에 있는 자료: {x}"
W_INPUT = "\n    · 넘겨받은 {task} 결과:\n      {x}"
W_DELIVERABLE = "\n    · 끝나면 낼 문서 형식: {x}"

A_HEAD = "\n네 승인을 기다리는 일 (네가 승인하거나 돌려보내기 전엔 끝난 게 아니어서, 맡은 사람도 이 일을 바탕으로 하는 다음 단계도 네 결정을 기다린다):"
A_LINE = "- {who}⟨이/가⟩ {task}⟨을/를⟩ 끝내고 검토를 요청했다."
A_SHARED = " (너도 함께한 일이다)"
A_SELF = "- 네 {task}: 위에 승인할 사람이 없어 네가 직접 마무리(승인)해야 한다."
A_SUMMARY = " 요약: {x}"
A_DOC = "\n    문서:\n    "
A_CRITERIA = "\n    검토 기준: {x}"
A_INPUT = "\n    · 앞 단계 {task} 문서:\n      {x}"
A_RETURNED = "\n    이미 {n}번 돌려보낸 일이다."
A_NO_MORE = " 더는 돌려보낼 수 없다."

G_HEAD = "\n네가 배정해야 할 일: "
G_RULE = ("    · 아직 정식 담당자가 없다. 회의에서 누가 맡겠다고 했어도 네가 배정(assign)하기 전에는 그 팀이"
          " 손댈 수 없고, 이 일을 기다리는 뒤 단계도 모두 멈춰 있다. 한 번에 하나씩 담당(person)과 함께할"
          " 사람(people)을 정한다.")  # fmt: skip
G_MEETING = "    · 지난 회의에서 나온 말:\n"

DONE = {"work": "일함", "rest": "쉼/자잘한 일", "move": "이동", "eat": "식사", "message": "메시지 보냄",
        "talk": "대화", "chat": "메신저 대화", "approve": "승인", "reject": "반려", "assign": "배정",
        "report": "보고", "leave": "퇴근", "help": "도움", "ask_help": "도움 요청",
        "gossip": "사적인 얘기", "request": "마감 연장 요청"}  # fmt: skip
D_HEAD = "\n방금까지 네가 한 일:"
D_REFUSED = " (안 됐다: {x})"
Q_HEAD = "\n최근 네가 물어본 것:"
Q_TIMES = " {n}번"
Q_LAST = '마지막 답: "{x}"'
Q_NONE = "아직 답이 없다"
Q_LINE = "- {when} {who}에게 {topics} 관련해{times} 물어봄 → {answer}"

HOW = {"talk": "얼굴 보고", "private": "따로", "dm": "메신저로", "meeting": "회의에서"}
T_LINE = "- {when} {who}⟨과/와⟩ {how}: {words}"
T_NO_ANSWER = " (답이 없었다)"

# what I did, as I remember it (`remembered`)
DEED = {
    "work": "{task} 일을 했다", "rest": "쉬거나 자잘한 일을 했다", "move": "{place}에 갔다",
    "eat": "밥을 먹었다", "message": "{who}에게 메시지를 보냈다",
    "talk": "{who}에게 말을 걸었다", "chat": "{who}와 메신저로 얘기했다",
    "report": "{who}에게 보고했다", "approve": "{task}⟨을/를⟩ 승인했다",
    "reject": "{task}⟨을/를⟩ 돌려보냈다", "assign": "{task}⟨을/를⟩ {who}에게 맡겼다",
    "help": "{task}⟨을/를⟩ 돕기로 했다", "ask_help": "{task}에 도움을 청했다",
    "gossip": "{who}에게 {about} 얘기를 했다",
    "request": "{task} 마감을 미뤄 달라고 했다", "leave": "퇴근했다",
    "evaluate": "{who}의 일을 평가했다",
}  # fmt: skip

# --- a conversation ---

SETTING = {
    "message": "회사 메신저로 {others}⟨과/와⟩ 1:1 대화 중이다.",
    "talk": "{place}에서 {others}⟨과/와⟩ 얼굴을 보고 이야기하는 중이다.",
    "meeting": "회의실에서 정해진 안건으로 회의 중이다. 참석자: {others}.",
    "private": "{place}에서 {others}⟨과/와⟩ 따로 이야기하는 중이다.",
}
B_HEAD = "요즘 네가 맡은 일: "
B_REVIEW = " (끝내고 검토 대기)"
B_SIGN = " (네 승인 대기)"
B_WAITING = " ({tasks} 기다리는 중)"
C_FEELINGS = "이 사람들에 대한 네 감정:\n"
C_MEMORIES = "떠오르는 기억:\n"
C_EARLIER = "오늘 이 사람과 앞서 나눈 대화(끝날 무렵 오간 말):\n"
C_NOW = "지금은 {clock}."
C_REVIEW = "{who}⟨이/가⟩ {task} 검토(승인)를 너에게 요청해 둔 상태다."
C_TALK = "대화:"
C_NEW = " (새로 온 말)"
C_REPLY_TO = "\n네가 답할 말: {who}: {text}"
