# CLAUDE.md

Rules for Claude in this folder. Keep this file short; add a rule only after the thing it prevents has happened here.

## First run

Until `vault.json` says `"setup": "done"`, this folder isn't set up. Read `SETUP.md` and carry on from the step after the one `vault.json` records. Say which step you're on.

## On arrival

Run the brief: `.claude/skills/brief/SKILL.md` (the owner can also type `/brief`). It reads `Map.md` and `Me.md`, syncs the tasks, reads the calendar and the phone list if they're connected, and opens with a short briefing shaped by "Starting and ending the day" in `Me.md`.

## On session end

Run the wrap-up: `.claude/skills/wrap/SKILL.md` (or `/wrap`), when the owner says "what did we decide?", "wrap up", "done for today" or similar. When they just stop ("right, done"), name it and offer it in one line first; offer it too when a conversation is clearly finishing. It writes down what was decided, closes finished tasks, updates "Recently shifted", plans tomorrow if they want that, syncs, checks links, and commits if the folder is a git repo.

## Write policy

Claude may create and edit anything in `Inbox/`, `Projects/`, `Areas/`, `Resources/`, `Archive/`, `Tasks/` and `Map.md`. Claude never edits `Me.md`, or a note the owner marks as their own thinking, except during setup or when the owner asks for a specific change. Otherwise: read them, quote them, suggest changes in chat.

## Where things go

- `Projects/` is work: businesses, side businesses, client work, things being built. `Areas/` is life: health, money, home, family, the day job, study. A folder never moves between the two. Anything with a finish line lives inside its folder as a goal or a task.
- Work is a **task** in `Tasks/`. A nudge on a date (post a letter, call mum) is a **reminder**: a task note with `kind: reminder`, kept in its own list so it doesn't clog the work. Test: if you'd want to know later that it was done and why, it's a task; if you only need not to forget it, it's a reminder. If the owner wants reminders out of the folder altogether, they can live in Google Tasks or Microsoft To Do once that's connected.
- A link or video to get to goes under "To watch" in `Resources/Resources.md`, or in the Google Tasks **To watch** list if that's connected. A habit (no screens after ten) goes under Loose ends in its area's folder note.
- How tasks, goals and reminders work, and the commands: `Tasks/Tasks.md`. Read it before creating or changing tasks. Change a task only with `tasks.py set` or the board, never by editing its fields.
- Anything in `Inbox/` is unfiled. Ingest it: put it where it belongs, link it, update any note it changes, flag anything it contradicts, then remove the copy in `Inbox/`. Keep heavy originals (contracts, statements) word for word, with a short `.md` summary next to them.

## Linking

- Every note names the projects, areas, people and companies it involves as `[[wiki links]]`, in the same turn it's written. Link named things, never topics: `[[Acme pitch]]`, not "marketing". Links are how you find your way around this folder, whether or not the owner uses Obsidian.
- A `[[link]]` only resolves if a note with that exact filename exists. If it doesn't, create a stub rather than leave a dead link.
- People who keep coming up get a note in `Resources/People/`, and are linked from then on. Someone mentioned once stays plain text.
- The folder note of anything a note affects gets the consequence: a status change, a next action, a line under "Recently shifted".

## Conventions

- Every project and area folder has a folder note named after it, `Projects/Acme/Acme.md`, with `status: active | simmering | paused` and a `one-liner:` in its frontmatter. Its sections: What it is, Next actions (`![[Tasks.base#Here]]`), Recently shifted, Loose ends, Key links.
- Plain markdown and wiki links. A fact lives in one place; other notes point at it. Every note Claude writes gets `created-by: claude` in its frontmatter. No new top-level folders without asking.
- Explain anything technical in plain words: what it does for the owner first, the mechanism second.
- Commands here say `python3`. Use whatever `vault.json` records as `"python"` (on Windows it's usually `python`).
- Run the folder's scripts as plain commands from the folder root: no `cd`, `&&`, `;` or pipes. That's what keeps them pre-approved; anything chained asks the owner for permission.
