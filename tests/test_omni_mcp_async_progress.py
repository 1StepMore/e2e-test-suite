"""R-03: omni-mcp long-running tools must not block the event loop and must
emit MCP progress notifications.

Contract locked here:
  * ``server.translate_file`` offloads the synchronous orchestrator to a
    worker thread, so a concurrent MCP request (``ping``) is serviced while
    a long translation is still in flight.
  * the orchestrator emits one progress event per stage (opp -> ol -> orf)
    through an injected ``progress_callback``.
  * when the client opted into progress (``_meta.progressToken``), the server
    forwards those events to the live MCP session as
    ``notifications/progress`` messages with a stable token + total.
  * cancelling an in-flight call still leaves the server responsive (the
    worker thread is not force-killed — documented limitation).

Red-first: before this change ``server.translate_file`` awaited the sync
orchestrator inline on the event loop (``omni_mcp/server.py:85``) and emitted
no progress.
"""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from mcp.server.lowlevel.server import request_ctx

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _RecordingSession:
    """Minimal stand-in for ``ServerSession`` that records progress calls."""

    def __init__(self) -> None:
        self.notifications: list[dict[str, object]] = []

    async def send_progress_notification(
        self,
        progress_token,
        progress,
        total=None,
        message=None,
        related_request_id=None,
    ) -> None:
        self.notifications.append(
            {
                "progress_token": progress_token,
                "progress": progress,
                "total": total,
                "message": message,
            }
        )


@pytest.fixture
def fake_mcp_request():
    """Install a fake MCP ``RequestContext`` carrying a progress token.

    Mirrors the low-level server: it sets the ``request_ctx`` contextvar
    before dispatching a tool call.  The client opted into progress by
    sending ``_meta.progressToken``.
    """
    session = _RecordingSession()
    ctx = SimpleNamespace(
        request_id=1,
        meta=SimpleNamespace(progressToken="tok-r03"),
        session=session,
    )
    token = request_ctx.set(ctx)
    try:
        yield session
    finally:
        request_ctx.reset(token)


def _docx(tmp_path, name="sample.docx") -> Path:
    p = tmp_path / name
    p.write_bytes(b"PK\x03\x04")
    return p


def _fake_pipeline(cmd, **kwargs):
    """Stub ``_run_cli`` that materializes each stage's expected output."""
    if cmd[0] == "opp":
        for i, arg in enumerate(cmd):
            if arg == "--output-dir" and i + 1 < len(cmd):
                out = Path(cmd[i + 1])
                out.mkdir(parents=True, exist_ok=True)
                (out / "sample.md").write_text("# Hello\n\nWorld\n")
        return {"success": True, "suggested_pipeline": "md_only"}
    if cmd[0] == "ol":
        for i, arg in enumerate(cmd):
            if arg == "-o" and i + 1 < len(cmd):
                out = Path(cmd[i + 1])
                out.mkdir(parents=True, exist_ok=True)
                (out / "sample.md").write_text("# 你好\n\n世界\n")
        return {"success": True}
    if cmd[0] == "orf":
        for i, arg in enumerate(cmd):
            if arg == "-o" and i + 1 < len(cmd):
                Path(cmd[i + 1]).write_text("fake docx")
        return {"success": True}
    return {"success": True}


# ---------------------------------------------------------------------------
# Progress notification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_translate_file_emits_progress_notifications(
    fake_mcp_request, tmp_path, monkeypatch
):
    """At least one MCP progress notification is sent for a translate_file call."""
    from omni_mcp.server import translate_file

    monkeypatch.setenv("MCP_ALLOWED_DIRECTORIES", str(tmp_path))
    src = _docx(tmp_path)

    with patch("omni_mcp.orchestrator._run_cli", side_effect=_fake_pipeline):
        result = await translate_file(
            file_path=str(src),
            source_lang="en",
            target_lang="zh",
            output_format="docx",
        )

    assert result["success"] is True, result
    notes = fake_mcp_request.notifications
    assert len(notes) >= 1, "expected at least one MCP progress notification"
    assert notes[0]["progress_token"] == "tok-r03"
    assert notes[0]["total"] == 3
    assert any("OPP" in str(n["message"]) for n in notes)


@patch("omni_mcp.orchestrator._run_cli")
def test_orchestrator_emits_one_event_per_stage(mock_cli, tmp_path, monkeypatch):
    """The orchestrator reports each pipeline stage through the callback."""
    from omni_mcp.orchestrator import translate_file

    monkeypatch.setenv("MCP_ALLOWED_DIRECTORIES", str(tmp_path))
    src = _docx(tmp_path)
    mock_cli.side_effect = _fake_pipeline
    events: list[dict[str, object]] = []

    result = translate_file(
        file_path=str(src),
        source_lang="en",
        target_lang="zh",
        output_format="docx",
        progress_callback=events.append,
    )

    assert result["success"] is True, result
    assert [e["stage"] for e in events] == ["opp", "ol", "orf"]
    assert [e["index"] for e in events] == [1, 2, 3]
    assert all(e["total"] == 3 for e in events)


# ---------------------------------------------------------------------------
# Event-loop responsiveness (concurrency probe)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_translate_file_does_not_block_concurrent_request(monkeypatch):
    """A second request is serviced while translate_file is still running."""
    import omni_mcp.server as server_mod
    from omni_mcp.server import ping, translate_file

    started = threading.Event()
    release = threading.Event()
    worker_thread: dict[str, int] = {}

    def _slow_translate(**kwargs):
        worker_thread["id"] = threading.get_ident()
        started.set()
        if not release.wait(timeout=5):
            raise AssertionError("test never released the worker")
        return {"success": True, "content": {"output_path": "/tmp/x.docx"}}

    monkeypatch.setattr(server_mod, "_translate_file", _slow_translate)

    task = asyncio.create_task(
        translate_file(
            file_path="/tmp/sample.docx",
            source_lang="en",
            target_lang="zh",
            output_format="docx",
        )
    )
    # Wait for the worker thread to start without blocking the event loop.
    assert await asyncio.to_thread(started.wait, 5), "worker never started"

    # Second request must complete while the first is still in flight.
    pong = await asyncio.wait_for(ping(), timeout=2)
    assert pong["success"] is True
    assert not task.done(), "translate_file finished before the second request"

    release.set()
    result = await asyncio.wait_for(task, timeout=5)
    assert result["success"] is True
    assert worker_thread["id"] != threading.get_ident(), (
        "orchestrator ran on the event-loop thread"
    )


@pytest.mark.asyncio
async def test_cancelled_translate_keeps_server_responsive(monkeypatch):
    """Cancelling an in-flight call does not block the server event loop."""
    import omni_mcp.server as server_mod
    from omni_mcp.server import ping, translate_file

    started = threading.Event()
    release = threading.Event()

    def _hang(**kwargs):
        started.set()
        release.wait(timeout=5)
        return {"success": True, "content": {}}

    monkeypatch.setattr(server_mod, "_translate_file", _hang)

    task = asyncio.create_task(
        translate_file(
            file_path="/tmp/sample.docx",
            source_lang="en",
            target_lang="zh",
            output_format="docx",
        )
    )
    assert await asyncio.to_thread(started.wait, 5), "worker never started"

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # The server is still responsive after cancellation.
    assert (await asyncio.wait_for(ping(), timeout=2))["success"] is True
    release.set()
