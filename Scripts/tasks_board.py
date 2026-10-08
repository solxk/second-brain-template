#!/usr/bin/env python3
"""tasks_board.py — the web board over the folder's task notes (Tasks/).

Part of the Second Brain template. Run from the folder's top level (where vault.json is):

  python3 Scripts/tasks_board.py serve [--host 127.0.0.1] [--port 8765]
  python3 Scripts/tasks_board.py export            # writes Tasks/Board.html, the read-only snapshot
  python3 Scripts/tasks_board.py style [NAME]      # lists the board styles, or switches to one

The board's look comes from Scripts/board_styles/: styles.json lists the styles, one .css file each.
vault.json "board_style" picks one; /styles on the running board shows the owner's own tasks in every style.

The server reads and writes task notes only through tasks.py. It listens on this computer only, unless --host
says otherwise. Nothing here is meant for the public internet. Starting it while it is already running just says so.

Tasks/Board.html, the read-only copy for a phone, is written by `sync` and `export`. When two computers share
the folder, vault.json "snapshot_host" names the one that writes it; two writers make sync-service conflict copies.
"""
from __future__ import annotations

import argparse
import errno
import http.client
import json
import socket
import sys
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tasks as T  # noqa: E402

HTML = Path(__file__).with_name("tasks_board.html")
SNAPSHOT = T.TASKS_DIR / "Board.html"
MARKER = "/*BOARD_DATA*/"
STYLES_DIR = Path(__file__).with_name("board_styles")
STYLE_MARKER = "<!--BOARD_STYLE-->"
CONFIG = T.VAULT / "vault.json"
WRITE_LOCK = threading.Lock()                    # one writer at a time: version check, write and sync together
EFFORT_WORDS = {"deep": "Deep", "medium": "Medium", "easy": "Quick"}           # easy is stored; "quick" is what it means
DEFAULT_LABELS = {"task": "Task", "project": "Goal", "reminder": "Reminder"}   # what the board calls each kind;
                                                 # vault.json "labels" overrides (e.g. {"project": "Project"})


def board_tree(tasks: dict) -> dict:
    """Open tasks grouped by folder (project or area) → open goals (kind: project, with their open children)
    + loose tasks. A child whose goal is not open is loose, so a filter on the page can never hide it.
    Reminders are left out: they have their own list."""
    open_ = {n: t for n, t in tasks.items() if t[T.STATUS] in T.OPEN and t.get("kind") != "reminder"}
    tree: dict = {}
    for name, t in sorted(open_.items(), key=lambda kv: (T.link_name(kv[1].get("project") or "—"), kv[0])):
        v = T.link_name(t["project"]) if t.get("project") else "—"
        node = tree.setdefault(v, {"projects": [], "loose": []})
        if t.get("kind") == "project":
            kids = sorted(n for n, c in open_.items() if c.get("parent") and T.link_name(c["parent"]) == name)
            node["projects"].append({"name": name, "children": kids})
        else:
            parent = open_.get(T.link_name(t["parent"])) if t.get("parent") else None
            if not (parent and parent.get("kind") == "project"):
                node["loose"].append(name)
    return tree


def task_json(t: dict, today: date | None = None, tasks: dict | None = None, archived: dict | None = None) -> dict:
    d = {k: v for k, v in t.items() if not k.startswith("_")}
    d["name"] = t["_path"].stem
    d["body"] = t["_body"]
    d["version"] = str(t["_path"].stat().st_mtime_ns)      # a string: the integer exceeds JavaScript's safe range
    d["project_name"] = T.link_name(t["project"]) if t.get("project") else ""
    d["parent_name"] = T.link_name(t["parent"]) if t.get("parent") else ""
    d["decision"] = T.is_decision(t)
    d["mine"] = T.is_me(t.get("owner")) or t.get("kind") == "reminder"
    d["carried"] = T.carried_days(t, today or date.today())   # the page reads "Carried N days"
    d["waiting-on"] = T.watch_parties(t)
    held = T.open_dependencies(t, tasks or {}, archived) if tasks is not None else []
    d["held_by"] = [{"name": h["_path"].stem, "title": h["title"], "status": h[T.STATUS]} for h in held]   # "Waiting on: X"
    return d


