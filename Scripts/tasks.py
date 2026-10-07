#!/usr/bin/env python3
"""tasks.py — operator for the vault task database (Tasks/).

Part of the Second Brain template. Run from the vault root:

Commands (run from anywhere):
  python3 Scripts/tasks.py brief          # arrival rollup
  python3 Scripts/tasks.py sync           # derive blocked, done dates, archive done + dropped
  python3 Scripts/tasks.py add "Title" --project "Acme" [--due 2026-09-24]
        [--priority high|normal|low] [--owner Name] [--parent "Title"] [--after "Title" ...] [--inbox] [--note "text"]
        [--kind project|reminder] [--effort deep|medium|easy] [--decision]
  python3 Scripts/tasks.py list [--project X] [--status Y]

The status field is `task-status` (not `status`, so Obsidian's value suggestions show only task
values, not every `status:` in the vault). STATUS below names the key once; nothing else should spell it.

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
    """vault.json at the vault root: {"owner": "Your name", "vault_name": "Folder name"}. Written by the setup."""
    try:
        import json
        return json.loads((VAULT / "vault.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


OWNER = _config().get("owner") or "Me"            # the person whose tasks these are; others are "waiting on"

STATUS = "task-status"                       # the frontmatter key
FIELDS = ["type", "title", "project", "parent", "depends-on", STATUS, "priority",
          "kind", "effort", "decision", "due", "owner", "created", "updated", "done", "created-by"]
LIST_FIELDS = {"depends-on"}
DATE_FIELDS = {"due", "created", "updated", "done"}
STATUSES = {"inbox", "todo", "blocked", "doing", "done", "someday", "dropped"}
PRIORITIES = {"high", "normal", "low"}
KINDS = {"project", "task", "reminder"}      # project = a goal: a finish line with tasks under it; task = one session or
                                             # one decision; reminder = a nudge on a date, kept out of the work lists
EFFORTS = {"deep", "medium", "easy"}         # deep = a focused block; medium = an ordinary session; easy = minutes
EDITABLE = {"project", "parent", STATUS, "priority", "kind", "effort", "decision", "due", "owner"}
OPEN = {"todo", "blocked", "doing"}          # statuses that count as live work
CLOSED = {"done", "dropped"}                 # satisfy nothing further; dropped archives on the next sync
STALE_DAYS, SOON_DAYS, ARCHIVE_DAYS = 14, 7, 30
STALE_SHOWN = 5                              # the brief lists this many stale tasks and counts the rest

WIKI = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")
NEEDS_QUOTE = re.compile(r'[\[\]:#"\'{}]|^[-?&*!|>%@`]|^\s|\s$')
BAD_FILENAME = re.compile(r'[\\/:*?"<>|#^\[\]]')
CONTROL = re.compile(r"[\x00-\x1f\x7f]")       # a newline in a value would break the frontmatter


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
    keys = FIELDS + [k for k in fm if k not in FIELDS and not k.startswith("_")]
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


def link_to(name) -> str:
    """The wiki link to a task or folder note, by the name it is saved under ("Decide: X" -> [[Decide- X]])."""
    return f"[[{safe_filename(link_name(name))}]]"


def is_decision(t: dict) -> bool:
    return str(t.get("decision")).lower() == "true"


def hierarchy_review(tasks: dict) -> list[str]:
    """Folder > goal (kind: project) > task, no deeper. Only a goal can be a parent. Parents that aren't
    live (archived) are left alone."""
    out = []
    for name, t in tasks.items():
        if not t.get("parent"):
            continue
        pname = link_name(t["parent"])
        parent = tasks.get(pname)
        if parent is None:
            continue
        if t.get("kind") == "project":
            out.append(f"{name}: a goal (kind: project) cannot sit under [[{pname}]]")
        elif parent.get("kind") != "project":
            out.append(f"{name}: parent [[{pname}]] is not a goal (kind: project)")
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
            validate(fm, p)
            fm["_path"], fm["_body"] = p, body
            tasks[p.stem] = fm
        except TaskError as e:
            errors.append((p, str(e)))
    return tasks, errors


def _write(t: dict) -> None:
    clean = {k: v for k, v in t.items() if not k.startswith("_")}
    t["_path"].write_text(serialize(clean, t["_body"]), encoding="utf-8")


def archived_statuses(folder: Path = TASKS_DIR) -> dict[str, str]:
    """{name: status} for the notes in Tasks/Archive/. Unreadable ones are left out."""
    out = {}
    for p in sorted((folder / "Archive").glob("*.md")):
        try:
            fm, _ = parse_frontmatter(p.read_text(encoding="utf-8"))
        except TaskError:
            continue
        out[p.stem] = fm.get(STATUS)
    return out


def deps_state(task: dict, tasks: dict, archived: dict | None = None) -> tuple[bool, list[str]]:
    """(all dependencies done?, [missing dependency names]). A dependency that sync has archived counts
    by its archived status: done unblocks, dropped does not."""
    missing, all_done = [], True
    for d in task.get("depends-on") or []:
        name = link_name(d)
        dep = tasks.get(name)
        status = dep[STATUS] if dep is not None else (archived or {}).get(name)
        if status is None:
            missing.append(name)
        elif status != "done":                # a dropped dependency does not unblock; sync flags it
            all_done = False
    return all_done, missing


def update_task(folder: Path, name: str, changes: dict, today: date, source: str = "board") -> dict:
    """Change EDITABLE fields on one task, validate, log one line, bump `updated`. Raises TaskError."""
    tasks, _ = load_tasks(folder)
    t = tasks.get(name)
    if t is None:
        raise TaskError(f"no task {name!r}")
    bad = set(changes) - EDITABLE
    if bad:
        raise TaskError(f"not editable: {', '.join(sorted(bad))}")
    for k, v in changes.items():
        if isinstance(v, str) and CONTROL.search(v):
            raise TaskError(f"{k}: control characters are not allowed")
    if source == "board" and changes.get(STATUS) == "blocked":
        raise TaskError("blocked is derived from depends-on by sync; set the dependency instead")
    before = {k: t.get(k) for k in changes}
    log = []
    for k, v in changes.items():
        if k in {"project", "parent"}:
            v = link_to(v) if v else None
        elif k == "decision":
            v = "true" if str(v).lower() == "true" else None
        elif v in ("", None):
            v = None
        if t.get(k) == v:
            continue
        log.append(f"{k} {t.get(k) or '—'} → {v or '—'}")
        t[k] = v
    if not log:
        return t
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


def views(tasks: dict, today: date, me: str = OWNER) -> dict:
    """The board's views. Today is by rule: my open tasks that are overdue, due within SOON_DAYS,
    in progress, or high priority and not blocked. Goals (kind: project) and reminders never appear in Today."""
    live = [t for t in tasks.values() if t[STATUS] in OPEN]

    def due(t):
        return _parse_date(t["due"], "due") if t.get("due") else None

    def today_rank(t):
        d = due(t)
        bucket = 0 if d and d < today else 1 if d else 2 if t[STATUS] == "doing" else 3
        return (bucket, t.get("due") or "9999", t["title"])

    mine = [t for t in live if t.get("owner") == me and t.get("kind") not in ("project", "reminder")]
    today_rows = [t for t in mine if (due(t) and due(t) <= today + timedelta(days=SOON_DAYS))
                  or t[STATUS] == "doing" or (t["priority"] == "high" and t[STATUS] != "blocked")]
    return {
        "today": sorted(today_rows, key=today_rank),
        "reminders": sorted((t for t in live if t.get("kind") == "reminder"), key=lambda t: (t.get("due") or "9999", t["title"])),
        "decisions": sorted((t for t in live if is_decision(t)), key=lambda t: (t.get("created") or "", t["title"])),
        "waiting": [t for t in live if t.get("owner") != me] + [t for t in live if t.get("owner") == me and t[STATUS] == "blocked"],
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
    copy of its archived one is removed; one that differs is reported and never archived over it."""
    today = today or date.today()
    if archive:
        for name in in_both(folder):
            live = folder / f"{name}.md"
            if live.read_bytes() == (folder / "Archive" / live.name).read_bytes():
                live.unlink()                     # nothing in it the archive doesn't already hold
    tasks, errors = load_tasks(folder)
    report = {"changed": [], "archived": [], "review": [], "errors": [f"{p.name}: {e}" for p, e in errors]}
    for name in in_both(folder):
        report["review"].append(f"{name}: also in Archive/ (reused name) - compare, keep one")
    report["review"] += hierarchy_review(tasks)
    archived = archived_statuses(folder)
    dropped = {n for n, t in tasks.items() if t[STATUS] == "dropped"} | {n for n, s in archived.items() if s == "dropped"}
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
                if link_name(d) in dropped:
                    report["review"].append(f"{name}: depends on dropped [[{link_name(d)}]]")
        if t[STATUS] in {"todo", "blocked"} and not missing:
            want = "todo" if all_done else "blocked"
            if t[STATUS] != want:
                t[STATUS] = want
                changed = True
        if t[STATUS] == "done" and not t.get("done"):
            t["done"] = today.isoformat()
            changed = True
        if changed:
            t["updated"] = today.isoformat()
            _write(t)
            report["changed"].append(f"{name}: {STATUS}={t[STATUS]} done={t.get('done') or ''}")
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
    today = today or date.today()
    tasks, errors = load_tasks(folder)
    archived = archived_statuses(folder)
    nudges = [t for t in tasks.values() if t[STATUS] in OPEN and t.get("kind") == "reminder"]
    live = [t for t in tasks.values() if t[STATUS] in OPEN and t.get("kind") != "reminder"]
    dated = [t for t in live if t.get("due")]
    return {
        "overdue": sorted((t for t in dated if _parse_date(t["due"], "due") < today), key=lambda t: t["due"]),
        "soon": sorted((t for t in dated if today <= _parse_date(t["due"], "due") <= today + timedelta(days=SOON_DAYS)),
                       key=lambda t: t["due"]),
        "high": [t for t in live if t["priority"] == "high" and t[STATUS] != "blocked" and not t.get("due")
                 and t.get("kind") != "project"],
        "reminders": sorted((t for t in nudges if t.get("due") and _parse_date(t["due"], "due") <= today),
                            key=lambda t: (t["due"], t["title"])),
        "inbox": [t for t in tasks.values() if t[STATUS] == "inbox"],
        "decisions": sorted((t for t in live if is_decision(t)), key=lambda t: (t.get("created") or "", t["title"])),
        "stale": [t for t in live if t.get("updated") and (today - _parse_date(t["updated"], "updated")).days >= STALE_DAYS],
        "unblocked": [t for t in live if t[STATUS] == "blocked" and deps_state(t, tasks, archived) == (True, [])],
        "blocked": [t for t in live if t[STATUS] == "blocked"],
        "errors": [f"{p.name}: {e}" for p, e in errors],
        "in_both": in_both(folder) if folder.is_dir() else [],
        "counts": {s: sum(1 for t in tasks.values() if t[STATUS] == s) for s in sorted(STATUSES)},
    }


