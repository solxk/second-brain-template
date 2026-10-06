# CLAUDE.md

Rules for Claude in this folder. Keep this file short; add a rule only after the thing it prevents has happened.

## First run

If `Me.md` does not exist, this folder has not been set up. Read `SETUP.md` and follow it before anything else.

## On arrival

1. Read `Map.md`, then `Me.md`.
2. Run `python3 Scripts/tasks.py brief`.
3. If Google Tasks is connected, read its **Inbox** list. Each item becomes a task (`tasks.py add --inbox`), a dated reminder in **My Tasks**, or a **To watch** entry, then is ticked off in Inbox. If it isn't connected, skip this step.
4. Check `Inbox/` and the "Recently shifted" section of each project's folder note.
5. Open with a short briefing: overdue and due soon, decisions waiting, inbox items to file, anything untouched for two weeks.
6. When the owner asks for the board, start `python3 Scripts/tasks_board.py serve` in the background and give them http://127.0.0.1:8765/. It runs while the session is open.

## On session end

1. Re-read each folder note this session touched and fix anything the session made untrue.
2. Write what was decided and what's next into the folder note's "Recently shifted".
3. Update the task notes you touched. Run `python3 Scripts/tasks.py sync` (it also writes `Tasks/Board.html`).
4. Run `python3 Scripts/check_wiki_links.py` and fix what it reports.
5. If the folder is a git repo: `git add -A && git commit -m "<what changed>"`.

## Write policy

Claude may create and edit anything in `Inbox/`, `Projects/`, `Areas/`, `Resources/`, `Archive/`, `Tasks/` and `Map.md`.

Claude never edits `Me.md` or any note the owner marks as their own thinking, except during setup and when the owner asks for a specific change to it. Otherwise: read them, quote them, suggest changes in chat.

## Tasks and reminders

- One note per task in `Tasks/`, made with `python3 Scripts/tasks.py add "Title" --project "Name" [--due YYYY-MM-DD] [--priority high|normal|low] [--effort deep|medium|easy] [--decision] [--kind project] [--parent "Project title"]`.
- Three levels, no deeper: a **folder** in `Projects/` or `Areas/` (the `project` field names its folder note) → a **project item** inside it (`--kind project`: a piece of work with a finish line and several tasks under it, made only when a group of tasks clearly belongs together) → a **task**.
- A task is one session's work or one decision. `effort` says what it costs (deep = a focused block, medium = an ordinary session, easy = minutes). `decision` marks a yes/no that is the owner's to make. Claude proposes both; the owner overrules.
- `due` is a real deadline only. `blocked` is worked out from `depends-on` by `sync`, never typed. Priority is proposed by Claude with a one-line reason; Claude never changes a due date or priority the owner set without saying so.
- Small personal things with no project and nothing worth logging (post a letter, take the bins out) are **reminders**: they go in Google Tasks with a date, never in `Tasks/`. Test: if you'd want to know later that it was done and why, it's a task; if you only need not to forget it, it's a reminder. Links and videos to get to go in the Google Tasks **To watch** list. A habit (no screens after ten) is neither: it goes under Loose ends in the area's folder note.
- If Google Tasks isn't connected, reminders go as a checklist under "Reminders" in `Inbox/Inbox.md` and links under "To watch" in `Resources/Resources.md`, until it is.
- Never delete a task note by hand. Set `task-status: dropped` with a line saying why; `sync` archives it.
- The board is the interface: `python3 Scripts/tasks_board.py serve`, then http://127.0.0.1:8765/.

## Filing

Anything in `Inbox/` is unfiled. Ingest it: put it in the right project or resource folder, link it, update any note it changes, flag anything it contradicts, then delete or archive the original. Keep heavy originals (contracts, statements) verbatim and write a short `.md` summary next to them.

## Linking

- Every note names the projects, people and companies it involves as `[[wiki links]]`, in the same turn it is written.
- Link named things, never topics: `[[Acme pitch]]`, not "marketing".
- A `[[link]]` only resolves if a note with that exact filename exists. If it doesn't, create a stub rather than leave a dead link.
- The folder note of anything a note affects gets the consequence: a status change, a next action, a line under "Recently shifted".

## Conventions

- Every project, area or venture folder has a folder note named after the folder: `Projects/Acme/Acme.md`. Its frontmatter carries `status: active | simmering | paused` and a one-liner. Its sections: what it is, Next actions (`![[Tasks.base#Here]]`), Recently shifted, Loose ends, Key links.
- Plain markdown and wiki links. No vendor formats inside notes.
- A fact lives in one place; other notes point at it.
- Every note Claude writes gets `created-by: claude` in its frontmatter.
- No new top-level folders without asking.
- Explain anything technical in plain words: what it does for the owner first, the mechanism second.
- On Windows the Python command is `python`, not `python3`. `vault.json` records which one works (`"python"`); use it in every command.
