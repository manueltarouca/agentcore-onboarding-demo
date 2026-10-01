import json

from fastapi.testclient import TestClient

from onboarding_demo.web.api import create_app


class FakeRuntime:
    """Stands in for AgentCore Runtime: records who called it, replays scripted events."""

    def __init__(self):
        self.calls = []

    async def invoke(self, token: str, session_id: str, payload: dict):
        self.calls.append((token, session_id, payload["action"]))
        if payload["action"] == "start":
            yield {"type": "run_started", "at": 0, "steps": []}
            yield {"type": "awaiting_approval", "at": 1, "step": "human_review"}
        else:
            yield {"type": "step_completed", "at": 2, "step": "human_review", "detail": {}}
            yield {"type": "run_completed", "at": 3, "totals": {}}


class FakeAuth:
    async def sign_in(self, username: str) -> str:
        return f"token-for-{username}"


def make_client(tmp_path, runtime=None):
    runtime = runtime or FakeRuntime()
    app = create_app(runtime=runtime, auth=FakeAuth(), outputs={"Region": "us-west-2"},
                     replay_file=tmp_path / "replay.json", static_dir=None)
    return TestClient(app), runtime


def read_events(client, run_id):
    """Approve first: the test client buffers the whole stream, so it cannot answer mid-stream."""
    client.post(f"/api/runs/{run_id}/approve")
    with client.stream("GET", f"/api/runs/{run_id}/events") as stream:
        return [json.loads(l.removeprefix("data: ")) for l in stream.iter_lines() if l.startswith("data: ")]


def test_live_run_starts_as_the_relationship_manager_and_approves_as_compliance(tmp_path):
    client, runtime = make_client(tmp_path)
    run_id = client.post("/api/runs", json={"mode": "live"}).json()["run_id"]

    events = read_events(client, run_id)

    assert [e["type"] for e in events][-1] == "run_completed"
    (first_token, first_session, _), (second_token, second_session, _) = runtime.calls
    assert first_token == "token-for-rita.almeida"
    assert second_token == "token-for-compliance.officer"
    assert first_session == second_session and len(first_session) >= 33


def test_a_live_run_is_saved_as_the_replay(tmp_path):
    client, _ = make_client(tmp_path)
    read_events(client, client.post("/api/runs", json={"mode": "live"}).json()["run_id"])

    replay_id = client.post("/api/runs", json={"mode": "replay", "speed": 100}).json()["run_id"]

    assert [e["type"] for e in read_events(client, replay_id)][-1] == "run_completed"


def test_config_lists_personas_and_console_links(tmp_path):
    client, _ = make_client(tmp_path)

    config = client.get("/api/config").json()

    assert [p["id"] for p in config["personas"]] == ["client", "relationship_manager", "compliance", "engineering"]
    assert "links" in config


def test_unknown_run_returns_404(tmp_path):
    client, _ = make_client(tmp_path)

    assert client.get("/api/runs/nope/events").status_code == 404


def test_a_reconnecting_browser_resumes_after_the_last_event_it_saw(tmp_path):
    client, _ = make_client(tmp_path)
    run_id = client.post("/api/runs", json={"mode": "live"}).json()["run_id"]
    client.post(f"/api/runs/{run_id}/approve")

    with client.stream("GET", f"/api/runs/{run_id}/events", headers={"Last-Event-ID": "1"}) as stream:
        lines = [l for l in stream.iter_lines() if l.startswith(("data: ", "id: "))]

    assert lines[0] == "id: 2"
    assert json.loads(lines[1].removeprefix("data: "))["type"] == "step_completed"


def test_config_describes_every_step_before_any_run(tmp_path):
    client, _ = make_client(tmp_path)

    steps = client.get("/api/config").json()["steps"]

    assert len(steps) == 10
    assert all(s["description"] for s in steps)
    assert [s["invocation"] for s in steps] == [1] * 6 + [2] * 4


def test_the_page_is_never_cached_so_a_new_build_shows_up_immediately(tmp_path):
    (tmp_path / "dist" / "assets").mkdir(parents=True)
    (tmp_path / "dist" / "index.html").write_text("<html></html>")
    app = create_app(runtime=FakeRuntime(), auth=FakeAuth(), outputs={}, replay_file=tmp_path / "r.json",
                     static_dir=tmp_path / "dist")

    response = TestClient(app).get("/")

    assert response.headers["cache-control"] == "no-store"