def _line(t: dict) -> str:
    if t.get("kind") == "reminder":
        return f"  - {t['title']}  {t.get('due') or ''}".rstrip()
    proj = link_name(t["project"]) if t.get("project") else "—"
    due = f"  due {t['due']}" if t.get("due") else ""
    return f"  - [{t['priority']}] {t['title']}  ({proj}, {t['owner']}){due}"


def format_brief(b: dict, today: date) -> str:
    parts = [f"Task brief — {today.isoformat()}",
             "counts: " + (", ".join(f"{k} {v}" for k, v in b["counts"].items() if v) or "no tasks")]
    sections = [("OVERDUE", "overdue"), ("Reminders for today", "reminders"), (f"Due in {SOON_DAYS} days", "soon"),
                ("High priority, undated, unblocked", "high"), ("Decisions waiting", "decisions"),
                ("To sort", "inbox"),
                ("Newly unblocked — sync will flip to todo", "unblocked"),
                (f"Stale — no change in {STALE_DAYS}+ days", "stale"), ("Blocked", "blocked")]
    rank = {"high": 0, "normal": 1, "low": 2}
    for label, key in sections:
        if b[key]:
            parts.append(f"\n{label} ({len(b[key])})")
            rows = b[key]
            if key == "stale":                      # a long nag list gets ignored: the five that matter most
                rows = sorted(rows, key=lambda t: (rank[t["priority"]], t.get("updated") or ""))[:STALE_SHOWN]
            parts += [_line(t) for t in rows]
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


