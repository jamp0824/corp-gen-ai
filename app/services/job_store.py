"""
인메모리 Job 이벤트 큐.

백그라운드 태스크(Producer) → SSE 핸들러(Consumer) 간 이벤트 전달.
단일 프로세스 안에서만 동작한다. 다중 프로세스 배포 시에는 Redis PubSub으로 교체.

이벤트 유형:
  phase     — 단계별 진행 상황
  complete  — 작업 완료 (result 포함)
  error     — 작업 실패
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Literal

logger = logging.getLogger(__name__)

PhaseId = Literal[
    "preflight",   # Phase A: URL 검증
    "crawl",       # Phase B: 크롤링
    "source_pool", # Phase C: 소스 풀 구성
    "llm",         # Phase D: LLM 호출
    "validate",    # Phase E: 검증
    "persist",     # Phase F: DB 저장
]

EventType = Literal["phase", "complete", "error"]


@dataclass
class JobEvent:
    """SSE 로 전송할 이벤트 1건."""
    event_type: EventType
    phase: PhaseId | None = None
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_sse_data(self) -> dict[str, Any]:
        """SSE data 필드에 직렬화할 dict."""
        out: dict[str, Any] = {
            "event_type": self.event_type,
            "message":    self.message,
        }
        if self.phase:
            out["phase"] = self.phase
        out.update(self.data)
        return out


# ─────────────────────────────────────────────

class JobStore:
    """
    프로세스 싱글톤 job 큐 저장소.

    job_id → asyncio.Queue[JobEvent]
    """

    # 큐에 이벤트가 없어도 이 시간(초) 내에 연결이 없으면 큐 자동 정리
    _TTL_AFTER_LAST_EVENT = 300.0

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[JobEvent]] = {}
        # 가비지 컬렉션 방지용 task 참조 집합
        self._tasks: set[asyncio.Task[Any]] = set()

    def create(self, job_id: str) -> asyncio.Queue[JobEvent]:
        """새 job 큐 생성 후 반환."""
        q: asyncio.Queue[JobEvent] = asyncio.Queue(maxsize=200)
        self._queues[job_id] = q
        return q

    def get(self, job_id: str) -> asyncio.Queue[JobEvent] | None:
        return self._queues.get(job_id)

    async def emit(self, job_id: str, event: JobEvent) -> None:
        """이벤트를 해당 job 큐에 넣는다. 큐가 없으면 무시."""
        q = self._queues.get(job_id)
        if q is not None:
            await q.put(event)

    def cleanup(self, job_id: str) -> None:
        """SSE 연결 종료 후 큐 삭제."""
        self._queues.pop(job_id, None)
        logger.debug("job_store: cleaned up job_id=%s", job_id)

    def track_task(self, task: asyncio.Task[Any]) -> None:
        """fire-and-forget 태스크 참조 유지 (GC 방지)."""
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)


# 앱 수준 싱글톤
job_store = JobStore()


# ─────────────────────────────────────────────
# 헬퍼 — emit 편의 함수
# ─────────────────────────────────────────────

async def emit_phase(
    job_id: str,
    phase: PhaseId,
    message: str,
    **extra: Any,
) -> None:
    """단계 시작/진행 이벤트 emit."""
    await job_store.emit(
        job_id,
        JobEvent(
            event_type="phase",
            phase=phase,
            message=message,
            data=extra,
        ),
    )


async def emit_complete(job_id: str, result: Any, elapsed_ms: int) -> None:
    """완료 이벤트 emit. result는 ContentPackageResponse."""
    import json
    await job_store.emit(
        job_id,
        JobEvent(
            event_type="complete",
            message="완료",
            data={
                "result": json.loads(result.model_dump_json()),
                "elapsed_ms": elapsed_ms,
            },
        ),
    )


async def emit_error(job_id: str, code: str, message: str) -> None:
    """오류 이벤트 emit."""
    await job_store.emit(
        job_id,
        JobEvent(
            event_type="error",
            message=message,
            data={"code": code},
        ),
    )
