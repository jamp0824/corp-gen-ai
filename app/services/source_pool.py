"""
Phase C: Source 풀 빌더.

NormalizedInput(사용자 입력) + list[CrawlPage](크롤 결과)를
Source 목록으로 통합한다.

Source ID 규칙: src_001, src_002, ... (0-패딩 3자리)
"""
from __future__ import annotations

from app.models.crawl import CrawlPage
from app.models.schemas import NormalizedInput, Source


def build_source_pool(
    normalized: NormalizedInput,
    crawl_pages: list[CrawlPage],
) -> list[Source]:
    """
    input 소스와 crawl 소스를 합쳐 정렬된 Source 목록 반환.

    정렬 순서:
    - input 소스 먼저 (신뢰도 높고 LLM에 먼저 보여줘야 함)
    - crawl은 page_type 우선순위 순 (about → service → history → portfolio → contact → other)

    Parameters
    ----------
    normalized   : 검증된 사용자 입력
    crawl_pages  : crawler가 반환한 CrawlPage 목록 (없으면 빈 리스트)

    Returns
    -------
    list[Source]
        source_id가 src_001부터 순차 부여된 목록
    """
    sources: list[Source] = []
    sid = 1

    # ── 1. Input 소스 ──────────────────────────────────────────────
    for pointer, value in normalized.iter_evidence_fields():
        # tone/homepage_type은 LLM 지시용이므로 source에서 제외
        if pointer in ("/tone", "/homepage_type"):
            continue
        sources.append(
            Source(
                source_id=f"src_{sid:03d}",
                source_type="input",
                origin=pointer,
                page_type=None,
                text=value,
                confidence=1.0,
            )
        )
        sid += 1

    # ── 2. Crawl 소스 (page_type 우선순위 정렬) ───────────────────
    _CRAWL_TYPE_ORDER = {
        "about": 0,
        "service": 1,
        "history": 2,
        "portfolio": 3,
        "contact": 4,
        "other": 5,
    }
    sorted_pages = sorted(
        crawl_pages,
        key=lambda p: (_CRAWL_TYPE_ORDER.get(p.page_type, 5), -p.char_count),
    )

    for page in sorted_pages:
        sources.append(
            Source(
                source_id=f"src_{sid:03d}",
                source_type="crawl",
                origin=page.url,
                page_type=page.page_type,
                text=page.to_source_text(),
                confidence=0.7,
            )
        )
        sid += 1

    return sources
