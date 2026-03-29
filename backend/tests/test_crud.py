"""
tests/test_crud.py
------------------
CRUD coverage: GET / POST / PUT / DELETE + health check.
"""

import pytest


class TestGetTasks:

    def test_empty_list(self, client):
        resp = client.get("/tasks")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_created_tasks(self, client, make_task):
        make_task(title="Alpha")
        make_task(title="Beta")
        titles = [t["title"] for t in client.get("/tasks").json()]
        assert "Alpha" in titles and "Beta" in titles

    def test_filter_by_status(self, client, make_task):
        make_task(title="Todo",  status="To-Do")
        make_task(title="Done",  status="Done")
        data = client.get("/tasks?status=Done").json()
        assert len(data) == 1
        assert data[0]["title"] == "Done"

    def test_filter_by_search(self, client, make_task):
        make_task(title="Buy groceries")
        make_task(title="Write tests")
        data = client.get("/tasks?search=grocer").json()
        assert len(data) == 1
        assert data[0]["title"] == "Buy groceries"

    def test_search_case_insensitive(self, client, make_task):
        make_task(title="Deploy to Production")
        assert len(client.get("/tasks?search=DEPLOY").json()) == 1

    def test_combined_filter(self, client, make_task):
        make_task(title="Fix bug",        status="In Progress")
        make_task(title="Fix deployment", status="Done")
        data = client.get("/tasks?status=In Progress&search=fix").json()
        assert len(data) == 1
        assert data[0]["title"] == "Fix bug"

    def test_response_shape(self, client, make_task):
        task = make_task()
        required = {"id", "title", "description", "due_date", "status", "blocked_by", "recurring"}
        assert required.issubset(task.keys())

    def test_tasks_ordered_by_id(self, client, make_task):
        make_task(title="First")
        make_task(title="Second")
        make_task(title="Third")
        ids = [t["id"] for t in client.get("/tasks").json()]
        assert ids == sorted(ids)


class TestCreateTask:

    def test_minimal(self, client):
        resp = client.post("/tasks", json={"title": "Minimal"})
        assert resp.status_code == 201
        d = resp.json()
        assert d["title"] == "Minimal"
        assert d["status"] == "To-Do"
        assert d["recurring"] == "None"
        assert d["blocked_by"] is None
        assert d["id"] > 0

    def test_all_fields(self, client):
        payload = {
            "title": "Full",
            "description": "All fields",
            "due_date": "2025-12-31",
            "status": "In Progress",
            "recurring": "Weekly",
        }
        resp = client.post("/tasks", json=payload)
        assert resp.status_code == 201
        d = resp.json()
        assert d["description"] == "All fields"
        assert d["due_date"] == "2025-12-31"
        assert d["recurring"] == "Weekly"

    def test_title_trimmed(self, client):
        resp = client.post("/tasks", json={"title": "  Padded  "})
        assert resp.status_code == 201
        assert resp.json()["title"] == "Padded"

    def test_empty_title_rejected(self, client):
        assert client.post("/tasks", json={"title": ""}).status_code == 422

    def test_whitespace_title_rejected(self, client):
        assert client.post("/tasks", json={"title": "   "}).status_code == 422

    def test_invalid_status_rejected(self, client):
        assert client.post("/tasks", json={"title": "T", "status": "NOPE"}).status_code == 422

    def test_invalid_recurring_rejected(self, client):
        assert client.post("/tasks", json={"title": "T", "recurring": "Hourly"}).status_code == 422

    def test_nonexistent_blocked_by_rejected(self, client):
        assert client.post("/tasks", json={"title": "T", "blocked_by": 9999}).status_code == 404

    def test_blocked_by_valid_task(self, client, make_task):
        blocker = make_task(title="Blocker")
        resp = client.post("/tasks", json={"title": "Blocked", "blocked_by": blocker["id"]})
        assert resp.status_code == 201
        assert resp.json()["blocked_by"] == blocker["id"]

    def test_unique_ids(self, client, make_task):
        t1 = make_task(title="T1")
        t2 = make_task(title="T2")
        assert t1["id"] != t2["id"]

    def test_description_defaults_empty(self, client):
        assert client.post("/tasks", json={"title": "T"}).json()["description"] == ""

    def test_due_date_null_when_omitted(self, client):
        assert client.post("/tasks", json={"title": "T"}).json()["due_date"] is None

    def test_extra_fields_ignored(self, client):
        resp = client.post("/tasks", json={"title": "T", "unknown": "ignored"})
        assert resp.status_code == 201
        assert "unknown" not in resp.json()

    def test_missing_title_rejected(self, client):
        assert client.post("/tasks", json={"description": "no title"}).status_code == 422


class TestUpdateTask:

    def test_update_title(self, client, make_task):
        task = make_task(title="Old")
        resp = client.put(f"/tasks/{task['id']}", json={"title": "New"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "New"

    def test_update_status(self, client, make_task):
        task = make_task(title="T")
        resp = client.put(f"/tasks/{task['id']}", json={"status": "In Progress"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "In Progress"

    def test_update_nonexistent_404(self, client):
        assert client.put("/tasks/99999", json={"title": "Ghost"}).status_code == 404

    def test_empty_title_rejected(self, client, make_task):
        task = make_task()
        assert client.put(f"/tasks/{task['id']}", json={"title": "  "}).status_code == 422

    def test_title_trimmed_on_update(self, client, make_task):
        task = make_task(title="Original")
        resp = client.put(f"/tasks/{task['id']}", json={"title": "  Trimmed  "})
        assert resp.json()["title"] == "Trimmed"

    def test_partial_preserves_other_fields(self, client, make_task):
        task = make_task(title="Full", description="Keep me", status="In Progress")
        resp = client.put(f"/tasks/{task['id']}", json={"title": "Updated"})
        d = resp.json()
        assert d["description"] == "Keep me"
        assert d["status"] == "In Progress"

    def test_update_due_date(self, client, make_task):
        task = make_task()
        resp = client.put(f"/tasks/{task['id']}", json={"due_date": "2026-06-15"})
        assert resp.json()["due_date"] == "2026-06-15"

    def test_update_recurring(self, client, make_task):
        task = make_task()
        resp = client.put(f"/tasks/{task['id']}", json={"recurring": "Daily"})
        assert resp.json()["recurring"] == "Daily"


class TestDeleteTask:

    def test_delete_existing(self, client, make_task):
        task = make_task()
        assert client.delete(f"/tasks/{task['id']}").status_code == 204

    def test_deleted_not_in_list(self, client, make_task):
        task = make_task()
        client.delete(f"/tasks/{task['id']}")
        ids = [t["id"] for t in client.get("/tasks").json()]
        assert task["id"] not in ids

    def test_delete_nonexistent_404(self, client):
        assert client.delete("/tasks/99999").status_code == 404

    def test_delete_clears_blocked_by(self, client, make_task):
        blocker = make_task(title="Blocker")
        dep = make_task(title="Dependent", blocked_by=blocker["id"])
        client.delete(f"/tasks/{blocker['id']}")
        tasks = {t["id"]: t for t in client.get("/tasks").json()}
        assert tasks[dep["id"]]["blocked_by"] is None

    def test_delete_response_empty_body(self, client, make_task):
        task = make_task()
        resp = client.delete(f"/tasks/{task['id']}")
        assert resp.content == b""


class TestHealthCheck:

    def test_root_ok(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        d = resp.json()
        assert d["status"] == "ok"
        assert "version" in d

    def test_returns_json(self, client):
        resp = client.get("/tasks")
        assert "application/json" in resp.headers["content-type"]
