"""
Phase E: ContentPackage 검증기 (풀버전).

검사 항목:
1. FORBIDDEN_EXPRESSION   — 금지 표현 regex 매칭 (blocker)
2. MISSING_EVIDENCE_REF   — evidence_refs가 비어있거나 src_id가 sources에 없음 (blocker)
3. VERBATIM_COPY_FROM_CRAWL — crawl 소스 본문을 25자 이상 그대로 복붙 (warning)
4. INSUFFICIENT_SECTION   — sufficient=False로 표시된 섹션 (warning)
5. HALLUCINATION_RISK     — input/crawl 어디에도 없는 수치/고유명사가 본문에 등장 (warning)
"""
from __future__ import annotations

import re
from typing import Any

from app.models.content_package import ContentPackage
from app.models.schemas import Source, ValidationIssue, ValidationResult

# ─────────────────────────────────────────────
# 1. 금지 표현 패턴 (blocker)
# ─────────────────────────────────────────────

_FORBIDDEN_PATTERNS: list[tuple[str, str]] = [
    # (패턴, human-readable 설명)
    (r"국내\s*(최고|1위|최초|유일|최대|최다|최장)", "국내 순위/최상급 표현"),
    (r"업계\s*(1위|최고|최초|선도|리더|표준)", "업계 순위/최상급 표현"),
    (r"(세계|글로벌|전세계)\s*(최고|1위|최초|유일|최대)", "글로벌 순위/최상급 표현"),
    (r"(시장|업계)\s*(점유율|쉐어)", "시장점유율 표현"),
    (r"압도적",                    "과장 형용사: 압도적"),
    (r"독보적",                    "과장 형용사: 독보적"),
    (r"혁신(적인|을 이끄는|의 선두)", "근거 없는 혁신 표현"),
    (r"(가장\s+많이|가장\s+선택|가장\s+신뢰)", "최상급 비교 표현"),
    (r"\d+\s*%\s*(점유율|성장율|성장률)", "수치 점유율/성장률"),
    (r"(국가|정부)\s*(인정|공인|선정|추천)", "공공기관 보증 표현 (근거 필요)"),
]

_COMPILED_FORBIDDEN = [
    (re.compile(pattern, re.IGNORECASE), desc)
    for pattern, desc in _FORBIDDEN_PATTERNS
]

# ─────────────────────────────────────────────
# 2. verbatim 복붙 검사
# ─────────────────────────────────────────────

_VERBATIM_NGRAM_SIZE = 25   # 이 길이 이상 연속 일치면 복붙 의심


def _has_verbatim_overlap(text: str, source_text: str, n: int = _VERBATIM_NGRAM_SIZE) -> bool:
    """text 안에 source_text의 연속 n자 부분 문자열이 포함되면 True."""
    if len(source_text) < n:
        return False
    # 공백 정규화 후 비교
    t = re.sub(r"\s+", " ", text.lower())
    s = re.sub(r"\s+", " ", source_text.lower())
    for i in range(len(s) - n + 1):
        if s[i: i + n] in t:
            return True
    return False


# ─────────────────────────────────────────────
# 3. 수치/고유명사 환각 검사
# ─────────────────────────────────────────────

_NUM_RE = re.compile(r"\d[\d,]*(\.\d+)?(\s*(개|명|년|월|억|만|천|백|건|%|km|m|kg|대))?"  )
_COMPANY_NAME_RE = re.compile(r"[A-Z][a-z]+|[가-힣]{2,4}(주식회사|㈜|Inc\.|Corp\.|Ltd\.)")


def _extract_numbers_and_entities(text: str) -> set[str]:
    """
    텍스트에서 수치(숫자+단위)와 고유명사 후보를 추출.
    환각 검사의 입력으로 사용.
    """
    found: set[str] = set()
    for m in _NUM_RE.finditer(text):
        found.add(m.group(0).strip())
    return found


def _is_grounded(value: str, sources: list[Source]) -> bool:
    """value에 등장하는 수치가 모두 소스에 존재하는지 확인."""
    nums = _extract_numbers_and_entities(value)
    if not nums:
        return True  # 수치 없으면 환각 의심 없음
    all_source_text = " ".join(s.text for s in sources)
    return all(num in all_source_text for num in nums)


# ─────────────────────────────────────────────
# 내부 검증 헬퍼
# ─────────────────────────────────────────────

