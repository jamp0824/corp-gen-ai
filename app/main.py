"""FastAPI 앱 진입점."""
from __future__ import annotations

import logging

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
    description="Step 2 공식 홈페이지 크롤링 + LLM 콘텐츠 보강 API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 운영 환경에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(enrichment_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
