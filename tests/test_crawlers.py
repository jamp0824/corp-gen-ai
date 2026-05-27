"""
크롤러 모듈 단위 테스트.

외부 네트워크 없이 실행 가능 (httpx mock 사용).
"""
from __future__ import annotations

import pytest

from app.crawlers.page_extractor import classify_page, extract_title, extract_page
from app.crawlers.preflight import InvalidURL, _is_blocked_domain
from app.crawlers.website_crawler import _score_link, iter_links, _dedup_by_type

# ─────────────────────────────────────────────
# preflight: 차단 도메인
# ─────────────────────────────────────────────

@pytest.mark.parametrize("netloc,expected", [
    ("naver.com",           True),
    ("blog.naver.com",      True),
    ("sub.blog.naver.com",  True),
    ("instagram.com",       True),
    ("happyfarm.co.kr",     False),
    ("ibkbox.com",          False),
    ("sub.happyfarm.co.kr", False),
    ("mynaversite.com",     False),   # naver.com을 포함하지만 서브도메인 아님
])
def test_blocked_domain(netloc: str, expected: bool) -> None:
    assert _is_blocked_domain(netloc) == expected


# ─────────────────────────────────────────────
# page_extractor: title 추출
# ─────────────────────────────────────────────

def test_extract_title_normal() -> None:
    html = "<html><head><title>  해피팜 - 회사소개  </title></head></html>"
    assert extract_title(html) == "해피팜 - 회사소개"


def test_extract_title_missing() -> None:
    html = "<html><head></head><body>텍스트</body></html>"
    assert extract_title(html) == ""


def test_extract_title_entity() -> None:
    html = "<title>A &amp; B &lt;Test&gt;</title>"
    assert extract_title(html) == "A & B <Test>"


# ─────────────────────────────────────────────
# page_extractor: 페이지 유형 분류
# ─────────────────────────────────────────────

@pytest.mark.parametrize("url,text_preview,expected", [
    ("https://example.com/about", "회사소개 2015년 설립", "about"),
    ("https://example.com/service", "서비스 목록 솔루션", "service"),
    ("https://example.com/contact", "문의하기 주소 서울", "contact"),
    ("https://example.com/history", "연혁 설립 2010년", "history"),
    ("https://example.com/portfolio", "포트폴리오 프로젝트 사례", "portfolio"),
    ("https://example.com/news", "뉴스 공지사항", "other"),
])
def test_classify_page(url: str, text_preview: str, expected: str) -> None:
    assert classify_page(url, text_preview) == expected


# ─────────────────────────────────────────────
# page_extractor: extract_page 최소 글자 수
# ─────────────────────────────────────────────

def test_extract_page_too_short() -> None:
    html = "<html><body><p>짧은 텍스트</p></body></html>"
    result = extract_page("https://example.com/", html)
    assert result is None  # 300자 미만


def test_extract_page_sufficient() -> None:
    long_text = "이것은 충분히 긴 본문 텍스트입니다. " * 20  # 약 600자
    html = f"<html><head><title>테스트</title></head><body><p>{long_text}</p></body></html>"
    result = extract_page("https://example.com/about", html)
    assert result is not None
    assert result.page_type == "about"
    assert result.title == "테스트"
    assert len(result.text) >= 300


# ─────────────────────────────────────────────
# website_crawler: 링크 점수
# ─────────────────────────────────────────────

def test_score_link_high() -> None:
    score = _score_link("https://example.com/about-us", "회사소개")
    assert score >= 2  # "about"(EN) + "소개"(KO) 최소 2점


def test_score_link_zero() -> None:
    score = _score_link("https://example.com/random-page-123", "클릭")
    assert score == 0


# ─────────────────────────────────────────────
# website_crawler: 링크 추출
# ─────────────────────────────────────────────

def test_iter_links_same_origin() -> None:
    html = """
    <a href="/about">회사소개</a>
    <a href="https://example.com/service">서비스</a>
    <a href="https://other.com/page">외부</a>
    <a href="mailto:info@example.com">메일</a>
    """
    links = iter_links(html, "https://example.com", "example.com")
    urls = [u for u, _ in links]
    assert any("about" in u for u in urls)
    assert any("service" in u for u in urls)
    assert not any("other.com" in u for u in urls)
    assert not any("mailto" in u for u in urls)


