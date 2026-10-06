# Second Brain

A folder that remembers. Plain markdown files, a few small scripts, and Claude Code pointed at the folder. Claude reads who you are and what you're working on before it answers, files what you throw at it, keeps your task list, and writes down what changed at the end of every session.

Nothing is hosted anywhere. The folder is the system.

## What you need

- A Mac or Windows PC.
- [Claude Code](https://claude.com/claude-code) (needs a Claude Pro or Max subscription).
- Python 3.9 or newer. Macs have it. On Windows, install it from python.org and tick "Add to PATH"; the command there is `python`, so wherever these notes say `python3`, type `python`.
- A Google account. Reminders and quick capture from your phone use Google Tasks.
- [Obsidian](https://obsidian.md) (free). Optional, but it makes the notes readable and the links clickable.

## Start

1. Get this folder onto your computer. Either click **Use this template** above (needs a GitHub account), or **Code → Download ZIP** and unzip it somewhere sensible, like `Documents/Second Brain`.
2. Open a terminal in that folder and run `claude`. (Mac: open Terminal, type `cd `, drag the folder onto the window, press Enter. Windows: open the folder in Explorer, click the address bar, type `cmd`, press Enter.)
3. Say: **"Set me up."**

Claude reads `SETUP.md`, interviews you for about twenty minutes, and builds the folder around your answers. You approve what it writes about you before anything else happens.

That's it. Everything after that is a conversation: "what's on today?", "file this", "add a task", "what did we decide last time?".

## What's in the box

| | |
|---|---|
| `CLAUDE.md` | The rules Claude follows in this folder. Short on purpose. |
| `SETUP.md` | The one-time setup Claude runs for you. |
| `Me.md` | Who you are and how you work. Written from the interview. Yours. |
| `Map.md` | Where everything lives. |
| `Inbox/` | Anything, unfiled. Claude sorts it. |
| `Projects/` | One folder per thing you're building or running. |
| `Areas/` | Ongoing parts of life with no end date: health, money, home. |
| `Resources/` | Reference, ideas, research. |
| `Tasks/` | One note per task, and the board that shows them. |
| `Archive/` | Finished or dead. Nothing is deleted. |
| `Scripts/` | The task board and two helpers. Python, no installs. |

## The task board

```
python3 Scripts/tasks_board.py serve
```

then open http://127.0.0.1:8765/ in your browser. Or just tell Claude "open the board". It runs while that terminal is open; close it and the board goes away until next time, but your tasks are files and lose nothing. A brain-dump box, your day, your decisions, and everything grouped by project. On your phone, `Tasks/Board.html` is a read-only copy that updates every time Claude syncs tasks; it opens from any folder-syncing app (Google Drive, Dropbox, iCloud).

## Made by

Sol Khan, from the folder he runs his own businesses out of. Claude Code only for now.
