"""
SQLAlchemy ORM 모델.

EnrichmentJob 하나가 POST /content-enrichment 요청 1건을 나타낸다.
콘텐츠 패키지·소스·검증 결과는 JSON 텍스트로 직렬화해 저장한다.
(JSONB가 없는 SQLite 호환성 유지)
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class JobStatus(str, enum.Enum):
    pending    = "pending"
    processing = "processing"
    completed  = "completed"
    failed     = "failed"


class EnrichmentJob(Base):
    """
    콘텐츠 보강 작업 1건.

    Columns
    -------
    id              : UUID-like 문자열 (job_id)
    company_id      : 회사명 슬러그 (URL-safe)
    company_name    : 원본 회사명
    official_url    : 크롤링 대상 URL
    status          : pending → processing → completed | failed
    evidence_level  : input_plus_crawl | input_only
    request_json    : EnrichmentRequest JSON 직렬화
    package_json    : ContentPackage JSON (완료 시 채워짐)
    sources_json    : list[Source] JSON
    validation_json : ValidationResult JSON
    meta_json       : EnrichmentMeta JSON
    error_code      : 실패 시 에러 코드
    error_message   : 실패 시 에러 메시지
    created_at      : 작업 생성 시각
    updated_at      : 마지막 업데이트 시각
    """

    __tablename__ = "enrichment_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    company_id:   Mapped[str]        = mapped_column(String(100), index=True)
    company_name: Mapped[str]        = mapped_column(String(200))
    official_url: Mapped[str]        = mapped_column(String(2000))

    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False),
        default=JobStatus.pending,
        index=True,
    )

    evidence_level: Mapped[str | None] = mapped_column(String(50),  nullable=True)
    request_json:   Mapped[str | None] = mapped_column(Text,         nullable=True)
    package_json:   Mapped[str | None] = mapped_column(Text,         nullable=True)
    sources_json:   Mapped[str | None] = mapped_column(Text,         nullable=True)
    validation_json:Mapped[str | None] = mapped_column(Text,         nullable=True)
    meta_json:      Mapped[str | None] = mapped_column(Text,         nullable=True)
    error_code:     Mapped[str | None] = mapped_column(String(100),  nullable=True)
    error_message:  Mapped[str | None] = mapped_column(Text,         nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # company_id 최신순 조회용 복합 인덱스
    __table_args__ = (
        Index("ix_company_created", "company_id", "created_at"),
    )
