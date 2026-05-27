"""
크롤링 결과를 담는 데이터 모델.
CrawlPage 하나가 단일 웹페이지 크롤링 결과를 나타낸다.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


PageType = Literal[
    "about",      # 회사소개
    "service",    # 서비스/제품
    "portfolio",  # 포트폴리오/사례
    "history",    # 연혁
    "contact",    # 문의/연락처
    "other",      # 분류 불가
]


class CrawlPage(BaseModel):
    """
    단일 페이지 크롤링 결과.

    Attributes
    ----------
    url:        원본 URL
    title:      <title> 태그 텍스트 (없으면 "")
    text:       trafilatura로 추출한 본문 (최대 6000자 cap 적용 후)
    page_type:  URL/본문 키워드로 분류한 페이지 유형
    depth:      seed=0, 1-hop=1, 2-hop=2
    fetch_ms:   실제 HTTP 왕복 + 추출 소요 시간(ms)
    """

    url: str = Field(..., description="크롤링한 URL")
    title: str = Field(default="", description="페이지 <title>")
    text: str = Field(..., min_length=1, description="추출된 본문 텍스트")
    page_type: PageType = Field(default="other")
    depth: int = Field(default=0, ge=0, le=2)
    fetch_ms: int = Field(default=0, ge=0)

    @field_validator("text")
    @classmethod
    def cap_text_length(cls, v: str) -> str:
        """LLM 토큰 과다 소비 방지: 페이지당 최대 6000자."""
        return v[:6000] if len(v) > 6000 else v

    @property
    def char_count(self) -> int:
        return len(self.text)

    def to_source_text(self) -> str:
        """Source 블록에 삽입할 텍스트 (title이 있으면 앞에 붙임)."""
        if self.title:
            return f"[{self.title}]\n{self.text}"
        return self.text
