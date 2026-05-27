"""
Phase A: Pre-flight 검증 모듈.

수행하는 검사:
1. URL 형식 (scheme + netloc)
2. 차단 도메인 (SNS, 블로그 플랫폼 등)
3. robots.txt — IBKBoxBot/1.0 기준으로 접근 허용 여부

목표 실행 시간: ≤2s
"""
from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# 상수
# ─────────────────────────────────────────────

BOT_NAME = "IBKBoxBot/1.0"

# 공식 홈페이지로 사용할 수 없는 플랫폼 도메인
# endswith() 비교이므로 서브도메인도 모두 매칭됨
BLOCKED_DOMAINS: frozenset[str] = frozenset({
    # 소셜 미디어
    "instagram.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "threads.net",
    "tiktok.com",
    "linkedin.com",
    "youtube.com",
    "pinterest.com",
    # 한국 블로그/커뮤니티
    "naver.com",          # 메인 포함 (공식 홈이 naver.com 자체인 경우는 극히 드묾)
    "blog.naver.com",
    "cafe.naver.com",
    "post.naver.com",
    "daum.net",
    "blog.daum.net",
    "tistory.com",
    "brunch.co.kr",
    "velog.io",
    "medium.com",
    "tumblr.com",
    "notion.site",        # 임시 소개 페이지로는 OK지만 공식 홈으론 부족
    # 리뷰/디렉토리
    "google.com",
    "namu.wiki",
    "wikipedia.org",
    "naverbiz.com",
    "jobplanet.co.kr",
    "wanted.co.kr",
    "saramin.co.kr",
})


# ─────────────────────────────────────────────
# 예외
# ─────────────────────────────────────────────

class InvalidURL(Exception):
    """Pre-flight 검증 실패 예외."""

    # code 필드를 통해 API 에러 응답에서 구체적 이유를 반환
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"[{code}] {detail}")


# ─────────────────────────────────────────────
# Pre-flight 로직
# ─────────────────────────────────────────────

def _is_blocked_domain(netloc: str) -> bool:
    """netloc이 차단 도메인이거나 그 서브도메인이면 True."""
    netloc_lower = netloc.lower().lstrip("www.")
    return any(
        netloc_lower == d or netloc_lower.endswith("." + d)
        for d in BLOCKED_DOMAINS
    )


def _read_robots(robots_url: str) -> RobotFileParser:
    """robots.txt를 동기로 읽어 파서 반환. 실패 시 빈 파서(모두 허용)."""
    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()  # urllib 동기 IO
    except Exception as exc:
        logger.debug("robots.txt 읽기 실패 (%s): %s", robots_url, exc)
    return rp


async def preflight(url: str) -> "PreflightResult":  # noqa: F821
    """
    URL 유효성 검사 + robots.txt 확인.

    Parameters
    ----------
    url : str
        검증할 공식 홈페이지 URL.

    Returns
    -------
    PreflightResult
        origin (도메인), scheme, robots_allowed 포함.

    Raises
    ------
    InvalidURL
        검증 실패 시. .code 속성으로 실패 이유를 구분.
    """
    # 1. 형식 검사
    try:
        parsed = urlparse(url.strip())
    except Exception:
        raise InvalidURL("invalid_format", "URL 파싱 실패")

    if parsed.scheme not in ("http", "https"):
        raise InvalidURL(
            "invalid_scheme",
            f"지원하는 scheme: http, https  (입력: {parsed.scheme!r})",
        )

    if not parsed.netloc:
        raise InvalidURL("missing_netloc", "도메인이 없는 URL입니다.")

    # 2. 차단 도메인
    if _is_blocked_domain(parsed.netloc):
        raise InvalidURL(
            "blocked_domain",
            f"{parsed.netloc}은 공식 홈페이지로 사용할 수 없는 도메인입니다. "
            "기업 공식 도메인 URL을 입력해 주세요.",
        )

    # 3. robots.txt (timeout 2s, 실패해도 허용으로 처리)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        rp = await asyncio.wait_for(
            asyncio.to_thread(_read_robots, robots_url),
            timeout=2.0,
        )
        robots_allowed = rp.can_fetch(BOT_NAME, url)
    except asyncio.TimeoutError:
        logger.warning("robots.txt timeout: %s", robots_url)
        robots_allowed = True  # timeout → 허용으로 간주
    except Exception as exc:
        logger.warning("robots.txt 예외: %s — %s", robots_url, exc)
        robots_allowed = True

    if not robots_allowed:
        raise InvalidURL(
            "robots_disallow",
            "공식 홈페이지가 봇 접근을 막고 있어요. "
            "정보를 직접 입력하거나 다른 URL을 시도해 주세요.",
        )

    # 순환 import 방지를 위해 여기서만 import
    from app.models.schemas import PreflightResult

    return PreflightResult(
        origin=parsed.netloc,
        scheme=parsed.scheme,  # type: ignore[arg-type]
        robots_allowed=robots_allowed,
    )
