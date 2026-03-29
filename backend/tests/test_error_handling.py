"""
tests/test_error_handling.py
----------------------------
Tests for consistent error envelope, input validation edge cases,
and HTTP contract guarantees.
"""

import pytest


class TestErrorEnvelope:
    """Every error response must be  { "error": true, "detail": "<string>" }"""

    def test_404_update_nonexistent(self, client):
        resp = client.put("/tasks/99999", json={"title": "Ghost"})
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"] is True
        assert isinstance(body["detail"], str)

    def test_404_delete_nonexistent(self, client):
        resp = client.delete("/tasks/99999")
        assert resp.status_code == 404
        assert resp.json()["error"] is True

    def test_422_empty_title(self, client):
        resp = client.post("/tasks", json={"title": ""})
        assert resp.status_code == 422
        assert resp.json()["error"] is True

    def test_422_circular_dep(self, client, make_task):
        a = make_task(title="A")
        b = make_task(title="B", blocked_by=a["id"])
        resp = client.put(f"/tasks/{a['id']}", json={"blocked_by": b["id"]})
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"] is True
        assert "circular" in body["detail"].lower()

    def test_422_self_block(self, client, make_task):
        task = make_task()
        resp = client.put(f"/tasks/{task['id']}", json={"blocked_by": task["id"]})
        assert resp.status_code == 422
        assert resp.json()["error"] is True

    def test_detail_always_string(self, client):
        resp = client.put("/tasks/99999", json={"title": "x"})
        assert isinstance(resp.json()["detail"], str)

    def test_404_blocked_by_nonexistent(self, client):
        resp = client.post("/tasks", json={"title": "T", "blocked_by": 9999})
        assert resp.status_code == 404
        assert resp.json()["error"] is True


class TestInputValidation:

    def test_missing_title_rejected(self, client):
        assert client.post("/tasks", json={"description": "no title"}).status_code == 422

    def test_spaces_only_title_rejected(self, client):
        assert client.post("/tasks", json={"title": "     "}).status_code == 422

    def test_single_char_title_accepted(self, client):
        assert client.post("/tasks", json={"title": "X"}).status_code == 201

    def test_255_char_title_accepted(self, client):
        assert client.post("/tasks", json={"title": "A" * 255}).status_code == 201

    def test_invalid_date_format_rejected(self, client):
        assert client.post("/tasks", json={"title": "T", "due_date": "31-12-2025"}).status_code == 422

    def test_null_title_rejected(self, client):
        assert client.post("/tasks", json={"title": None}).status_code == 422

    def test_string_blocked_by_rejected(self, client):
        assert client.post("/tasks", json={"title": "T", "blocked_by": "abc"}).status_code == 422

    def test_float_blocked_by_rejected(self, client):
        assert client.post("/tasks", json={"title": "T", "blocked_by": 1.5}).status_code == 422

    def test_invalid_json_rejected(self, client):
        resp = client.post(
            "/tasks",
            content="not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422


class TestHttpContract:

    def test_get_tasks_json_content_type(self, client):
        assert "application/json" in client.get("/tasks").headers["content-type"]

    def test_post_returns_json(self, client):
        assert "application/json" in client.post("/tasks", json={"title": "T"}).headers["content-type"]

    def test_id_is_integer(self, client, make_task):
        assert isinstance(make_task()["id"], int)

    def test_blocked_by_in_response(self, client, make_task):
        a = make_task(title="A")
        b = make_task(title="B", blocked_by=a["id"])
        assert b["blocked_by"] == a["id"]

    def test_due_date_null_when_not_set(self, client, make_task):
        assert make_task()["due_date"] is None

    def test_due_date_iso_format(self, client, make_task):
        task = make_task(due_date="2025-11-30")
        assert task["due_date"] == "2025-11-30"

    def test_status_defaults_to_todo(self, client):
        assert client.post("/tasks", json={"title": "T"}).json()["status"] == "To-Do"

    def test_recurring_defaults_to_none(self, client):
        assert client.post("/tasks", json={"title": "T"}).json()["recurring"] == "None"
