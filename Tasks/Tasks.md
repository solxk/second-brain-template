---
created-by: claude
---
# Tasks

The task database: one note per task, and this folder is the only place tasks live.

- **See everything**: run `python3 Scripts/tasks_board.py serve` and open http://127.0.0.1:8765/. Or open `Tasks.base` in Obsidian.
- **Add**: type lines into the board's brain-dump box, or tell Claude.
- **Finish**: tick it on the board, or set `task-status: done`.
- **Not doing it after all**: set `task-status: dropped` with a line saying why. Never delete a task note by hand.
- **Rules**: `due` is a real deadline only. `blocked` is worked out from `depends-on`. Priority and effort are proposed by Claude; you overrule.

## Board

![[Tasks.base#Board]]
