"""Tests for tasks.py. Run from the folder's top level:
    python3 -m unittest Scripts/test_tasks.py -v
"""
import contextlib
import io
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tasks as T  # noqa: E402

SAMPLE = '''---
type: task
title: "Reply to InCorp: both threads"
project: "[[Wave Skin Wellness]]"
parent:
depends-on:
  - "[[Answer CJAY questions]]"
task-status: todo
priority: high
kind: task
effort: easy
decision:
due: 2026-09-06
when:
owner: Sol
created: 2026-09-04
updated: 2026-09-04
done:
created-by: claude
---

Body text with a [[link]].
'''


class ParseSerialize(unittest.TestCase):
    def test_roundtrip(self):
        fm, body = T.parse_frontmatter(SAMPLE)
        self.assertEqual(fm["title"], "Reply to InCorp: both threads")
        self.assertEqual(fm["project"], "[[Wave Skin Wellness]]")
        self.assertIsNone(fm["parent"])
        self.assertEqual(fm["depends-on"], ["[[Answer CJAY questions]]"])
        self.assertEqual(fm["due"], "2026-09-06")
        self.assertEqual(body, "Body text with a [[link]].\n")
        self.assertEqual(T.serialize(fm, body), SAMPLE)

    def test_inline_list(self):
        fm, _ = T.parse_frontmatter('---\ndepends-on: ["[[A, b]]", "[[C]]"]\n---\n')
        self.assertEqual(fm["depends-on"], ["[[A, b]]", "[[C]]"])

    def test_empty_list_roundtrip(self):
        fm, body = T.parse_frontmatter('---\ntype: task\ndepends-on: []\n---\n')
        self.assertEqual(fm["depends-on"], [])
        self.assertIn("depends-on: []", T.serialize(fm, body))

    def test_no_frontmatter_raises(self):
        with self.assertRaises(T.TaskError):
            T.parse_frontmatter("# just a heading\n")


def make(folder: Path, title, **kw):
    fm = {"type": "task", "title": title, "project": "[[P]]", "parent": None,
          "depends-on": [], T.STATUS: "todo", "priority": "normal",
          "kind": "task", "effort": None, "decision": None, "due": None,
          "owner": T.OWNER, "created": "2026-09-01", "updated": "2026-09-01",
          "done": None, "created-by": "claude"}
    if "status" in kw:                      # convenience: status="done" -> the real key
        kw[T.STATUS] = kw.pop("status")
    fm.update(kw)
    (folder / f"{title}.md").write_text(T.serialize(fm, ""))


