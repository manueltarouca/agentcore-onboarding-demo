"""Web API for the demo UI.

POST /api/runs                 start a run: "live" (AgentCore Runtime) or "replay" (a recorded live run)
GET  /api/runs/{id}/events     the run's events as Server-Sent Events
POST /api/runs/{id}/approve    the compliance officer's decision
GET  /api/config               personas and AWS console links
POST /api/chat                 one message from the client to the agent; returns what the agent did

A live run is two invocations of the same Runtime session: first as the relationship
manager, then, after approval, as the compliance officer.
"""
import asyncio
import json
import uuid
from pathlib import Path
from typing import Literal, Protocol

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from onboarding_demo.web.console_links import console_links
from onboarding_demo.workflow.runner import describe_steps

RELATIONSHIP_MANAGER = "rita.almeida"
COMPLIANCE_OFFICER = "compliance.officer"
CLIENT = "lusitania.client"
PERSONAS = [
    {"id": "client", "label": "Client", "user": "Lusitania Holdings SGPS"},
    {"id": "relationship_manager", "label": "Relationship manager", "user": "Rita Almeida"},
    {"id": "compliance", "label": "Compliance officer", "user": "Compliance officer"},
    {"id": "engineering", "label": "Engineering", "user": ""},
]
REPLAY_MIN_GAP_MS, REPLAY_MAX_GAP_MS = 500, 2500
HEARTBEAT_SECONDS = 10  # keeps proxies from closing an idle stream while a human decides


class Runtime(Protocol):
    def invoke(self, token: str, session_id: str, payload: dict): ...


class Auth(Protocol):
    async def sign_in(self, username: str) -> str: ...


class RunRequest(BaseModel):
    mode: Literal["live", "replay"] = "replay"
    speed: float = 1.0


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class Run:
    """One case run. Its events are kept, so a browser that reconnects can catch up."""

    def __init__(self, mode: str, speed: float):
        self.mode = mode
        self.speed = max(speed, 0.1)
        self.session_id = f"onboarding-{uuid.uuid4().hex}"  # Runtime needs 33+ characters
        self.approved = asyncio.Event()
        self.events: list[dict] = []
        self.done = False
        self.task: asyncio.Task | None = None
        self.changed: asyncio.Condition | None = None


def create_app(runtime: Runtime, auth: Auth, outputs: dict, replay_file: Path, static_dir: Path | None) -> FastAPI:
    app = FastAPI(title="Onboarding agent demo")
    runs: dict[str, Run] = {}

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "replay_available": replay_file.exists()}

    @app.get("/api/config")
    def config() -> dict:
        return {"personas": PERSONAS, "steps": describe_steps(), "links": console_links(outputs),
                "replay_available": replay_file.exists()}

    @app.post("/api/runs")
    def start_run(request: RunRequest) -> dict:
        if request.mode == "replay" and not replay_file.exists():
            raise HTTPException(404, "No recording yet. Run once in live mode.")
        run_id = uuid.uuid4().hex[:10]
        runs[run_id] = Run(request.mode, request.speed)
        return {"run_id": run_id}

    @app.post("/api/chat")
    async def chat(request: ChatRequest) -> dict:
        """One chat turn, as the client. The Runtime session (and Memory session) is the conversation."""
        session_id = request.session_id or f"client-chat-{uuid.uuid4().hex}"
        token = await auth.sign_in(CLIENT)
        events = [e async for e in runtime.invoke(token, session_id, {"action": "chat", "message": request.message})]
        return {"session_id": session_id, "events": events}

    @app.post("/api/runs/{run_id}/approve", status_code=204)
    def approve(run_id: str) -> None:
        find(run_id).approved.set()

    @app.get("/api/runs/{run_id}/events")
    def events(run_id: str, last_event_id: str | None = Header(default=None)) -> StreamingResponse:
        run = find(run_id)
        start = int(last_event_id) + 1 if last_event_id and last_event_id.isdigit() else 0

        async def server_sent_events():
            if run.task is None:  # the run executes in the background, not inside this connection
                run.changed = asyncio.Condition()
                run.task = asyncio.create_task(produce(run))
            index = start
            while True:
                while index < len(run.events):
                    yield f"id: {index}\ndata: {json.dumps(run.events[index])}\n\n"
                    index += 1
                if run.done:
                    return
                async with run.changed:
                    try:
                        await asyncio.wait_for(run.changed.wait(), HEARTBEAT_SECONDS)
                    except TimeoutError:
                        yield ": heartbeat\n\n"

        return StreamingResponse(server_sent_events(), media_type="text/event-stream")

    async def produce(run: Run) -> None:
        source = live(run) if run.mode == "live" else replay(run)
        try:
            async for e in source:
                run.events.append(e)
                async with run.changed:
                    run.changed.notify_all()
        except Exception as error:  # show it in the UI instead of a stream that just stops
            run.events.append({"type": "error", "at": 0, "message": f"{type(error).__name__}: {error}"})
        finally:
            run.done = True
            async with run.changed:
                run.changed.notify_all()

    def find(run_id: str) -> Run:
        if run_id not in runs:
            raise HTTPException(404, "Unknown run")
        return runs[run_id]

    async def live(run: Run):
        recorded = []
        token = await auth.sign_in(RELATIONSHIP_MANAGER)
        async for e in runtime.invoke(token, run.session_id, {"action": "start"}):
            recorded.append(e)
            yield e
        if recorded and recorded[-1]["type"] != "awaiting_approval":
            return  # the first invocation failed; nothing to approve
        await run.approved.wait()
        token = await auth.sign_in(COMPLIANCE_OFFICER)
        async for e in runtime.invoke(token, run.session_id, {"action": "approve"}):
            recorded.append(e)
            yield e
        if recorded[-1]["type"] == "run_completed":
            replay_file.parent.mkdir(parents=True, exist_ok=True)
            replay_file.write_text(json.dumps(recorded, indent=1))

    async def replay(run: Run):
        previous = None
        for e in json.loads(replay_file.read_text()):
            if previous is not None:
                gap = min(max(e["at"] - previous, REPLAY_MIN_GAP_MS), REPLAY_MAX_GAP_MS)
                await asyncio.sleep(gap / 1000 / run.speed)
            previous = e["at"]
            yield e
            if e["type"] == "awaiting_approval":
                await run.approved.wait()

    if static_dir and static_dir.exists():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

        @app.get("/{path:path}")
        def index(path: str) -> FileResponse:
            # Asset file names change on every build; the page that points to them must never be cached.
            return FileResponse(static_dir / "index.html", headers={"Cache-Control": "no-store"})

    return app
