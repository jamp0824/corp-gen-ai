"""Alembic 마이그레이션 환경 설정."""
from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# 앱 모델 임포트 (메타데이터 등록)
from app.db.base import Base
from app.db.models import EnrichmentJob  # noqa: F401

config  = context.config
fileConfig(config.config_file_name)
target_metadata = Base.metadata

def get_url() -> str:
    return os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url") or "")

def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    engine = create_async_engine(get_url())
    async with engine.connect() as conn:
        await conn.run_sync(
            lambda sync_conn: context.configure(
                connection=sync_conn,
                target_metadata=target_metadata,
            )
        )
        async with conn.begin():
            await conn.run_sync(lambda _: context.run_migrations())
    await engine.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