def payload(folder: Path = T.TASKS_DIR, today: date | None = None, vault_name: str | None = None,
            labels: dict | None = None) -> dict:
    today = today or date.today()
    if labels is None:
        labels = T._config().get("labels") or {}
    tasks, errors = T.load_tasks(folder)
    archived, _ = T.load_tasks(folder / "Archive")
    v = T.views(tasks, today)
    return {
        "today": today.isoformat(),
        "vault": vault_name or T._config().get("vault_name") or T.VAULT.name,
        "me": T.OWNER,
        "tasks": [task_json(t, today, tasks, archived) for t in tasks.values()],
        "views": {k: [t["_path"].stem for t in rows] for k, rows in v.items()},
        "tree": board_tree(tasks),
        "labels": {**DEFAULT_LABELS, **labels},
        "folders": sorted({T.link_name(t["project"]) for t in tasks.values() if t.get("project")}),
        "projects": sorted(n for n, t in tasks.items() if t.get("kind") == "project" and t[T.STATUS] in T.OPEN),
        "errors": [f"{p.name}: {e}" for p, e in errors],
    }


def styles() -> dict:
    """styles.json: {"default": name, "styles": {name: {"label", "blurb", "fonts", ...options for the page}}}.
    A style counts only if its .css file is there too."""
    data = json.loads((STYLES_DIR / "styles.json").read_text(encoding="utf-8"))
    data["styles"] = {k: v for k, v in data["styles"].items() if (STYLES_DIR / f"{k}.css").is_file()}
    return data


def chosen_style(name: str | None = None) -> str:
    """The style to show: `name` if it exists, else vault.json's "board_style", else the default."""
    known = styles()
    for candidate in (name, T._config().get("board_style")):
        if candidate in known["styles"]:
            return candidate
    return known["default"]


def style_block(name: str) -> str:
    """What replaces STYLE_MARKER: the style's fonts, its CSS, and its options for the page's script."""
    meta = styles()["styles"][name]
    css = (STYLES_DIR / f"{name}.css").read_text(encoding="utf-8").replace("</", "<\\/")
    options = {k: v for k, v in meta.items() if k not in ("label", "blurb", "fonts")}
    options["name"] = name
    fonts = ""
    if meta.get("fonts"):
        fonts = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
                 '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
                 f'<link rel="stylesheet" href="{_esc(meta["fonts"])}">\n')
    return f'{fonts}<style id="board-style">\n{css}</style>\n<script>window.BOARD_STYLE = {json.dumps(options)};</script>'


def page(name: str | None = None) -> str:
    return HTML.read_text(encoding="utf-8").replace(STYLE_MARKER, style_block(chosen_style(name)), 1)


