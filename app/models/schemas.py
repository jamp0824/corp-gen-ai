"""
API 요청/응답 및 내부 서비스 간 전달 스키마.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Annotated, Iterator, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .content_package import ContentPackage


# ─────────────────────────────────────────────
# Source  (input + crawl 통합 소스 풀)
# ─────────────────────────────────────────────

class Source(BaseModel):
    """
    LLM에 전달하는 단일 근거 단위.

    source_type="input"  → 사용자가 직접 입력한 값, 신뢰도 1.0
    source_type="crawl"  → 공식 홈페이지에서 추출, 신뢰도 0.7
    """
    source_id: str = Field(
        ...,
        pattern=r"^src_\d{3,}$",
        description="예: src_001",
    )
    source_type: Literal["input", "crawl"]
    origin: str = Field(
        ...,
        description="input이면 JSON Pointer, crawl이면 URL",
    )
    page_type: str | None = Field(
        default=None,
        description="crawl 전용: about / service / portfolio / history / contact / other",
    )
    text: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)

    def format_for_prompt(self) -> str:
        """프롬프트 SOURCES 블록에 삽입할 포맷."""
        if self.source_type == "input":
            header = f"[{self.source_id}] type=input  pointer={self.origin}"
        else:
            header = (
                f"[{self.source_id}] type=crawl  "
                f"page={self.page_type or 'other'}  url={self.origin}"
            )
        return f"{header}\n  {self.text}"


# ─────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────

class ValidationIssue(BaseModel):
    section: str = Field(..., description="예: about, hero, strengths[0]")
    code: str = Field(
        ...,
        description=(
            "FORBIDDEN_EXPRESSION | MISSING_EVIDENCE_REF | "
            "VERBATIM_COPY_FROM_CRAWL | INSUFFICIENT_SECTION | "
            "HALLUCINATION_RISK"
        ),
    )
    hint: str = Field(..., description="사람이 읽을 수 있는 설명")
    blocker: bool = Field(
        ...,
        description="True면 재시도 대상, False면 warning만",
    )


class ValidationResult(BaseModel):
    blockers: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)

    @property
    def has_blocker(self) -> bool:
        return len(self.blockers) > 0

    @property
    def all_issues(self) -> list[ValidationIssue]:
        return self.blockers + self.warnings


# ─────────────────────────────────────────────
# API 요청
# ─────────────────────────────────────────────

HomepageType = Literal[
    "general",      # 일반 기업
    "startup",      # 스타트업 / 벤처
    "manufacturing",# 제조업
    "finance",      # 금융
    "medical",      # 의료 / 바이오
    "education",    # 교육
    "retail",       # 유통 / 커머스
]

Tone = Literal[
    "professional",  # 전문적
    "friendly",      # 친근한
    "formal",        # 격식체
    "dynamic",       # 역동적
]


class EnrichmentRequest(BaseModel):
    """Step 2 → POST /content-enrichment 요청 바디."""
    company_name: Annotated[str, Field(min_length=1, max_length=100)]
    industry: Annotated[str, Field(min_length=1, max_length=100,
                                   description="예: IT·소프트웨어, 제조업")]
    business_type: Annotated[str, Field(min_length=1, max_length=100,
                                        description="예: 솔루션 개발 및 공급")]
    main_business_description: Annotated[
        str, Field(min_length=10, max_length=1000,
                   description="주요 사업 내용 자유 기술")
    ]
    official_url: Annotated[str, Field(
        description="공식 홈페이지 URL (필수, https:// 권장)",
    )]
    homepage_type: HomepageType = "general"
    tone: Tone = "professional"

    @field_validator("official_url")
    @classmethod
    def validate_url_format(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^https?://", v, re.IGNORECASE):
            raise ValueError("URL은 http:// 또는 https://로 시작해야 합니다.")
        return v

    @field_validator("company_name", "industry", "business_type",
                     "main_business_description", mode="before")
    @classmethod
    def strip_and_normalize(cls, v: object) -> str:
        if not isinstance(v, str):
            raise ValueError("문자열이어야 합니다.")
        # NFC 정규화 + 앞뒤 공백 제거
        return unicodedata.normalize("NFC", v.strip())


# ─────────────────────────────────────────────
# NormalizedInput  (내부 서비스 전달용)
# ─────────────────────────────────────────────

class NormalizedInput(BaseModel):
    """
    EnrichmentRequest를 검증·정규화한 내부 표현.
    company_id는 URL-safe slug로 생성한다.
    """
    company_id: str
    company_name: str
    industry: str
    business_type: str
    main_business_description: str
    official_url: str
    homepage_type: HomepageType
    tone: Tone

    def iter_evidence_fields(self) -> Iterator[tuple[str, str]]:
        """
        (JSON Pointer, 값) 쌍을 생성해 Source 풀 빌더에서 사용.
        빈 값은 건너뜀.
        """
        mapping = {
            "/company_name":               self.company_name,
            "/industry":                   self.industry,
            "/business_type":              self.business_type,
            "/main_business_description":  self.main_business_description,
            "/homepage_type":              self.homepage_type,
            "/tone":                       self.tone,
        }
        for ptr, val in mapping.items():
            if val:
                yield ptr, str(val)


# ─────────────────────────────────────────────
# API 응답
# ─────────────────────────────────────────────

class EnrichmentMeta(BaseModel):
    evidence_level: Literal["input_plus_crawl", "input_only"]
    crawled_pages: int = 0
    crawl_duration_ms: int = 0
    llm_duration_ms: int = 0
    total_duration_ms: int = 0
    retry_count: int = 0


class ContentPackageResponse(BaseModel):
    """POST /content-enrichment 성공 응답."""
    company_id: str
    package: ContentPackage
    sources: list[Source]
    validation: ValidationResult
    meta: EnrichmentMeta


# ─────────────────────────────────────────────
# Preflight 결과
# ─────────────────────────────────────────────

class PreflightResult(BaseModel):
    origin: str = Field(..., description="도메인 (예: happyfarm.co.kr)")
    scheme: Literal["http", "https"]
    robots_allowed: bool = True
