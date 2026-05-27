"""
Phase B (보조): 단일 HTML → CrawlPage 변환 모듈.

책임:
- trafilatura 본문 추출
- 페이지 유형 분류 (classify_page)
- <title> 추출
- 300자 미만 본문은 None 반환 (메뉴·네비 파편 제거)
"""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.crawl import CrawlPage

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# 상수
# ─────────────────────────────────────────────

MIN_TEXT_LENGTH = 300   # 이보다 짧으면 파편으로 간주
MAX_TEXT_LENGTH = 6000  # LLM 토큰 보호 cap

# 페이지 유형 키워드 맵 (URL path + 본문 앞 500자 검사)
_PAGE_TYPE_KEYWORDS: dict[str, list[str]] = {
    "about":     ["about", "company", "intro", "corporate",
                  "회사", "소개", "기업", "개요", "우리는"],
    "service":   ["service", "product", "solution", "offering",
                  "서비스", "제품", "솔루션", "사업"],
    "portfolio": ["portfolio", "case", "client", "work", "project",
                  "포트폴리오", "사례", "고객", "프로젝트"],
    "history":   ["history", "milestone", "since", "founded",
                  "연혁", "설립", "역사", "창립"],
    "contact":   ["contact", "location", "address", "reach",
                  "문의", "위치", "연락", "주소", "오시는"],
}

# <title> 추출용 정규식
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


# ─────────────────────────────────────────────
# 공개 함수
# ─────────────────────────────────────────────

def extract_title(html: str) -> str:
    """HTML에서 <title> 텍스트 추출. 없으면 ""."""
    m = _TITLE_RE.search(html)
    if not m:
        return ""
    raw = m.group(1).strip()
    # HTML 엔티티 간단 처리
    raw = raw.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    # 탭/줄바꿈 → 공백
    return re.sub(r"\s+", " ", raw)[:120]


def classify_page(url: str, text_preview: str) -> str:
    """
    URL path와 본문 앞 500자로 페이지 유형을 추론.

    Returns
    -------
    str
        about | service | portfolio | history | contact | other
    """
    haystack = (url + " " + text_preview[:500]).lower()
    scores: dict[str, int] = {}
    for page_type, keywords in _PAGE_TYPE_KEYWORDS.items():
        scores[page_type] = sum(1 for kw in keywords if kw in haystack)

    best_type = max(scores, key=lambda t: scores[t])
    return best_type if scores[best_type] > 0 else "other"


def extract_page(url: str, html: str, depth: int = 0,
                 fetch_ms: int = 0) -> "CrawlPage | None":
    """
    HTML 문자열 → CrawlPage.

    Returns
    -------
    CrawlPage | None
        본문이 MIN_TEXT_LENGTH 미만이면 None 반환.
    """
    # trafilatura가 설치돼 있지 않으면 간단 fallback
    text = _extract_text(html)
    if not text or len(text) < MIN_TEXT_LENGTH:
        logger.debug("본문 부족 (%d자), 건너뜀: %s", len(text) if text else 0, url)
        return None

    title = extract_title(html)
    page_type = classify_page(url, text)

    # 순환 import 방지
    from app.models.crawl import CrawlPage

    return CrawlPage(
        url=url,
        title=title,
        text=text,       # CrawlPage.cap_text_length validator가 6000자 cap 적용
        page_type=page_type,  # type: ignore[arg-type]
        depth=depth,
        fetch_ms=fetch_ms,
    )


# ─────────────────────────────────────────────
# 내부: 텍스트 추출
# ─────────────────────────────────────────────

def _extract_text(html: str) -> str | None:
    """
    trafilatura 우선, 실패 시 간단 HTML 스트리퍼로 폴백.
    """
    # 1) trafilatura 시도
    try:
        import trafilatura  # type: ignore[import-untyped]

        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            favor_recall=True,
            deduplicate=True,
        )
        if text and len(text) >= MIN_TEXT_LENGTH:
            return text[:MAX_TEXT_LENGTH]
    except ImportError:
        pass
    except Exception as exc:
        logger.debug("trafilatura 오류: %s", exc)

    # 2) 간단 폴백: script/style 제거 후 태그 제거
    return _simple_strip(html)


_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL
)
_WHITESPACE_RE = re.compile(r"\s{2,}")


def _simple_strip(html: str) -> str | None:
    """최소한의 HTML → 텍스트 변환 (trafilatura 없을 때 폴백)."""
    text = _SCRIPT_STYLE_RE.sub(" ", html)
    text = _TAG_RE.sub(" ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text[:MAX_TEXT_LENGTH] if len(text) >= MIN_TEXT_LENGTH else None
