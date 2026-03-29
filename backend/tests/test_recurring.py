"""
tests/test_recurring.py
-----------------------
Tests for recurring task auto-spawn logic.

Rules
-----
• Daily  → due_date + 1 day,  status = To-Do
• Weekly → due_date + 7 days, status = To-Do
• Only fires on the Done transition (idempotent guard)
• Non-recurring tasks must NOT spawn
• Tasks with no due_date still spawn (next due_date stays None)
"""

import pytest


def all_tasks(client):
    return client.get("/tasks").json()


def by_title(client, title):
    return [t for t in all_tasks(client) if t["title"] == title]


class TestDailyRecurring:

    def test_spawns_new_task_on_done(self, client, make_task):
        task = make_task(title="Daily", due_date="2025-06-01", recurring="Daily")
        client.put(f"/tasks/{task['id']}", json={"status": "Done"})
        assert len(by_title(client, "Daily")) == 2

    def test_new_task_due_date_plus_one(self, client, make_task):
        task = make_task(title="D+1", due_date="2025-06-10", recurring="Daily")
        client.put(f"/tasks/{task['id']}", json={"status": "Done"})
        nxt = next(t for t in by_title(client, "D+1") if t["id"] != task["id"])
        assert nxt["due_date"] == "2025-06-11"

    def test_new_task_status_todo(self, client, make_task):
        task = make_task(title="DStatus", due_date="2025-01-01", recurring="Daily")
        client.put(f"/tasks/{task['id']}", json={"status": "Done"})
        nxt = next(t for t in by_title(client, "DStatus") if t["id"] != task["id"])
        assert nxt["status"] == "To-Do"

    def test_original_task_preserved(self, client, make_task):
        task = make_task(title="DOrig", due_date="2025-03-01", recurring="Daily")
        client.put(f"/tasks/{task['id']}", json={"status": "Done"})
        orig = next(t for t in by_title(client, "DOrig") if t["id"] == task["id"])
        assert orig["status"] == "Done"
        assert orig["due_date"] == "2025-03-01"

    def test_new_task_has_new_id(self, client, make_task):
        task = make_task(title="DID", due_date="2025-05-05", recurring="Daily")
        client.put(f"/tasks/{task['id']}", json={"status": "Done"})
        ids = [t["id"] for t in by_title(client, "DID")]
        assert len(set(ids)) == 2

    def test_copies_description(self, client, make_task):
        task = make_task(title="DDesc", description="Notes", due_date="2025-07-01", recurring="Daily")
        client.put(f"/tasks/{task['id']}", json={"status": "Done"})
        nxt = next(t for t in by_title(client, "DDesc") if t["id"] != task["id"])
        assert nxt["description"] == "Notes"

    def test_copies_recurring_field(self, client, make_task):
        task = make_task(title="DRec", due_date="2025-08-01", recurring="Daily")
        client.put(f"/tasks/{task['id']}", json={"status": "Done"})
        nxt = next(t for t in by_title(client, "DRec") if t["id"] != task["id"])
        assert nxt["recurring"] == "Daily"


class TestWeeklyRecurring:

    def test_spawns_new_task_on_done(self, client, make_task):
        task = make_task(title="Weekly", due_date="2025-06-01", recurring="Weekly")
        client.put(f"/tasks/{task['id']}", json={"status": "Done"})
        assert len(by_title(client, "Weekly")) == 2

    def test_new_task_due_date_plus_seven(self, client, make_task):
        task = make_task(title="W+7", due_date="2025-06-01", recurring="Weekly")
        client.put(f"/tasks/{task['id']}", json={"status": "Done"})
        nxt = next(t for t in by_title(client, "W+7") if t["id"] != task["id"])
        assert nxt["due_date"] == "2025-06-08"

    def test_month_boundary(self, client, make_task):
        """June 28 + 7 = July 5."""
        task = make_task(title="WMonth", due_date="2025-06-28", recurring="Weekly")
        client.put(f"/tasks/{task['id']}", json={"status": "Done"})
        nxt = next(t for t in by_title(client, "WMonth") if t["id"] != task["id"])
        assert nxt["due_date"] == "2025-07-05"

    def test_year_boundary(self, client, make_task):
        """Dec 29 + 7 = Jan 5."""
        task = make_task(title="WYear", due_date="2025-12-29", recurring="Weekly")
        client.put(f"/tasks/{task['id']}", json={"status": "Done"})
        nxt = next(t for t in by_title(client, "WYear") if t["id"] != task["id"])
        assert nxt["due_date"] == "2026-01-05"

    def test_new_task_status_todo(self, client, make_task):
        task = make_task(title="WStatus", due_date="2025-06-15", recurring="Weekly")
        client.put(f"/tasks/{task['id']}", json={"status": "Done"})
        nxt = next(t for t in by_title(client, "WStatus") if t["id"] != task["id"])
        assert nxt["status"] == "To-Do"


class TestNoRecurring:

    def test_no_spawn_on_done(self, client, make_task):
        task = make_task(title="OneOff", recurring="None")
        client.put(f"/tasks/{task['id']}", json={"status": "Done"})
        assert len(by_title(client, "OneOff")) == 1

    def test_total_count_unchanged(self, client, make_task):
        make_task(title="T1")
        make_task(title="T2")
        t3 = make_task(title="T3", recurring="None")
        before = len(all_tasks(client))
        client.put(f"/tasks/{t3['id']}", json={"status": "Done"})
        assert len(all_tasks(client)) == before


class TestIdempotency:

    def test_done_to_done_no_extra_spawn(self, client, make_task):
        """Marking an already-Done recurring task Done again must NOT re-spawn."""
        task = make_task(title="Idem", due_date="2025-09-01", recurring="Daily")
        client.put(f"/tasks/{task['id']}", json={"status": "Done"})
        assert len(by_title(client, "Idem")) == 2
        client.put(f"/tasks/{task['id']}", json={"status": "Done"})
        assert len(by_title(client, "Idem")) == 2  # still 2, not 3


class TestNoDueDate:

    def test_daily_no_due_date_still_spawns(self, client, make_task):
        task = make_task(title="NDD", recurring="Daily")
        client.put(f"/tasks/{task['id']}", json={"status": "Done"})
        assert len(by_title(client, "NDD")) == 2

    def test_next_task_also_has_no_due_date(self, client, make_task):
        task = make_task(title="NDDNext", recurring="Daily")
        client.put(f"/tasks/{task['id']}", json={"status": "Done"})
        nxt = next(t for t in by_title(client, "NDDNext") if t["id"] != task["id"])
        assert nxt["due_date"] is None