def add_task(folder: Path, today: date, title: str, project: str | None = None, due: str | None = None,
             priority: str = "normal", owner: str = OWNER, parent: str | None = None,
             after: list[str] | None = None, inbox: bool = False, note: str = "",
             status: str | None = None, kind: str = "task", effort: str | None = None,
             decision: bool = False) -> Path:
    if priority not in PRIORITIES:
        raise TaskError(f"bad priority {priority!r}")
    if kind not in KINDS:
        raise TaskError(f"bad kind {kind!r}")
    if effort is not None and effort not in EFFORTS:
        raise TaskError(f"bad effort {effort!r}")
    if status and status not in STATUSES:
        raise TaskError(f"bad status {status!r}")
    if kind == "reminder" and not due:
        raise TaskError("a reminder needs a date (--due)")
    if due:
        _parse_date(due, "due")
    path = folder / f"{safe_filename(title)}.md"
    if path.exists():
        raise TaskError(f"task already exists: {path.name}")
    fm = {
        "type": "task", "title": title,
        "project": link_to(project) if project else None,
        "parent": link_to(parent) if parent else None,
        "depends-on": [link_to(a) for a in (after or [])],
        STATUS: status or ("inbox" if inbox else "todo"),
        "priority": priority,
        "kind": kind, "effort": effort, "decision": "true" if decision else None,
        "due": due or None, "owner": owner,
        "created": today.isoformat(), "updated": today.isoformat(), "done": None,
        "created-by": "claude",
    }
    body = (note.rstrip() + "\n\n" if note else "") + f"- {today.isoformat()} created"
    folder.mkdir(exist_ok=True)
    path.write_text(serialize(fm, body), encoding="utf-8")
    return path


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
    ap.add_argument("--today", help="override today's date (YYYY-MM-DD), for testing")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("brief")
    sub.add_parser("sync")
    a = sub.add_parser("add")
    a.add_argument("title")
    a.add_argument("--project")
    a.add_argument("--due")
    a.add_argument("--priority", default="normal", choices=sorted(PRIORITIES))
    a.add_argument("--owner", default=OWNER)
    a.add_argument("--parent")
    a.add_argument("--after", action="append", default=[], help="task this one depends on (repeatable)")
    a.add_argument("--inbox", action="store_true", help="unfiled brain dump")
    a.add_argument("--status", choices=sorted(STATUSES), help="override the initial status (e.g. someday)")
    a.add_argument("--note", default="", help="body text")
    a.add_argument("--kind", default="task", choices=sorted(KINDS),
                   help="project = a goal with tasks under it; reminder = a nudge on a date (needs --due)")
    a.add_argument("--effort", choices=sorted(EFFORTS), help="deep | medium | easy")
    a.add_argument("--decision", action="store_true", help="a yes/no call that is yours to make")
    l = sub.add_parser("list")
    l.add_argument("--project")
    l.add_argument("--status", choices=sorted(STATUSES))
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
            out, written = tasks_board.export_snapshot(TASKS_DIR, today)
            print("snapshot:", out.relative_to(VAULT) if written else f"{out.relative_to(VAULT)} (unchanged)")
        except Exception as e:                      # the snapshot is a convenience; sync must still succeed
            print("snapshot: not written:", e)
        return 1 if r["errors"] else 0
    if args.cmd == "add":
        try:
            p = add_task(TASKS_DIR, today, args.title, args.project, args.due, args.priority, args.owner,
                         args.parent, args.after, args.inbox, args.note, args.status,
                         args.kind, args.effort, args.decision)
        except TaskError as e:
            print("ERROR:", e, file=sys.stderr)
            return 1
        print("created:", p.relative_to(VAULT))
        return 0
    if args.cmd == "list":
        for t in list_tasks(TASKS_DIR, args.project, args.status):
            print(f"{t[STATUS]:8} {t['priority']:6} {t.get('due') or '':10} "
                  f"{link_name(t.get('project') or '—'):22} {t['title']}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