def _check_section(
    section_name: str,
    text_fields: list[str],
    evidence_refs: list[str],
    sufficient: bool,
    sources: list[Source],
    src_map: dict[str, Source],
    issues: list[ValidationIssue],
) -> None:
    """단일 섹션 검증. 발견된 이슈를 issues 리스트에 추가."""
    combined_text = " ".join(text_fields)

    # ── 1. 금지 표현 ─────────────────────────
    for pattern, desc in _COMPILED_FORBIDDEN:
        if pattern.search(combined_text):
            issues.append(ValidationIssue(
                section=section_name,
                code="FORBIDDEN_EXPRESSION",
                hint=f"금지 표현 발견: {desc}",
                blocker=True,
            ))

    # ── 2. evidence_refs 무결성 ───────────────
    if not evidence_refs:
        issues.append(ValidationIssue(
            section=section_name,
            code="MISSING_EVIDENCE_REF",
            hint="evidence_refs가 비어 있습니다. 근거 source_id를 1개 이상 명시해야 합니다.",
            blocker=True,
        ))
    else:
        for ref in evidence_refs:
            if ref not in src_map:
                issues.append(ValidationIssue(
                    section=section_name,
                    code="MISSING_EVIDENCE_REF",
                    hint=f"{ref}가 Sources 목록에 없습니다.",
                    blocker=True,
                ))

    # ── 3. verbatim 복붙 (crawl 소스만) ──────
    crawl_sources = [s for s in sources if s.source_type == "crawl"]
    for src in crawl_sources:
        if _has_verbatim_overlap(combined_text, src.text):
            issues.append(ValidationIssue(
                section=section_name,
                code="VERBATIM_COPY_FROM_CRAWL",
                hint=(
                    f"crawl 소스({src.source_id}, {src.origin})의 "
                    f"25자 이상 구문이 그대로 사용됐습니다. "
                    "홈페이지용 문장으로 재구성해 주세요."
                ),
                blocker=False,  # warning만
            ))

    # ── 4. sufficient=False ───────────────────
    if not sufficient:
        issues.append(ValidationIssue(
            section=section_name,
            code="INSUFFICIENT_SECTION",
            hint="LLM이 이 섹션은 근거가 부족하다고 판단했습니다.",
            blocker=False,
        ))

    # ── 5. 환각 위험 (수치 그라운딩) ─────────
    if not _is_grounded(combined_text, sources):
        issues.append(ValidationIssue(
            section=section_name,
            code="HALLUCINATION_RISK",
            hint="본문의 수치가 어떤 source에도 등장하지 않습니다. 근거를 확인하세요.",
            blocker=False,
        ))


# ─────────────────────────────────────────────
# 공개 함수
# ─────────────────────────────────────────────

def validate_package(
    package: ContentPackage,
    sources: list[Source],
) -> ValidationResult:
    """
    ContentPackage 전체를 검증해 ValidationResult 반환.

    Parameters
    ----------
    package : LLM이 생성한 ContentPackage
    sources : build_source_pool()이 반환한 Source 목록

    Returns
    -------
    ValidationResult
        blockers: 재시도가 필요한 이슈
        warnings: 운영자 검토 권장 이슈
    """
    src_map: dict[str, Source] = {s.source_id: s for s in sources}
    all_issues: list[ValidationIssue] = []

    sections = package.sections

    # ── hero ─────────────────────────────────
    _check_section(
        "hero",
        [sections.hero.headline, sections.hero.subheadline, sections.hero.cta_label],
        sections.hero.evidence_refs,
        sections.hero.sufficient,
        sources, src_map, all_issues,
    )

    # ── about ─────────────────────────────────
    _check_section(
        "about",
        [sections.about.title, sections.about.body],
        sections.about.evidence_refs,
        sections.about.sufficient,
        sources, src_map, all_issues,
    )

    # ── strengths ─────────────────────────────
    for i, strength in enumerate(sections.strengths):
        _check_section(
            f"strengths[{i}]",
            [strength.title, strength.description],
            strength.evidence_refs,
            strength.sufficient,
            sources, src_map, all_issues,
        )

    # ── services (optional) ───────────────────
    if sections.services:
        for i, svc in enumerate(sections.services):
            _check_section(
                f"services[{i}]",
                [svc.name, svc.description],
                svc.evidence_refs,
                svc.sufficient,
                sources, src_map, all_issues,
            )

    # ── history (optional) ────────────────────
    if sections.history:
        for i, item in enumerate(sections.history):
            _check_section(
                f"history[{i}]",
                [item.event],
                item.evidence_refs,
                True,   # history는 sufficient 필드 없음
                sources, src_map, all_issues,
            )

    # ── contact (optional) ────────────────────
    if sections.contact:
        contact_fields = [
            f for f in [
                sections.contact.address,
                sections.contact.phone,
                sections.contact.email,
            ] if f
        ]
        _check_section(
            "contact",
            contact_fields,
            sections.contact.evidence_refs,
            sections.contact.sufficient,
            sources, src_map, all_issues,
        )

    # ── 분리 ──────────────────────────────────
    blockers = [i for i in all_issues if i.blocker]
    warnings = [i for i in all_issues if not i.blocker]

    return ValidationResult(blockers=blockers, warnings=warnings)
