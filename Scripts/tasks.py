#!/usr/bin/env python3
"""tasks.py — keeps the folder's task notes (Tasks/): adds them, changes them, checks them, and lists them.

Part of the Second Brain template. Run every command from the folder's top level (where vault.json is):

  python3 Scripts/tasks.py brief          # what's on: Today, reminders, decisions, waits, things to sort
  python3 Scripts/tasks.py sync           # work out blocked tasks and done dates, archive done and dropped tasks
  python3 Scripts/tasks.py add "Title" --project "Acme" [--due 2026-09-24] [--when 2026-09-20]
        [--priority high|normal|low] [--owner Name] [--parent "Goal title"] [--after "Title" ...] [--inbox] [--note "text"]
        [--kind project|reminder] [--effort deep|medium|easy] [--decision]
        [--waiting-on "Dan"] [--expecting "the quote"] [--chase-after 2026-10-14]
  python3 Scripts/tasks.py set "Title or file name" [--when 2026-10-07] [--status done] ...
        [--decision] [--waiting-on x] [--expecting y] [--chase-after d] [--chased] [--clear-watch] [--clear when]
        [--note "what happened"] [--source claude]
  python3 Scripts/tasks.py list [--project X] [--status Y]

Two dates, never mixed: `due` is a real deadline someone else set; `when` is the day you plan to do it
(a reminder's day is its `when`). Tasks change only through `set` or the board, so every change is logged.

The status field is `task-status` (not `status`, so Obsidian's value suggestions show only task values,
not every `status:` in the folder). STATUS below names the key once; nothing else should spell it.

Frontmatter is parsed here without PyYAML (not installed). Only the shapes this
script writes are supported: scalars, quoted strings, empty values, inline lists
and block lists. Anything else is reported as malformed, never skipped silently.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1]
TASKS_DIR = VAULT / "Tasks"


def _config() -> dict:
    """vault.json at the folder's top level: {"owner": "Your name", "vault_name": "Folder name", ...}. Written by the setup."""
    try:
        import json
        return json.loads((VAULT / "vault.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def platform_key(platform: str | None = None) -> str:
    """This kind of computer, as vault.json's "python" names it: "darwin" (Mac), "windows" or "linux"."""
    p = (platform or sys.platform).lower()
    if p.startswith("win") or p in ("cygwin", "msys"):
        return "windows"
    return "linux" if p.startswith("linux") else p


def python_command(config: dict | None = None, platform: str | None = None) -> str | None:
    """The Python command vault.json records for this kind of computer. A folder shared by two computers
    syncs vault.json between them, so "python" is kept per platform: {"darwin": "python3", "windows": "python"}.
    The old single string ("python3") is still read. None when nothing is recorded for this platform: then
    find it again (python3, python, py) and record it under this platform's key."""
    v = (_config() if config is None else config).get("python")
    if isinstance(v, str):
        return v.strip() or None
    if isinstance(v, dict):
        found = v.get(platform_key(platform))
        return found.strip() if isinstance(found, str) and found.strip() else None
    return None


OWNER = _config().get("owner") or "Me"            # the person whose tasks these are; others are waited on

STATUS = "task-status"                       # the frontmatter key
FIELDS = ["type", "title", "project", "parent", "depends-on", STATUS, "priority",
          "kind", "effort", "decision", "due", "when", "owner", "created", "updated", "done", "created-by"]
WATCH_FIELDS = ["waiting-on", "expecting", "chase-after"]   # optional; only tasks waiting on someone outside carry them
CHASE_DAYS = 7                                              # a watch with no chase date gets one a week out
CLAUDE = "Claude"                                           # the owner on tasks Claude runs: its own view, never Waiting on others
LIST_FIELDS = {"depends-on"}
DATE_FIELDS = {"due", "when", "created", "updated", "done", "chase-after"}   # due = a real deadline; when = the day you plan to do it
STATUSES = {"inbox", "todo", "blocked", "doing", "done", "someday", "dropped"}
PRIORITIES = {"high", "normal", "low"}
KINDS = {"project", "task", "reminder"}      # project = a goal: a finish line with tasks under it; task = one session or
                                             # one decision; reminder = a nudge on a day (its `when`), kept out of the work lists
EFFORTS = {"deep", "medium", "easy"}         # deep = a focused block; medium = an ordinary session; easy = minutes
EDITABLE = {"project", "parent", STATUS, "priority", "kind", "effort", "decision", "due", "when", "owner",
            "waiting-on", "expecting", "chase-after"}
OPEN = {"todo", "blocked", "doing"}          # statuses that count as live work
CLOSED = {"done", "dropped"}                 # satisfy nothing further; dropped archives on the next sync
NEEDS_DEPS_DONE = {"todo", "doing"}          # statuses a task cannot take while a dependency is still open
STALE_DAYS, SOON_DAYS = 14, 7
ARCHIVE_DAYS = 7                             # done tasks move to Tasks/Archive/ a week after they're done
STALE_SHOWN = 5                              # the brief lists this many untouched tasks and counts the rest
REMINDER_AHEAD = 2                           # the brief shows a reminder from this many days before its day
REMINDER_SKIP = {"priority": "normal", "effort": None, "decision": None, "parent": None, "depends-on": [], "due": None,
                 "owner": None}             # a reminder is saved without these when they hold nothing; load puts them back

WIKI = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")
NEEDS_QUOTE = re.compile(r'[\[\]:#"\'{}]|^[-?&*!|>%@`]|^\s|\s$')
BAD_FILENAME = re.compile(r'[\\/:*?"<>|#^\[\]]')
CONTROL = re.compile(r"[\x00-\x1f\x7f]")       # a newline in a value would break the frontmatter
LOG_LINE = re.compile(r"^- (\d{4}-\d{2}-\d{2})\s+(\S+)", re.M)
WHEN_CHANGE = re.compile(r"\bwhen\b([^;\n]*?)(?:→|->)")   # a when change in a log line; group 1 holds the old value
ISO_DAY = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
BULK_SOURCES = {"migration"}      # one-off rewrites of every task: they say nothing about whether a task moved
LABELS = {"task-status": "status"}   # how a field reads in a log line; the key itself stays in the file


class TaskError(Exception):
    pass


# ---------- frontmatter ----------

def _unquote(s: str):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1].replace('\\"', '"')
    return s


def _split_inline_list(inner: str) -> list[str]:
    return [_unquote(m) for m in re.findall(r'"(?:[^"\\]|\\.)*"|[^,]+', inner) if m.strip()]


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        raise TaskError("no frontmatter block")
    end = text.find("\n---", 4)
    if end == -1:
        raise TaskError("unterminated frontmatter")
    block, rest = text[4:end], text[end + 4:]
    body = rest[1:] if rest.startswith("\n") else rest
    body = body.lstrip("\n") if body.strip() else ""
    fm: dict = {}
    key = None
    for line in block.split("\n"):
        if not line.strip():
            continue
        if re.match(r"^\s*- ", line):
            if key is None:
                raise TaskError(f"list item without a key: {line!r}")
            if not isinstance(fm.get(key), list):
                fm[key] = []
            fm[key].append(_unquote(line.split("- ", 1)[1]))
            continue
        if ":" not in line or line.startswith(" "):
            raise TaskError(f"unparseable line: {line!r}")
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        if val == "":
            fm[key] = None
        elif val == "[]":
            fm[key] = []
        elif val.startswith("[") and val.endswith("]"):
            fm[key] = _split_inline_list(val[1:-1])
        else:
            fm[key] = _unquote(val)
    return fm, body


def _quote(v) -> str:
    s = str(v)
    if NEEDS_QUOTE.search(s):
        return '"' + s.replace('"', '\\"') + '"'
    return s


def serialize(fm: dict, body: str) -> str:
    keys = FIELDS + [k for k in WATCH_FIELDS if k in fm] + \
        [k for k in fm if k not in FIELDS and k not in WATCH_FIELDS and not k.startswith("_")]
    if fm.get("kind") == "reminder":             # a nudge is a title and a day, not a wall of blanks
        keys = [k for k in keys if not (k in REMINDER_SKIP and fm.get(k) in (REMINDER_SKIP[k], None, "", []))]
    lines = ["---"]
    for k in keys:
        if k not in fm and k not in FIELDS:
            continue
        v = fm.get(k)
        if k in LIST_FIELDS or isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
            else:
                lines.append(f"{k}:")
                lines += [f"  - {_quote(x)}" for x in v]
        elif v is None or v == "":
            lines.append(f"{k}:")
        else:
            lines.append(f"{k}: {_quote(v)}")
    lines.append("---")
    out = "\n".join(lines) + "\n"
    if body.strip():
        out += "\n" + body.rstrip("\n") + "\n"
    return out


# ---------- task model ----------

def _parse_date(s, field: str) -> date:
    try:
        return date.fromisoformat(str(s))
    except ValueError:
        raise TaskError(f"{field} is not an ISO date: {s!r}")


def link_name(link) -> str:
    """'[[Name|alias]]' -> 'Name'. Plain strings pass through."""
    m = WIKI.fullmatch(str(link).strip())
    return m.group(1).strip() if m else str(link).strip()


def link_target(name) -> str:
    """The note name a link should point at: the task's file name, which drops characters files can't hold
    (`Decide: price?` is saved as `Decide- price-.md`, so its links must say [[Decide- price-]])."""
    return safe_filename(link_name(name))


def _find(tasks: dict, name: str):
    """A task by link text. A link typed by hand may keep a title's colon while the file name can't,
    so try the file-name form too."""
    return tasks.get(name) or tasks.get(safe_filename(name))


def is_decision(t: dict) -> bool:
    return str(t.get("decision")).lower() == "true"


def is_me(owner, me: str = OWNER) -> bool:
    """The owner's own task. Names match without regard to case, so `--owner sam` is Sam's."""
    return str(owner or "").strip().casefold() == me.strip().casefold()


def is_claude(owner) -> bool:
    return str(owner or "").strip().casefold() == CLAUDE.casefold()


def watch_parties(t: dict) -> list[str]:
    """`waiting-on` as a list: who or what the task waits on (a person, a company, an address). Accepts a list,
    or one value or a comma-separated value typed by hand in Obsidian. Repeats are dropped, ignoring case."""
    v = t.get("waiting-on")
    if not v:
        return []
    items = v if isinstance(v, list) else str(v).split(",")
    out, seen = [], set()
    for s in (x.strip() for x in items):
        if s and s.casefold() not in seen:
            seen.add(s.casefold())
            out.append(s)
    return out


def waits_outside(t: dict, me: str = OWNER) -> bool:
    """The one definition of waiting: a watch is set (`waiting-on`), or the owner is a named person who is
    neither you nor Claude. The board's Waiting on others, the brief and sync's default chase date all read it.
    Reminders never wait."""
    if t.get("kind") == "reminder":
        return False
    owner = t.get("owner")
    return bool(watch_parties(t)) or bool(owner and not is_me(owner, me) and not is_claude(owner))


def late_chases(tasks: dict, today: date, me: str = OWNER) -> list[dict]:
    """The waiting list cut to the tasks whose chase date is before today, in its order: the most overdue first."""
    return [t for t in views(tasks, today, me)["waiting"]
            if t.get("chase-after") and _parse_date(t["chase-after"], "chase-after") < today]


def last_activity(t: dict) -> date | None:
    """The date of the task's last real log line, so a sync service rewriting files doesn't make old tasks look
    touched. Bulk rewrites (BULK_SOURCES, which touch every task) don't count, or they would hide every untouched
    task at once. No log lines: `updated`, then `created`."""
    days = []
    for m in LOG_LINE.finditer(t.get("_body") or ""):
        if m.group(2).rstrip(":") in BULK_SOURCES:
            continue
        try:
            days.append(date.fromisoformat(m.group(1)))
        except ValueError:
            continue
    if days:
        return max(days)
    for f in ("updated", "created"):
        if t.get(f):
            return _parse_date(t[f], f)
    return None


def carried_days(t: dict, today: date) -> int:
    """Days the task has been carried: since the earliest plan date that arrived while it was still the plan.
    That is the current `when` when it is today or earlier, and the old value X of a logged change
    "- L source: when X → Y" when X is L or earlier (its day came before it was moved). A plan moved before its
    day was never missed, so it does not count; nor does a new value Y on its own: it is the
    current `when` or the X of a later change. Only the when part of a log line is read, so a due change on the
    same line is not. 0 when no plan date has passed."""
    found = []
    if t.get("when"):
        try:
            found.append(date.fromisoformat(str(t["when"])))
        except ValueError:
            pass
    for line in (t.get("_body") or "").splitlines():
        m = LOG_LINE.match(line)
        if not m:
            continue
        try:
            logged = date.fromisoformat(m.group(1))
        except ValueError:
            continue
        for c in WHEN_CHANGE.finditer(line):
            for s in ISO_DAY.findall(c.group(1)):
                try:
                    d = date.fromisoformat(s)
                except ValueError:
                    continue
                if d <= logged:
                    found.append(d)
    passed = [d for d in found if d <= today]
    return (today - min(passed)).days if passed else 0


def is_stale(t: dict, today: date) -> bool:
    a = last_activity(t)
    return a is not None and (today - a).days >= STALE_DAYS


def _show(v) -> str:
    """A field value as it reads in a log line."""
    if isinstance(v, list):
        return ", ".join(v) or "—"
    return "—" if v in (None, "") else str(v)


def hierarchy_review(tasks: dict) -> list[str]:
    """Folder > goal (kind: project) > task, no deeper. Only a goal can be a parent. Parents that aren't
    live (archived) are left alone. A goal whose tasks are all finished is reported, so it gets closed."""
    out = []
    for name, t in tasks.items():
        if not t.get("parent"):
            continue
        pname = link_name(t["parent"])
        parent = _find(tasks, pname)
        if parent is None:
            continue
        if t.get("kind") == "project":
            out.append(f"{name}: a goal (kind: project) cannot sit under [[{pname}]]")
        elif parent.get("kind") != "project":
            out.append(f"{name}: parent [[{pname}]] is not a goal (kind: project)")
    for name, g in tasks.items():
        if g.get("kind") != "project" or g[STATUS] not in OPEN:
            continue
        kids = [t for t in tasks.values() if t.get("parent") and _find({name: g}, link_name(t["parent"]))]
        if kids and all(t[STATUS] in CLOSED for t in kids):
            out.append(f"{name}: every task under this goal is finished - close it?")
    return out


def validate(fm: dict, path: Path) -> None:
    if fm.get("type") != "task":
        raise TaskError("type is not 'task'")
    if not fm.get("title"):
        raise TaskError("missing title")
    if fm.get(STATUS) not in STATUSES:
        raise TaskError(f"bad {STATUS} {fm.get(STATUS)!r}")
    if fm.get("priority") not in PRIORITIES:
        raise TaskError(f"bad priority {fm.get('priority')!r}")
    if fm.get("kind") is not None and fm.get("kind") not in KINDS:
        raise TaskError(f"bad kind {fm.get('kind')!r}")
    if fm.get("effort") is not None and fm.get("effort") not in EFFORTS:
        raise TaskError(f"bad effort {fm.get('effort')!r}")
    if fm.get("decision") not in (None, "true", "false", True, False):
        raise TaskError(f"bad decision {fm.get('decision')!r}")
    for f in DATE_FIELDS:
        if fm.get(f):
            _parse_date(fm[f], f)
    if not isinstance(fm.get("depends-on"), list):
        raise TaskError("depends-on must be a list")


def load_tasks(folder: Path = TASKS_DIR) -> tuple[dict[str, dict], list[tuple[Path, str]]]:
    """Return ({stem: frontmatter+_path+_body}, [(path, error)]). Top level only, not Archive/."""
    tasks, errors = {}, []
    if not folder.is_dir():
        return tasks, errors
    for p in sorted(folder.glob("*.md")):
        if p.stem == folder.name:          # the folder note, Tasks/Tasks.md
            continue
        try:
            fm, body = parse_frontmatter(p.read_text(encoding="utf-8"))
            if fm.get("kind") == "reminder":
                for k, v in REMINDER_SKIP.items():
                    if k not in fm:
                        fm[k] = list(v) if isinstance(v, list) else v
            validate(fm, p)
            fm["_path"], fm["_body"] = p, body
            tasks[p.stem] = fm
        except TaskError as e:
            errors.append((p, str(e)))
    return tasks, errors


def _write(t: dict) -> None:
    clean = {k: v for k, v in t.items() if not k.startswith("_")}
    t["_path"].write_text(serialize(clean, t["_body"]), encoding="utf-8")


def deps_state(task: dict, tasks: dict, archived: dict | None = None) -> tuple[bool, list[str]]:
    """(all dependencies done?, [missing dependency names]). A dependency that is done and has since been
    archived (ARCHIVE_DAYS after done) still counts as done; an archived dropped one does not unblock."""
    missing, all_done = [], True
    for d in task.get("depends-on") or []:
        name = link_name(d)
        dep = _find(tasks, name) or _find(archived or {}, name)
        if dep is None:
            missing.append(name)
        elif dep[STATUS] != "done":           # a dropped dependency does not unblock; sync flags it
            all_done = False
    return all_done, missing


def open_dependencies(task: dict, tasks: dict, archived: dict | None = None) -> list[dict]:
    """The dependencies that still hold a task up, by the rule deps_state and sync use: found (live or
    archived) and not done. A dropped one counts; missing ones are sync's to report."""
    out = []
    for d in task.get("depends-on") or []:
        name = link_name(d)
        dep = _find(tasks, name) or _find(archived or {}, name)
        if dep is not None and dep[STATUS] != "done":
            out.append(dep)
    return out


def update_task(folder: Path, name: str, changes: dict, today: date, source: str = "board",
                note: str = "") -> dict:
    """Change EDITABLE fields on one task, validate, log one line, bump `updated`. Raises TaskError.
    `note` adds free text to the log line, so a skill can record what happened ("title register arrived")
    even when no field changes. Setting `waiting-on` without a chase date gives it one CHASE_DAYS out.
    `{"chased": true}` is not a field: you chased them today, so `chase-after` moves to CHASE_DAYS from today
    (unless a chase-after is given too) and the log line says "chased".
    Refuses todo or doing while a dependency is open (sync would undo it), and dropped without a note."""
    tasks, _ = load_tasks(folder)
    t = tasks.get(name)
    if t is None:
        raise TaskError(f"no task {name!r}")
    changes = dict(changes)
    chased = str(changes.pop("chased", False)).lower() == "true"
    bad = set(changes) - EDITABLE
    if bad:
        raise TaskError(f"not editable: {', '.join(sorted(bad))}")
    for k, v in list(changes.items()) + [("note", note)]:
        vals = v if isinstance(v, list) else [v]
        if any(isinstance(x, str) and CONTROL.search(x) for x in vals):
            raise TaskError(f"{k}: control characters are not allowed")
    if source == "board" and changes.get(STATUS) == "blocked":
        raise TaskError("blocked is derived from depends-on by sync; set the dependency instead")
    new_status = changes.get(STATUS)
    if new_status in NEEDS_DEPS_DONE and new_status != t[STATUS]:
        held = open_dependencies(t, tasks, load_tasks(folder / "Archive")[0])
        if held and held[0][STATUS] == "dropped":   # a dropped dependency never unblocks; only editing depends-on does
            raise TaskError(f"blocked by {held[0]['title']}, which is dropped; remove it from depends-on first")
        if held:                                  # sync would put it straight back to blocked
            raise TaskError(f"blocked by {held[0]['title']}; finish it first")
    if new_status == "dropped" and new_status != t[STATUS] and not note.strip():
        raise TaskError("say why in one line: --note ...")
    before = {k: t.get(k) for k in changes}
    log = []
    for k, v in changes.items():
        if k in {"project", "parent"}:
            v = f"[[{link_target(v)}]]" if v else None
        elif k == "waiting-on":
            v = watch_parties({"waiting-on": v}) or None
        elif k == "decision":
            v = "true" if str(v).lower() == "true" else None
        elif k == "owner" and v and is_me(v):
            v = OWNER                                 # the owner's name as vault.json spells it
        elif v in ("", None):
            v = None
        if t.get(k) == v:
            continue
        log.append(f"{LABELS.get(k, k)} {_show(t.get(k))} → {_show(v)}")
        t[k] = v
    if "waiting-on" in changes and watch_parties(t) and not t.get("chase-after"):
        t["chase-after"] = (today + timedelta(days=CHASE_DAYS)).isoformat()
        log.append(f"chase-after — → {t['chase-after']}")
    if chased:
        if not changes.get("chase-after"):
            t["chase-after"] = (today + timedelta(days=CHASE_DAYS)).isoformat()
        log.append("chased")
    if note.strip():
        log.append(note.strip())
    if not log:
        return t
    for k in WATCH_FIELDS:
        if k in t and not t[k]:
            del t[k]                              # a cleared watch leaves no empty lines behind
    try:
        validate(t, t["_path"])
    except TaskError:
        t.update(before)
        raise
    if t[STATUS] == "done" and not t.get("done"):
        t["done"] = today.isoformat()
    if STATUS in changes and t[STATUS] != "done" and t.get("done"):
        t["done"] = None                          # reopened; otherwise sync flips it straight back
    t["updated"] = today.isoformat()
    t["_body"] = t["_body"].rstrip("\n") + f"\n- {today.isoformat()} {source}: " + "; ".join(log) + "\n"
    _write(t)
    return t


def reminder_day(t: dict):
    """A reminder's day: its `when` (older notes may carry it in `due`)."""
    v = t.get("when") or t.get("due")
    return _parse_date(v, "when") if v else None


def views(tasks: dict, today: date, me: str = OWNER) -> dict:
    """The board's views. Today is the day's plan: your open tasks, never goals or reminders, planned (`when`)
    for today or an earlier day, with a deadline (`due`) today or earlier, or in progress. A blocked task with a
    passed `when` stays; its row shows what holds it up. Order: deadlines due or late first (late first), then
    deep, medium, quick (easy), unsized; in each group the earliest `when` first (carried tasks), then title. The
    page marks row one "Start here". "unplanned" is Not planned yet: your open tasks, not blocked and not on
    Today, with no `when`, that are high priority or have a deadline within SOON_DAYS. A later `when` is a plan,
    so it keeps a task off both until that day; its deadline still puts it on Today on the day.
    "waiting" is Waiting on others: open tasks that wait outside (waits_outside), by chase date (late first; none
    yet last), then title. "onhold" is your open blocked tasks that wait on nothing outside. "claude" is Claude's
    open tasks: high priority first, then deadline, then created. "reminders" are open reminders by day.
    "decisions" (open yes/no calls, oldest first) feeds the brief; the board has no tab for it."""
    live = [t for t in tasks.values() if t[STATUS] in OPEN]
    rank = {"high": 0, "normal": 1, "low": 2}

    def due(t):
        return _parse_date(t["due"], "due") if t.get("due") else None

    def when(t):
        return _parse_date(t["when"], "when") if t.get("when") else None

    def on_today(t):
        d, w = due(t), when(t)
        return bool((w and w <= today) or (d and d <= today) or t[STATUS] == "doing")

    def today_rank(t):
        if due(t) and due(t) <= today:
            return (0, t["due"], t.get("when") or "9999", t["title"])
        effort = {"deep": 1, "medium": 2, "easy": 3}.get(t.get("effort"), 4)
        return (effort, "", t.get("when") or "9999", t["title"])

    work = [t for t in live if t.get("kind") != "reminder"]
    mine = [t for t in work if is_me(t.get("owner"), me) and t.get("kind") != "project"]
    unplanned = [t for t in mine if not on_today(t) and not when(t) and t[STATUS] != "blocked"
                 and (t["priority"] == "high" or (due(t) and due(t) <= today + timedelta(days=SOON_DAYS)))]
    return {
        "today": sorted((t for t in mine if on_today(t)), key=today_rank),
        "unplanned": sorted(unplanned, key=lambda t: (t.get("due") or "9999", t["priority"] != "high", t["title"])),
        "reminders": sorted((t for t in live if t.get("kind") == "reminder"),
                            key=lambda t: ((reminder_day(t) or date.max).isoformat(), t["title"])),
        "decisions": sorted((t for t in work if is_decision(t)), key=lambda t: (t.get("created") or "", t["title"])),
        "waiting": sorted((t for t in work if waits_outside(t, me)), key=lambda t: (t.get("chase-after") or "9999", t["title"])),
        "onhold": sorted((t for t in work if is_me(t.get("owner"), me) and t[STATUS] == "blocked" and not waits_outside(t, me)),
                         key=lambda t: t["title"]),
        "claude": sorted((t for t in work if is_claude(t.get("owner"))),
                         key=lambda t: (rank[t["priority"]], t.get("due") or "9999", t.get("created") or "", t["title"])),
        "inbox": sorted((t for t in tasks.values() if t[STATUS] == "inbox"), key=lambda t: (t.get("created") or "", t["title"])),
        "someday": sorted((t for t in tasks.values() if t[STATUS] == "someday"), key=lambda t: t["title"]),
        "done": sorted((t for t in tasks.values() if t[STATUS] == "done"), key=lambda t: t.get("done") or "", reverse=True),
    }


def in_both(folder: Path = TASKS_DIR) -> list[str]:
    """Names with a live note AND an archived one: a new task reusing an old name, or a copy that came back."""
    archive = folder / "Archive"
    return sorted(p.stem for p in folder.glob("*.md") if (archive / p.name).is_file())


def sync(folder: Path = TASKS_DIR, today: date | None = None, archive: bool = True) -> dict:
    """Derive blocked/todo, done from a done date (and vice versa), refresh `updated` from mtime,
    archive done tasks after ARCHIVE_DAYS and dropped tasks immediately. A live note that is an exact
    copy of its archived one is removed; one that differs is reported and never archived over it.
    An open task that waits outside and has no chase date gets one, CHASE_DAYS after its last activity
    (today when it has none), logged; one already there is never overwritten, so the board's sync after
    every save writes it once."""
    today = today or date.today()
    if archive:
        for name in in_both(folder):
            live = folder / f"{name}.md"
            if live.read_bytes() == (folder / "Archive" / live.name).read_bytes():
                live.unlink()                     # nothing in it the archive doesn't already hold
    tasks, errors = load_tasks(folder)
    archived, _ = load_tasks(folder / "Archive")
    report = {"changed": [], "archived": [], "review": [], "errors": [f"{p.name}: {e}" for p, e in errors]}
    for name in in_both(folder):
        report["review"].append(f"{name}: also in Archive/ (reused name) - compare, keep one")
    report["review"] += hierarchy_review(tasks)
    dropped = {n for n, t in tasks.items() if t[STATUS] == "dropped"}
    for name, t in tasks.items():
        changed = False
        if t.get("done") and t[STATUS] not in CLOSED:
            t[STATUS] = "done"                    # dated done in Obsidian (Bases only offers the date field)
            changed = True
        all_done, missing = deps_state(t, tasks, archived)
        if t[STATUS] in OPEN:                     # closed tasks may point at archived deps; that's fine
            for m in missing:
                report["errors"].append(f"{name}: depends-on [[{m}]] does not exist")
            for d in (t.get("depends-on") or []):
                n = link_name(d)
                if n in dropped or safe_filename(n) in dropped:
                    report["review"].append(f"{name}: depends on dropped [[{n}]]")
                elif _find(tasks, n) is None and (_find(archived, n) or {}).get(STATUS) == "dropped":
                    report["review"].append(f"{name}: depends on dropped [[{n}]] (archived)")   # keep saying so
        if t[STATUS] in {"todo", "blocked"} and not missing:
            want = "todo" if all_done else "blocked"
            if t[STATUS] != want:
                t[STATUS] = want
                changed = True
        if t[STATUS] == "done" and not t.get("done"):
            t["done"] = today.isoformat()
            changed = True
        chase = ""
        if t[STATUS] in OPEN and waits_outside(t) and not t.get("chase-after"):
            t["chase-after"] = chase = ((last_activity(t) or today) + timedelta(days=CHASE_DAYS)).isoformat()
            t["_body"] = t["_body"].rstrip("\n") + f"\n- {today.isoformat()} sync: chase-after → {chase} (default)\n"
            changed = True
        if changed:
            t["updated"] = today.isoformat()
            _write(t)
            report["changed"].append(f"{name}: {STATUS}={t[STATUS]} done={t.get('done') or ''}"
                                     + (f" chase-after={chase} (default)" if chase else ""))
            continue
        mtime = date.fromtimestamp(t["_path"].stat().st_mtime)
        if t.get("updated") and mtime > _parse_date(t["updated"], "updated"):
            t["updated"] = mtime.isoformat()      # edited in Obsidian
            _write(t)
            report["changed"].append(f"{name}: updated -> {mtime}")
    for name, t in tasks.items():
        if not archive:                           # the board derives only; archiving waits for the CLI sync
            break
        old_done = t[STATUS] == "done" and t.get("done") and \
            (today - _parse_date(t["done"], "done")).days >= ARCHIVE_DAYS
        if old_done or t[STATUS] == "dropped":
            archive = folder / "Archive"
            archive.mkdir(exist_ok=True)
            if (archive / t["_path"].name).exists():
                continue                          # reported above; rename would overwrite the archived note
            t["_path"].rename(archive / t["_path"].name)
            report["archived"].append(name + (" (dropped)" if t[STATUS] == "dropped" else ""))
    return report


# ---------- brief ----------

def brief(folder: Path = TASKS_DIR, today: date | None = None) -> dict:
    """The arrival rollup. Its task lists come from views(), so it has no rule of its own: Today (row one is
    "Start here"), Not planned yet, Waiting on others, On hold and Claude's tasks. Around them: reminders due
    within REMINDER_AHEAD days or overdue, open decisions oldest first, things to sort, newly unblocked tasks,
    tasks untouched for STALE_DAYS (counted from the last real log line), names in both Tasks/ and Archive/, and
    malformed files."""
    today = today or date.today()
    tasks, errors = load_tasks(folder)
    archived, _ = load_tasks(folder / "Archive")
    v = views(tasks, today)
    work = [t for t in tasks.values() if t[STATUS] in OPEN and t.get("kind") != "reminder"]
    return {
        "today": v["today"],
        "reminders": [t for t in v["reminders"] if reminder_day(t) and reminder_day(t) <= today + timedelta(days=REMINDER_AHEAD)],
        "unplanned": v["unplanned"],
        "decisions": v["decisions"],
        "waiting": v["waiting"],
        "onhold": v["onhold"],
        "claude": v["claude"],
        "inbox": v["inbox"],
        "unblocked": [t for t in work if t[STATUS] == "blocked" and deps_state(t, tasks, archived) == (True, [])],
        "stale": [t for t in work if t.get("kind") != "project" and is_stale(t, today)],
        "errors": [f"{p.name}: {e}" for p, e in errors],
        "in_both": in_both(folder) if folder.is_dir() else [],
        "counts": {**{s: sum(1 for t in tasks.values() if t[STATUS] == s and t.get("kind") != "reminder")
                      for s in sorted(STATUSES)},
                   "reminders": sum(1 for t in tasks.values() if t[STATUS] in OPEN and t.get("kind") == "reminder")},
    }


def _line(t: dict, today: date, mark: str = "") -> str:
    if t.get("kind") == "reminder":
        d = reminder_day(t)
        late = " (overdue)" if d and d < today else ""
        return f"  - {t['title']}  {d.isoformat() if d else ''}{late}".rstrip()
    proj = link_name(t["project"]) if t.get("project") else "—"
    due = f"  deadline {t['due']}" if t.get("due") else ""
    when = f"  planned {t['when']}" if t.get("when") else ""
    chase = f"  chase after {t['chase-after']}" if t.get("chase-after") else ""
    return f"  - {mark}[{t['priority']}] {t['title']}  ({proj}, {t.get('owner') or '—'}){due}{when}{chase}"


def format_brief(b: dict, today: date) -> str:
    parts = [f"Task brief — {today.isoformat()}",
             "counts: " + (", ".join(f"{k} {v}" for k, v in b["counts"].items() if v or k == "inbox")   # inbox even at 0
                           if any(b["counts"].values()) else "no tasks")]
    sections = [("Today", "today"), (f"Reminders: overdue, today and the next {REMINDER_AHEAD} days", "reminders"),
                ("Not planned yet", "unplanned"),
                ("Decisions waiting, oldest first", "decisions"),
                ("Waiting on others", "waiting"), ("On hold", "onhold"), ("Claude's tasks", "claude"),
                ("To sort", "inbox"), ("Newly unblocked — sync will flip to todo", "unblocked"),
                (f"Untouched for {STALE_DAYS}+ days", "stale")]
    rank = {"high": 0, "normal": 1, "low": 2}
    for label, key in sections:
        if b[key]:
            parts.append(f"\n{label} ({len(b[key])})")
            rows = b[key]
            if key == "stale":                      # a long nag list gets ignored: the five that matter most
                rows = sorted(rows, key=lambda t: (rank[t["priority"]], (last_activity(t) or today).isoformat()))[:STALE_SHOWN]
            parts += [_line(t, today, "Start here: " if key == "today" and i == 0 else "") for i, t in enumerate(rows)]
            if len(rows) < len(b[key]):
                parts.append(f"  … and {len(b[key]) - len(rows)} more")
    if b["in_both"]:
        parts.append(f"\nALSO IN ARCHIVE — a live note and an archived one share a name; compare and keep one ({len(b['in_both'])})")
        parts += [f"  - {n}" for n in b["in_both"]]
    if b["errors"]:
        parts.append("\nMALFORMED — fix these")
        parts += [f"  - {e}" for e in b["errors"]]
    return "\n".join(parts) + "\n"


# ---------- add / list ----------

def safe_filename(title: str) -> str:
    return BAD_FILENAME.sub("-", title).strip()


def resolve(tasks: dict, name: str) -> str:
    """A task's file name, from its file name or its title (a title may hold characters the file name dropped)."""
    if name in tasks:
        return name
    if safe_filename(name) in tasks:
        return safe_filename(name)
    hits = [n for n, t in tasks.items() if t.get("title") == name]
    if len(hits) == 1:
        return hits[0]
    raise TaskError(f"no task {name!r}")


def folder_note(name: str) -> Path | None:
    """The folder note a `project` link points at: Projects/<name>/<name>.md or Areas/<name>/<name>.md."""
    for top in ("Projects", "Areas"):
        p = VAULT / top / name / f"{name}.md"
        if p.is_file():
            return p
    return None


def add_task(folder: Path, today: date, title: str, project: str | None = None, due: str | None = None,
             priority: str = "normal", owner: str = OWNER, parent: str | None = None,
             after: list[str] | None = None, inbox: bool = False, note: str = "",
             status: str | None = None, kind: str = "task", effort: str | None = None,
             decision: bool = False, when: str | None = None, waiting_on: list[str] | None = None,
             expecting: str | None = None, chase_after: str | None = None) -> Path:
    if priority not in PRIORITIES:
        raise TaskError(f"bad priority {priority!r}")
    if kind not in KINDS:
        raise TaskError(f"bad kind {kind!r}")
    if effort is not None and effort not in EFFORTS:
        raise TaskError(f"bad effort {effort!r}")
    if status and status not in STATUSES:
        raise TaskError(f"bad status {status!r}")
    for value, field in ((due, "due"), (when, "when"), (chase_after, "chase-after")):
        if value:
            _parse_date(value, field)
    if kind == "reminder":
        if due and not when:
            raise TaskError("a reminder's day is --when, not --due (a deadline is for tasks)")
        if not when:
            raise TaskError("a reminder needs its day: --when YYYY-MM-DD")
        extra = [f for f, v in (("--decision", decision), ("--parent", parent), ("--after", after), ("--effort", effort),
                                ("--waiting-on", waiting_on), ("--due", due)) if v]
        if extra:
            raise TaskError(f"a reminder takes a title and a day; leave out {', '.join(extra)}")
    if parent:
        tasks, _ = load_tasks(folder)
        goal = _find(tasks, link_name(parent))
        if goal is None:
            raise TaskError(f"no goal called {parent!r}")
        if goal.get("kind") != "project":
            raise TaskError(f"{parent!r} is not a goal (kind: project), so nothing can sit under it")
        if kind == "project":
            raise TaskError("a goal cannot sit under another goal")
    path = folder / f"{safe_filename(title)}.md"
    if path.exists():
        raise TaskError(f"task already exists: {path.name}")
    if owner and is_me(owner):
        owner = OWNER                                 # the owner's name as vault.json spells it
    elif owner and is_claude(owner):
        owner = CLAUDE
    fm = {
        "type": "task", "title": title,
        "project": f"[[{link_target(project)}]]" if project else None,
        "parent": f"[[{link_target(parent)}]]" if parent else None,
        "depends-on": [f"[[{link_target(a)}]]" for a in (after or [])],
        STATUS: status or ("inbox" if inbox else "todo"),
        "priority": priority,
        "kind": kind, "effort": effort, "decision": "true" if decision else None,
        "due": due or None, "when": when or None, "owner": None if kind == "reminder" else owner,
        "created": today.isoformat(), "updated": today.isoformat(), "done": None,
        "created-by": "claude",
    }
    parties = watch_parties({"waiting-on": waiting_on})
    if parties:
        fm["waiting-on"] = parties
    if expecting:
        fm["expecting"] = expecting               # kept for a task handed to someone else too, not only a watch
    if waits_outside(fm) or chase_after:
        fm["chase-after"] = chase_after or (today + timedelta(days=CHASE_DAYS)).isoformat()
    body = (note.rstrip() + "\n\n" if note else "") + f"- {today.isoformat()} created"
    folder.mkdir(exist_ok=True)
    path.write_text(serialize(fm, body), encoding="utf-8")
    return path


def format_list(rows: list[dict]) -> str:
    """One line per task. A goal is marked with vault.json's word for it ("goal" unless setup chose another)."""
    goal = ((_config().get("labels") or {}).get("project") or "Goal").lower()
    marks = {"project": f"  ({goal})", "reminder": "  (reminder)"}
    return "".join(f"{t[STATUS]:8} {t['priority']:6} {t.get('due') or '':10} {t.get('when') or '':10} "
                   f"{link_name(t.get('project') or '—'):22} {t['title']}{marks.get(t.get('kind'), '')}\n" for t in rows)


def list_tasks(folder: Path, project: str | None = None, status: str | None = None) -> list[dict]:
    tasks, _ = load_tasks(folder)
    rows = list(tasks.values())
    if project:
        rows = [t for t in rows if t.get("project") and link_name(t["project"]).lower() == project.lower()]
    if status:
        rows = [t for t in rows if t[STATUS] == status]
    order = {"high": 0, "normal": 1, "low": 2}
    return sorted(rows, key=lambda t: (link_name(t.get("project") or "~"), order[t["priority"]], t.get("due") or "9999"))


# ---------- CLI ----------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--today", help="pretend today is this date (YYYY-MM-DD), for testing")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("brief", help="what's on: Today, reminders, decisions, waits, things to sort")
    sub.add_parser("sync", help="work out blocked tasks and done dates; archive done and dropped tasks")
    a = sub.add_parser("add", help="add a task, a goal or a reminder")
    a.add_argument("title", help="what to do, in a few words")
    a.add_argument("--project", help="the project or area folder it belongs to, by name (e.g. Home)")
    a.add_argument("--due", help="a real deadline only, YYYY-MM-DD; for the day you plan to do it, use --when")
    a.add_argument("--when", help="the day you plan to do it (a reminder's day), YYYY-MM-DD; a later day keeps it off Today")
    a.add_argument("--priority", default="normal", choices=sorted(PRIORITIES), help="normal unless there's a reason")
    a.add_argument("--owner", default=OWNER, help=f"whose move it is (default {OWNER}); someone else's puts it under Waiting on others")
    a.add_argument("--parent", help="the goal it sits under, by title")
    a.add_argument("--after", action="append", default=[], help="a task that has to be finished first (repeatable)")
    a.add_argument("--inbox", action="store_true", help="a brain-dump line: To sort, no folder yet")
    a.add_argument("--status", choices=sorted(STATUSES), help="start it somewhere other than To do (e.g. someday)")
    a.add_argument("--note", default="", help="text for the note's body")
    a.add_argument("--kind", default="task", choices=sorted(KINDS),
                   help="project = a goal with tasks under it; reminder = a nudge on a day (needs --when)")
    a.add_argument("--effort", choices=sorted(EFFORTS), help="deep = a focused block, medium = an ordinary session, easy = minutes")
    a.add_argument("--decision", action="store_true", help="a yes/no call that is yours to make")
    a.add_argument("--waiting-on", action="append", help="who or what it waits on: a person, a company, an address (repeatable)")
    a.add_argument("--expecting", help="what you're waiting for, in plain words")
    a.add_argument("--chase-after", help=f"YYYY-MM-DD: when silence counts as late; default {CHASE_DAYS} days after --waiting-on")
    s = sub.add_parser("set", help="change one task the way the board does: checked, dated, logged")
    s.add_argument("name", help="the task's file name or title")
    s.add_argument("--status", choices=sorted(STATUSES), help="dropped needs --note saying why")
    s.add_argument("--priority", choices=sorted(PRIORITIES), help="high, normal or low")
    s.add_argument("--effort", choices=sorted(EFFORTS), help="deep, medium or easy")
    s.add_argument("--decision", action="store_true", help="mark it a yes/no call that is yours to make")
    s.add_argument("--due", help="a real deadline, YYYY-MM-DD")
    s.add_argument("--when", help="the day you plan to do it, YYYY-MM-DD")
    s.add_argument("--owner", help="whose move it is")
    s.add_argument("--project", help="the project or area folder, by name")
    s.add_argument("--parent", help="the goal it sits under, by title")
    s.add_argument("--expecting", help="what you're waiting for, in plain words")
    s.add_argument("--chase-after", help="YYYY-MM-DD: when silence counts as late")
    s.add_argument("--waiting-on", action="append", help="who or what it waits on (repeatable)")
    s.add_argument("--chased", action="store_true", help=f"you chased them today: chase-after moves {CHASE_DAYS} days on, logged")
    s.add_argument("--clear-watch", action="store_true", help="remove waiting-on, expecting and chase-after")
    s.add_argument("--clear", action="append", default=[], choices=["due", "when", "parent", "effort", "owner", "decision"],
                   help="empty a field (repeatable)")
    s.add_argument("--note", default="", help="what happened, for the log line")
    s.add_argument("--source", default="claude", help="the word the log line starts with (claude, board, ...)")
    l = sub.add_parser("list", help="every task, one line each")
    l.add_argument("--project", help="only this project or area")
    l.add_argument("--status", choices=sorted(STATUSES), help="only this status")
    args = ap.parse_args(argv)
    today = date.fromisoformat(args.today) if args.today else date.today()

    if args.cmd == "brief":
        print(format_brief(brief(TASKS_DIR, today), today), end="")
        return 0
    if args.cmd == "sync":
        r = sync(TASKS_DIR, today)
        for line in r["changed"]:
            print("changed:", line)
        for name in r["archived"]:
            print("archived:", name)
        for line in r["review"]:
            print("REVIEW:", line)
        for e in r["errors"]:
            print("ERROR:", e)
        if not (r["changed"] or r["archived"] or r["review"] or r["errors"]):
            print("sync: nothing to change")
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import tasks_board
            if not tasks_board.is_snapshot_host():     # one writer only: two machines writing it make conflict copies
                print(f"snapshot: skipped, only {tasks_board.snapshot_host()} writes Tasks/Board.html")
            else:
                out, written = tasks_board.export_snapshot(TASKS_DIR, today)
                print("snapshot:", out.relative_to(VAULT) if written else f"{out.relative_to(VAULT)} (unchanged)")
        except Exception as e:                      # the snapshot is a convenience; sync must still succeed
            print("snapshot: not written:", e)
        return 1 if r["errors"] else 0
    if args.cmd == "add":
        try:
            p = add_task(TASKS_DIR, today, args.title, args.project, args.due, args.priority, args.owner,
                         args.parent, args.after, args.inbox, args.note, args.status,
                         args.kind, args.effort, args.decision, args.when,
                         args.waiting_on, args.expecting, args.chase_after)
        except TaskError as e:
            print("ERROR:", e, file=sys.stderr)
            return 1
        print("created:", p.relative_to(VAULT) if VAULT in p.parents else p)
        if args.project and folder_note(link_name(args.project)) is None:
            print(f"WARNING: no folder note for {args.project!r} (Projects/{args.project}/{args.project}.md or "
                  f"Areas/{args.project}/{args.project}.md). Check the spelling, or create the folder.", file=sys.stderr)
        return 0
    if args.cmd == "set":
        fields = {STATUS: args.status, "priority": args.priority, "effort": args.effort,
                  "decision": "true" if args.decision else None, "due": args.due,
                  "when": args.when, "owner": args.owner, "project": args.project, "parent": args.parent,
                  "waiting-on": args.waiting_on, "expecting": args.expecting, "chase-after": args.chase_after,
                  "chased": True if args.chased else None}
        changes = {k: v for k, v in fields.items() if v is not None}
        for f in args.clear:
            changes[f] = None
        if args.clear_watch:
            changes.update({k: None for k in WATCH_FIELDS})
        if not changes and not args.note.strip():
            print("ERROR: nothing to change", file=sys.stderr)
            return 1
        try:
            tasks, _ = load_tasks(TASKS_DIR)
            name = resolve(tasks, args.name)
            update_task(TASKS_DIR, name, changes, today, source=args.source, note=args.note)
        except TaskError as e:
            print("ERROR:", e, file=sys.stderr)
            return 1
        print("updated:", name)
        return 0
    if args.cmd == "list":
        print(format_list(list_tasks(TASKS_DIR, args.project, args.status)), end="")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