class LoadAndSync(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.today = date(2026, 9, 4)

    def test_malformed_reported_not_skipped(self):
        make(self.tmp, "Good")
        (self.tmp / "Bad.md").write_text("no frontmatter\n")
        make(self.tmp, "Wrong status", status="waiting")
        tasks, errors = T.load_tasks(self.tmp)
        self.assertEqual(set(tasks), {"Good"})
        self.assertEqual(sorted(e[0].name for e in errors), ["Bad.md", "Wrong status.md"])

    def test_blocked_derived_across_chain(self):
        make(self.tmp, "A", status="done", done="2026-09-01")
        make(self.tmp, "B", **{"depends-on": ["[[A]]"]})                      # unblocked
        make(self.tmp, "C", **{"depends-on": ["[[B]]"]})                      # blocked by B
        make(self.tmp, "D", status="blocked", **{"depends-on": ["[[A]]"]})    # should reopen
        make(self.tmp, "E", **{"depends-on": ["[[Missing]]"]})               # bad link
        report = T.sync(self.tmp, self.today)
        tasks, _ = T.load_tasks(self.tmp)
        self.assertEqual(tasks["B"][T.STATUS], "todo")
        self.assertEqual(tasks["C"][T.STATUS], "blocked")
        self.assertEqual(tasks["D"][T.STATUS], "todo")
        self.assertEqual(tasks["C"]["updated"], "2026-09-04")
        self.assertTrue(any(e.startswith("E:") for e in report["errors"]))

    def test_done_date_set_and_archive(self):
        make(self.tmp, "Fresh done", status="done")                         # gets done=today
        make(self.tmp, "Old done", status="done", done="2026-07-01")        # archived
        make(self.tmp, "Week done", status="done", done="2026-08-28")       # 7 days: archived
        make(self.tmp, "Six days done", status="done", done="2026-08-29")   # 6 days: stays
        T.sync(self.tmp, self.today)
        tasks, _ = T.load_tasks(self.tmp)
        self.assertEqual(tasks["Fresh done"]["done"], "2026-09-04")
        self.assertNotIn("Old done", tasks)
        self.assertTrue((self.tmp / "Archive" / "Old done.md").exists())
        self.assertEqual(T.ARCHIVE_DAYS, 7)
        self.assertNotIn("Week done", tasks)
        self.assertTrue((self.tmp / "Archive" / "Week done.md").exists())
        self.assertIn("Six days done", tasks)

    def test_dropped_archives_immediately_and_flags_dependents(self):
        make(self.tmp, "Dead", status="dropped")
        make(self.tmp, "Leaner", status="blocked", **{"depends-on": ["[[Dead]]"]})
        make(self.tmp, "Finished", status="done", done="2026-09-03", **{"depends-on": ["[[Gone]]"]})
        report = T.sync(self.tmp, self.today)
        tasks, errors = T.load_tasks(self.tmp)
        self.assertNotIn("Dead", tasks)
        self.assertTrue((self.tmp / "Archive" / "Dead.md").exists())
        self.assertIn("Dead (dropped)", report["archived"])
        self.assertEqual(tasks["Leaner"][T.STATUS], "blocked")          # not silently unblocked
        self.assertIsNone(tasks["Dead.md"] if "Dead.md" in tasks else None)
        self.assertTrue(any(r.startswith("Leaner:") for r in report["review"]))
        self.assertFalse(any(e.startswith("Finished:") for e in report["errors"]))  # closed: missing dep is fine
        self.assertEqual(errors, [])

    def test_done_date_does_not_reopen_dropped(self):
        make(self.tmp, "Dropped dated", status="dropped", done="2026-09-01")
        T.sync(self.tmp, self.today)
        self.assertTrue((self.tmp / "Archive" / "Dropped dated.md").exists())

    def test_updated_refreshed_from_mtime(self):
        make(self.tmp, "Edited", updated="2026-08-01")   # file mtime is now (2026-09-xx) > updated
        T.sync(self.tmp, self.today)
        tasks, _ = T.load_tasks(self.tmp)
        self.assertEqual(tasks["Edited"]["updated"], date.today().isoformat())


    def test_live_copy_of_archived_task_is_reported_not_archived_over(self):
        (self.tmp / "Archive").mkdir()
        make(self.tmp / "Archive", "Ghost", status="dropped", updated="2026-09-03")
        make(self.tmp, "Ghost", status="dropped")               # differs: never overwrite the archived copy
        make(self.tmp / "Archive", "Twin", status="dropped")
        make(self.tmp, "Twin", status="dropped")                # identical: the live copy just goes
        report = T.sync(self.tmp, self.today)
        self.assertIn("task-status: dropped\n", (self.tmp / "Ghost.md").read_text())
        self.assertIn("updated: 2026-09-03", (self.tmp / "Archive" / "Ghost.md").read_text())
        self.assertFalse((self.tmp / "Twin.md").exists())
        self.assertEqual(T.in_both(self.tmp), ["Ghost"])
        self.assertTrue(any(r.startswith("Ghost: also in Archive/") for r in report["review"]))

class Brief(unittest.TestCase):
    def test_sections_come_from_views(self):
        # the CLI brief prints the board's lists, so it has no rule of its own (2026-10-08)
        tmp = Path(tempfile.mkdtemp()); today = date(2026, 9, 4)
        make(tmp, "Overdue", due="2026-09-01")
        make(tmp, "Planned", when="2026-09-04", effort="deep")
        make(tmp, "Soon", due="2026-09-08")
        make(tmp, "Later", due="2026-10-01")
        make(tmp, "Hot", priority="high")
        make(tmp, "Dump", status="inbox", project=None)
        make(tmp, "Theirs", owner="Rahma")
        make(tmp, "Stale", status="blocked", updated="2026-08-01", **{"depends-on": ["[[Overdue]]"]})
        make(tmp, "Gate", status="done", done="2026-09-03")
        b = T.brief(tmp, today)
        self.assertEqual([t["title"] for t in b["today"]], ["Overdue", "Planned"])
        self.assertEqual([t["title"] for t in b["unplanned"]], ["Soon", "Hot"])
        self.assertEqual([t["title"] for t in b["waiting"]], ["Theirs"])          # your blocked task is on hold, not waiting on others
        text = T.format_brief(b, today)
        self.assertIn("\nToday (2)\n  - Start here: [normal] Overdue  (P, Me)  deadline 2026-09-01\n"
                      "  - [normal] Planned  (P, Me)  planned 2026-09-04\n", text)
        self.assertIn("\nNot planned yet (2)\n  - [normal] Soon", text)
        self.assertIn("\nWaiting on others (1)\n", text)
        self.assertIn("inbox 1", text.splitlines()[1])          # the counts line keeps the inbox count
        for gone in ("OVERDUE", "High priority", "Inbox", "Stale —", "Newly unblocked", "Blocked ("):
            self.assertNotIn(gone, text)
        self.assertEqual(cli(tmp, today, "brief"), (0, text))

    def test_reports_names_in_both_live_and_archive(self):
        tmp = Path(tempfile.mkdtemp()); today = date(2026, 9, 4)
        (tmp / "Archive").mkdir()
        make(tmp / "Archive", "Ghost", status="dropped")
        make(tmp, "Ghost")
        make(tmp, "Fine")
        b = T.brief(tmp, today)
        self.assertEqual(b["in_both"], ["Ghost"])
        text = T.format_brief(b, today)
        self.assertIn("ALSO IN ARCHIVE", text)
        self.assertIn("counts: inbox 0, todo 2\n", text)          # the inbox count shows even at 0

    def test_missing_folder_is_empty(self):
        b = T.brief(Path(tempfile.mkdtemp()) / "nope", date(2026, 9, 4))
        self.assertEqual((b["today"], b["unplanned"], b["waiting"]), ([], [], []))


class Add(unittest.TestCase):
    def test_add_creates_valid_task_with_safe_filename(self):
        tmp = Path(tempfile.mkdtemp()); today = date(2026, 9, 4)
        p = T.add_task(tmp, today, "Reply: InCorp / both threads?", project="Wave Skin Wellness",
                       due="2026-09-06", priority="high", after=["Gate"], note="why: deadline")
        self.assertEqual(p.name, "Reply- InCorp - both threads-.md")
        tasks, errors = T.load_tasks(tmp)
        self.assertEqual(errors, [])
        t = tasks[p.stem]
        self.assertEqual(t["title"], "Reply: InCorp / both threads?")
        self.assertEqual(t["project"], "[[Wave Skin Wellness]]")
        self.assertEqual(t["depends-on"], ["[[Gate]]"])
        self.assertIn("why: deadline", t["_body"])
        with self.assertRaises(T.TaskError):
            T.add_task(tmp, today, "Reply: InCorp / both threads?", project="X")   # duplicate


class ModelV2(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.today = date(2026, 10, 6)

    def test_bad_kind_effort_decision_rejected(self):
        make(self.tmp, "K", kind="epic")
        make(self.tmp, "E", effort="huge")
        make(self.tmp, "D", decision="yes")
        _, errors = T.load_tasks(self.tmp)
        self.assertEqual(sorted(p.stem for p, _ in errors), ["D", "E", "K"])

    def test_decision_is_bool_from_string(self):
        make(self.tmp, "Yes", decision="true")
        make(self.tmp, "No")
        tasks, _ = T.load_tasks(self.tmp)
        self.assertTrue(T.is_decision(tasks["Yes"]))
        self.assertFalse(T.is_decision(tasks["No"]))

    def test_hierarchy_review(self):
        make(self.tmp, "Proj", kind="project")
        make(self.tmp, "Plain", kind="task")
        make(self.tmp, "Under project", kind="task", parent="[[Proj]]")
        make(self.tmp, "Under plain task", kind="task", parent="[[Plain]]")
        make(self.tmp, "Nested project", kind="project", parent="[[Proj]]")
        tasks, _ = T.load_tasks(self.tmp)
        lines = T.hierarchy_review(tasks)
        self.assertTrue(any(l.startswith("Under plain task:") for l in lines))
        self.assertTrue(any(l.startswith("Nested project:") for l in lines))
        self.assertFalse(any(l.startswith("Under project:") for l in lines))

    def test_hierarchy_archived_parent_ignored(self):
        make(self.tmp, "Orphan", kind="task", parent="[[Gone]]")
        tasks, _ = T.load_tasks(self.tmp)
        self.assertEqual(T.hierarchy_review(tasks), [])

    def test_sync_reports_hierarchy_under_review(self):
        make(self.tmp, "Plain", kind="task")
        make(self.tmp, "Child", kind="task", parent="[[Plain]]")
        r = T.sync(self.tmp, self.today)
        self.assertTrue(any(l.startswith("Child:") for l in r["review"]))

    def test_update_task_writes_fields_and_log(self):
        make(self.tmp, "Edit me")
        t = T.update_task(self.tmp, "Edit me", {"effort": "deep", "priority": "high", "decision": True}, self.today)
        fm, body = T.parse_frontmatter((self.tmp / "Edit me.md").read_text())
        self.assertEqual(fm["effort"], "deep")
        self.assertEqual(fm["priority"], "high")
        self.assertEqual(fm["decision"], "true")
        self.assertEqual(fm["updated"], "2026-10-06")
        self.assertIn("- 2026-10-06 board: effort — → deep; priority normal → high; decision — → true", body)

    def test_update_task_done_sets_date(self):
        make(self.tmp, "Finish")
        T.update_task(self.tmp, "Finish", {T.STATUS: "done"}, self.today)
        fm, _ = T.parse_frontmatter((self.tmp / "Finish.md").read_text())
        self.assertEqual(fm["done"], "2026-10-06")

    def test_update_reopen_clears_done(self):
        make(self.tmp, "Reopen", status="done", done="2026-10-01")
        T.update_task(self.tmp, "Reopen", {T.STATUS: "todo"}, self.today)
        fm, _ = T.parse_frontmatter((self.tmp / "Reopen.md").read_text())
        self.assertIsNone(fm["done"])
        self.assertEqual(fm[T.STATUS], "todo")
        r = T.sync(self.tmp, self.today)
        fm, _ = T.parse_frontmatter((self.tmp / "Reopen.md").read_text())
        self.assertEqual(fm[T.STATUS], "todo")

    def test_update_task_rejects_unknown_field_and_bad_value(self):
        make(self.tmp, "Strict")
        with self.assertRaises(T.TaskError):
            T.update_task(self.tmp, "Strict", {"title": "x"}, self.today)
        with self.assertRaises(T.TaskError):
            T.update_task(self.tmp, "Strict", {"effort": "enormous"}, self.today)
        fm, body = T.parse_frontmatter((self.tmp / "Strict.md").read_text())
        self.assertNotIn("board:", body)

    def test_update_task_no_change_no_log(self):
        make(self.tmp, "Same", effort="easy")
        T.update_task(self.tmp, "Same", {"effort": "easy"}, self.today)
        _, body = T.parse_frontmatter((self.tmp / "Same.md").read_text())
        self.assertNotIn("board:", body)

    def test_update_project_and_parent_become_links(self):
        make(self.tmp, "Proj", kind="project")
        make(self.tmp, "Move")
        T.update_task(self.tmp, "Move", {"project": "Echo", "parent": "Proj"}, self.today)
        fm, _ = T.parse_frontmatter((self.tmp / "Move.md").read_text())
        self.assertEqual(fm["project"], "[[Echo]]")
        self.assertEqual(fm["parent"], "[[Proj]]")

    def test_views_today_rule(self):
        # today is 2026-10-06. Today is the plan (2026-10-08): a near deadline or high priority alone no longer
        # puts a task there; they wait under Not planned yet.
        make(self.tmp, "Overdue", due="2026-10-01")
        make(self.tmp, "Soon", due="2026-10-10")
        make(self.tmp, "Far", due="2026-11-30")
        make(self.tmp, "Doing", status="doing")
        make(self.tmp, "High", priority="high")
        make(self.tmp, "High blocked", priority="high", status="blocked")
        make(self.tmp, "Not mine", priority="high", owner="Rahma")
        make(self.tmp, "A project", kind="project", priority="high")
        tasks, _ = T.load_tasks(self.tmp)
        v = T.views(tasks, self.today)
        self.assertEqual([t["title"] for t in v["today"]], ["Overdue", "Doing"])
        self.assertEqual([t["title"] for t in v["unplanned"]], ["Soon", "High"])
        self.assertEqual([t["title"] for t in v["waiting"]], ["Not mine"])
        self.assertEqual([t["title"] for t in v["onhold"]], ["High blocked"])

    def test_views_today_respects_when(self):
        # today is 2026-10-06. `when` is the day you plan to do it; a later `when` keeps a task off Today and off
        # Not planned yet until that day (the "extension"); being in progress still puts it on Today.
        make(self.tmp, "Planned today", when="2026-10-06")
        make(self.tmp, "Carried over", when="2026-10-03")
        make(self.tmp, "Later, high", priority="high", when="2026-10-31")
        make(self.tmp, "Later, deadline soon", when="2026-10-31", due="2026-10-09")
        make(self.tmp, "Later, in progress", when="2026-10-31", status="doing")
        make(self.tmp, "Planned but blocked", when="2026-10-06", status="blocked")
        make(self.tmp, "High, unplanned", priority="high")
        make(self.tmp, "Planned, someone else", when="2026-10-06", owner="Rahma")
        tasks, _ = T.load_tasks(self.tmp)
        v = T.views(tasks, self.today)
        self.assertEqual([t["title"] for t in v["today"]],
                         ["Carried over", "Planned but blocked", "Planned today", "Later, in progress"])
        self.assertEqual([t["title"] for t in v["unplanned"]], ["High, unplanned"])

    def test_when_is_a_checked_editable_date(self):
        make(self.tmp, "Plan me")
        t = T.update_task(self.tmp, "Plan me", {"when": "2026-10-31"}, self.today)
        self.assertEqual(t["when"], "2026-10-31")
        self.assertIn("when — → 2026-10-31", (self.tmp / "Plan me.md").read_text())
        with self.assertRaises(T.TaskError):
            T.update_task(self.tmp, "Plan me", {"when": "31/10"}, self.today)
        T.update_task(self.tmp, "Plan me", {"when": ""}, self.today)
        self.assertIsNone(T.load_tasks(self.tmp)[0]["Plan me"].get("when"))
        p = T.add_task(self.tmp, self.today, "Planned at birth", when="2026-10-08")
        self.assertIn("when: 2026-10-08", p.read_text())
        with self.assertRaises(T.TaskError):
            T.add_task(self.tmp, self.today, "Bad plan", when="next week")

    def test_unplanned_leaves_out_tasks_planned_later(self):
        make(self.tmp, "High now", priority="high")
        make(self.tmp, "High later", priority="high", when="2026-10-31")
        make(self.tmp, "Planned now", when="2026-10-06")
        b = T.brief(self.tmp, self.today)
        self.assertEqual([t["title"] for t in b["unplanned"]], ["High now"])
        self.assertEqual([t["title"] for t in b["today"]], ["Planned now"])

    def test_views_decisions_oldest_first(self):
        make(self.tmp, "New call", decision="true", created="2026-10-01")
        make(self.tmp, "Old call", decision="true", created="2026-09-01")
        make(self.tmp, "Done call", decision="true", status="done", done="2026-09-20")
        tasks, _ = T.load_tasks(self.tmp)
        self.assertEqual([t["title"] for t in T.views(tasks, self.today)["decisions"]], ["Old call", "New call"])

    def test_add_task_kind_effort_decision(self):
        p = T.add_task(self.tmp, self.today, "Big build", project="Echo", kind="project")
        fm, _ = T.parse_frontmatter(p.read_text())
        self.assertEqual(fm["kind"], "project")
        p = T.add_task(self.tmp, self.today, "Pick a name", project="Echo", effort="easy", decision=True)
        fm, _ = T.parse_frontmatter(p.read_text())
        self.assertEqual((fm["kind"], fm["effort"], fm["decision"]), ("task", "easy", "true"))
        with self.assertRaises(T.TaskError):
            T.add_task(self.tmp, self.today, "Bad", kind="epic")


class ReviewFixes(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.today = date(2026, 10, 6)

    def test_update_rejects_control_characters(self):
        make(self.tmp, "Owned")
        with self.assertRaises(T.TaskError):
            T.update_task(self.tmp, "Owned", {"owner": "Sam\nproject: [[X]]"}, self.today)
        fm, _ = T.parse_frontmatter((self.tmp / "Owned.md").read_text())
        self.assertEqual(fm["owner"], T.OWNER)

    def test_board_cannot_set_blocked(self):
        make(self.tmp, "Derived")
        with self.assertRaises(T.TaskError):
            T.update_task(self.tmp, "Derived", {T.STATUS: "blocked"}, self.today, source="board")

    def test_sync_without_archive_keeps_dropped_in_place(self):
        make(self.tmp, "Dropped", status="dropped")
        r = T.sync(self.tmp, self.today, archive=False)
        self.assertEqual(r["archived"], [])
        self.assertTrue((self.tmp / "Dropped.md").exists())


class LinkFixes(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.today = date(2026, 10, 7)

    def test_links_point_at_the_file_name(self):
        gate = T.add_task(self.tmp, self.today, "Decide: sole trader now?", project="Echo", kind="project")
        p = T.add_task(self.tmp, self.today, "Register as sole trader", project="Echo",
                       parent="Decide: sole trader now?", after=["Decide: sole trader now?"])
        tasks, errors = T.load_tasks(self.tmp)
        self.assertEqual(errors, [])
        self.assertEqual(gate.stem, "Decide- sole trader now-")
        self.assertEqual(tasks[p.stem]["parent"], "[[Decide- sole trader now-]]")
        self.assertEqual(tasks[p.stem]["depends-on"], ["[[Decide- sole trader now-]]"])

    def test_old_colon_link_still_unblocks(self):
        make(self.tmp, "Decide- sole trader now-", status="done", done="2026-10-06")
        make(self.tmp, "Register", status="blocked", **{"depends-on": ["[[Decide: sole trader now?]]"]})
        r = T.sync(self.tmp, self.today)
        tasks, _ = T.load_tasks(self.tmp)
        self.assertEqual(tasks["Register"][T.STATUS], "todo")
        self.assertEqual(r["errors"], [])

    def test_update_parent_points_at_file_name(self):
        make(self.tmp, "Decide- pricing", kind="project")
        make(self.tmp, "Child")
        T.update_task(self.tmp, "Child", {"parent": "Decide: pricing"}, self.today)
        tasks, _ = T.load_tasks(self.tmp)
        self.assertEqual(tasks["Child"]["parent"], "[[Decide- pricing]]")

    def test_archived_done_dependency_counts_as_done(self):
        (self.tmp / "Archive").mkdir()
        make(self.tmp / "Archive", "Old gate", status="done", done="2026-08-01")
        make(self.tmp / "Archive", "Dropped gate", status="dropped")
        make(self.tmp, "After old gate", status="blocked", **{"depends-on": ["[[Old gate]]"]})
        make(self.tmp, "After dropped gate", **{"depends-on": ["[[Dropped gate]]"]})
        make(self.tmp, "After nothing", **{"depends-on": ["[[Never existed]]"]})
        r = T.sync(self.tmp, self.today)
        tasks, _ = T.load_tasks(self.tmp)
        self.assertEqual(tasks["After old gate"][T.STATUS], "todo")
        self.assertEqual(tasks["After dropped gate"][T.STATUS], "blocked")
        self.assertFalse(any(e.startswith("After old gate:") for e in r["errors"]))
        self.assertTrue(any(e.startswith("After nothing:") for e in r["errors"]))

    def test_dropped_then_archived_dependency_keeps_being_flagged(self):
        make(self.tmp, "Gate", status="dropped")
        make(self.tmp, "After gate", **{"depends-on": ["[[Gate]]"]})
        T.sync(self.tmp, self.today)                       # flags it once, then archives Gate
        r = T.sync(self.tmp, self.today)                   # the mini runs sync every 3 minutes: keep saying so
        tasks, _ = T.load_tasks(self.tmp)
        self.assertEqual(tasks["After gate"][T.STATUS], "blocked")
        self.assertIn("After gate: depends on dropped [[Gate]] (archived)", r["review"])

    def test_deps_state_sees_archived_dependency(self):
        (self.tmp / "Archive").mkdir()
        make(self.tmp / "Archive", "Old gate", status="done", done="2026-08-01")
        make(self.tmp, "Waiting", status="blocked", **{"depends-on": ["[[Old gate]]"]})
        tasks, _ = T.load_tasks(self.tmp)
        archived, _ = T.load_tasks(self.tmp / "Archive")
        self.assertEqual(T.deps_state(tasks["Waiting"], tasks, archived), (True, []))


def cli(folder: Path, today: date, *argv) -> tuple[int, str]:
    """Run tasks.py's CLI against `folder`; returns (exit code, what it printed to stdout and stderr)."""
    old, buf = T.TASKS_DIR, io.StringIO()
    T.TASKS_DIR = folder
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            code = T.main(["--today", today.isoformat(), *argv])
        return code, buf.getvalue()
    finally:
        T.TASKS_DIR = old


class Watches(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.today = date(2026, 10, 7)

    def run_cli(self, *argv):
        return cli(self.tmp, self.today, *argv)[0]

    def test_add_with_watch_defaults_chase_to_a_week(self):
        p = T.add_task(self.tmp, self.today, "Get the title register", project="42 Mercury",
                       waiting_on=["JMW.co.uk"], expecting="updated title register")
        tasks, errors = T.load_tasks(self.tmp)
        self.assertEqual(errors, [])
        t = tasks[p.stem]
        self.assertEqual(T.watch_parties(t), ["JMW.co.uk"])   # the template keeps the case typed
        self.assertEqual(t["expecting"], "updated title register")
        self.assertEqual(t["chase-after"], "2026-10-14")

    def test_add_without_watch_writes_no_watch_fields(self):
        text = T.add_task(self.tmp, self.today, "Plain", project="Echo").read_text()
        for k in T.WATCH_FIELDS:
            self.assertNotIn(k + ":", text)

    def test_setting_a_watch_logs_and_defaults_chase(self):
        make(self.tmp, "Chase JMW")
        T.update_task(self.tmp, "Chase JMW", {"waiting-on": "jmw.co.uk, incorp.asia"}, self.today, source="brief")
        fm, body = T.parse_frontmatter((self.tmp / "Chase JMW.md").read_text())
        self.assertEqual(fm["waiting-on"], ["jmw.co.uk", "incorp.asia"])
        self.assertEqual(fm["chase-after"], "2026-10-14")
        self.assertIn("- 2026-10-07 brief: waiting-on — → jmw.co.uk, incorp.asia; chase-after — → 2026-10-14", body)

    def test_clearing_a_watch_removes_the_fields(self):
        make(self.tmp, "Watched", **{"waiting-on": ["jmw.co.uk"], "expecting": "MR01", "chase-after": "2026-10-10"})
        T.update_task(self.tmp, "Watched", {"waiting-on": None, "expecting": None, "chase-after": None}, self.today)
        text = (self.tmp / "Watched.md").read_text()
        for k in T.WATCH_FIELDS:
            self.assertNotIn(k + ":", text)

    def test_bad_chase_date_rejected(self):
        make(self.tmp, "Bad chase", **{"chase-after": "next week"})
        _, errors = T.load_tasks(self.tmp)
        self.assertEqual([p.stem for p, _ in errors], ["Bad chase"])

    def test_hand_written_scalar_waiting_on_is_one_party(self):
        make(self.tmp, "Hand")
        p = self.tmp / "Hand.md"
        p.write_text(p.read_text().replace("created-by: claude\n",
                                           "created-by: claude\nwaiting-on: JMW.co.uk\nchase-after: 2026-10-10\n"))
        tasks, errors = T.load_tasks(self.tmp)
        self.assertEqual(errors, [])
        self.assertEqual(T.watch_parties(tasks["Hand"]), ["JMW.co.uk"])

    def test_note_only_writes_a_log_line(self):
        make(self.tmp, "Quiet")
        T.update_task(self.tmp, "Quiet", {}, self.today, source="brief", note="title register arrived; filed")
        fm, body = T.parse_frontmatter((self.tmp / "Quiet.md").read_text())
        self.assertIn("- 2026-10-07 brief: title register arrived; filed", body)
        self.assertEqual(fm["updated"], "2026-10-07")

    def test_set_by_title_with_colon_sets_when_and_logs(self):
        T.add_task(self.tmp, self.today, "Decide: price?", project="Wave")
        self.assertEqual(self.run_cli("set", "Decide: price?", "--when", "2026-10-07", "--source", "brief"), 0)
        fm, body = T.parse_frontmatter((self.tmp / "Decide- price-.md").read_text())
        self.assertEqual(fm["when"], "2026-10-07")
        self.assertIn("- 2026-10-07 brief: when — → 2026-10-07", body)

    def test_set_clear_watch_with_note(self):
        make(self.tmp, "Watched", **{"waiting-on": ["jmw.co.uk"], "expecting": "MR01", "chase-after": "2026-10-10"})
        self.assertEqual(self.run_cli("set", "Watched", "--clear-watch", "--note", "MR01 arrived", "--source", "brief"), 0)
        text = (self.tmp / "Watched.md").read_text()
        self.assertNotIn("waiting-on:", text)
        self.assertIn("MR01 arrived", text)

    def test_set_unknown_task_or_nothing_to_change_fails(self):
        make(self.tmp, "Real")
        self.assertEqual(self.run_cli("set", "Nope", "--when", "2026-10-07"), 1)
        self.assertEqual(self.run_cli("set", "Real"), 1)


class Guards(unittest.TestCase):
    """Task system changes, 2026-10-08: refusals the board and the CLI share, and set --decision."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.today = date(2026, 10, 8)
        make(self.tmp, "Gate")
        make(self.tmp, "After gate", status="blocked", **{"depends-on": ["[[Gate]]"]})

    def text(self, name):
        return (self.tmp / f"{name}.md").read_text()

    def test_todo_or_doing_refused_while_a_dependency_is_open(self):
        before = self.text("After gate")
        for status in ("todo", "doing"):
            with self.assertRaises(T.TaskError) as cm:
                T.update_task(self.tmp, "After gate", {T.STATUS: status}, self.today, source="claude")
            self.assertEqual(str(cm.exception), "blocked by Gate; finish it first")
        self.assertEqual(self.text("After gate"), before)          # nothing written, no log line

    def test_refusal_holds_whatever_the_current_status(self):
        make(self.tmp, "Dumped", status="inbox", **{"depends-on": ["[[Gate]]"]})
        with self.assertRaises(T.TaskError):
            T.update_task(self.tmp, "Dumped", {T.STATUS: "todo"}, self.today)

    def test_a_dropped_dependency_still_holds_it_as_sync_does(self):
        T.update_task(self.tmp, "Gate", {T.STATUS: "dropped"}, self.today, note="not needed")
        want = "blocked by Gate, which is dropped; remove it from depends-on first"
        for _ in ("live", "archived"):
            with self.assertRaises(T.TaskError) as cm:
                T.update_task(self.tmp, "After gate", {T.STATUS: "todo"}, self.today)
            self.assertEqual(str(cm.exception), want)
            T.sync(self.tmp, self.today)                           # archives Gate; it still holds

    def test_an_archived_done_dependency_lets_it_through(self):
        (self.tmp / "Archive").mkdir()
        make(self.tmp / "Archive", "Old gate", status="done", done="2026-09-01")
        make(self.tmp, "After old gate", status="inbox", **{"depends-on": ["[[Old gate]]"]})
        T.update_task(self.tmp, "After old gate", {T.STATUS: "doing"}, self.today)
        self.assertEqual(T.load_tasks(self.tmp)[0]["After old gate"][T.STATUS], "doing")

    def test_sync_still_flips_blocked_to_todo_when_the_dependency_is_done(self):
        T.update_task(self.tmp, "Gate", {T.STATUS: "done"}, self.today)
        T.sync(self.tmp, self.today)
        self.assertEqual(T.load_tasks(self.tmp)[0]["After gate"][T.STATUS], "todo")
        T.update_task(self.tmp, "After gate", {T.STATUS: "doing"}, self.today)   # and nothing refuses it now
        self.assertEqual(T.load_tasks(self.tmp)[0]["After gate"][T.STATUS], "doing")

    def test_set_status_todo_on_a_blocked_task_fails(self):
        code, out = cli(self.tmp, self.today, "set", "After gate", "--status", "todo")
        self.assertEqual(code, 1)
        self.assertIn("ERROR: blocked by Gate; finish it first", out)

    def test_dropped_needs_a_note(self):
        before = self.text("Gate")
        for note in ("", "   "):
            with self.assertRaises(T.TaskError) as cm:
                T.update_task(self.tmp, "Gate", {T.STATUS: "dropped"}, self.today, note=note)
            self.assertEqual(str(cm.exception), "say why in one line: --note ...")
        self.assertEqual(self.text("Gate"), before)
        T.update_task(self.tmp, "Gate", {T.STATUS: "dropped"}, self.today, note="superseded by the new plan")
        self.assertIn("- 2026-10-08 board: status todo → dropped; superseded by the new plan", self.text("Gate"))

    def test_set_dropped_from_the_cli_needs_a_note(self):
        code, out = cli(self.tmp, self.today, "set", "Gate", "--status", "dropped")
        self.assertEqual(code, 1)
        self.assertIn("ERROR: say why in one line: --note ...", out)
        self.assertNotIn("dropped", self.text("Gate"))
        code, _ = cli(self.tmp, self.today, "set", "Gate", "--status", "dropped", "--note", "they said no")
        self.assertEqual(code, 0)
        self.assertIn("- 2026-10-08 claude: status todo → dropped; they said no", self.text("Gate"))

    def test_set_decision_and_clear_it(self):
        self.assertEqual(cli(self.tmp, self.today, "set", "Gate", "--decision")[0], 0)
        fm, body = T.parse_frontmatter(self.text("Gate"))
        self.assertEqual(fm["decision"], "true")
        self.assertIn("- 2026-10-08 claude: decision — → true", body)
        self.assertEqual(cli(self.tmp, self.today, "set", "Gate", "--clear", "decision")[0], 0)
        fm, body = T.parse_frontmatter(self.text("Gate"))
        self.assertIsNone(fm["decision"])
        self.assertIn("- 2026-10-08 claude: decision true → —", body)


def with_log(folder: Path, title: str, *lines: str, **kw):
    make(folder, title, **kw)
    p = folder / f"{title}.md"
    p.write_text(p.read_text() + "\n" + "\n".join(lines) + "\n")


class Stale(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_migration_lines_do_not_count(self):
        with_log(self.tmp, "Old", "- 2026-09-04 created", "- 2026-10-06 migration: kind — → task",
                 created="2026-09-04", updated="2026-10-06")
        tasks, _ = T.load_tasks(self.tmp)
        self.assertEqual(T.last_activity(tasks["Old"]), date(2026, 9, 4))
        self.assertTrue(T.is_stale(tasks["Old"], date(2026, 10, 7)))

    def test_a_real_change_counts(self):
        with_log(self.tmp, "Moved", "- 2026-09-04 created", "- 2026-10-01 board: priority normal → high",
                 created="2026-09-04")
        tasks, _ = T.load_tasks(self.tmp)
        self.assertEqual(T.last_activity(tasks["Moved"]), date(2026, 10, 1))
        self.assertFalse(T.is_stale(tasks["Moved"], date(2026, 10, 7)))

    def test_no_log_falls_back_to_updated_then_created(self):
        make(self.tmp, "Bare", created="2026-09-01", updated="2026-09-20")
        make(self.tmp, "Bare2", created="2026-09-01", updated=None)
        tasks, _ = T.load_tasks(self.tmp)
        self.assertEqual(T.last_activity(tasks["Bare"]), date(2026, 9, 20))
        self.assertEqual(T.last_activity(tasks["Bare2"]), date(2026, 9, 1))


class TodayIsThePlan(unittest.TestCase):
    """Today = what you planned, deadlines due today or late, and anything in progress."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.today = date(2026, 10, 8)

    def views(self):
        tasks, _ = T.load_tasks(self.tmp)
        return T.views(tasks, self.today), tasks

    def titles(self, rows):
        return [t["title"] for t in rows]

    def test_planned_today_shows(self):
        make(self.tmp, "Planned", when="2026-10-08")
        v, tasks = self.views()
        self.assertEqual(self.titles(v["today"]), ["Planned"])
        self.assertEqual(T.carried_days(tasks["Planned"], self.today), 0)

    def test_planned_earlier_shows_and_is_carried(self):
        make(self.tmp, "Carried", when="2026-10-05")
        v, tasks = self.views()
        self.assertEqual(self.titles(v["today"]), ["Carried"])
        self.assertEqual(T.carried_days(tasks["Carried"], self.today), 3)

    def test_blocked_and_planned_shows(self):
        make(self.tmp, "Gate")
        make(self.tmp, "Held", when="2026-10-07", status="blocked", **{"depends-on": ["[[Gate]]"]})
        v, _ = self.views()
        self.assertEqual(self.titles(v["today"]), ["Held"])
        self.assertEqual(self.titles(v["unplanned"]), [])

    def test_high_priority_without_when_is_not_planned_yet(self):
        make(self.tmp, "Hot", priority="high")
        v, _ = self.views()
        self.assertEqual(v["today"], [])
        self.assertEqual(self.titles(v["unplanned"]), ["Hot"])

    def test_deadline_in_five_days_is_not_planned_yet(self):
        make(self.tmp, "Deadline soon", due="2026-10-13")
        make(self.tmp, "Deadline far", due="2026-10-30")
        v, _ = self.views()
        self.assertEqual(v["today"], [])
        self.assertEqual(self.titles(v["unplanned"]), ["Deadline soon"])

    def test_due_today_shows_first_whatever_its_when(self):
        make(self.tmp, "Deep planned", when="2026-10-01", effort="deep")
        make(self.tmp, "Due today", due="2026-10-08", when="2026-10-20", effort="easy")
        v, _ = self.views()
        self.assertEqual(self.titles(v["today"]), ["Due today", "Deep planned"])

    def test_doing_shows(self):
        make(self.tmp, "Under way", status="doing")
        v, _ = self.views()
        self.assertEqual(self.titles(v["today"]), ["Under way"])

    def test_order_late_then_deep_medium_easy_unsized(self):
        make(self.tmp, "Easy", effort="easy", when="2026-10-08")
        make(self.tmp, "Medium", effort="medium", when="2026-10-08")
        make(self.tmp, "Deep", effort="deep", when="2026-10-08")
        make(self.tmp, "Deep carried", effort="deep", when="2026-10-05")
        make(self.tmp, "Unsized doing", status="doing")
        make(self.tmp, "Due today", due="2026-10-08")
        make(self.tmp, "Late", due="2026-10-06", effort="easy")
        v, _ = self.views()
        self.assertEqual(self.titles(v["today"]),
                         ["Late", "Due today", "Deep carried", "Deep", "Medium", "Easy", "Unsized doing"])

    def test_unplanned_order_and_exclusions(self):
        make(self.tmp, "B high", priority="high")
        make(self.tmp, "A high", priority="high")
        make(self.tmp, "Deadline normal", due="2026-10-10")
        make(self.tmp, "Deadline high", due="2026-10-10", priority="high")
        make(self.tmp, "Deadline first", due="2026-10-09")
        make(self.tmp, "High later", priority="high", when="2026-10-20")          # a later when is a plan
        make(self.tmp, "High blocked", priority="high", status="blocked")
        make(self.tmp, "High, theirs", priority="high", owner="Rahma")
        make(self.tmp, "High project", priority="high", kind="project")
        make(self.tmp, "High someday", priority="high", status="someday")
        v, _ = self.views()
        self.assertEqual(self.titles(v["unplanned"]),
                         ["Deadline first", "Deadline high", "Deadline normal", "A high", "B high"])

    def test_carried_days_reads_when_changes_in_the_log(self):
        body = ("- 2026-10-01 created\n"
                "- 2026-10-02 interview: when — → 2026-10-05; this week\n"
                "- 2026-10-06 wrap: when 2026-10-05 → 2026-10-07; due 2026-09-20 → 2026-10-30\n"
                "- 2026-10-07 wrap: when 2026-10-07 → 2026-10-08\n"
                "- 2026-10-03 note: asked when 2026-09-01 suits them\n"     # no change arrow: prose, not a plan
                "when 2026-09-02 → 2026-10-08\n")                           # not a log line
        t = {"when": "2026-10-08", "_body": body}
        self.assertEqual(T.carried_days(t, self.today), 3)                  # 5 Oct arrived and was missed
        self.assertEqual(T.carried_days({"when": "2026-10-20", "_body": "- 2026-10-09 board: when — → 2026-10-20\n"},
                                        self.today), 0)                      # nothing planned has passed
        self.assertEqual(T.carried_days({"when": "2026-10-06", "_body": ""}, self.today), 2)
        self.assertEqual(T.carried_days({"_body": ""}, self.today), 0)

    def test_a_plan_moved_before_its_day_is_not_carried(self):
        # planned for 5 Oct, moved on 4 Oct to 7 Oct: on 7 Oct it was never missed
        body = "- 2026-10-02 interview: when — → 2026-10-05\n- 2026-10-04 board: when 2026-10-05 → 2026-10-07\n"
        self.assertEqual(T.carried_days({"when": "2026-10-07", "_body": body}, date(2026, 10, 7)), 0)

    def test_an_extension_is_not_carried(self):
        # moved on 3 Oct from 5 Oct to 20 Oct (the extension): on 20 Oct it is planned today, not carried 15 days
        body = "- 2026-10-01 interview: when — → 2026-10-05\n- 2026-10-03 wrap: when 2026-10-05 → 2026-10-20\n"
        self.assertEqual(T.carried_days({"when": "2026-10-20", "_body": body}, date(2026, 10, 20)), 0)

    def test_carried_days_from_a_task_note(self):
        with_log(self.tmp, "Moved on", "- 2026-10-07 wrap: when 2026-10-06 → 2026-10-08", when="2026-10-08")
        _, tasks = self.views()
        self.assertEqual(T.carried_days(tasks["Moved on"], self.today), 2)


class OneWaiting(unittest.TestCase):
    """One definition of waiting: a watch, or a named owner who is neither you nor Claude."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.today = date(2026, 10, 8)

    def views(self):
        tasks, errors = T.load_tasks(self.tmp)
        self.assertEqual(errors, [])
        return T.views(tasks, self.today), tasks

    def test_waits_outside(self):
        self.assertTrue(T.waits_outside({"owner": T.OWNER, "waiting-on": ["jmw.co.uk"]}, T.OWNER))      # a watch
        self.assertTrue(T.waits_outside({"owner": "Rahma"}, T.OWNER))                                  # a person
        self.assertFalse(T.waits_outside({"owner": "Claude"}, T.OWNER))
        self.assertFalse(T.waits_outside({"owner": T.OWNER}, T.OWNER))
        self.assertTrue(T.waits_outside({"owner": "Claude", "waiting-on": "jmw.co.uk"}, T.OWNER))      # a watch still counts
        self.assertFalse(T.waits_outside({"owner": None, "waiting-on": " "}, T.OWNER))                 # no one named

    def test_sync_sets_a_default_chase_date_once_and_never_overwrites_one(self):
        with_log(self.tmp, "Handed over", "- 2026-10-01 board: owner Me → Rahma", owner="Rahma")
        make(self.tmp, "Quiet", owner="Mercedy", updated="2026-09-20")
        make(self.tmp, "No dates", owner="Rahma", created=None, updated=None)
        make(self.tmp, "Watched", **{"waiting-on": ["jmw.co.uk"]})
        make(self.tmp, "Dated", owner="Rahma", **{"chase-after": "2026-12-01"})
        for title, kw in (("Mine", {}), ("Claude's", {"owner": "Claude"}),
                          ("Done theirs", {"owner": "Rahma", "status": "done", "done": "2026-10-07"}),
                          ("Someday theirs", {"owner": "Rahma", "status": "someday"})):
            make(self.tmp, title, **kw)
        r = T.sync(self.tmp, self.today, archive=False)
        _, tasks = self.views()
        chase = {n: t.get("chase-after") for n, t in tasks.items()}
        self.assertEqual(chase, {"Handed over": "2026-10-08", "Quiet": "2026-09-27", "No dates": "2026-10-15",
                                 "Watched": "2026-09-08", "Dated": "2026-12-01", "Mine": None, "Claude's": None,
                                 "Done theirs": None, "Someday theirs": None})
        self.assertIn("- 2026-10-08 sync: chase-after → 2026-10-08 (default)", tasks["Handed over"]["_body"])
        self.assertIn("Quiet: task-status=todo done= chase-after=2026-09-27 (default)", r["changed"])
        self.assertNotIn("sync:", tasks["Dated"]["_body"])
        before = {p.name: p.read_text() for p in self.tmp.glob("*.md")}
        self.assertEqual(T.sync(self.tmp, self.today, archive=False)["changed"], [])   # the board syncs after every save
        self.assertEqual({p.name: p.read_text() for p in self.tmp.glob("*.md")}, before)

    def test_waiting_is_outside_waits_by_chase_date_late_first(self):
        make(self.tmp, "Watch late", **{"waiting-on": ["jmw.co.uk"], "chase-after": "2026-10-01"})
        make(self.tmp, "Person soon", owner="Rahma", **{"chase-after": "2026-10-10"})
        make(self.tmp, "Alpha same day", owner="Rahma", **{"chase-after": "2026-10-10"})
        make(self.tmp, "No chase yet", owner="Mercedy")
        make(self.tmp, "Blocked mine", status="blocked")
        make(self.tmp, "Claude's", owner="Claude")
        make(self.tmp, "Theirs done", owner="Rahma", status="done", done="2026-10-07")
        v, tasks = self.views()
        self.assertEqual([t["title"] for t in v["waiting"]], ["Watch late", "Alpha same day", "Person soon", "No chase yet"])
        self.assertEqual([t["title"] for t in T.late_chases(tasks, self.today)], ["Watch late"])
        self.assertEqual([t["title"] for t in T.late_chases(tasks, date(2026, 10, 11))],
                         ["Watch late", "Alpha same day", "Person soon"])

    def test_onhold_is_my_blocked_tasks_that_wait_on_nothing_outside(self):
        make(self.tmp, "Held", status="blocked")
        make(self.tmp, "Held and watched", status="blocked", **{"waiting-on": ["jmw.co.uk"]})
        make(self.tmp, "Theirs blocked", status="blocked", owner="Rahma")
        make(self.tmp, "Free", status="todo")
        v, _ = self.views()
        self.assertEqual([t["title"] for t in v["onhold"]], ["Held"])
        self.assertEqual([t["title"] for t in v["waiting"]], ["Held and watched", "Theirs blocked"])

    def test_claude_view_by_priority_then_deadline_then_created(self):
        make(self.tmp, "Low", owner="Claude", priority="low", due="2026-10-09")
        make(self.tmp, "Normal late deadline", owner="Claude", due="2026-10-20")
        make(self.tmp, "Normal early deadline", owner="Claude", due="2026-10-10")
        make(self.tmp, "Normal newer", owner="Claude", created="2026-09-01")
        make(self.tmp, "Normal older", owner="Claude", created="2026-08-01")
        make(self.tmp, "High", owner="Claude", priority="high")
        make(self.tmp, "Claude done", owner="Claude", status="done", done="2026-10-07")
        make(self.tmp, "Mine", priority="high")
        v, _ = self.views()
        self.assertEqual([t["title"] for t in v["claude"]],
                         ["High", "Normal early deadline", "Normal late deadline", "Normal older", "Normal newer", "Low"])
        self.assertNotIn("High", [t["title"] for t in v["waiting"]])

    def test_chased_moves_the_chase_date_and_logs(self):
        make(self.tmp, "Chase JMW", **{"waiting-on": ["jmw.co.uk"], "chase-after": "2026-10-01"})
        T.update_task(self.tmp, "Chase JMW", {"chased": True}, self.today, source="brief")
        fm, body = T.parse_frontmatter((self.tmp / "Chase JMW.md").read_text())
        self.assertEqual((fm["chase-after"], fm["updated"]), ("2026-10-15", "2026-10-08"))
        self.assertIn("- 2026-10-08 brief: chased\n", body)
        T.update_task(self.tmp, "Chase JMW", {"chased": True, "chase-after": "2026-10-30"}, self.today)
        fm, body = T.parse_frontmatter((self.tmp / "Chase JMW.md").read_text())
        self.assertEqual(fm["chase-after"], "2026-10-30")                     # a date given with it wins
        self.assertIn("- 2026-10-08 board: chase-after 2026-10-15 → 2026-10-30; chased\n", body)

    def test_set_chased_from_the_cli(self):
        make(self.tmp, "Books", owner="Rahma", **{"chase-after": "2026-10-02"})
        self.assertEqual(cli(self.tmp, self.today, "set", "Books", "--chased", "--note", "rang her")[0], 0)
        fm, body = T.parse_frontmatter((self.tmp / "Books.md").read_text())
        self.assertEqual(fm["chase-after"], "2026-10-15")
        self.assertIn("- 2026-10-08 claude: chased; rang her\n", body)


# ---------- the template's own: reminders, the brief's sections, the readability fixes ----------

class Reminders(unittest.TestCase):
    """kind: reminder — a nudge on a day (its `when`). Lives in its own list, never in Today's work."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.today = date(2026, 10, 7)

    def test_a_reminders_day_is_when_and_it_takes_no_task_fields(self):
        with self.assertRaises(T.TaskError):
            T.add_task(self.tmp, self.today, "Call mum", kind="reminder")                      # no day
        with self.assertRaisesRegex(T.TaskError, "--when, not --due"):
            T.add_task(self.tmp, self.today, "Call mum", kind="reminder", due="2026-10-09")
        with self.assertRaisesRegex(T.TaskError, "--decision"):
            T.add_task(self.tmp, self.today, "Call mum", kind="reminder", when="2026-10-09", decision=True)
        p = T.add_task(self.tmp, self.today, "Call mum", kind="reminder", when="2026-10-09")
        text = p.read_text()
        for blank in ("priority:", "effort:", "decision:", "parent:", "depends-on:", "owner:", "due:"):
            self.assertNotIn(blank, text)                  # a title and a day, not a wall of blanks
        t = T.load_tasks(self.tmp)[0]["Call mum"]
        self.assertEqual((t["kind"], t["when"], t["priority"], t["depends-on"]), ("reminder", "2026-10-09", "normal", []))

    def test_a_board_edit_keeps_a_reminder_lean(self):
        T.add_task(self.tmp, self.today, "Call mum", kind="reminder", when="2026-10-09")
        T.update_task(self.tmp, "Call mum", {"when": "2026-10-10"}, self.today)
        text = (self.tmp / "Call mum.md").read_text()
        self.assertIn("when: 2026-10-10", text)
        self.assertNotIn("priority:", text)

    def test_reminders_never_in_today_and_have_their_own_view(self):
        make(self.tmp, "Call mum", kind="reminder", project=None, when="2026-10-06")
        make(self.tmp, "Buy sandpaper", kind="reminder", project=None, when="2026-11-01")
        make(self.tmp, "Old style", kind="reminder", project=None, due="2026-10-20")         # an older note's day in due
        make(self.tmp, "Old reminder", kind="reminder", project=None, when="2026-10-01", status="done", done="2026-10-01")
        make(self.tmp, "Real work", due="2026-10-07")
        v = T.views(T.load_tasks(self.tmp)[0], self.today)
        self.assertEqual([t["title"] for t in v["today"]], ["Real work"])
        self.assertEqual([t["title"] for t in v["reminders"]], ["Call mum", "Old style", "Buy sandpaper"])
        self.assertEqual(v["unplanned"], [])

    def test_brief_lists_reminders_from_two_days_ahead_and_marks_the_late_ones(self):
        make(self.tmp, "Late nudge", kind="reminder", project=None, when="2026-10-05")
        make(self.tmp, "Today nudge", kind="reminder", project=None, when="2026-10-07")
        make(self.tmp, "Friday nudge", kind="reminder", project=None, when="2026-10-09")
        make(self.tmp, "Next week nudge", kind="reminder", project=None, when="2026-10-12")
        b = T.brief(self.tmp, self.today)
        self.assertEqual([t["title"] for t in b["reminders"]], ["Late nudge", "Today nudge", "Friday nudge"])
        text = T.format_brief(b, self.today)
        self.assertIn("Reminders: overdue, today and the next 2 days (3)", text)
        self.assertIn("  - Late nudge  2026-10-05 (overdue)\n", text)
        self.assertIn("  - Today nudge  2026-10-07\n", text)

    def test_reminders_are_never_stale_and_never_wait(self):
        make(self.tmp, "Far nudge", kind="reminder", project=None, when="2026-12-01", updated="2026-08-01", owner="Dan")
        b = T.brief(self.tmp, self.today)
        self.assertEqual((b["stale"], b["waiting"]), ([], []))


class BriefSections(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.today = date(2026, 10, 7)

    def test_decisions_oldest_first_without_an_age(self):
        make(self.tmp, "New call", decision="true", created="2026-10-05")
        make(self.tmp, "Old call", decision="true", created="2026-09-20")
        make(self.tmp, "Not a call")
        b = T.brief(self.tmp, self.today)
        self.assertEqual([t["title"] for t in b["decisions"]], ["Old call", "New call"])
        self.assertIn("Decisions waiting, oldest first (2)", T.format_brief(b, self.today))

    def test_unsorted_section_matches_the_board(self):
        make(self.tmp, "Half a thought", status="inbox", project=None)
        self.assertIn("To sort (1)", T.format_brief(T.brief(self.tmp, self.today), self.today))

    def test_counts_keep_reminders_apart_from_work(self):
        make(self.tmp, "Work")
        make(self.tmp, "Nudge", kind="reminder", project=None, when="2026-10-20")
        b = T.brief(self.tmp, self.today)
        self.assertEqual(b["counts"]["todo"], 1)
        self.assertIn("counts: inbox 0, todo 1, reminders 1", T.format_brief(b, self.today))

    def test_others_tasks_wait_and_never_sit_on_today(self):
        make(self.tmp, "Accountant sends figures", owner="Dan", due="2026-10-05")
        b = T.brief(self.tmp, self.today)
        self.assertEqual(b["today"], [])
        self.assertEqual([t["title"] for t in b["waiting"]], ["Accountant sends figures"])

    def test_untouched_shows_five_high_priority_first(self):
        for i in range(6):
            make(self.tmp, f"Old {i}", updated="2026-08-01")
        make(self.tmp, "Old but important", updated="2026-09-01", priority="high")
        b = T.brief(self.tmp, self.today)
        self.assertEqual(len(b["stale"]), 7)
        text = T.format_brief(b, self.today).split("Untouched for 14+ days (7)")[1]
        lines = [l for l in text.splitlines() if l.startswith("  - ")]
        self.assertEqual(len(lines), 5)
        self.assertIn("Old but important", lines[0])
        self.assertIn("and 2 more", text)

    def test_archived_done_dependency_shows_as_newly_unblocked(self):
        (self.tmp / "Archive").mkdir()
        make(self.tmp / "Archive", "Gate", status="done", done="2026-08-01")
        make(self.tmp, "Freed", status="blocked", **{"depends-on": ["[[Gate]]"]})
        self.assertEqual([t["title"] for t in T.brief(self.tmp, self.today)["unblocked"]], ["Freed"])


class Readability(unittest.TestCase):
    """The template readability review (2026-10-08): names, goals, the owner, list labels."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.today = date(2026, 10, 7)

    def test_owner_name_matches_without_regard_to_case(self):
        p = T.add_task(self.tmp, self.today, "Mine in lower case", owner=T.OWNER.lower())
        self.assertIn(f"owner: {T.OWNER}", p.read_text())
        make(self.tmp, "Typed by hand", owner=T.OWNER.upper(), when="2026-10-07")
        v = T.views(T.load_tasks(self.tmp)[0], self.today)
        self.assertEqual([t["title"] for t in v["today"]], ["Typed by hand"])
        self.assertEqual(v["waiting"], [])

    def test_add_refuses_a_parent_that_is_not_a_goal(self):
        make(self.tmp, "Sell the flat", kind="project")
        make(self.tmp, "Plain task")
        with self.assertRaisesRegex(T.TaskError, "not a goal"):
            T.add_task(self.tmp, self.today, "Child", parent="Plain task")
        with self.assertRaisesRegex(T.TaskError, "no goal"):
            T.add_task(self.tmp, self.today, "Child", parent="Nothing by that name")
        with self.assertRaisesRegex(T.TaskError, "another goal"):
            T.add_task(self.tmp, self.today, "Sub-goal", parent="Sell the flat", kind="project")
        T.add_task(self.tmp, self.today, "Get a valuation", parent="Sell the flat")

    def test_add_warns_when_the_folder_note_is_missing(self):
        code, out = cli(self.tmp, self.today, "add", "Typo task", "--project", "Hoem-does-not-exist")
        self.assertEqual(code, 0)
        self.assertIn("WARNING: no folder note for 'Hoem-does-not-exist'", out)

    def test_sync_reports_a_goal_whose_tasks_are_all_finished(self):
        make(self.tmp, "Sell the flat", kind="project")
        make(self.tmp, "Get a valuation", parent="[[Sell the flat]]", status="done", done="2026-10-06")
        make(self.tmp, "Pick an agent", parent="[[Sell the flat]]", status="dropped")
        make(self.tmp, "Open goal", kind="project")
        make(self.tmp, "Still to do", parent="[[Open goal]]")
        review = T.sync(self.tmp, self.today, archive=False)["review"]
        self.assertIn("Sell the flat: every task under this goal is finished - close it?", review)
        self.assertFalse(any(l.startswith("Open goal") for l in review))

    def test_log_lines_say_status_not_the_key(self):
        make(self.tmp, "Thing")
        T.update_task(self.tmp, "Thing", {T.STATUS: "doing"}, self.today)
        self.assertIn("board: status todo → doing", (self.tmp / "Thing.md").read_text())

    def test_list_marks_goals_and_reminders(self):
        make(self.tmp, "Sell the flat", kind="project")
        make(self.tmp, "Call mum", kind="reminder", project=None, when="2026-10-09")
        make(self.tmp, "Get a valuation")
        text = T.format_list(T.list_tasks(self.tmp))
        self.assertIn("Sell the flat  (goal)", text)
        self.assertIn("Call mum  (reminder)", text)
        self.assertIn("Get a valuation\n", text)

    def test_a_task_handed_to_someone_keeps_what_is_expected_and_gets_a_chase_date(self):
        p = T.add_task(self.tmp, self.today, "Quote for shelves", owner="Dan", expecting="the quote")
        fm, _ = T.parse_frontmatter(p.read_text())
        self.assertEqual((fm["expecting"], fm["chase-after"]), ("the quote", "2026-10-14"))

    def test_archive_is_a_week(self):
        self.assertEqual(T.ARCHIVE_DAYS, 7)



class PythonPerComputer(unittest.TestCase):
    """vault.json syncs between computers, so the Python command is kept per platform."""

    def test_dict_valued_python_is_read_for_this_platform(self):
        cfg = {"python": {"darwin": "python3", "windows": "python"}}
        self.assertEqual(T.python_command(cfg, "darwin"), "python3")
        self.assertEqual(T.python_command(cfg, "win32"), "python")       # sys.platform's name for Windows

    def test_unknown_or_missing_platform_falls_back_to_finding_it_again(self):
        self.assertIsNone(T.python_command({"python": {"darwin": "python3"}}, "win32"))
        self.assertIsNone(T.python_command({"python": {"darwin": "python3"}}, "linux"))
        self.assertIsNone(T.python_command({}, "darwin"))
        self.assertIsNone(T.python_command({"python": {"windows": "  "}}, "win32"))

    def test_the_old_single_string_is_still_read(self):
        self.assertEqual(T.python_command({"python": "python3"}, "darwin"), "python3")

    def test_platform_names(self):
        self.assertEqual([T.platform_key(p) for p in ("darwin", "win32", "cygwin", "linux")],
                         ["darwin", "windows", "windows", "linux"])

if __name__ == "__main__":
    unittest.main()
