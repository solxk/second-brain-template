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

Who they are:
1. What are you working on or building? (A business, a side business, client work, something you're making. Each becomes a folder in `Projects/`.)
2. What parts of your life need looking after? (Health, money, home, family, the day job, study. Each becomes a folder in `Areas/`. Group related things: gym and sleep are both Health. Make an area only where there will be something in it, a task, a reminder or a habit; the day job often has none.)
3. What would you like to have done a year from now, in a sentence?

How they work:
4. When does your work day start, and when are you sharpest?
5. What usually trips you up? (Starting, finishing, deciding, remembering, saying no.)
6. What do you want from an AI partner: pushing you, keeping you organised, thinking things through with you, doing the admin? Direct or gentle?

Logistics:
7. Where do your calendar, email, tasks and reminders live today? (Google, Outlook, Apple, a notebook, nowhere.)
8. Mac or Windows? Which phone?

Close:
9. Anything about you that an assistant usually gets wrong?

Something with a finish line ("sell the flat", "launch the shop") isn't a folder. It belongs inside the project or area it's part of, and becomes a goal or a task later.

## 2. Write Me.md and get it approved

Write `Me.md` from the notes. It's the owner's file: in their words, first person, and tool-agnostic (no mention of Claude or this folder's mechanics). Include only what they said, and leave out any heading with nothing under it.

The list of projects and areas doesn't go in `Me.md`. It goes into `Map.md` and the folders in step 3. `Me.md` is read every session and Claude can't edit it, so a list kept there would go stale.

Shape:

```markdown
# Me

> Written from the setup interview on <date>. This file is mine. Any AI I use reads it first.

I'm <name>. <One paragraph: what they do and, in a line, what they're juggling.>

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

- **Projects.** Make one folder per thing they're working on or building: `Projects/<Name>/`, with a folder note `Projects/<Name>/<Name>.md`.
  - Frontmatter: `status: active`, `one-liner:`, `created-by: claude`.
  - Sections: **What it is** (two or three sentences from the interview), **Next actions** (containing exactly `![[Tasks.base#Here]]`), **Recently shifted** (one dated line: "set up"), **Loose ends** and **Key links**.
- **Freelancers.** A freelancer's regular clients each get a project folder when each brings its own stream of work. Otherwise make one folder for the freelance business, with clients as tasks. Ask if it isn't obvious.
- **Areas.** Make one folder per part of life they named, `Areas/<Name>/`, with the same folder-note shape.
- **Habits** they mentioned (sleep, gym days) go under Loose ends in their area's folder note, not into tasks.
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

Ask: "Everything on your mind that needs doing, big or small, one per line. Don't sort it."

Then, for each line, propose one of:
- a **task**: which project or area, a priority with a one-line reason, the effort, and whether it's a decision;
- a **reminder**: the day it's for, no folder needed;
- a **To watch** entry: a link or video;
- a **habit**: Loose ends in the area note. If it has no area yet, offer to make one.

Something that repeats (a long run every Sunday) is a habit, or a repeating event in their calendar: tasks and reminders don't repeat. Say so if it comes up.

Ask about any date that isn't certain. Show the proposed list as a table and apply their corrections. Then create everything: tasks with `python3 Scripts/tasks.py add ...`, reminders with `add "..." --kind reminder --due <date>`, and the rest where it belongs.

Then add two reminders of your own, and tell them why:
- "Re-read Me.md and fix whatever's drifted", one month from today;
- "What haven't I used? Cut it", two weeks from today. Anything they never touch is worth removing.

## 6. First arrival

1. Run `python3 Scripts/tasks.py sync`, then `python3 Scripts/tasks.py brief`.
2. Start the board: run `python3 Scripts/tasks_board.py serve` in the background, and tell them to open http://127.0.0.1:8765/. Walk them through it in four sentences:
   - the brain-dump box;
   - Today;
   - Reminders;
   - Board, with Decisions next to it.

   Say that it runs while this session is open, and that "open the board" in any session brings it back.
3. Explain the two rituals in plain words:
   - At the start of a session, Claude briefs them.
   - At the end, they say "what did we decide?" or "wrap up", and Claude writes down what changed and what's next.

   They never file anything themselves.
4. Explain the phone:
   - capture goes to the Phone list (step 4), or gets pasted in later;
   - if the folder syncs to their phone, `Tasks/Board.html` is a read-only copy of the board.
5. Explain backup in one line: it's a folder, so back it up like any other. If it lives in iCloud Drive, OneDrive, Dropbox or Google Drive, it's already copied. If they ever want a history of every change, it can become a git repo, and Claude will commit at the end of each session.
6. Delete `Inbox/Setup notes.md` and set `"setup": "done"` in `vault.json`.
7. End by saying what to try tomorrow: open a session and say "what's on today?".

## What not to do

- Don't ship rules from anyone else's folder. `CLAUDE.md` grows only when something goes wrong here.
- Don't create an "Ideas" or "Someday" structure in advance. Add a folder when they feel the absence of it.
- Don't put anything in `Me.md` they didn't say.
- Don't set up git or anything that needs an always-on computer. Both are later conversations, if they want them.
