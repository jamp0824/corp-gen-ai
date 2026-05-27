# ── 백엔드 Dockerfile ─────────────────────────
# FastAPI + uvicorn

FROM python:3.11-slim AS base

# 시스템 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── 의존성 설치 (레이어 캐시 활용) ───────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── 앱 소스 복사 ─────────────────────────────
COPY app/ ./app/

# ── 데이터 디렉토리 생성 (SQLite 마운트용) ────
RUN mkdir -p /app/data

# ── 포트 노출 ─────────────────────────────────
EXPOSE 8000

# ── 헬스체크 ─────────────────────────────────
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ── 실행 ─────────────────────────────────────
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--log-level", "info"]