def test_iter_links_skips_static() -> None:
    html = """
    <a href="/doc.pdf">PDF</a>
    <a href="/image.jpg">이미지</a>
    <a href="/about">소개</a>
    """
    links = iter_links(html, "https://example.com", "example.com")
    urls = [u for u, _ in links]
    assert not any(".pdf" in u for u in urls)
    assert not any(".jpg" in u for u in urls)
    assert any("about" in u for u in urls)


# ─────────────────────────────────────────────
# website_crawler: dedup
# ─────────────────────────────────────────────

def test_dedup_by_type_limits_per_type() -> None:
    from app.models.crawl import CrawlPage

    pages = [
        CrawlPage(url=f"https://ex.com/service{i}", text="서비스 " * 50, page_type="service", depth=1)
        for i in range(5)  # service 5개, MAX_PER_TYPE=3이면 3개로 줄어야 함
    ]
    result = _dedup_by_type(pages)
    service_pages = [p for p in result if p.page_type == "service"]
    assert len(service_pages) <= 3


def test_dedup_seed_always_kept() -> None:
    from app.models.crawl import CrawlPage

    seed = CrawlPage(url="https://ex.com/", text="홈페이지 " * 50, page_type="other", depth=0)
    others = [
        CrawlPage(url=f"https://ex.com/other{i}", text="기타 " * 50, page_type="other", depth=1)
        for i in range(10)
    ]
    result = _dedup_by_type([seed] + others)
    assert any(p.depth == 0 for p in result)


# ─────────────────────────────────────────────
# source_pool
# ─────────────────────────────────────────────

def test_build_source_pool_ordering() -> None:
    from app.models.crawl import CrawlPage
    from app.models.schemas import NormalizedInput
    from app.services.source_pool import build_source_pool

    normalized = NormalizedInput(
        company_id="test",
        company_name="테스트",
        industry="IT",
        business_type="솔루션",
        main_business_description="AI 솔루션 개발 및 공급합니다.",
        official_url="https://test.co.kr",
        homepage_type="general",
        tone="professional",
    )
    pages = [
        CrawlPage(url="https://test.co.kr/service", text="서비스 " * 60, page_type="service", depth=1),
        CrawlPage(url="https://test.co.kr/about", text="소개 " * 60, page_type="about", depth=1),
    ]
    sources = build_source_pool(normalized, pages)

    # input 소스가 crawl 소스보다 먼저 나와야 함
    types = [s.source_type for s in sources]
    last_input_idx = max(i for i, t in enumerate(types) if t == "input")
    first_crawl_idx = min(i for i, t in enumerate(types) if t == "crawl")
    assert last_input_idx < first_crawl_idx

    # about이 service보다 먼저
    page_types = [s.page_type for s in sources if s.source_type == "crawl"]
    assert page_types.index("about") < page_types.index("service")


# ─────────────────────────────────────────────
# validator
# ─────────────────────────────────────────────

def test_validator_forbidden_expression() -> None:
    from app.models.content_package import (
        AboutSection, ContentMeta, ContentPackage, ContentSections,
        HeroSection, StrengthItem,
    )
    from app.models.schemas import Source
    from app.services.validator import validate_package

    src = Source(source_id="src_001", source_type="input",
                 origin="/company_name", text="테스트", confidence=1.0)

    pkg = ContentPackage(
        sections=ContentSections(
            hero=HeroSection(
                headline="국내 최고의 AI 솔루션",  # 금지 표현
                subheadline="최고의 서비스를 제공합니다.",
                cta_label="문의하기",
                evidence_refs=["src_001"],
                sufficient=True,
            ),
            about=AboutSection(
                title="회사소개",
                body="AI 솔루션을 개발하는 기업입니다. " * 5,
                evidence_refs=["src_001"],
                sufficient=True,
            ),
            strengths=[
                StrengthItem(
                    title="전문성",
                    description="AI 분야 전문 기업입니다. 다년간의 경험을 바탕으로 솔루션을 제공합니다.",
                    evidence_refs=["src_001"],
                    sufficient=True,
                ),
                StrengthItem(
                    title="신뢰성",
                    description="검증된 기술력으로 안정적인 서비스를 제공합니다.",
                    evidence_refs=["src_001"],
                    sufficient=True,
                ),
            ],
        ),
        meta=ContentMeta(evidence_level="input_only", warnings=[]),
    )

    result = validate_package(pkg, [src])
    blocker_codes = [b.code for b in result.blockers]
    assert "FORBIDDEN_EXPRESSION" in blocker_codes


