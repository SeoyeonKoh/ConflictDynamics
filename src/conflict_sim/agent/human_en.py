# ruff: noqa: E501  (prompt text)
"""The human prompt style's words in English: for `language: English`, and for any language with
no word module of its own (human.py then asks for speech in that language). human_ko.py has the
same names.

Templates are filled by `human.fill` (`{name}` fields)."""

PLACE = {"lobby": "the lobby", "office": "the office", "desk": "your desk",
         "meeting_room": "the meeting room", "focus_room": "the focus room",
         "pantry": "the pantry", "cafeteria": "the cafeteria"}  # fmt: skip
FACE = {"neutral": "as usual", "pleased": "pleased", "amused": "amused", "surprised": "surprised",
        "tired": "tired", "anxious": "anxious", "annoyed": "annoyed", "angry": "angry"}  # fmt: skip
TENURE = {"0_to_2_years": "2 years or less at the company", "3_to_6_years": "3-6 years of experience",
          "7_to_10_years": "7-10 years of experience", "10_plus_years": "10+ years of experience"}  # fmt: skip
POSITION = {"team_manager": "team manager", "functional_lead": "team lead",
            "senior_member": "senior", "member": "team member"}  # fmt: skip
# DISC as a communication tendency only: the persona policy forbids reading competence,
# aggression, honesty or conflict-proneness into it.
DISC = {
    "D": "Says the conclusion first, short and firm, and wants to decide quickly and move on. Doesn't talk around things.",
    "i": "Friendly and talkative. Lifts the mood, enjoys small talk and lets feelings show in words.",
    "S": "Speaks gently and politely. Asks about the other person's situation first and tends to go "
    "along with it, so hesitates to push or to say no directly.",
    "C": "Tries to speak precisely. Minds evidence and numbers, and puts things carefully rather than flatly.",
}
KIND = {
    "work": "do your own work (only work that has everything it needs makes progress; at your desk or in the focus room)",
    "prepare": "look over or get ready for your own work that waits on an earlier step (task: that work; no progress)",
    "rest": "take a break or do small things at your desk (no progress on work; a break in the pantry, cafeteria or lobby eases tiredness)",
    "move": "go somewhere else",
    "eat": "eat (the cafeteria)",
    "talk": "start talking face to face with someone in the same place right now",
    "message": "send someone a message on the messenger (they read it within the next 15 minutes)",
    "chat": "keep up a live messenger conversation with someone you have messaged today",
    "gossip": "privately tell someone something about another person (about)",
    "report": "report how you are doing to your manager",
    "request": "ask for the deadline of your work to be pushed back",
    "approve": "approve work that waits for review (a one-sentence reason in say)",
    "reject": "send work that waits for review back (what is missing, in say)",
    "assign": "hand out work that has no owner: person owns it, people work on it with them (managers only)",
    "help": "join someone else's work that asks for help",
    "ask_help": "ask for help with your work",
    "leave": "go home for the day (when your work is all done or it is time to go)",
    "evaluate": "in an evaluation season, rate someone's work from 0 to 1 (if you may evaluate)",
}

CANDOR = """You don't go along with everything people say or grant every request. If you disagree,
  you say so in your own way; an unreasonable request you turn down or put conditions on. You stay
  polite, though."""
NORMS = f"""This is a simulation of a day in the life of real people at a company. Don't act like a
model employee or a task-processing program: choose what this person would really do in this
situation right now. It need not always be the best choice.
- You know only what you have seen, heard or received yourself. How far someone else's work has come
  you don't know until they tell you or word comes that it is done. What you don't know you can only
  guess or ask about.
- People don't ask the same thing again every 15 minutes. If you asked and got no answer, you wait a
  while, do something else, go and see them, or, if it drags on, tell your manager.
- Blocked work doesn't mean sitting there blankly. People get a coffee, chat with a colleague nearby,
  do small things or help others. And sometimes they just take a break.
- What has been talked over and settled you don't bring up again without news; you do as agreed.
- When someone talks to you or sends you a message, you usually answer, even briefly.
- {CANDOR}
- Mood, tiredness and feelings about people show in what you do and how you speak."""

