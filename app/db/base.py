"""
SQLAlchemy async 엔진 + 세션 팩토리.

지원 DB:
  - SQLite  (개발/테스트용, 기본값)  sqlite+aiosqlite:///./data/ibkbox.db
  - PostgreSQL (운영용)              postgresql+asyncpg://user:pw@host/db
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# ─────────────────────────────────────────────
# 엔진
# ─────────────────────────────────────────────

_connect_args = {}
if settings.database_url.startswith("sqlite"):
    # SQLite 동시성 허용
    _connect_args = {"check_same_thread": False}

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args=_connect_args,
    # PostgreSQL 전용 풀 설정 (SQLite에서는 무시됨)
    pool_pre_ping=True,
)

# ─────────────────────────────────────────────
# 세션 팩토리
# ─────────────────────────────────────────────

async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ─────────────────────────────────────────────
# Base
# ─────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────
# FastAPI Depends 헬퍼
# ─────────────────────────────────────────────

async def get_db() -> AsyncSession:  # type: ignore[return]
    """FastAPI Depends로 사용하는 세션 의존성."""
    async with async_session() as session:
        yield session
