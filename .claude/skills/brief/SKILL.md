---
name: brief
description: Use when the owner types /brief, opens a session in this folder, or asks "what's on today?" or for their plan for the day. Syncs the tasks, reads the calendar and the phone list if they're connected, files what's clear, and proposes the day in one short message.
---

# Brief

The morning brief: one short message that makes the first thing to do need no decisions. Run every command from the folder's top level, with the Python command `vault.json` records (`python3` below).

Read `Map.md`, then `Me.md` first. The "Starting and ending the day" section in `Me.md` says what the owner wants in the brief, how much a day should hold, and whether the plan goes on their calendar. Their words win over the defaults below. If they want it done differently, suggest the change to that section; edit `Me.md` only when they ask you to.

**When `Me.md` scopes the brief** ("the first thing, and anything about Dad"; "whats due, who to ring, whats late. Thats it"), the brief is Start here plus exactly those, nothing added after their "that's it". Every other section waits until they ask. When it says how they read it ("on my phone"), keep it to eight lines.

**Never:**
- send anything;
- close a task without the owner's yes;
- put anything on the calendar before their OK, or at all if `Me.md` says they don't want blocks;
- edit `Me.md`.

**A second run the same day** (usually because something new came in): write only what's new since the last run. That means new phone items, new things to sort, and changes to today's plan (a new meeting, a clash). Leave out every section that didn't change.

## 1. The tasks

```bash
python3 Scripts/tasks.py sync
python3 Scripts/tasks.py brief
```

If `sync` prints `ERROR` or `REVIEW` lines, put them on the brief's last line in plain words. A `REVIEW` line saying every task under a goal is finished becomes "Close <goal>?" under Needs you today.

The brief's sections are the board's lists: Today (its first row is Start here), Reminders, Not planned yet, Decisions waiting, Waiting on others, On hold, Claude's tasks, To sort, Newly unblocked, and Untouched for 14+ days.

## 2. The calendar, if it's connected

Read today's events, and tomorrow's until midday.
- **Meetings** (events with other people or a place) get one line each: who, what it's about, and any open task that names them or their project.
- **Busy times** are for fitting the plan.
- **All-day items** that need doing go under Needs you today.

If no calendar is connected, skip this step. If one is connected but can't be read, say so, and propose the plan as an order of tasks without times.

## 3. The phone list and To sort

If Google Tasks is connected, read its **Phone** list. Each item becomes one of:
- a task (`python3 Scripts/tasks.py add "Title" --inbox` when the folder isn't clear);
- a reminder (`python3 Scripts/tasks.py add "Title" --kind reminder --when <day>`);
- a line under "To watch" in `Resources/Resources.md`.

Use the task-or-reminder test in `Tasks/Tasks.md`. Then tick the item off in the Phone list.

Then file To sort: `python3 Scripts/tasks.py list --status inbox`.
- **Folder is clear:** `python3 Scripts/tasks.py set "<task>" --project "<Folder>" --status todo --source brief`, plus `--effort` when it's obvious.
- **Two plausible folders:** it stays in To sort and goes under "File these?" with your guess.

If `Inbox/` holds anything, count it and offer to file it after the brief.

## 4. The plan

The day's limit comes from `Me.md`. If it doesn't say, the limit is two deep, two medium and five quick tasks, the quick ones done as one sweep.

- **Already planned:** Today has tasks planned for today. Show them in order, and flag only what no longer fits: a meeting added since, or more than the limit. Over the limit, suggest which to leave for another day.
- **Nothing planned yet:** propose a plan up to the limit, in this order:
  1. deadlines due or late (always in, and they don't count toward the limit);
  2. tasks carried longest;
  3. anything in progress;
  4. the high-priority ones from Not planned yet.

  Put the rest on one line, "Left for another day". Give clock-time blocks only when a calendar is connected and `Me.md` says they want them. Without that, label the plan with the parts of the day `Me.md` names ("morning", "9 to 1", "before football"). Deep work goes in the hours they said they're sharpest, medium and quick work after, around busy times.
- **Decisions:** a decision in the plan gets no time slot.
- **Start here:** the plan's first task, with the first thing to do as one concrete action ("open the contract and read clause 4", not "work on the contract").

**When they OK the plan** (after any changes they ask for):
- each planned task: `python3 Scripts/tasks.py set "<task>" --when <today> --source brief`;
- a task that was already on Today and is now left for another day: `python3 Scripts/tasks.py set "<task>" --when <next working day> --note "left for another day" --source brief`;
- calendar blocks only if they want them and a calendar is connected. Title each one `<Folder>: <task>`, and make the quick sweep a single event.

## 5. Write it

One message, one screen, plain words. Leave out every section that's empty. Use the board's labels as written ("Start here", "Not planned yet", "Waiting on others").

```
<Weekday d Month>
<one line: what's on the calendar, and whether the day is planned>

Start here: <task> (<Folder>) · <the first thing to do>

Needs you today
1. <late or due-today deadline · reminder due · meeting to prepare · goal to close>

Plan · <the limit> · OK?              (or "Today's plan" when it's already planned)
<time>  Deep    <task> (<Folder>)
<time>  Medium  <task> (<Folder>)
<time>  Quick   <task> · <task> · <task>
        Decide  <decision> (<Folder>)
Left for another day: <task> · <task>

Meetings
<time> <who>: <what it's about> · open: <task>

Decision waiting: <the oldest open decision> (<Folder>). <n> others; say if you'd like to go through them.
Waiting on others: <who>, <what> · <n> days past the chase date
File these? <task>: <your guess>

To sort: <n> filed · Inbox: <n> to file · Untouched for two weeks: <n>
<anything not read, and why>
```

- **Decision waiting:** only the oldest open one, then the count of the rest. Never name a second decision. If they say yes, go through them one at a time: lay each out in two or three lines, ask for the call, and record it with `set`.
- **Untouched for two weeks:** a count only. The full list waits until they ask.
