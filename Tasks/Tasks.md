---
created-by: claude
---
# Tasks

Every task, goal and reminder is one note in this folder, and this is the only place they live. The owner uses the board; the rest of this note is for Claude.

Three words that look alike: a task's `project` field links a **project or area** folder note (`--project Health` is fine); `kind: project` means a **goal**, and is called a goal on screen (the word comes from `"labels"` in `vault.json`); `Projects/` is the folder for work. Say "goal" to the owner.

## For the owner

- **See everything**: say "open the board". (In Obsidian, `Tasks.base` shows the same notes as tables.)
- **Add**: type into the board's brain-dump box, or tell Claude. Claude sorts whatever lands in To sort.
- **Finish**: tick it on the board. Goals have a tick box too.
- **Not doing it after all**: choose Dropped on the board and say why in one line, or tell Claude. Task notes are never deleted by hand.

## What's on Today

Today is the day's plan. A task is on it when it's yours, open, and one of these:
- **planned** for today or an earlier day (`when`); one planned for an earlier day shows "Carried N days";
- its **deadline** (`due`) is today or has passed;
- it's **in progress** (`doing`).

Deadlines due or late come first, then deep, medium and quick tasks. The first row is marked **Start here**. Goals and reminders never show on Today; a goal's tasks do.

Below Today, a folded **Not planned yet** strip holds your high-priority tasks and anything with a deadline in the next week that has no planned day. Give one a planned day to put it on Today. A planned day later than today keeps a task off both until that day, even at high priority; its deadline still puts it on Today on the day.

## How it's shaped

Three levels, no deeper:

1. A **project or area** folder (`Projects/Acme`, `Areas/Home`). A task's `project` field links that folder's note.
2. A **goal**: a task note with `kind: project`. It's a finish line with several tasks under it ("Sell the flat"). Goals are optional: make one only when a group of tasks clearly belongs together, never at setup. When every task under a goal is finished, `sync` says so; ask the owner whether to close it.
3. A **task**: one session's work or one decision. Its `parent` field links the goal it sits under, if there is one. Most tasks sit straight under their folder.

Only a goal can have tasks under it, and a goal can't sit under another goal. `add` refuses both; `sync` reports anything hand-made that breaks the rule.

A **reminder** is a task note with `kind: reminder`: a nudge on a day with nothing to do but remember it. It needs no folder, but give it one when it plainly belongs to one (`--project Home`). Its day is its `when` ("school trip money, Friday" is Friday), never `due`; it's saved without the fields only tasks use. The brief shows it from two days before, marks it overdue once the day has passed, and it stays until ticked. Reminders never show in Today; they have their own list on the board and their own section in the brief.

Task or reminder? People call everything a reminder; the owner's word doesn't decide it. If it takes real work, or has a date someone else set, it's a task: designing the party invitations is a task, transferring the money for it is a reminder, and booking an appointment (dentist, vet, boiler service) is a task, low priority if need be. Say so in one line and let the owner overrule. An event on a date (a race, an exam, a party) is a reminder on its day, plus a task for anything that must be done for it; never a habit. "Book X" has two dates: when X is (the reminder) and the last day to book (the task's `due`); record both. Never invent a deadline or a dependency the owner didn't state. A target with a date is a task with that deadline. Loose ends in a folder note never hold anything with a date.

Nothing repeats on its own. Something weekly (a long run on Sundays) is a habit, kept under Loose ends in its area, or a repeating event in the owner's calendar.

## Fields

