# SETUP.md

Instructions for Claude. Run this the first time the owner says "set me up", and whenever `vault.json` doesn't say `"setup": "done"`. The owner reads only `README.md`; everything below is yours to carry out.

Work through the steps in order and say which step you're on. After each step, record it in `vault.json` as `"setup": "<step number>"`, so a closed window or a usage limit costs nothing. Next time, carry on from the step after the one recorded. The whole thing takes about an hour, most of it talking.

## 0. Check the ground

Before any questions:

- **Find Python.** Try `python3 --version`, then `python --version`, then `py --version`. It needs 3.9 or newer.
  - On a fresh Mac, the first `python3` may open an Apple pop-up offering to install developer tools. Tell the owner to click Install, wait a few minutes, then carry on.
  - On Windows the working command is usually `python`. A `python3` stub there opens the Microsoft Store; ignore it.
  - If none works, tell the owner to install Python from python.org with "Add to PATH" ticked, then come back.
  - Use whichever command worked for every command below and in every session, and store it in `vault.json` as `"python"`.
- **Run the tests**: `python3 -m unittest Scripts/test_tasks.py Scripts/test_tasks_board.py Scripts/test_check_wiki_links.py`. They should end with `OK`.
- **Explain the permission prompts** in one line. Claude asks before running commands; this folder's own scripts are pre-approved in `.claude/settings.json`, and edits inside the folder go through without asking. The pre-approvals only work once the owner has said yes to "do you trust this folder?". If every script run asks for permission, that's why: tell them to reopen the folder and accept it.
- **Ask whether Obsidian is installed.** It isn't required: the board shows the tasks either way.
  - If they have it: File → Open folder as vault → this folder.
  - If they don't, recommend it once and move on. The `![[Tasks.base#Here]]` lines in folder notes are for Obsidian (1.9 or later) and do nothing elsewhere, which is fine.
  - Start `Inbox/Setup notes.md` with their answer, so a resumed setup knows it.

## 1. The interview

About twenty minutes. Ask one question at a time, in plain words, with no jargon. Follow up when an answer is thin; move on when it's enough. Ask about anything ambiguous ("the 18th" of which month?) rather than guess.

Append each answer to `Inbox/Setup notes.md` the moment it's given, before you ask the next question. On a resume, read that file first and pick up at the first question without an answer.

Before question 1, ask their first name, as they'd write it, and put it at the top of `Inbox/Setup notes.md`: `Me.md` opens with it and `vault.json` needs it.