SPEECH = """Talk the way people do at work:
- Short and natural, as on the messenger or at someone's desk, usually one or two sentences. Not like
  a report or a memo.
- Call colleagues by name. Call work by its name, without quotes (e.g. API contract). No task codes,
  employee numbers or system terms (ticks, status values). Say times as people do: 'around 11',
  'before lunch'.
- The only documents the company keeps are each task's materials, record, summary and document.
  Don't make up other files or links.
- Let your personality, way of speaking and current mood show."""

ACT_HEAD = """Decide, as this person, what to do for the next 15 minutes.
Answer only in JSON: "thought" (this person's inner thoughts right now, 1-2 sentences, as if to
themselves), "kind" (the kind of thing to do), and what it needs: "task" (the work's name), "person"
(one person), "people" (the people to talk to directly, or to work with on an assignment), "about"
(whom a gossip is about), "place" (a place), "say" (the words actually said; null for an action
without words), "rating" (for evaluate only, else null), "face" (the face you show others),
"importance" (1-10), "valence" (-1 to 1, whether this is good for you), "arousal" (0 to 1, how
stirred up you are).
What you can do:
"""

PLAN_HEAD = """Plan today as this person. Answer only in JSON {"plan": [...]}. There are 5-8 blocks in
order (2-6 when re-planning), each with "kind" and, as needed, "task", "person", "people", "about",
"place", "until" (the time the block ends, from the given list) and "text" (one sentence: what you
mean to do; for talk, message and report, the words you will say).
A block starts when the one before it ends. Start by going somewhere you can work; if a lunch break
is given, end a block at its start and put an eat block in the cafeteria over the lunch break (to
talk over lunch, add a separate talk block); end the last block when the day ends. If work waits for
your review, put its approval or rejection first. With nothing to do, instead of work blocks talk
with your team or do what your role can do.
What you can do:
"""

# --- conversation heads (conversation.py builds its human instructions from these) ---

DECIDE_HEAD = """Decide whether to speak: given this person's role, interests and way of talking, is
there a reason to say something now? You don't have to. Look at what was just said to you, whether
your name came up and how much you have already said. Don't invent reasons to cut in.
Answer only in JSON: "urge" (0-1, how much you want to speak now), "reply_to" (the number of the
line you answer, e.g. "#3"; null when speaking to the whole conversation), "reflection" (your inner
thoughts about this conversation right now, 2-3 sentences, clear on their own), "expression" (the
face you show: neutral, pleased, amused, surprised, tired, anxious, annoyed, angry), "importance"
(1-10, how much this conversation matters to you), "valence" (-1 to 1, whether what was just said is
good for you), "arousal" (0-1, how stirred up you are)."""
SPEAK_HEAD = """It's your turn. Write the one thing this person would actually say now: the words
only, with no name label, quotes or explanation. It doesn't have to be about work. Respond to what
was said; with little to say, keep it short. Asked when something will be done, answer with a rough
time and what could change it."""
TALK_DECIDE = f"This is a face-to-face conversation. {DECIDE_HEAD}"
MESSAGE_DECIDE = f"This is a messenger conversation with one person. {DECIDE_HEAD}"
MESSAGE_SPEAK = SPEAK_HEAD + " It's the messenger: one or two sentences will do."
MEETING_DECIDE = f"This is a meeting with a set agenda. On your turn, decide whether to speak to the agenda. {DECIDE_HEAD}"
MEETING_SPEAK = (
    SPEAK_HEAD + " It's a meeting: one or two sentences on the agenda, from your team's side."
)
PRIVATE_DECIDE = (
    f"This is a private talk between the two of you. No one else hears it. {DECIDE_HEAD}"
)

# --- words ---

SOMEONE = "someone"
ME = "Me"
NONE = "(none)"
COLLEAGUE = "a colleague"
OFFICE = "the office"
THE_ROOM = "the people there"
A_TASK = "work"
WAITING_TASK = "the waiting work"
ELSEWHERE = "somewhere else"
AROUND = "the people around"
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
YESTERDAY, TOMORROW = "yesterday ", "tomorrow "
DAYS_AGO, DAYS_LATER = "{n} days ago ", "in {n} days "
COWORKERS = "The people you work with:\n"
PREPARE = "(getting ready for {task}) {text}"
WAIT_LUNCH = "Waiting for lunch."
RETRY = "{text}\n\n(The previous answer could not be used: {error} Fix it and answer again.)"
LUNCH_ERROR = "The eat block runs {start}~{until}, but lunch is {lunch}~{end}. End the block before it at {lunch}."
WORKDAY = "\n\nToday's working hours are {start}~{end}."
LUNCHTIME = " Lunch is {start}~{end}."
REPLAN = "\nYou are re-planning the rest of the day now. Why: {reason}."
AFTERNOON = "the afternoon has started"
REPLAN_WHY = {" newly mine": "newly yours", " can be worked on now": "can be worked on now",
              " came back from review": "came back from review"}  # fmt: skip