- `due` is a **deadline**: a real date someone else set. Never use it for the day the owner means to do something. If the owner decides to finish before a deadline ("I'll aim for Friday"), set `when` to that day and leave `due` as the other side set it.
- `when` is the **planned** day: when the owner means to do it. To get a task done on a set day, give it a `when`. A reminder's day is its `when`.
- `effort`: deep (a focused block), medium (an ordinary session) or easy (minutes; the board says "quick"). Claude proposes it; the owner overrules.
- `decision: true` marks a yes/no that's the owner's to make. The brief lists open decisions, oldest first. A choice the owner parks ("nothing to decide right now", when to take a pension) is still a decision task: add it with `--decision --status someday` and put the figures in its note, so it's on record and out of the daily brief. Never a Loose end.
- `priority` is high, normal or low, proposed by Claude with a one-line reason in the note. High priority doesn't put a task on Today; it puts it in Not planned yet until it has a day. Never change a deadline, planned day or priority the owner set without saying so.
- `owner` is whose move it is: the owner's name, written as `vault.json` spells it (case doesn't matter when typing it). Set it to someone else's (`--owner Dev`) when the next move is theirs, or to `Claude` for things Claude runs; Claude's tasks have their own list.
- `waiting-on`, `expecting` and `chase-after` are for a task that waits on someone outside: who (a person, a company), what's expected, and when silence counts as late. Setting `waiting-on`, or giving the task to someone else, sets a chase date a week out if there isn't one. "Chased them" (the board's button, or `set --chased`) logs it and moves the chase date a week on.
- `depends-on` lists tasks that must be finished first. While one is open the task is **on hold** (`blocked`), and the board shows what it waits on.
- A title's `: ? / " *` and similar characters become `-` in its filename ("Decide: X?" is saved as `Decide- X-.md`). Links use the filename; the board and the brief show the title.
- `task-status` (the board calls it Status):
  - `inbox` (To sort): not filed yet;
  - `todo` (To do) and `doing` (Doing);
  - `blocked` (On hold): worked out from `depends-on` by `sync`, never typed; To do and Doing are refused while a dependency is open;
  - `someday`: parked. It's a status, not a folder; parked tasks have their own list on the board;
  - `done`: finished. Done tasks move to `Tasks/Archive/` a week after;
  - `dropped`: not doing it. It needs a one-line reason, and `sync` moves it to `Tasks/Archive/` straight away.

When you show the owner a table of tasks, keep it to three columns at most (what, where, when); split a wider or longer one.

## Lists on the board

Today (with Not planned yet underneath), Reminders, By project, Waiting on others (outside waits by chase date), On hold (the owner's tasks held up by another task), Claude (Claude's tasks), To sort, Someday and Done.

## Commands

Tasks change only through `set` or the board, so every change is checked, dated and logged. Never edit a task note's fields by hand.

```
python3 Scripts/tasks.py add "Title" --project "Folder" [--due YYYY-MM-DD] [--when YYYY-MM-DD] [--priority high|normal|low]
        [--effort deep|medium|easy] [--decision] [--parent "Goal title"] [--after "Title it waits on"]
        [--owner Name] [--waiting-on "Dan"] [--expecting "the quote"] [--chase-after YYYY-MM-DD]
python3 Scripts/tasks.py add "Sell the flat" --project "Home" --kind project        # a goal
python3 Scripts/tasks.py add "Call mum" --kind reminder --when 2026-10-09            # a reminder
python3 Scripts/tasks.py add "Half a thought" --inbox                                # to sort later
python3 Scripts/tasks.py set "Title" --when 2026-10-09                               # plan it for a day
python3 Scripts/tasks.py set "Title" --status done
python3 Scripts/tasks.py set "Title" --status dropped --note "why, in one line"
python3 Scripts/tasks.py set "Title" --decision                                      # make it a yes/no call
python3 Scripts/tasks.py set "Title" --chased                                        # chased them today
python3 Scripts/tasks.py set "Title" --clear when --note "what happened"
python3 Scripts/tasks.py sync                                                        # on hold, done dates, archive
python3 Scripts/tasks.py brief
python3 Scripts/tasks.py list [--project X] [--status Y]
python3 Scripts/tasks_board.py serve
python3 Scripts/tasks_board.py style [name]                                        # list the board styles, or switch
```

`add` warns when the project or area has no folder note: check the spelling or create the folder.

Start the board in the background and give the owner http://127.0.0.1:8765/. It runs while this session is open. If it's already running, it says so.

If the owner wants the board to look different, give them http://127.0.0.1:8765/styles, which shows their own tasks in every style, then switch with `style <name>`. The choice is saved in `vault.json` as `board_style`.

`Tasks/Board.html` is a read-only copy of the board for a phone, rewritten by `sync`. If two computers share this folder, set `"snapshot_host"` in `vault.json` to the name of the one that should write it (its computer name, as `hostname` prints it); the other leaves it alone, so the sync service never makes conflict copies of it.

## Board

![[Tasks.base#Board]]
