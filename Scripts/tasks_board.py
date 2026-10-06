#!/usr/bin/env python3
"""tasks_board.py — the web board over the vault task database (Tasks/).

Part of the Second Brain template. Run from the vault root:

  python3 Scripts/tasks_board.py serve [--host 127.0.0.1] [--port 8765]
  python3 Scripts/tasks_board.py export            # writes Tasks/Board.html, the read-only snapshot

The server reads and writes task notes only through tasks.py. It listens on the laptop itself unless --host is
given; an always-on machine passes its private-network (e.g. Tailscale) address. Nothing here is meant for the public internet.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tasks as T  # noqa: E402

HTML = Path(__file__).with_name("tasks_board.html")
SNAPSHOT = T.TASKS_DIR / "Board.html"
MARKER = "/*BOARD_DATA*/"
WRITE_LOCK = threading.Lock()                    # one writer at a time: version check, write and sync together


def board_tree(tasks: dict) -> dict:
    """Open tasks grouped venture → open projects (with their open children) + loose tasks. A child whose
    parent is not an open project is loose, so a filter on the page can never hide it."""
    open_ = {n: t for n, t in tasks.items() if t[T.STATUS] in T.OPEN}
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


def task_json(t: dict) -> dict:
    d = {k: v for k, v in t.items() if not k.startswith("_")}
    d["name"] = t["_path"].stem
    d["body"] = t["_body"]
    d["version"] = str(t["_path"].stat().st_mtime_ns)      # a string: the integer exceeds JavaScript's safe range
    d["project_name"] = T.link_name(t["project"]) if t.get("project") else ""
    d["parent_name"] = T.link_name(t["parent"]) if t.get("parent") else ""
    d["decision"] = T.is_decision(t)
    return d


def payload(folder: Path = T.TASKS_DIR, today: date | None = None, vault_name: str | None = None) -> dict:
    today = today or date.today()
    tasks, errors = T.load_tasks(folder)
    v = T.views(tasks, today)
    return {
        "today": today.isoformat(),
        "vault": vault_name or T._config().get("vault_name") or T.VAULT.name,
        "me": T.OWNER,
        "tasks": [task_json(t) for t in tasks.values()],
        "views": {k: [t["_path"].stem for t in rows] for k, rows in v.items()},
        "tree": board_tree(tasks),
        "ventures": sorted({T.link_name(t["project"]) for t in tasks.values() if t.get("project")}),
        "projects": sorted(n for n, t in tasks.items() if t.get("kind") == "project" and t[T.STATUS] in T.OPEN),
        "errors": [f"{p.name}: {e}" for p, e in errors],
    }


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
        if self.path == "/":
            return self._send(200, HTML.read_text(encoding="utf-8"), "text/html")
        if self.path.split("?")[0] == "/api/tasks":
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
            created, errors = [], []
            for line in str(req.get("lines", "")).splitlines():
                if not line.strip():
                    continue
                try:
                    created.append(T.add_task(self.folder, today, line.strip(), inbox=True).stem)
                except T.TaskError as e:
                    errors.append(f"{line.strip()}: {e}")
            return self._send(200, {"created": created, "errors": errors})
        if self.path == "/api/update":
            tasks, _ = T.load_tasks(self.folder)
            t = tasks.get(str(req.get("name")))
            if t is None:
                return self._send(404, {"error": "no such task"})
            if str(t["_path"].stat().st_mtime_ns) != str(req.get("version")):
                return self._send(409, {"error": "changed on disk, reloaded", "task": task_json(t)})
            try:
                T.update_task(self.folder, req["name"], req.get("changes") or {}, today)
            except T.TaskError as e:
                return self._send(400, {"error": str(e)})
            T.sync(self.folder, today, archive=False)  # blocked/todo and the done date; archiving waits for the CLI sync
            tasks, _ = T.load_tasks(self.folder)
            t = tasks.get(req["name"])
            return self._send(200, {"task": task_json(t) if t else None})
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


def _chips(t: dict, today: str) -> str:
    out = []
    if t.get("due"):
        late = t["due"] < today
        out.append(f'<span class="chip {"overdue" if late else ""}">{"overdue " if late else "due "}{_esc(t["due"])}</span>')
    if t.get("priority") == "high":
        out.append('<span class="chip high">high</span>')
    if t.get("effort"):
        out.append(f'<span class="chip {_esc(t["effort"])}">{_esc(t["effort"])}</span>')
    if t.get("decision"):
        out.append('<span class="chip">decision</span>')
    if t.get(T.STATUS) in ("blocked", "doing"):
        out.append(f'<span class="chip">{t[T.STATUS]}</span>')
    if t.get("owner") and t["owner"] != T.OWNER:
        out.append(f'<span class="chip">{_esc(t["owner"])}</span>')
    return "".join(out)


def static_html(data: dict) -> str:
    """The snapshot's lists as plain HTML, for viewers that never run JavaScript (the iOS Files app preview).
    When the page's script does run it replaces this with the interactive board."""
    by = {t["name"]: t for t in data["tasks"]}
    today = data["today"]

    def row(t, sub=False):
        return (f'<div class="task{" sub" if sub else ""}"><input type="checkbox" disabled{" checked" if t[T.STATUS] == "done" else ""}>'
                f'<div class="t"><div>{_esc(t["title"])}</div><div class="meta">{_esc(t.get("project_name"))} · {_chips(t, today)}</div></div></div>')

    def section(title, names):
        rows = [row(by[n]) for n in names if n in by]
        return f'<div class="group">{title}</div>' + ("".join(rows) if rows else '<p class="empty">Nothing here.</p>')

    parts = [section("Today", data["views"]["today"]), section("Decisions", data["views"]["decisions"]),
             section("Waiting on others", data["views"]["waiting"]), section("Inbox", data["views"]["inbox"])]
    board = ['<div class="group">Board</div>']
    for venture, node in data["tree"].items():
        board.append(f'<div class="group">{_esc(venture)}</div>')
        for pr in node["projects"]:
            p = by.get(pr["name"])
            if p:
                board.append(f'<div class="project"><span>▾</span><span class="t">{_esc(p["title"])}</span><span class="count">{len(pr["children"])}</span></div>')
                board += [row(by[n], True) for n in pr["children"] if n in by]
        board += [row(by[n]) for n in node["loose"] if n in by]
    return "".join(parts) + "".join(board)


def export_snapshot(folder: Path = T.TASKS_DIR, today: date | None = None, out: Path = SNAPSHOT,
                    vault_name: str | None = None) -> Path:
    with WRITE_LOCK:
        data = payload(folder, today, vault_name)
    blob = json.dumps(data).replace("</", "<\\/")
    html = (HTML.read_text(encoding="utf-8")
            .replace(MARKER, f"window.BOARD_DATA = {blob};")
            .replace('<main id="main"></main>', f'<main id="main">{static_html(data)}</main>', 1))
    out.write_text(html, encoding="utf-8")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--host", default="127.0.0.1", help="this machine only by default; the mini passes its Tailscale address")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--vault-name", default=None, help="Obsidian vault name for open links (default: vault.json, else the folder name)")
    e = sub.add_parser("export")
    e.add_argument("--vault-name", default=None)
    args = ap.parse_args(argv)
    if args.cmd == "export":
        print("wrote:", export_snapshot(vault_name=args.vault_name).relative_to(T.VAULT))
        return 0
    server = make_server(T.TASKS_DIR, args.host, args.port, args.vault_name)
    print(f"Task board: http://{args.host}:{server.server_address[1]}/  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