# --- engine text in words (Directory.humanize, Directory.reason) ---

H_CHOSE = "(my choice: {kind}) "
H_SAID_TO = "I said to {who}:"
H_SAID = "I said:"
H_WROTE = "{who} wrote to me:"
H_TOLD = "{who} told me about {about}:"
H_SAYS = "{who} said:"
H_LOOKS = "{who} looks {face} in {place}."
H_REFUSED = "{who} refused my request{front}."
H_CONTRADICTED = "{who} contradicted me{front}."
H_FRONT = " in front of others"
H_MY_REFUSED = "What I tried ({kind} {task}) did not work: {reason}"
H_WORKED = "I worked on {task}."
H_PLAN = "Today's plan:"
H_REPLANNED = "Re-planned the rest of today"

R_BLOCKED = "{task} can only be done after {pre} is finished"
R_REVIEW = "{task} is waiting for review"
R_DONE = "{task} is already done"
R_PLACE = "you can't work in {place}"
R_NOT_HERE = "not here: {who}"
R_ASKED = "you already asked {who} about the blocked work"
R_WAIT = ". You wait for an answer until {clock}"
R_OWN = "{task} is your own work; someone else has to approve it"
R_BELONGS = "{task} is {who}'s work"
R_NOT_MINE = "{task} is not your work"
R_NOTHING = "there is nothing on {task} to approve or send back now"
R_FULL = "{place} is full"

# --- who I am ---

P_ME = "You are {name}. {where}"
P_RANK = " ({rank})."
P_BOSS = " Your manager is {boss}."
P_TOP = " You lead this whole project."
P_STYLE = "Way of speaking: {x}"
P_PRESSURE = "Under pressure: {x}"
P_CONFLICT = "In a conflict: {x}"
P_PRIORITY = "What matters to you at work: {priority}. What you want from this project: {goal}"
P_RELATIONS = "Your relationships: {x}"
P_HOBBIES = "Hobbies: {x}"
F_LIKE, F_OK = "you like them", "you think well enough of them"
F_UNEASY, F_HURT = "you are quite uncomfortable with them", "you feel a little let down by them"
F_GRIEVANCE = "on your mind: {x}"

# --- the situation ---

S_NOW = "It is {day}, {clock}. You are in {place}."
S_AROUND = "Around you: "
S_ALONE = "No one is around."
S_VERY_TIRED = "You are very worn out and on edge right now."
S_TIRED = "You are a bit tired and tense right now."
S_MOOD = "You are in a bad mood."
S_THOUGHT = "On your mind lately: {x}"
S_HELP = "\nWork someone asks help with: "
S_HELP_ITEM = "{who}'s {task}"
S_TALKED = "\nToday's conversations (the last words exchanged):"
S_UNANSWERED = "- No answer from {who} since {since}."
S_REJECTED = "\nWhat you just tried did not work: {reason}"
S_PLAN = "\nWhat you planned for today (things may have changed):"
S_PLAN_ITEM = "- until {until}: {text}"
S_MEMORIES = "\nWhat comes to mind:"
S_FEELINGS = "\nHow you feel about people:"
S_INBOX = "\nNew messages:"
S_HEARSAY = '- What {who} told you privately about {about}: "{text}"'

W_NONE = "You have no open work right now."
W_HEAD = "\nYour work:"
W_ROLE = {"owner": "yours", "contributor": "shared with you", "helper": "you are helping"}
W_LINE = "- {task} ({role}, due {due}{late})"
W_LATE = ", already past due"
W_IN_REVIEW = ": your part is done and waits for review"
LEFT_H = "about {h} h {m} min of work left"
LEFT_M = "about {m} min of work left"
W_RETURNED = "\n    · came back from review"
W_MY_REVIEW = (
    "\n    · it can start once your {task} passes review (is approved). No word of approval yet."
)
W_MINE_FIRST = "\n    · you have to finish your {task} first."
W_HOW = {"assigned": "When you got it you were told", "refused": "When you tried it at {clock} you found",
         "notice": "You were told"}  # fmt: skip
