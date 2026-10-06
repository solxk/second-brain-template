"""Tests for tasks.py. Run from the vault root:
    python3 -m unittest Scripts/test_tasks.py -v
or from this folder: python3 -m unittest test_tasks -v
"""
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
owner: Me
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
        T.sync(self.tmp, self.today)
        tasks, _ = T.load_tasks(self.tmp)
        self.assertEqual(tasks["Fresh done"]["done"], "2026-09-04")
        self.assertNotIn("Old done", tasks)
        self.assertTrue((self.tmp / "Archive" / "Old done.md").exists())

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
    def test_sections(self):
        tmp = Path(tempfile.mkdtemp()); today = date(2026, 9, 4)
        make(tmp, "Overdue", due="2026-09-01")
        make(tmp, "Soon", due="2026-09-08")
        make(tmp, "Later", due="2026-10-01")
        make(tmp, "Hot", priority="high")
        make(tmp, "Dump", status="inbox", project=None)
        make(tmp, "Stale", updated="2026-08-01")
        make(tmp, "Parked", status="someday", updated="2026-01-01")
        make(tmp, "Gate", status="done", done="2026-09-03")
        make(tmp, "Freed", status="blocked", **{"depends-on": ["[[Gate]]"]})
        b = T.brief(tmp, today)
        self.assertEqual([t["title"] for t in b["overdue"]], ["Overdue"])
        self.assertEqual([t["title"] for t in b["soon"]], ["Soon"])
        self.assertEqual([t["title"] for t in b["high"]], ["Hot"])
        self.assertEqual([t["title"] for t in b["inbox"]], ["Dump"])
        self.assertEqual([t["title"] for t in b["stale"]], ["Stale"])
        self.assertEqual([t["title"] for t in b["unblocked"]], ["Freed"])
        text = T.format_brief(b, today)
        self.assertIn("OVERDUE", text)
        self.assertIn("Overdue", text)

    def test_reports_names_in_both_live_and_archive(self):
        tmp = Path(tempfile.mkdtemp()); today = date(2026, 9, 4)
        (tmp / "Archive").mkdir()
        make(tmp / "Archive", "Ghost", status="dropped")
        make(tmp, "Ghost")
        make(tmp, "Fine")
        b = T.brief(tmp, today)
        self.assertEqual(b["in_both"], ["Ghost"])
        self.assertIn("ALSO IN ARCHIVE", T.format_brief(b, today))

    def test_missing_folder_is_empty(self):
        b = T.brief(Path(tempfile.mkdtemp()) / "nope", date(2026, 9, 4))
        self.assertEqual(b["overdue"], [])


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
        self.assertEqual([t["title"] for t in v["today"]], ["Overdue", "Soon", "Doing", "High"])
        self.assertEqual([t["title"] for t in v["waiting"]], ["Not mine", "High blocked"])

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
            T.update_task(self.tmp, "Owned", {"owner": "Me\nproject: [[X]]"}, self.today)
        fm, _ = T.parse_frontmatter((self.tmp / "Owned.md").read_text())
        self.assertEqual(fm["owner"], T.OWNER)

    def test_board_cannot_set_blocked(self):
        make(self.tmp, "Derived")
        with self.assertRaises(T.TaskError):
            T.update_task(self.tmp, "Derived", {T.STATUS: "blocked"}, self.today, source="board")

    def test_brief_lists_decisions_oldest_first(self):
        make(self.tmp, "New call", decision="true", created="2026-10-01")
        make(self.tmp, "Old call", decision="true", created="2026-09-01")
        make(self.tmp, "Not a call")
        b = T.brief(self.tmp, self.today)
        self.assertEqual([t["title"] for t in b["decisions"]], ["Old call", "New call"])
        self.assertIn("Decisions waiting (2)", T.format_brief(b, self.today))

    def test_sync_without_archive_keeps_dropped_in_place(self):
        make(self.tmp, "Dropped", status="dropped")
        r = T.sync(self.tmp, self.today, archive=False)
        self.assertEqual(r["archived"], [])
        self.assertTrue((self.tmp / "Dropped.md").exists())


if __name__ == "__main__":
    unittest.main()
