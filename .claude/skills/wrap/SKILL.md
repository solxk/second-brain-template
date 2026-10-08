---
name: wrap
description: Use when the owner types /wrap, or says "what did we decide?", "wrap up", "done for today", "that's enough", or otherwise stops. Writes down what the session decided and changed, closes finished tasks, and plans the next day. Safe to run twice.
---

# Wrap

The end of a session or a day. Its job: everything decided is written down where it belongs, so the next session starts briefed, and tomorrow's first task is named tonight. Run every command from the folder's top level, with the Python command `vault.json` records (`python3` below).

Read the "Starting and ending the day" section of `Me.md` first. It says what the owner wants asked at the end, and whether to plan tomorrow now or leave it to the morning. Their words win over the defaults below. If they want it done differently, suggest the change to that section; edit `Me.md` only when they ask you to.

**When they just stop** ("right, done", "that's enough for this morning"), don't wrap up silently. Name it and offer it in one line: "Shall I wrap up? I'll write down what we decided and plan tomorrow." Go on their yes. Offer it too when a conversation is clearly finishing.

**Never:**
- send anything;
- close a task without the owner's yes;
- put anything on the calendar before their OK, or at all if `Me.md` says they don't want blocks;
- edit `Me.md`, or a note they've marked as their own thinking.

**A second wrap the same day:** cover only what happened since the last one, and ask one question: "Anything since the last wrap?"

## 1. Check in

Ask the questions `Me.md` lists. If it lists none, ask these two, in one message:
1. Anything happen today that I didn't see?
2. Anything on your mind for tomorrow or later?

Run `python3 Scripts/tasks.py brief` for the lists. For each task under Waiting on others whose chase date has passed, ask in the same message: "Did you chase <who> about <what>?" If yes, run `python3 Scripts/tasks.py set "<task>" --chased --source wrap`, which moves the chase date a week on. If no, leave it.

Each answer becomes a task, a reminder, a line in a folder note, or nothing. Use the task-or-reminder test in `Tasks/Tasks.md`.

## 2. Write it down

- **Make it true:** re-read each folder note and task note this session touched, and fix any sentence the session made untrue. The log line keeps the history; the body should still read true.
- **Close what's finished:** list the tasks that look done (finished in this session, or they said so) under "Close these?". Close each on their yes with `python3 Scripts/tasks.py set "<task>" --status done --note "<what finished it>" --source wrap`.
- **Log what moved:** for a task that moved but stays open, `python3 Scripts/tasks.py set "<task>" --note "<what moved>" --source wrap`.
- **Recently shifted:** one line for each project or area that moved, at the top of the "Recently shifted" section of its folder note. Use the shape `- <YYYY-MM-DD> — **<what moved, in a few words>.** <one or two sentences>`. If a line dated today is already there, revise it instead of adding a second. Keep eight lines; move older ones to a "History" section at the bottom of the note.

## 3. Plan tomorrow

Skip this step if `Me.md` says to leave planning to the morning; the brief will do it.

"Tomorrow" is the next working day. Run `python3 Scripts/tasks.py --today <tomorrow> brief` to see tomorrow's Today and Not planned yet.

- **Unfinished today:** if tasks planned for today or earlier are still open, offer "Carry everything unfinished to tomorrow" as one answer. On yes, run `python3 Scripts/tasks.py set "<task>" --when <tomorrow> --source wrap` for each one that isn't on hold. Their carry count survives, so tomorrow they read "Carried N days".
- **Propose tomorrow** the way the brief does (`.claude/skills/brief/SKILL.md`, step 4): up to the day's limit from `Me.md`, deadlines first, then carried tasks, then high priority. Put the rest on one line, "Left for another day". Never plan a task that's on hold.
- **First thing:** name the first thing to do tomorrow as one concrete action.
- **When they OK the plan:** run `python3 Scripts/tasks.py set "<task>" --when <tomorrow> --source wrap` for each task. Add calendar blocks only if they want them and a calendar is connected; check tomorrow's events first, so nothing is added twice.

## 4. Tidy up

```bash
python3 Scripts/tasks.py sync
python3 Scripts/check_wiki_links.py
```

Fix any broken links (links into `Archive/` are fine). If this folder is a git repo, commit with `git add -A`, then `git commit -m "Wrap <YYYY-MM-DD>: <what moved>"`.

## 5. What they see

The check-in questions (step 1) go first, in their own message. Then one short message, one screen, with empty sections left out. It starts with what was decided, not with what's next.

```
Wrap · <Weekday d Month>

Decided
- <decision> (<Folder>)

Moved
- <Folder>: <what moved>              (five lines at most)

Close these?
- <task> · <why it looks done>

Tomorrow (<Weekday>) · OK?
<time>  Deep    <task> (<Folder>)
<time>  Medium  <task> (<Folder>)
<time>  Quick   <task> · <task>
First thing: <one concrete action>
Left for another day: <task> · <task>
Or: carry everything unfinished to tomorrow (<n> tasks)

Still waiting on you
- <the oldest open decision>
- <who, what: past its chase date>
```