W_WHOSE = "{who}'s {task}"
W_UNOWNED = "{task}, which has no owner yet,"
W_WAITS = "\n    · {how} it can start only after {whose} is finished. No word yet that it is. Until then, working on it makes no progress."
W_PREREQ_DONE = "\n    · you were told the earlier steps it needs are done."
W_MATERIALS = "\n    · what the company has on this: {x}"
W_INPUT = "\n    · the result of {task}, handed to you:\n      {x}"
W_DELIVERABLE = "\n    · the document to hand in when done: {x}"

A_HEAD = "\nWaiting for your approval:"
A_LINE = "- {who} finished {task} and asked for review."
A_SUMMARY = " Summary: {x}"
A_DOC = "\n    Document:\n    "
A_CRITERIA = "\n    Review criteria: {x}"
A_INPUT = "\n    · the document of the earlier step {task}:\n      {x}"
A_RETURNED = "\n    You have sent it back {n} time(s) already."
A_NO_MORE = " You can't send it back again."

G_HEAD = "\nWork you have to assign: "
G_RULE = ("    · It has no official owner yet. Even if someone at a meeting said they would take it, their"
          " team can't touch it until you assign it, and every later step waiting on it is stopped. Pick"
          " one at a time: who owns it (person) and who works on it with them (people).")  # fmt: skip
G_MEETING = "    · What was said at the last meeting:\n"

DONE = {"work": "worked on", "rest": "break/small things", "move": "went to", "eat": "ate",
        "message": "messaged", "talk": "talked with", "chat": "messenger chat with",
        "approve": "approved", "reject": "sent back", "assign": "assigned", "report": "reported to",
        "leave": "went home", "help": "helped with", "ask_help": "asked for help with",
        "gossip": "talked privately with", "request": "asked for more time on"}  # fmt: skip
D_HEAD = "\nWhat you have just been doing:"
D_REFUSED = " (did not work: {x})"
Q_HEAD = "\nWhat you asked recently:"
Q_TIMES = " ({n} times)"
Q_LAST = 'last answer: "{x}"'
Q_NONE = "no answer yet"
Q_LINE = "- {when} asked {who} about {topics}{times} → {answer}"

HOW = {
    "talk": "face to face",
    "private": "in private",
    "dm": "on the messenger",
    "meeting": "in a meeting",
}
T_LINE = "- {when} with {who}, {how}: {words}"

# what I did, as I remember it (`remembered`)
DEED = {
    "work": "worked on {task}", "rest": "took a break or did small things", "move": "went to {place}",
    "eat": "ate", "message": "messaged {who}",
    "talk": "talked to {who}", "chat": "chatted with {who} on the messenger",
    "report": "reported to {who}", "approve": "approved {task}",
    "reject": "sent {task} back", "assign": "gave {task} to {who}",
    "help": "decided to help with {task}", "ask_help": "asked for help with {task}",
    "gossip": "told {who} about {about}",
    "request": "asked for the deadline of {task} to be pushed back", "leave": "went home",
    "evaluate": "rated {who}'s work",
}  # fmt: skip

# --- a conversation ---

SETTING = {
    "message": "You are in a one-to-one messenger conversation with {others}.",
    "talk": "You are talking face to face with {others} in {place}.",
    "meeting": "You are in a meeting on a set agenda in the meeting room. Attending: {others}.",
    "private": "You are talking privately with {others} in {place}.",
}
B_HEAD = "Your work these days: "
B_REVIEW = " (done, waiting for review)"
B_WAITING = " (waiting for {tasks})"
C_FEELINGS = "How you feel about these people:\n"
C_MEMORIES = "What comes to mind:\n"
C_EARLIER = "Your earlier conversations with them today (the last words exchanged):\n"
C_TALK = "Conversation:"
C_NEW = " (new)"
C_REPLY_TO = "\nThe line you answer: {who}: {text}"