def test_validator_missing_ref() -> None:
    from app.models.content_package import (
        AboutSection, ContentMeta, ContentPackage, ContentSections,
        HeroSection, StrengthItem,
    )
    from app.models.schemas import Source
    from app.services.validator import validate_package

    src = Source(source_id="src_001", source_type="input",
                 origin="/company_name", text="테스트", confidence=1.0)

    pkg = ContentPackage(
        sections=ContentSections(
            hero=HeroSection(
                headline="AI 솔루션 기업",
                subheadline="AI로 업무를 혁신합니다.",
                cta_label="문의하기",
                evidence_refs=[],      # 비어있음 → blocker
                sufficient=True,
            ),
            about=AboutSection(
                title="회사소개",
                body="전문적인 AI 솔루션을 제공합니다. " * 5,
                evidence_refs=["src_001"],
                sufficient=True,
            ),
            strengths=[
                StrengthItem(
                    title="전문성",
                    description="다년간의 경험을 바탕으로 솔루션을 제공하는 전문 기업입니다.",
                    evidence_refs=["src_001"],
                    sufficient=True,
                ),
                StrengthItem(
                    title="안정성",
                    description="검증된 인프라를 기반으로 안정적인 운영 환경을 제공합니다.",
                    evidence_refs=["src_001"],
                    sufficient=True,
                ),
            ],
        ),
        meta=ContentMeta(evidence_level="input_only", warnings=[]),
    )

    result = validate_package(pkg, [src])
    assert result.has_blocker
    assert any(b.code == "MISSING_EVIDENCE_REF" and b.section == "hero"
               for b in result.blockers)


def test_validator_verbatim_copy() -> None:
    from app.models.content_package import (
        AboutSection, ContentMeta, ContentPackage, ContentSections,
        HeroSection, StrengthItem,
    )
    from app.models.schemas import Source
    from app.services.validator import validate_package

    crawl_text = "2015년 설립된 해피팜은 농산물 도매업체를 위한 재고관리 소프트웨어를 개발했습니다."
    src = Source(source_id="src_001", source_type="crawl",
                 origin="https://example.com/about", page_type="about",
                 text=crawl_text, confidence=0.7)

    pkg = ContentPackage(
        sections=ContentSections(
            hero=HeroSection(
                headline="농산물 재고관리 전문",
                subheadline="AI로 농산물 재고를 최적화합니다.",
                cta_label="문의",
                evidence_refs=["src_001"],
                sufficient=True,
            ),
            about=AboutSection(
                title="회사소개",
                # 25자 이상 verbatim 복붙
                body=crawl_text + " 지속적으로 성장하고 있습니다.",
                evidence_refs=["src_001"],
                sufficient=True,
            ),
            strengths=[
                StrengthItem(
                    title="전문성",
                    description="농산물 도매 재고 관리에 특화된 솔루션을 개발합니다.",
                    evidence_refs=["src_001"],
                    sufficient=True,
                ),
                StrengthItem(
                    title="기술력",
                    description="AI 기반 수요예측 기술로 발주 오류를 줄입니다.",
                    evidence_refs=["src_001"],
                    sufficient=True,
                ),
            ],
        ),
        meta=ContentMeta(evidence_level="input_plus_crawl", warnings=[]),
    )

    result = validate_package(pkg, [src])
    warning_codes = [w.code for w in result.warnings]
    assert "VERBATIM_COPY_FROM_CRAWL" in warning_codes
    # blocker는 아님
    assert not any(b.code == "VERBATIM_COPY_FROM_CRAWL" for b in result.blockers)