def styles_page() -> str:
    """Every style side by side, each showing the owner's own board, so they can pick one."""
    known = styles()
    current = chosen_style()
    cards = []
    for name, meta in known["styles"].items():
        tag = " · in use" if name == current else ""
        cards.append(f'''<section><header><h2>{_esc(meta["label"])}<small>{tag}</small></h2><p>{_esc(meta["blurb"])}</p></header>
<div class="frames"><div class="desk"><iframe src="/?style={name}" title="{_esc(meta["label"])} on a computer" loading="lazy"></iframe></div>
<div class="phone"><iframe src="/?style={name}" title="{_esc(meta["label"])} on a phone" loading="lazy"></iframe></div></div>
<p class="say">To choose it, tell Claude: <b>use {_esc(meta["label"])}</b></p></section>''')
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Board styles</title><style>
body{{margin:0;background:#EEEEEA;color:#1d1d1b;font:16px/1.45 -apple-system,"Segoe UI",system-ui,sans-serif}}
main{{max-width:1500px;margin:0 auto;padding:32px 20px 64px}} h1{{margin:0;font-size:32px}} main>p{{margin:6px 0 28px;color:#5f5f5a}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,660px),1fr));gap:24px}}
section{{background:#fff;border:1px solid #deded8;border-radius:14px;padding:20px;min-width:0}} h2{{margin:0;font-size:20px}} h2 small{{color:#5f5f5a;font-weight:500;font-size:14px}}
header p{{margin:4px 0 16px;color:#5f5f5a;font-size:15px}} .frames{{display:flex;gap:14px;align-items:flex-start;overflow:hidden}}
.desk{{flex:none;width:480px;height:330px;overflow:hidden;border:1px solid #deded8;border-radius:8px}} .desk iframe{{width:1280px;height:880px;border:0;transform:scale(.375);transform-origin:0 0}}
.phone{{flex:none;width:146px;height:316px;overflow:hidden;border:1px solid #deded8;border-radius:14px}} .phone iframe{{width:390px;height:844px;border:0;transform:scale(.375);transform-origin:0 0}}
.say{{margin:14px 0 0;font-size:15px}} iframe{{pointer-events:none}}
</style></head><body><main><h1>Pick a style for your board</h1><p>Each one shows your own tasks. The style only changes how the board looks; your tasks stay the same.</p>
<div class="grid">{"".join(cards)}</div></main></body></html>'''


def set_style(name: str, config: Path = CONFIG) -> str:
    """Record the owner's choice in vault.json. Returns the style's label; raises ValueError for an unknown name."""
    known = styles()["styles"]
    match = next((k for k, v in known.items() if name.lower() in (k, v["label"].lower())), None)
    if match is None:
        raise ValueError(f"no style called {name!r}. The styles are: " + ", ".join(f"{k} ({v['label']})" for k, v in known.items()))
    data = json.loads(config.read_text(encoding="utf-8")) if config.is_file() else {}
    data["board_style"] = match
    config.write_text(json.dumps(data) + "\n", encoding="utf-8")
    return known[match]["label"]


class Handler(BaseHTTPRequestHandler):
    folder: Path = T.TASKS_DIR
    vault_name: str | None = None
    allowed_hosts: set = set()                   # filled by make_server once the port is known

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").strip().lower()
        if host in self.allowed_hosts:
            return True
        self._send(421, {"error": "wrong Host header"})       # DNS rebinding or a foreign page: not for us
        return False

    def _send(self, code: int, body, ctype: str = "application/json") -> None:
        data = (json.dumps(body) if not isinstance(body, str) else body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if not self._host_ok():
            return
        url = urlsplit(self.path)
        if url.path == "/":
            return self._send(200, page((parse_qs(url.query).get("style") or [None])[0]), "text/html")
        if url.path == "/styles":
            return self._send(200, styles_page(), "text/html")
        if url.path == "/api/tasks":
            return self._send(200, payload(self.folder, vault_name=self.vault_name))
        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        if not self._host_ok():
            return
        if not (self.headers.get("Content-Type") or "").lower().startswith("application/json"):
            return self._send(415, {"error": "send application/json"})   # forces a CORS preflight, which is never granted
        n = int(self.headers.get("Content-Length") or 0)
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "bad JSON"})
        with WRITE_LOCK:
            self._write(req)

    def _write(self, req: dict) -> None:
        today = date.today()
        if self.path == "/api/add":
            created, rejected = [], []                # rejected keeps each line as typed, so the page can put it back
            for line in str(req.get("lines", "")).splitlines():
                if not line.strip():
                    continue
                try:
                    created.append(T.add_task(self.folder, today, line.strip(), inbox=True).stem)
                except T.TaskError as e:
                    rejected.append({"line": line, "error": str(e)})
            return self._send(200, {"created": created, "rejected": rejected})
        if self.path == "/api/update":
            tasks, _ = T.load_tasks(self.folder)
            t = tasks.get(str(req.get("name")))
            if t is None:
                return self._send(404, {"error": "no such task"})
            if str(t["_path"].stat().st_mtime_ns) != str(req.get("version")):
                return self._send(409, {"error": "changed on disk, reloaded", "task": task_json(t, today)})
            try:
                T.update_task(self.folder, req["name"], req.get("changes") or {}, today, note=str(req.get("note") or ""))
            except T.TaskError as e:
                return self._send(400, {"error": str(e)})
            T.sync(self.folder, today, archive=False)  # blocked/todo and the done date; archiving waits for the CLI sync
            tasks, _ = T.load_tasks(self.folder)
            t = tasks.get(req["name"])
            return self._send(200, {"task": task_json(t, today) if t else None})
        self._send(404, {"error": "not found"})

    def log_message(self, *args) -> None:           # keep the terminal quiet
        pass


def make_server(folder: Path, host: str, port: int, vault_name: str | None) -> ThreadingHTTPServer:
    handler = type("BoardHandler", (Handler,), {"folder": folder, "vault_name": vault_name})
    server = ThreadingHTTPServer((host, port), handler)
    bound = server.server_address[1]
    handler.allowed_hosts = {f"{h}:{bound}" for h in ("127.0.0.1", "localhost", "[::1]", host.lower())}
    return server


def _esc(s) -> str:
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _short(iso: str) -> str:
    try:
        d = date.fromisoformat(iso)
        return f"{d.day} {d:%b}"
    except ValueError:
        return iso


def _chips(t: dict, today: str) -> str:
    out = []
    if t.get("kind") == "reminder":
        day = t.get("when") or t.get("due")
        if day:
            out.append(f'<span class="chip {"overdue" if day < today else ""}">{"Overdue · " if day < today else ""}{_esc(_short(day))}</span>')
        return "".join(out)
    if t.get("due"):
        late = t["due"] < today
        out.append(f'<span class="chip {"overdue" if late else ""}">{"Late · deadline " if late else "Deadline "}{_esc(_short(t["due"]))}</span>')
    if t.get("when"):
        out.append(f'<span class="chip">{"Carried" if t["when"] < today else "Planned"} {_esc(_short(t["when"]))}</span>')
    if t.get("priority") == "high":
        out.append('<span class="chip high">High priority</span>')
    if t.get("decision"):
        out.append('<span class="chip decision">Decision</span>')
    if t.get(T.STATUS) == "doing":
        out.append('<span class="chip doing">Doing</span>')
    if t.get("held_by"):
        out.append(f'<span class="chip">Waiting on: {_esc(t["held_by"][0]["title"])}</span>')
    if t.get("effort"):
        out.append(f'<span class="chip {_esc(t["effort"])}">{_esc(EFFORT_WORDS.get(t["effort"], t["effort"]))}</span>')
    if t.get("owner") and not t.get("mine"):
        out.append(f'<span class="chip">Whose move: {_esc(t["owner"])}</span>')
    return "".join(out)


def static_html(data: dict) -> str:
    """The snapshot's lists as plain HTML, for viewers that never run JavaScript (the iOS Files app preview).
    When the page's script does run it replaces this with the interactive board."""
    by = {t["name"]: t for t in data["tasks"]}
    today = data["today"]

    def row(t, sub=False, start=False):
        mark = '<span class="start">Start here</span> ' if start else ""
        return (f'<div class="task{" sub" if sub else ""}"><input type="checkbox" disabled{" checked" if t[T.STATUS] == "done" else ""}>'
                f'<div class="t"><div>{mark}{_esc(t["title"])}</div><div class="meta">{_esc(t["project_name"]) + " · " if t.get("project_name") else ""}{_chips(t, today)}</div></div></div>')

    def section(title, names, start=False):
        rows = [row(by[n], start=start and i == 0) for i, n in enumerate(n for n in names if n in by)]
        return f'<div class="group">{title}</div>' + ("".join(rows) if rows else '<p class="empty">Nothing here.</p>')

    v = data["views"]
    parts = [section("Today", v["today"], start=True), section("Not planned yet", v["unplanned"]),
             section("Reminders", v["reminders"]), section("Waiting on others", v["waiting"]),
             section("On hold", v["onhold"]), section("To sort", v["inbox"])]
    board = ['<div class="group">By project</div>']
    for folder, node in data["tree"].items():
        board.append(f'<div class="group">{_esc(folder)}</div>')
        for pr in node["projects"]:
            p = by.get(pr["name"])
            if p:
                board.append(f'<div class="project"><span>▾</span><span class="t">{_esc(p["title"])}</span><span class="count">{len(pr["children"])}</span></div>')
                board += [row(by[n], True) for n in pr["children"] if n in by]
        board += [row(by[n]) for n in node["loose"] if n in by]
    return "".join(parts) + "".join(board)


def snapshot_host() -> str:
    """vault.json "snapshot_host": the one computer that writes Tasks/Board.html; empty means any computer."""
    return str(T._config().get("snapshot_host") or "").strip()


def is_snapshot_host(name: str | None = None) -> bool:
    """True when this computer may write the snapshot: no snapshot_host is set (one computer), or this is it.
    Two computers on one synced folder both writing it make conflict copies."""
    want = snapshot_host()
    if not want:
        return True
    host = (socket.gethostname() if name is None else name).split(".")[0].lower()
    return host == want.split(".")[0].lower()


def export_snapshot(folder: Path = T.TASKS_DIR, today: date | None = None, out: Path = SNAPSHOT,
                    vault_name: str | None = None) -> tuple[Path, bool]:
    """Write the snapshot, only when it differs from the one on disk (a sync service then has nothing to
    copy). Returns (path, written)."""
    with WRITE_LOCK:
        data = payload(folder, today, vault_name)
    blob = json.dumps(data).replace("</", "<\\/")
    html = (page()
            .replace(MARKER, f"window.BOARD_DATA = {blob};")
            .replace('<main id="main"></main>', f'<main id="main">{static_html(data)}</main>', 1))
    if out.is_file() and out.read_text(encoding="utf-8") == html:
        return out, False
    out.write_text(html, encoding="utf-8")
    return out, True


def board_running(host: str, port: int) -> bool:
    """True if a task board already answers on host:port."""
    try:
        c = http.client.HTTPConnection(host, port, timeout=2)
        c.request("GET", "/")
        r = c.getresponse()
        ok = r.status == 200 and b"<title>Tasks</title>" in r.read()
        c.close()
        return ok
    except OSError:
        return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="start the board")
    s.add_argument("--host", default="127.0.0.1", help="this computer only (the default)")
    s.add_argument("--port", type=int, default=8765, help="the port to listen on (default 8765)")
    s.add_argument("--vault-name", default=None, help="Obsidian vault name for open links (default: vault.json, else the folder name)")
    e = sub.add_parser("export", help="write Tasks/Board.html, the read-only copy for a phone")
    e.add_argument("--vault-name", default=None, help="Obsidian vault name for open links")
    e.add_argument("--force", action="store_true", help="write it even though vault.json's snapshot_host names another computer")
    st = sub.add_parser("style", help="list the board styles, or switch to one")
    st.add_argument("name", nargs="?", help="the style to switch to, by name or label")
    args = ap.parse_args(argv)
    if args.cmd == "style":
        if not args.name:
            current = chosen_style()
            for k, v in styles()["styles"].items():
                print(f"{'*' if k == current else ' '} {k:<8} {v['label']}: {v['blurb']}")
            return 0
        try:
            label = set_style(args.name)
        except ValueError as err:
            print(err)
            return 1
        if is_snapshot_host():
            export_snapshot()
        print(f"Board style: {label}. Reload the board to see it.")
        return 0
    if args.cmd == "export":
        if not (args.force or is_snapshot_host()):
            print(f"snapshot: skipped, only {snapshot_host()} writes Tasks/Board.html; --force for a one-off")
            return 0
        out, written = export_snapshot(vault_name=args.vault_name)
        print("wrote:" if written else "unchanged:", out.relative_to(T.VAULT))
        return 0
    url = f"http://{args.host}:{args.port}/"
    if board_running(args.host, args.port):          # checked before binding: Windows lets a second server share the port
        print(f"Task board already running: {url}")
        return 0
    try:
        server = make_server(T.TASKS_DIR, args.host, args.port, args.vault_name)
    except OSError as e:
        if e.errno not in (errno.EADDRINUSE, getattr(errno, "WSAEADDRINUSE", None)):
            raise
        print(f"Port {args.port} is taken by something else. Start the board on another one: --port {args.port + 1}")
        return 1
    print(f"Task board: http://{args.host}:{server.server_address[1]}/  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
