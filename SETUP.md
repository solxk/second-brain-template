# SETUP.md

Instructions for Claude. Run this once, the first time the owner says "set me up" (or whenever `Me.md` is missing). The owner reads only `README.md`; everything below is yours to carry out. Work through the steps in order and say which step you're on.

## 0. Check the ground

Before any questions:

- Run `python3 --version`. Needs 3.9 or newer. If it fails on Windows, tell the owner to install Python from python.org with "Add to PATH" ticked, then come back.
- Run `python3 -m unittest Scripts/test_tasks.py Scripts/test_tasks_board.py`. Both should print `OK`.
- Check whether this folder is a git repo (`git status`). If not, run `git init` and commit at the end of setup. Explain in one line that this keeps a history of every change.
- Ask whether Obsidian is installed. It isn't required; the board works without it. If they have it: File → Open folder as vault → this folder. Recommend it once, then move on.

## 1. The interview

About twenty minutes. One question at a time, in plain words, no jargon. Follow up when an answer is thin; move on when it's enough. **Write each answer into `Me.md` as you go** (create it from the shape in section 2 with the first answer), so a crash or a long chat loses nothing.

Who they are:
1. What do you do, and what are you juggling right now? (Job, side projects, family admin, health, study: anything that takes attention. Get a list; these become the first projects and areas.)
2. For each thing on that list: is it something with a finish line, or something ongoing? (Finish line → `Projects/`. Ongoing → `Areas/`.)
3. What's the goal for the next year, if you had to say it in a sentence?

How they work:
4. When does your work day start, and when are you sharpest?
5. What usually trips you up? (Starting, finishing, deciding, remembering, saying no.)
6. What do you want from an AI partner: pushing you, keeping you organised, thinking things through with you, doing the admin? Direct or gentle?

Logistics:
7. Where do your calendar, email, tasks and reminders live today? (Google, Outlook, Apple, a notebook, nowhere.)
8. Mac or Windows? Which phone? Does any computer stay on all day?
9. Which Google account should the system use? (Gmail is simplest. A Hotmail address works for mail, but reminders need Google Tasks, so a Google account is needed regardless.)

Close:
10. Anything about you that an assistant usually gets wrong?

## 2. Write Me.md and get it approved

`Me.md` is the owner's file. Write it in their words, first person, tool-agnostic (no mention of Claude or this folder's mechanics). Shape:

```markdown
# Me

> Written from the setup interview on <date>. This file is mine. Any AI I use reads it first.

I'm <name>. <One paragraph: what they do and what they're juggling.>

## What I'm working on
<One line per project or area, with the finish line or the ongoing nature.>

## Goal
<The one-year sentence.>

## How I work
<Day shape, when they're sharpest, how they like to be worked with.>

## What trips me up
<Their answer, plainly.>

## What I want from an AI partner
<Their answer. Direct or gentle. What to push on, what to leave alone.>
```

Show it to them. Ask them to read it and correct anything. Don't build anything until they say it's right. Then write `vault.json` at the root:

```json
{"owner": "<first name as they'd write it>", "vault_name": "<this folder's name>"}
```

## 3. Build the structure

From the approved `Me.md`:

- One folder per project under `Projects/<Name>/` with a folder note `Projects/<Name>/<Name>.md`: frontmatter `status: active`, `one-liner:`, `created-by: claude`; sections **What it is** (two or three sentences from the interview), **Next actions** containing exactly `![[Tasks.base#Here]]`, **Recently shifted** (one dated line: "set up"), **Loose ends**, **Key links**.
- One folder per area under `Areas/<Name>/` with the same folder note shape.
- Rewrite `Map.md` so its tables list what actually exists now, one line each. Keep it short; it's a map, not an index.
- Leave `Inbox/`, `Resources/`, `Archive/` and `Tasks/` as they are.

Run `python3 Scripts/check_wiki_links.py`. Fix anything it reports.

## 4. Connect Google

Tell the owner, in plain words, that Claude will read their calendar and Gmail and manage a Google Tasks list, and that each connection needs a one-click sign-in from them. Then:

- Connect **Google Calendar**, **Gmail** and **Google Tasks** through the connectors available in this Claude Code session (Settings → Connectors, or the connector prompt the session offers). If a connector isn't available here, say so and skip it; the folder works without it.
- In Google Tasks, create two lists: **Inbox** (anything captured while out) and **To watch** (videos and articles). The default **My Tasks** list holds dated reminders.
- Tell them to install the Google Tasks app on their phone: anything they add to **Inbox** there gets filed at the start of the next session, and the share sheet drops a link straight into **To watch**.

## 5. Brain dump into tasks

Ask: "Everything on your mind that needs doing, big or small, one per line. Don't sort it." Then, for each line, propose: which project or area, priority with a one-line reason, effort, whether it's a decision, and whether it's actually a reminder (then it goes to Google Tasks, not `Tasks/`). Show the proposed list as a table. Apply their corrections. Create the tasks with `python3 Scripts/tasks.py add ...`.

## 6. First arrival

- Run `python3 Scripts/tasks.py sync`, then `python3 Scripts/tasks.py brief`.
- Start the board: `python3 Scripts/tasks_board.py serve` in the background, and tell them to open http://127.0.0.1:8765/. Walk them through it in four sentences: the brain-dump box, Today, Board, Decisions.
- Explain the two rituals in plain words: at the start of a session Claude briefs them; at the end it writes down what changed and what's next. They never file anything themselves.
- Explain the phone: capture goes into the Google Tasks Inbox list; `Tasks/Board.html` is a read-only copy of the board if the folder syncs to their phone.
- Commit: `git add -A && git commit -m "Set up"`.
- End by saying what to try tomorrow: open a session, say "what's on today?".

## What not to do

- Don't ship rules from anyone else's vault. `CLAUDE.md` grows only when something goes wrong here.
- Don't create an "Ideas" or "Someday" structure in advance. Add a folder when they feel the absence of it.
- Don't put anything in `Me.md` they didn't say.
- Don't set up anything that needs an always-on computer. If they have one, that's a later conversation.
