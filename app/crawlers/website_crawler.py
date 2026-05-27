"""
Phase B: 사이트 전체 크롤링 모듈 (풀버전).

알고리즘:
1. 시드 URL fetch → 링크 추출
2. priority 키워드 점수 기반 정렬 → 상위 MAX_PAGES 개 선택
3. asyncio Semaphore(5) 병렬 fetch
4. deadline 기반 종료 (budget_sec 초과 시 그때까지 수집된 페이지로 진행)
5. 300자 미만 본문 버림, depth ≤ 2 제한
6. 결과 최대 12페이지 (유형별 dedup 포함)

설계 원칙:
- 실패는 무시, 성공한 것만 모아서 반환 (부분 실패 허용)
- same-origin 링크만 추적
- 상대/절대 URL 모두 처리
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import defaultdict
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse, urlunparse

if TYPE_CHECKING:
    from app.models.crawl import CrawlPage

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# 상수
# ─────────────────────────────────────────────

MAX_PAGES: int = 12          # 최대 수집 페이지 수
MAX_PER_TYPE: int = 3        # 같은 page_type 내 중복 제한
CONCURRENCY: int = 5         # 동시 HTTP 요청 수
PAGE_TIMEOUT: float = 4.0    # 페이지당 HTTP timeout (초)
MIN_TEXT_LENGTH: int = 300   # 이 미만은 버림

BOT_HEADERS = {
    "User-Agent": "IBKBoxBot/1.0 (+https://box.ibk.co.kr/bot)",
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
}

# 링크 우선순위 키워드 (점수 합산, 높을수록 먼저 크롤)
PRIORITY_KO = [
    "회사소개", "소개", "서비스", "제품", "솔루션",
    "사업", "포트폴리오", "사례", "고객", "문의", "연혁", "인증",
]
PRIORITY_EN = [
    "about", "company", "service", "product", "solution",
    "business", "portfolio", "case", "contact", "history", "intro",
]
PRIORITY_KEYWORDS = PRIORITY_KO + PRIORITY_EN

# 수집 불필요 경로 패턴
_SKIP_PATH_RE = re.compile(
    r"\.(pdf|docx?|xlsx?|pptx?|zip|gz|tar|jpg|jpeg|png|gif|svg|ico|webp"
    r"|mp4|mp3|woff2?|ttf|eot|css|js|json|xml|rss|atom)(\?.*)?$",
    re.IGNORECASE,
)
_SKIP_FRAG_RE = re.compile(r"#.*$")

# <a href="..."> 추출용 정규식 (속도 중시, lxml 미사용)
_HREF_RE = re.compile(
    r'<a\b[^>]*\bhref=["\']([^"\'#][^"\']*)["\'][^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)


# ─────────────────────────────────────────────
# 링크 유틸리티
# ─────────────────────────────────────────────

def _normalize_url(url: str) -> str:
    """fragment 제거 + 트레일링 슬래시 통일."""
    url = _SKIP_FRAG_RE.sub("", url).strip()
    parsed = urlparse(url)
    # path가 비어 있으면 "/"
    path = parsed.path or "/"
    return urlunparse(parsed._replace(path=path, fragment=""))


def _same_origin(url: str, origin: str) -> bool:
    """URL의 netloc이 origin(도메인)과 같거나 서브도메인인지 확인."""
    netloc = urlparse(url).netloc.lower()
    origin_lower = origin.lower()
    return netloc == origin_lower or netloc.endswith("." + origin_lower)


def _score_link(href: str, anchor_text: str) -> int:
    """href + anchor 텍스트에서 우선순위 키워드 점수 합산."""
    combined = (href + " " + anchor_text).lower()
    return sum(1 for kw in PRIORITY_KEYWORDS if kw in combined)


def iter_links(html: str, base_url: str, origin: str) -> list[tuple[str, str]]:
    """
    HTML에서 same-origin 링크를 추출.

    Returns
    -------
    list of (normalized_url, anchor_text)
    """
    results: list[tuple[str, str]] = []
    for m in _HREF_RE.finditer(html):
        href = m.group(1).strip()
        anchor = re.sub(r"<[^>]+>", "", m.group(2)).strip()

        # javascript:, mailto:, tel: 등 제외
        if re.match(r"^(javascript|mailto|tel|ftp):", href, re.I):
            continue

        # 절대 URL로 변환
        abs_url = urljoin(base_url, href)

        # scheme 확인
        parsed = urlparse(abs_url)
        if parsed.scheme not in ("http", "https"):
            continue

        # same-origin 확인
        if not _same_origin(abs_url, origin):
            continue

        # 수집 불필요 확장자 제외
        if _SKIP_PATH_RE.search(parsed.path):
            continue

        results.append((_normalize_url(abs_url), anchor))

    return results


# ─────────────────────────────────────────────
# HTTP 단일 페이지 fetch
# ─────────────────────────────────────────────

async def _fetch_html(client: "httpx.AsyncClient", url: str) -> str:
    """
    단일 URL fetch → HTML 문자열.
    실패 시 예외를 그대로 올림.
    """
    import httpx  # 함수 안에서 import해서 의존성 없을 때 오류 방지

    resp = await client.get(url, timeout=PAGE_TIMEOUT)
    resp.raise_for_status()

    # Content-Type 확인
    ct = resp.headers.get("content-type", "")
    if "text/html" not in ct and "application/xhtml" not in ct:
        raise ValueError(f"HTML이 아님: {ct!r}")

    return resp.text


# ─────────────────────────────────────────────
# dedup: 같은 page_type이 MAX_PER_TYPE 개 초과 시 제거
# ─────────────────────────────────────────────

def _dedup_by_type(pages: list["CrawlPage"]) -> list["CrawlPage"]:
    """
    같은 page_type 내에서 텍스트가 가장 긴 MAX_PER_TYPE개만 남김.
    seed URL(depth=0)은 항상 유지.
    """
    per_type: dict[str, list["CrawlPage"]] = defaultdict(list)
    seed_pages: list["CrawlPage"] = []

    for p in pages:
        if p.depth == 0:
            seed_pages.append(p)
        else:
            per_type[p.page_type].append(p)

    result = list(seed_pages)
    for ptype, plist in per_type.items():
        # 글자 수 내림차순 정렬 후 상위 MAX_PER_TYPE개
        plist.sort(key=lambda x: -x.char_count)
        result.extend(plist[:MAX_PER_TYPE])

    return result[:MAX_PAGES]


# ─────────────────────────────────────────────
# 메인 크롤러
# ─────────────────────────────────────────────

async def crawl_site(
    seed: str,
    origin: str,
    *,
    budget_sec: float = 25.0,
) -> list["CrawlPage"]:
    """
    공식 홈페이지를 크롤링해 CrawlPage 목록 반환.

    Parameters
    ----------
    seed       : 시작 URL (= official_url)
    origin     : 도메인 (= PreflightResult.origin)
    budget_sec : 크롤링에 허용된 최대 초 (deadline 기반 종료)

    Returns
    -------
    list[CrawlPage]
        최대 12개, 300자 이상 본문, 유형별 dedup 완료.
        실패해도 빈 리스트 반환 (예외 X).
    """
    try:
        import httpx  # noqa: F401
    except ImportError:
        logger.error("httpx가 설치되지 않음. 크롤링을 건너뜀.")
        return []

    from .page_extractor import extract_page

    deadline = time.monotonic() + budget_sec
    collected_pages: list["CrawlPage"] = []
    visited: set[str] = set()

    # ── 공통 HTTP 클라이언트 ─────────────────
    import httpx

    async with httpx.AsyncClient(
        headers=BOT_HEADERS,
        follow_redirects=True,
        timeout=httpx.Timeout(PAGE_TIMEOUT),
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    ) as client:

        # ── Step 1: 시드 페이지 fetch ─────────
        seed_norm = _normalize_url(seed)
        visited.add(seed_norm)

        seed_start = time.monotonic()
        try:
            seed_html = await asyncio.wait_for(
                _fetch_html(client, seed_norm),
                timeout=min(PAGE_TIMEOUT, deadline - time.monotonic()),
            )
        except Exception as exc:
            logger.warning("시드 fetch 실패: %s — %s", seed_norm, exc)
            return []  # 시드 자체 실패 → input only fallback

        seed_ms = int((time.monotonic() - seed_start) * 1000)
        seed_page = extract_page(seed_norm, seed_html, depth=0, fetch_ms=seed_ms)
        if seed_page:
            collected_pages.append(seed_page)

        # ── Step 2: 링크 수집 + 점수 정렬 ────
        raw_links = iter_links(seed_html, seed_norm, origin)
        # (score, url, anchor) 내림차순
        scored: list[tuple[int, str, str]] = []
        for url, anchor in raw_links:
            if url not in visited:
                scored.append((_score_link(url, anchor), url, anchor))
                visited.add(url)

        scored.sort(key=lambda x: -x[0])
        targets = [u for _, u, _ in scored][: MAX_PAGES - 1]

        logger.info(
            "크롤 대상 %d개 (시드 포함 %d개), budget=%.1fs",
            len(targets), len(targets) + 1, budget_sec,
        )

        if not targets:
            # 링크가 없어도 시드 1개로 진행
            return _dedup_by_type(collected_pages)

        # ── Step 3: 병렬 fetch ────────────────
        sem = asyncio.Semaphore(CONCURRENCY)

        async def worker(url: str, depth: int = 1) -> "CrawlPage | None":
            async with sem:
                if time.monotonic() > deadline:
                    logger.debug("deadline 초과, 건너뜀: %s", url)
                    return None
                remaining = deadline - time.monotonic()
                t0 = time.monotonic()
                try:
                    html = await asyncio.wait_for(
                        _fetch_html(client, url),
                        timeout=min(PAGE_TIMEOUT, remaining),
                    )
                    ms = int((time.monotonic() - t0) * 1000)
                    return extract_page(url, html, depth=depth, fetch_ms=ms)
                except asyncio.TimeoutError:
                    logger.debug("timeout: %s", url)
                    return None
                except Exception as exc:
                    logger.debug("fetch 실패: %s — %s", url, exc)
                    return None

        results = await asyncio.gather(*(worker(u) for u in targets))

        for r in results:
            if r is not None:
                collected_pages.append(r)

    final = _dedup_by_type(collected_pages)
    logger.info(
        "크롤링 완료: 성공 %d페이지 / 시도 %d개 (%.1fs 경과)",
        len(final),
        len(targets) + 1,
        time.monotonic() - (deadline - budget_sec),
    )
    return final
