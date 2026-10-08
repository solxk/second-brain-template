---
created-by: claude
---
# Tasks

Every task, goal and reminder is one note in this folder, and this is the only place they live. The owner uses the board; the rest of this note is for Claude.

## For the owner

- **See everything**: say "open the board". (In Obsidian, `Tasks.base` shows the same notes as tables.)
- **Add**: type into the board's brain-dump box, or tell Claude. Claude sorts whatever lands in To sort.
- **Finish**: tick it on the board.
- **Not doing it after all**: tell Claude. Task notes are never deleted by hand.

## How it's shaped

Three levels, no deeper:

1. A **project or area** folder (`Projects/Acme`, `Areas/Home`). A task's `project` field links that folder's note.
2. A **goal**: a task note with `kind: project`. It's a finish line with several tasks under it ("Sell the flat"). Goals are optional: make one only when a group of tasks clearly belongs together, never at setup. A goal never shows in Today; its tasks do.
3. A **task**: one session's work or one decision. Its `parent` field links the goal it sits under, if there is one. Most tasks sit straight under their folder.

Only a goal can have tasks under it, and a goal can't sit under another goal. `sync` reports anything else.

A **reminder** is a task note with `kind: reminder`: a nudge on a date, no folder needed. Its date is the day it's for ("school trip money, Friday" is Friday); the brief starts showing it two days before. Reminders never show in Today. They have their own list on the board and their own section in the brief.

Nothing repeats on its own. Something weekly (a long run on Sundays) is a habit, kept under Loose ends in its area, or a repeating event in the owner's calendar.

On screen, a `kind: project` note is called a **goal**, so say "goal" to the owner. The word comes from `"labels"` in `vault.json`.

## Fields

- `effort`: deep (a focused block), medium (an ordinary session) or easy (minutes). Claude proposes it; the owner overrules.
- `decision: true` marks a yes/no that's the owner's to make.
- `due` is a real deadline only, or a reminder's day. Scheduling is a calendar conversation.
- `priority` is high, normal or low, proposed by Claude with a one-line reason in the note. Never change a due date or priority the owner set without saying so.
- `blocked` is worked out from `depends-on` by `sync`. Never type it.
- `owner` is the owner's name. Set it to someone else's (`--owner Dev`) when the next move is theirs; the task then shows under Waiting on others.
- A title's `: ? / " *` and similar characters become `-` in its filename ("Decide: X?" is saved as `Decide- X-.md`). Links use the filename; the board and the brief show the title.
- `task-status`:
  - `inbox` means to sort;
  - `todo`, `doing`, `blocked` and `someday` mean what they say;
  - `done` tasks move to `Archive/` thirty days after they're done;
  - `dropped` means not doing it: add a line saying why, and `sync` moves it to `Archive/` straight away.

## Commands

```
python3 Scripts/tasks.py add "Title" --project "Folder" [--due YYYY-MM-DD] [--priority high|normal|low]
        [--effort deep|medium|easy] [--decision] [--parent "Goal title"] [--after "Title it waits on"]
python3 Scripts/tasks.py add "Sell the flat" --project "Home" --kind project        # a goal
python3 Scripts/tasks.py add "Call mum" --kind reminder --due 2026-10-09             # a reminder
python3 Scripts/tasks.py add "Half a thought" --inbox                                # to sort later
python3 Scripts/tasks.py sync                                                        # blocked, done dates, archive
python3 Scripts/tasks.py brief
python3 Scripts/tasks.py list [--project X] [--status Y]
python3 Scripts/tasks_board.py serve
python3 Scripts/tasks_board.py style [name]                                        # list the board styles, or switch
```

Start the board in the background and give the owner http://127.0.0.1:8765/. It runs while this session is open. If it's already running, it says so.

If the owner wants the board to look different, give them http://127.0.0.1:8765/styles, which shows their own tasks in every style, then switch with `style <name>`. The choice is saved in `vault.json` as `board_style`.

## Board

![[Tasks.base#Board]]
