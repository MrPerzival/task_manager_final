"""
tests/test_dependencies.py
--------------------------
Tests for the task dependency system:
  blocked_by validation, self-block, circular dependency (DFS), orphan cleanup.
"""

import pytest


class TestSelfBlock:

    def test_self_block_on_update_rejected(self, client, make_task):
        task = make_task()
        resp = client.put(f"/tasks/{task['id']}", json={"blocked_by": task["id"]})
        assert resp.status_code == 422
        assert "itself" in resp.json()["detail"].lower()

    def test_new_task_never_self_blocked(self, client, make_task):
        task = make_task()
        assert task["blocked_by"] != task["id"]


class TestCircularDependency:

    def test_direct_cycle_rejected(self, client, make_task):
        """A → B, then B → A must be rejected."""
        a = make_task(title="A")
        b = make_task(title="B", blocked_by=a["id"])
        resp = client.put(f"/tasks/{a['id']}", json={"blocked_by": b["id"]})
        assert resp.status_code == 422
        assert "circular" in resp.json()["detail"].lower()

    def test_indirect_cycle_rejected(self, client, make_task):
        """A → B → C, then C → A must be rejected."""
        a = make_task(title="A")
        b = make_task(title="B", blocked_by=a["id"])
        c = make_task(title="C", blocked_by=b["id"])
        resp = client.put(f"/tasks/{a['id']}", json={"blocked_by": c["id"]})
        assert resp.status_code == 422
        assert "circular" in resp.json()["detail"].lower()

    def test_four_node_cycle_rejected(self, client, make_task):
        """A → B → C → D, then D → A must be rejected."""
        a = make_task(title="A")
        b = make_task(title="B", blocked_by=a["id"])
        c = make_task(title="C", blocked_by=b["id"])
        d = make_task(title="D", blocked_by=c["id"])
        resp = client.put(f"/tasks/{a['id']}", json={"blocked_by": d["id"]})
        assert resp.status_code == 422

    def test_independent_chain_allowed(self, client, make_task):
        """Separate chains — linking E → D should succeed."""
        a = make_task(title="A")
        make_task(title="B", blocked_by=a["id"])
        c = make_task(title="C")
        d = make_task(title="D", blocked_by=c["id"])
        e = make_task(title="E")
        resp = client.put(f"/tasks/{e['id']}", json={"blocked_by": d["id"]})
        assert resp.status_code == 200

    def test_cycle_check_leaves_tasks_unchanged(self, client, make_task):
        """After rejected cycle, involved tasks must be unchanged."""
        a = make_task(title="A")
        b = make_task(title="B", blocked_by=a["id"])
        client.put(f"/tasks/{a['id']}", json={"blocked_by": b["id"]})
        tasks = {t["id"]: t for t in client.get("/tasks").json()}
        assert tasks[a["id"]]["blocked_by"] is None
        assert tasks[b["id"]]["blocked_by"] == a["id"]


class TestBlockingState:

    def test_blocked_task_references_blocker(self, client, make_task):
        a = make_task(title="A — not done")
        b = make_task(title="B — blocked", blocked_by=a["id"])
        tasks = {t["id"]: t for t in client.get("/tasks").json()}
        assert tasks[b["id"]]["blocked_by"] == a["id"]
        assert tasks[a["id"]]["status"] != "Done"

    def test_blocker_done_unblocks_logically(self, client, make_task):
        """Once A is Done, B's blocked_by still points to A but A.status == Done."""
        a = make_task(title="A")
        b = make_task(title="B", blocked_by=a["id"])
        client.put(f"/tasks/{a['id']}", json={"status": "Done"})
        tasks = {t["id"]: t for t in client.get("/tasks").json()}
        assert tasks[a["id"]]["status"] == "Done"
        assert tasks[b["id"]]["blocked_by"] == a["id"]

    def test_missing_blocker_rejected_on_create(self, client):
        resp = client.post("/tasks", json={"title": "T", "blocked_by": 88888})
        assert resp.status_code == 404

    def test_blocker_deleted_clears_dependent(self, client, make_task):
        blocker = make_task(title="Blocker")
        dep = make_task(title="Dep", blocked_by=blocker["id"])
        client.delete(f"/tasks/{blocker['id']}")
        tasks = {t["id"]: t for t in client.get("/tasks").json()}
        assert tasks[dep["id"]]["blocked_by"] is None

    def test_three_task_chain(self, client, make_task):
        a = make_task(title="A")
        b = make_task(title="B", blocked_by=a["id"])
        c = make_task(title="C", blocked_by=b["id"])
        tasks = {t["id"]: t for t in client.get("/tasks").json()}
        assert tasks[b["id"]]["blocked_by"] == a["id"]
        assert tasks[c["id"]]["blocked_by"] == b["id"]