Who they are:
1. What are you working on or building? (A business, a side business, client work, something you're making, or something you run for other people, like a club, a committee or a team, paid or not. Each becomes a folder in `Projects/`.) If they say "I don't know if that counts", ask whether they run it or just belong to it: running it is work and goes in `Projects/`; belonging to it is life. If one sounds like an idea so far ("we're going to", "I guess"), ask whether any work has started. If none has, it's a line under Ideas in `Resources/Resources.md`, not a folder; ask before making a folder for it. It gets a folder when work starts.
2. What parts of your life need looking after? (Health, money, home, family, the day job, study. Each becomes a folder in `Areas/`. Group related things: gym and sleep are both Health. Make an area only where there will be something in it, a task, a reminder or a habit; the day job often has none.)
3. What would you like to have done a year from now, in a sentence?

How they work:
4. When does your work day start, and when are you sharpest?
5. What usually trips you up? (Starting, finishing, deciding, remembering, saying no.)
6. What do you want from an AI partner: pushing you, keeping you organised, thinking things through with you, doing the admin?
7. Should it be direct with you, or gentle?

Logistics:
8. Where do your calendar, email, tasks and reminders live today? (Google, Outlook, Apple, a notebook, nowhere.)
9. Mac or Windows? Which phone?

Close:
10. Anything about you that an assistant usually gets wrong?

Something with a finish line ("sell the flat", "launch the shop") isn't a folder. It belongs inside the project or area it's part of, and becomes a goal or a task later.

## 2. Write Me.md and get it approved

Write `Me.md` from the notes. It's the owner's file: in their words, first person, and tool-agnostic (no mention of Claude or this folder's mechanics). Include only what they said, and leave out any heading with nothing under it.

The list of projects and areas doesn't go in `Me.md`. It goes into `Map.md` and the folders in step 3. `Me.md` is read every session and Claude can't edit it, so a list kept there would go stale.

Shape:

```markdown
# Me

> Written from the setup interview on <date>. This file is mine. Any AI I use reads it first.

I'm <name>. <Two or three sentences on what they do, in words that will still be true in a year. No project names, statuses or dates: those live in `Map.md` and the folder notes.>

## This year
<The one-year sentence.>

## How I work
<Day shape, when they're sharpest.>

## What trips me up
<Their answer, plainly.>

## What I want from an AI partner
<Their answer. Direct or gentle. What to push on, what to leave alone. What assistants usually get wrong about them.>

## Tools
<Mac or Windows, phone, where calendar, email and reminders live.>
```

Show it to them. Ask them to read it and correct anything. Don't build anything until they say it's right. Then update `vault.json` with `"owner"` (their first name, as they'd write it) and `"vault_name"` (this folder's name), and keep the other keys.

## 3. Build the structure

From the notes:

- **Projects.** Make one folder per thing they're working on or building, and only for work that's under way (an idea with no work started stays a line in `Resources/Resources.md`): `Projects/<Name>/`, with a folder note `Projects/<Name>/<Name>.md`.
  - Frontmatter: `status: active`, `one-liner:`, `created-by: claude`.
  - Sections: **What it is** (two or three sentences from the interview), **Next actions** (containing exactly `![[Tasks.base#Here]]`), **Recently shifted** (one dated line: "set up"), **Loose ends** and **Key links**.
- **Freelancers.** A freelancer's regular clients each get a project folder when each brings its own stream of work. Otherwise make one folder for the freelance business, with clients as tasks. Ask if it isn't obvious.
- **Areas.** Make one folder per part of life they named, `Areas/<Name>/`, with the same folder-note shape.
- **Habits** they mentioned (sleep, gym days) go under Loose ends in their area's folder note, not into tasks. Loose ends never hold anything with a date.
- **Map.md.** Rewrite its "Projects and areas" section so it lists what exists now, one line each. Keep it short; it's a map, not an index.
- **No goals yet.** Don't make any goals (`kind: project`) at setup. They come later, when a group of tasks clearly belongs together.

Run `python3 Scripts/check_wiki_links.py` and fix anything it reports.

## 4. Connect Google, if they want to

Everything works without this. Say in plain words what each connection adds, and let them choose:

- **Google Calendar.** "What's on today?" then includes your day.
- **Google Tasks.** A **Phone** list you can type into on your phone while you're out; Claude files whatever's in it at the start of the next session. Also a **To watch** list that the phone's share button can drop links into.

Gmail isn't needed: nothing here reads email. An email that matters gets forwarded to themselves and pasted into `Inbox/`. If their calendar is Outlook, say the briefing can't include it unless a Microsoft connector is available here.

If they want it:
1. Ask which Google account to use, and note it in the Tools section of `Me.md`.
2. Connect through the connectors available in this Claude Code session: the `/mcp` command, or Settings → Connectors in the desktop app. Expect one browser sign-in per connection. Google Tasks may only be available through a connector hub such as Composio. That's a separate service holding the sign-in, so say so plainly before they agree.
3. In Google Tasks, create the **Phone** and **To watch** lists, and tell them to install the Google Tasks app on their phone.
4. Reminders stay in the folder unless they'd rather have them in Google Tasks (or Microsoft To Do, if they live in Outlook and a connector exists). In that case dated reminders go in the default **My Tasks** list.

If a connector isn't available here, say so and move on.

Without Google, phone capture is simple: note it however you already do (Notes, a message to yourself), and paste it in at the next session.

## 5. Brain dump

Ask: "Everything on your mind that needs doing, big or small, one per line. Don't sort it." When they pause, ask "Anything else?" and wait for a no before showing the table.

Then, for each line, propose one of:
- a **task**: which project or area, a priority with a one-line reason, the effort, whether it's a decision, any real deadline, and the day they plan to do it if they have one;
- a **reminder**: the day it's for, linked to its area when it plainly belongs to one (`--project Home`);
- a **To watch** entry: a link or video;
- a **habit**: Loose ends in the area note. If it has no area yet, offer to make one.

People call everything a reminder. The rule: if it takes real work, or has a date someone else set, it's a task, whatever they call it. Designing the invitations for a party is a task; transferring money for it is a reminder. Booking an appointment you keep putting off (dentist, vet) is a task too, low priority if need be. Say so in one line and let them overrule.

An event on a date (a race, an exam, a party) is a reminder on its day, plus a task for anything that must be done for it (enter the race, book the train). It's never a habit. When a line is "book X" or "enter X", ask both dates: when X is (the reminder's day) and the last day to book (the task's `--due`), and record both. A target with a date ("$2k emergency fund by summer") is a task with that deadline, or `someday` if no work has started. Loose ends never hold anything with a date.

Something that repeats (a long run every Sunday) is a habit, or a repeating event in their calendar: tasks and reminders don't repeat. Say so if it comes up.

A choice the owner parks ("nothing to decide right now", "I'll think about it") is still a decision: a task with `--decision --status someday`, the figures in its note. That keeps it on record and out of the daily brief. Never a Loose end. Ask by when it has to be made. If the outside world sets that date (a form, a pension provider), it's the task's `--due`; if not, write it in the note and add a reminder shortly before it, so the choice comes back.

If an item is vague ("the gas safe thing by end of month"), ask what it is before you name it, and whether a letter, email or form is behind it. If there is, ask them to paste it in or send a photo now; if they can't, make "Find the … letter" its own task. Never give a date as a deadline unless they stated it as one, and never add a dependency they didn't state. A half-remembered or guessed deadline ("by end of month", "the VAT is sometime in November") may show in the table marked as a guess, but it goes in the task's note as a guess, not in `--due`: `due` stays empty until the letter or email confirms it.

Ask about any date that isn't certain, and keep the two kinds apart: a deadline someone else set is `--due`; a day they mean to do it is `--when`. Show the proposed list as a table of at most three columns (what, where, when), with "high" or "decision" in the what cell only when it applies; over about twelve rows, show one folder at a time. Apply their corrections. If more items arrive after the table has been shown (often with the corrections), put them in a second short table and get their OK before creating them. Never save an item the owner hasn't seen sorted; "just remind me about all of it" isn't an OK. Then create everything: tasks with `python3 Scripts/tasks.py add ...`, reminders with `add "..." --kind reminder --when <date>`, and the rest where it belongs.

Then add two reminders of your own, and tell them why:
- "Re-read Me.md and fix whatever's drifted", one month from today;
- "What haven't I used? Cut it", two weeks from today. Anything they never touch is worth removing.

## 6. First arrival

1. Run `python3 Scripts/tasks.py sync`, then `python3 Scripts/tasks.py brief`.
2. Start the board: run `python3 Scripts/tasks_board.py serve` in the background, and tell them to open http://127.0.0.1:8765/. Walk them through it in four sentences:
   - the brain-dump box;
   - Today: what they planned for today, deadlines due or late, and anything in progress, with "Start here" on the first row; underneath, "Not planned yet" holds important things with no day yet;
   - Reminders;
   - By project, and Waiting on others for things someone else owes them.

   Say that it runs while this session is open, and that "open the board" in any session brings it back.

   Then let them choose how it looks. Give them http://127.0.0.1:8765/styles: it shows their own board in each of the four styles, on a computer and on a phone. When they pick one, run `python3 Scripts/tasks_board.py style <name>` and ask them to reload the board. Show Your Working is already set, so if they don't mind, move on. Tell them they can change it any time by asking.
3. Explain the two rituals in plain words:
   - At the start of a session, Claude briefs them.
   - At the end, they say "what did we decide?" or "wrap up", and Claude writes down what changed and what's next. When they just stop ("right, done", "that's enough for this morning"), Claude names the wrap-up and offers it in one line before doing it, and ends with the decisions made, not only the next steps.

   They never file anything themselves.
4. Read this folder's path yourself, and tell them in one line what it's in: iCloud Drive, OneDrive, Dropbox, Google Drive, or none of them. Don't ask them; if they don't know, the path does. Then explain the phone:
   - capture goes to the Phone list (step 4), or gets pasted in later;
   - if the path shows the folder syncs to their phone, `Tasks/Board.html` is a read-only copy of the board. If two computers share the folder, ask which one should write that copy, and set `"snapshot_host"` in `vault.json` to its name (run `hostname` on it); otherwise the sync service makes conflict copies of it.
5. Explain backup in one line: it's a folder, so back it up like any other. If the path is in iCloud Drive, OneDrive, Dropbox or Google Drive, it's already copied; if it isn't, say plainly there's no phone copy and no backup yet, and offer one next step. If they ever want a history of every change, it can become a git repo, and Claude will commit at the end of each session.
6. Delete `Inbox/Setup notes.md` and set `"setup": "done"` in `vault.json`.
7. End by saying what to try tomorrow: open a session and say "what's on today?".

## What not to do

- Don't ship rules from anyone else's folder. `CLAUDE.md` grows only when something goes wrong here.
- Don't create an "Ideas" or "Someday" structure in advance. Add a folder when they feel the absence of it.
- Don't put anything in `Me.md` they didn't say.
- Don't set up git or anything that needs an always-on computer. Both are later conversations, if they want them.
