"""Job Store (이벤트 큐) 단위 테스트."""
from __future__ import annotations

import asyncio
import pytest

from app.services.job_store import JobEvent, JobStore, emit_phase, emit_error, job_store


@pytest.mark.asyncio
async def test_create_and_emit() -> None:
    store = JobStore()
    q = store.create("job-a")
    assert q is not None
    assert store.get("job-a") is q

    await store.emit("job-a", JobEvent(event_type="phase", phase="preflight", message="테스트"))
    event = await asyncio.wait_for(q.get(), timeout=1.0)
    assert event.event_type == "phase"
    assert event.phase == "preflight"
    assert event.message == "테스트"


@pytest.mark.asyncio
async def test_cleanup() -> None:
    store = JobStore()
    store.create("job-b")
    assert store.get("job-b") is not None
    store.cleanup("job-b")
    assert store.get("job-b") is None


@pytest.mark.asyncio
async def test_emit_nonexistent() -> None:
    """존재하지 않는 job에 emit해도 예외 없음"""
    store = JobStore()
    await store.emit("nonexistent", JobEvent(event_type="phase", message="무시"))


@pytest.mark.asyncio
async def test_emit_complete_data() -> None:
    store = JobStore()
    q = store.create("job-c")

    event = JobEvent(
        event_type="complete",
        message="완료",
        data={"result": {"company_id": "test"}, "elapsed_ms": 12345},
    )
    await store.emit("job-c", event)

    received = await asyncio.wait_for(q.get(), timeout=1.0)
    assert received.event_type == "complete"
    assert received.data["elapsed_ms"] == 12345

    sse_data = received.to_sse_data()
    assert sse_data["event_type"] == "complete"
    assert "result" in sse_data


@pytest.mark.asyncio
async def test_track_task() -> None:
    store = JobStore()
    called = []

    async def dummy():
        called.append(True)

    task = asyncio.create_task(dummy())
    store.track_task(task)
    await asyncio.sleep(0.1)
    assert len(called) == 1
    # 완료 후 자동으로 _tasks에서 제거됨
    assert task not in store._tasks
