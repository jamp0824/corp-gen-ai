"""
LLM이 생성하는 콘텐츠 패키지 Pydantic 모델.

JSON Schema 강제 → LLM structured output 입력으로 그대로 사용.
각 섹션의 evidence_refs는 Source.source_id 목록으로 근거를 명시한다.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


# ─────────────────────────────────────────────
# 섹션별 모델
# ─────────────────────────────────────────────

class HeroSection(BaseModel):
    """히어로(첫 화면) 영역."""
    headline: Annotated[str, Field(min_length=5, max_length=60,
                                   description="메인 헤드라인 (5~60자)")]
    subheadline: Annotated[str, Field(min_length=10, max_length=150,
                                      description="서브 헤드라인 (10~150자)")]
    cta_label: Annotated[str, Field(min_length=2, max_length=20,
                                    description="CTA 버튼 레이블 (2~20자)")]
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="근거 source_id 목록 (예: ['src_001', 'src_003'])",
    )
    sufficient: bool = Field(
        default=True,
        description="근거가 충분해 고품질 작성이 가능한 경우 true",
    )


class AboutSection(BaseModel):
    """회사소개 영역."""
    title: Annotated[str, Field(min_length=2, max_length=40,
                                description="섹션 제목")]
    body: Annotated[str, Field(min_length=50, max_length=600,
                               description="회사 소개 본문 (50~600자)")]
    evidence_refs: list[str] = Field(default_factory=list)
    sufficient: bool = Field(default=True)


class StrengthItem(BaseModel):
    """강점 카드 1개 (보통 3~4개 생성)."""
    title: Annotated[str, Field(min_length=2, max_length=30,
                                description="강점 제목")]
    description: Annotated[str, Field(min_length=20, max_length=200,
                                      description="강점 설명")]
    evidence_refs: list[str] = Field(default_factory=list)
    sufficient: bool = Field(default=True)


class ServiceItem(BaseModel):
    """서비스/제품 항목 1개."""
    name: Annotated[str, Field(min_length=2, max_length=40,
                               description="서비스 이름")]
    description: Annotated[str, Field(min_length=20, max_length=300,
                                      description="서비스 설명")]
    evidence_refs: list[str] = Field(default_factory=list)
    sufficient: bool = Field(default=True)


class HistoryItem(BaseModel):
    """연혁 1건."""
    year: Annotated[int, Field(ge=1900, le=2100, description="연도")]
    event: Annotated[str, Field(min_length=5, max_length=200,
                                description="연혁 내용")]
    evidence_refs: list[str] = Field(default_factory=list)


class ContactSection(BaseModel):
    """문의/연락처 영역."""
    address: str | None = Field(default=None, description="주소 (없으면 null)")
    phone: str | None = Field(default=None, description="전화번호 (없으면 null)")
    email: str | None = Field(default=None, description="이메일 (없으면 null)")
    evidence_refs: list[str] = Field(default_factory=list)
    sufficient: bool = Field(default=True)

    @model_validator(mode="after")
    def at_least_one_contact(self) -> "ContactSection":
        """주소/전화/이메일 중 하나라도 있어야 유효."""
        if self.address is None and self.phone is None and self.email is None:
            # sufficient 를 false로 표시하되 예외는 던지지 않음
            object.__setattr__(self, "sufficient", False)
        return self


# ─────────────────────────────────────────────
# 섹션 통합 컨테이너
# ─────────────────────────────────────────────

class ContentSections(BaseModel):
    """
    모든 섹션을 담는 컨테이너.

    - hero / about / strengths: 항상 생성
    - services / history / contact: crawl 소스에 해당 데이터가 있을 때만
    """
    hero: HeroSection
    about: AboutSection
    strengths: Annotated[
        list[StrengthItem],
        Field(min_length=2, max_length=6, description="강점 2~6개"),
    ]
    services: list[ServiceItem] | None = Field(
        default=None,
        description="서비스/제품 목록 (crawl에 데이터 없으면 null)",
    )
    history: list[HistoryItem] | None = Field(
        default=None,
        description="연혁 목록 (crawl에 연도 데이터 없으면 null)",
    )
    contact: ContactSection | None = Field(
        default=None,
        description="연락처 (crawl에 데이터 없으면 null)",
    )


# ─────────────────────────────────────────────
# 메타 + 최상위 패키지
# ─────────────────────────────────────────────

EvidenceLevel = Literal["input_plus_crawl", "input_only"]


class ContentMeta(BaseModel):
    """LLM이 반환하는 메타 정보."""
    evidence_level: EvidenceLevel = Field(
        description="소스 유형: input+crawl 혼합 또는 input만",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="LLM이 직접 발견한 품질 우려사항 목록",
    )


class ContentPackage(BaseModel):
    """
    LLM이 최종 반환하는 JSON 구조.
    이 모델을 JSON Schema로 변환해 structured output 강제에 사용한다.
    """
    sections: ContentSections
    meta: ContentMeta
