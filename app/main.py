"""FastAPI 앱 진입점."""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.enrichment import router as enrichment_router
from app.core.config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="IBK BOX Content Enrichment API",
    version="1.0.0",
    description="공식 홈페이지 크롤링 + LLM 콘텐츠 보강 (SSE 스트리밍)",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 운영: 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(enrichment_router)


@app.on_event("startup")
async def startup() -> None:
    """앱 시작 시 DB 테이블 자동 생성."""
    # SQLite 데이터 디렉토리 생성
    if settings.database_url.startswith("sqlite"):
        db_path = settings.database_url.replace("sqlite+aiosqlite:///", "")
        db_dir  = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    from app.db.base import Base, engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logging.getLogger(__name__).info(
        "DB ready: %s", settings.database_url.split("@")[-1]  # 비밀번호 숨김
    )


@app.on_event("shutdown")
async def shutdown() -> None:
    from app.db.base import engine
    await engine.dispose()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": app.version}
