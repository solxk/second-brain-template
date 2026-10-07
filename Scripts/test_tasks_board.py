"""Tests for tasks_board.py. Run from the vault root:
    python3 -m unittest Scripts/test_tasks_board.py -v
"""
import contextlib
import http.client
import io
import json
import os
import socket
import sys
import tempfile
import threading
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tasks as T  # noqa: E402
import tasks_board as B  # noqa: E402
from test_tasks import make  # noqa: E402


class Payload(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.today = date(2026, 10, 6)

    def test_payload_shape(self):
        make(self.tmp, "Proj", kind="project")
        make(self.tmp, "Do it", parent="[[Proj]]", effort="easy", decision="true", due="2026-10-01")
        p = B.payload(self.tmp, self.today, vault_name="Second Brain")
        self.assertEqual(p["today"], "2026-10-06")
        self.assertEqual(p["vault"], "Second Brain")
        t = {x["name"]: x for x in p["tasks"]}["Do it"]
        self.assertEqual((t["project_name"], t["parent_name"], t["decision"], t["effort"]), ("P", "Proj", True, "easy"))
        self.assertIsInstance(t["version"], str)          # mtime_ns exceeds JS safe-integer range; a number would be rounded
        self.assertEqual(p["views"]["today"], ["Do it"])
        self.assertEqual(p["views"]["decisions"], ["Do it"])
        self.assertEqual(p["folders"], ["P"])
        self.assertEqual(p["projects"], ["Proj"])
        self.assertEqual(p["errors"], [])


class Api(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        make(self.tmp, "Existing")
        self.server = B.make_server(self.tmp, "127.0.0.1", 0, "Vault")
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def call(self, method, path, body=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        c.request(method, path, json.dumps(body) if body is not None else None, {"Content-Type": "application/json"})
        r = c.getresponse()
        data = r.read().decode()
        c.close()
        return r.status, (json.loads(data) if r.getheader("Content-Type", "").startswith("application/json") else data)

    def test_get_page_and_tasks(self):
        status, html = self.call("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("<title>Tasks</title>", html)
        self.assertIn("/*BOARD_DATA*/", html)
        status, p = self.call("GET", "/api/tasks")
        self.assertEqual(status, 200)
        self.assertEqual([t["name"] for t in p["tasks"]], ["Existing"])

    def test_add_lines_become_inbox_tasks(self):
        status, r = self.call("POST", "/api/add", {"lines": "Buy a new mouse\n\n   \nCall the bank: ask about fees\n"})
        self.assertEqual(status, 200)
        self.assertEqual(r["created"], ["Buy a new mouse", "Call the bank- ask about fees"])
        fm, _ = T.parse_frontmatter((self.tmp / "Buy a new mouse.md").read_text())
        self.assertEqual(fm[T.STATUS], "inbox")

    def test_add_duplicate_line_reports_error(self):
        status, r = self.call("POST", "/api/add", {"lines": "Existing\nFresh one"})
        self.assertEqual(status, 200)
        self.assertEqual(r["created"], ["Fresh one"])
        self.assertEqual(len(r["errors"]), 1)
        self.assertIn("Existing", r["errors"][0])

    def test_update_changes_field_and_runs_sync(self):
        _, p = self.call("GET", "/api/tasks")
        version = p["tasks"][0]["version"]
        status, r = self.call("POST", "/api/update", {"name": "Existing", "version": version,
                                                       "changes": {T.STATUS: "done"}})
        self.assertEqual(status, 200)
        self.assertEqual(r["task"][T.STATUS], "done")
        self.assertTrue(r["task"]["done"])
        self.assertNotEqual(r["task"]["version"], version)

    def test_update_stale_version_refused(self):
        status, r = self.call("POST", "/api/update", {"name": "Existing", "version": "1",
                                                       "changes": {"priority": "high"}})
        self.assertEqual(status, 409)
        self.assertEqual(r["task"]["priority"], "normal")
        fm, _ = T.parse_frontmatter((self.tmp / "Existing.md").read_text())
        self.assertEqual(fm["priority"], "normal")

    def test_update_bad_value_is_400_and_unknown_is_404(self):
        _, p = self.call("GET", "/api/tasks")
        version = p["tasks"][0]["version"]
        status, r = self.call("POST", "/api/update", {"name": "Existing", "version": version, "changes": {"effort": "huge"}})
        self.assertEqual(status, 400)
        status, r = self.call("POST", "/api/update", {"name": "Nope", "version": "1", "changes": {}})
        self.assertEqual(status, 404)



class Snapshot(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        make(self.tmp, "Overdue thing", due="2026-10-01")
        make(self.tmp, "Pick a colour", decision="true")

    def test_snapshot_has_data_and_no_fetch_on_load(self):
        out, _ = B.export_snapshot(self.tmp, date(2026, 10, 6), out=self.tmp / "Board.html", vault_name="V")
        html = out.read_text(encoding="utf-8")
        self.assertNotIn(B.MARKER, html)
        self.assertIn("window.BOARD_DATA = {", html)
        self.assertIn('"today": ["Overdue thing"]', html)      # json.dumps default separators
        self.assertIn("Pick a colour", html)
        # the page only fetches when BOARD_DATA is absent
        self.assertIn("const LIVE = !window.BOARD_DATA;", html)
        self.assertIn('if (!LIVE) { S.data = window.BOARD_DATA; render(); return; }', html)

    def test_snapshot_renders_lists_without_javascript(self):
        html = B.export_snapshot(self.tmp, date(2026, 10, 6), out=self.tmp / "Board.html")[0].read_text()
        static = html.split('<main id="main">', 1)[1].split("</main>", 1)[0]
        self.assertIn("Overdue thing", static)                 # Today, rendered as HTML, not only inside the JSON
        self.assertIn("Pick a colour", static)                 # Decisions
        self.assertIn('class="task', static)
        self.assertIn(">Today<", static)

    def test_snapshot_escapes_script_close(self):
        make(self.tmp, "Sneaky")
        (self.tmp / "Sneaky.md").write_text((self.tmp / "Sneaky.md").read_text() + "\nbody with </script> inside\n")
        html = B.export_snapshot(self.tmp, date(2026, 10, 6), out=self.tmp / "Board.html")[0].read_text()
        self.assertNotIn("</script> inside", html)
        self.assertIn("<\\/script> inside", html)


class ReviewFixes(unittest.TestCase):
    """Tree grouping and views that tolerate half-filled notes."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.today = date(2026, 10, 6)

    def test_tree_groups_children_under_open_projects_only(self):
        make(self.tmp, "Open proj", kind="project")
        make(self.tmp, "Child of open", parent="[[Open proj]]", effort="deep")
        make(self.tmp, "Parked proj", kind="project", status="someday")
        make(self.tmp, "Child of parked", parent="[[Parked proj]]")
        make(self.tmp, "Child of gone", parent="[[Gone]]")
        make(self.tmp, "Loose one")
        tree = B.payload(self.tmp, self.today)["tree"]
        self.assertEqual(list(tree), ["P"])
        self.assertEqual(tree["P"]["projects"], [{"name": "Open proj", "children": ["Child of open"]}])
        self.assertEqual(tree["P"]["loose"], ["Child of gone", "Child of parked", "Loose one"])

    def test_views_tolerate_missing_owner_and_created(self):
        make(self.tmp, "No owner", owner=None)
        make(self.tmp, "No created", created=None, status="inbox")
        make(self.tmp, "Also inbox", status="inbox")
        p = B.payload(self.tmp, self.today)
        self.assertEqual(p["errors"], [])
        self.assertIn("No created", p["views"]["inbox"])


class ReviewFixesApi(Api):
    def test_post_without_json_content_type_refused(self):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        c.request("POST", "/api/add", '{"lines": "Sneaked in"}', {"Content-Type": "text/plain"})
        r = c.getresponse(); r.read(); c.close()
        self.assertEqual(r.status, 415)
        self.assertFalse((self.tmp / "Sneaked in.md").exists())

    def test_foreign_host_refused(self):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        c.request("GET", "/api/tasks", headers={"Host": "evil.example.com"})
        r = c.getresponse(); r.read(); c.close()
        self.assertEqual(r.status, 421)

    def test_concurrent_same_version_one_wins(self):
        _, p = self.call("GET", "/api/tasks")
        version = p["tasks"][0]["version"]
        results = []

        def go(prio):
            results.append(self.call("POST", "/api/update", {"name": "Existing", "version": version,
                                                              "changes": {"priority": prio}})[0])
        ts = [threading.Thread(target=go, args=(x,)) for x in ("high", "low")]
        [t.start() for t in ts]; [t.join() for t in ts]
        self.assertEqual(sorted(results), [200, 409])

    def test_board_drop_is_not_archived_until_cli_sync(self):
        _, p = self.call("GET", "/api/tasks")
        version = p["tasks"][0]["version"]
        status, r = self.call("POST", "/api/update", {"name": "Existing", "version": version,
                                                       "changes": {T.STATUS: "dropped"}})
        self.assertEqual(status, 200)
        self.assertEqual(r["task"][T.STATUS], "dropped")
        self.assertTrue((self.tmp / "Existing.md").exists())
        self.assertFalse((self.tmp / "Archive" / "Existing.md").exists())


class TemplatePass(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.today = date(2026, 10, 7)

    def test_labels_name_goals_by_default_and_follow_config(self):
        self.assertEqual(B.payload(self.tmp, self.today, labels={})["labels"],
                         {"task": "Task", "project": "Goal", "reminder": "Reminder"})
        self.assertEqual(B.payload(self.tmp, self.today, labels={"project": "Project"})["labels"]["project"], "Project")

    def test_tree_leaves_reminders_out(self):
        make(self.tmp, "Call the plumber", kind="reminder", due="2026-10-09")
        make(self.tmp, "Fix the gutter")
        p = B.payload(self.tmp, self.today)
        self.assertEqual(p["tree"]["P"]["loose"], ["Fix the gutter"])
        self.assertEqual(p["views"]["reminders"], ["Call the plumber"])

    def test_snapshot_has_a_reminders_section(self):
        make(self.tmp, "Call the plumber", kind="reminder", due="2026-10-09")
        html = B.export_snapshot(self.tmp, self.today, out=self.tmp / "Board.html")[0].read_text()
        static = html.split('<main id="main">', 1)[1].split("</main>", 1)[0]
        self.assertIn(">Reminders<", static)
        self.assertIn("Call the plumber", static)

    def test_snapshot_rewritten_only_when_it_changed(self):
        make(self.tmp, "Something")
        out = self.tmp / "Board.html"
        self.assertTrue(B.export_snapshot(self.tmp, self.today, out=out)[1])
        os.utime(out, (0, 0))                         # mark the file so a rewrite would show
        path, written = B.export_snapshot(self.tmp, self.today, out=out)
        self.assertFalse(written)
        self.assertEqual(out.stat().st_mtime, 0)
        make(self.tmp, "Something new")
        self.assertTrue(B.export_snapshot(self.tmp, self.today, out=out)[1])
        self.assertNotEqual(out.stat().st_mtime, 0)


class SecondStart(unittest.TestCase):
    """Starting the board when it is already running says so instead of crashing."""

    def test_board_already_running(self):
        server = B.make_server(Path(tempfile.mkdtemp()), "127.0.0.1", 0, "V")
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = B.main(["serve", "--port", str(port)])
            self.assertEqual(rc, 0)
            self.assertIn(f"already running: http://127.0.0.1:{port}/", out.getvalue())
        finally:
            server.shutdown(); server.server_close()

    def test_port_taken_by_something_else(self):
        blocker = socket.socket()
        blocker.bind(("127.0.0.1", 0)); blocker.listen()
        port = blocker.getsockname()[1]
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = B.main(["serve", "--port", str(port)])
            self.assertEqual(rc, 1)
            self.assertIn(f"--port {port + 1}", out.getvalue())
        finally:
            blocker.close()


if __name__ == "__main__":
    unittest.main()
