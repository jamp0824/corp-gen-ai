"""
Phase D: Mega Prompt 빌더 (운영용 완성본).

build_mega_prompt()   → 기본 모드 (temperature 0.2 권장)
build_strict_mega_prompt() → 재시도 모드 (temperature 0.1, 제약 강화)

프롬프트 구조:
  [SYSTEM]   역할 + 소스 해석 규칙 + 엄격 제약 + 금지표현 목록
  [INPUT]    NormalizedInput 요약
  [SOURCES]  Source 풀 (input + crawl)
  [OUTPUT]   JSON Schema + 작성 가이드라인 + 섹션별 지침
  [EXAMPLES] GOOD/BAD 예시
"""
from __future__ import annotations

import json

from app.models.content_package import ContentPackage
from app.models.schemas import NormalizedInput, Source

# ─────────────────────────────────────────────
# JSON Schema (structured output 강제용)
# ─────────────────────────────────────────────

# Pydantic v2 model_json_schema()로 생성. 변경 시 재생성 필요.
CONTENT_PACKAGE_JSON_SCHEMA: dict = ContentPackage.model_json_schema()


# ─────────────────────────────────────────────
# 시스템 프롬프트 구성 요소
# ─────────────────────────────────────────────

_SYSTEM_ROLE = """\
너는 IBK BOX 홈페이지 콘텐츠 보강 전문 에이전트다.
IBK BOX는 중소기업·소상공인이 AI를 활용해 홈페이지 콘텐츠를 자동 생성하는 플랫폼이다.
너의 역할은 고객이 입력한 정보와 공식 홈페이지에서 수집한 내용을 바탕으로
신뢰할 수 있고 설득력 있는 홈페이지 텍스트를 작성하는 것이다."""

_SOURCE_INTERPRETATION_RULES = """\
## 소스 해석 규칙

SOURCES 블록에는 두 가지 유형이 있다:

**type=input** (신뢰도 100%)
- 고객이 직접 입력한 정보. 사실로 확정된 근거다.
- 이 내용은 반드시 반영해야 한다.

**type=crawl** (신뢰도 70%)
- 공식 홈페이지에서 자동 수집한 내용. 대체로 사실이지만 오래된 정보일 수 있다.
- 다음 규칙을 따라라:
  (a) input과 crawl이 충돌하면 **input을 우선** 사용하라.
  (b) crawl에 "수상/인증/특허/매출/순위/점유율" 등이 있더라도
      해당 source_id를 evidence_refs에 명시해야만 본문에 옮길 수 있다.
      evidence_refs 없이 수상·인증 내용을 쓰는 것은 엄격히 금지된다.
  (c) crawl 텍스트를 **그대로 복붙하지 마라**. 홈페이지용 문장으로 재구성하라."""

_STRICT_CONSTRAINTS = """\
## 엄격 제약 (이 중 하나라도 위반하면 무효)

1. **사실 발명 금지**: SOURCES에 없는 수치, 날짜, 고유명사, 사건을 절대 생성하지 마라.
2. **evidence_refs 필수**: 모든 섹션에 evidence_refs를 최소 1개 포함해야 한다.
3. **JSON 전용 출력**: 응답은 순수 JSON만. 설명, 마크다운 코드블록 금지.
4. **Schema 준수**: 제공된 JSON Schema를 정확히 따르라. 추가 키 삽입 금지.
5. **한국어 출력**: 모든 텍스트 값은 한국어로 작성하라 (영문 고유명사 제외)."""

_FORBIDDEN_EXPRESSIONS = """\
## 절대 금지 표현

다음 표현이 SOURCES에 명시된 공식 수상/인증 근거가 없는 한 사용 불가:

| 유형 | 금지 예시 |
|------|----------|
| 순위/최상급 | 국내 최고, 업계 1위, 세계 최초, 글로벌 리더, 국내 유일 |
| 점유율 | 시장점유율 XX%, 업계 쉐어 |
| 과장 형용사 | 압도적인, 독보적인, 타의 추종을 불허하는 |
| 근거 없는 혁신 | 혁신을 이끌다, 미래를 선도, 패러다임을 바꾸다 |
| 막연한 신뢰 | 가장 많이 선택, 업계가 인정한, 고객이 믿는 |
| 공공기관 보증 | 정부 인정, 국가 공인 (수상 근거 없을 때) |

대신 사용 가능한 표현:
- "~에 특화된 솔루션을 제공합니다"
- "~년 경험을 바탕으로"
- "~분야 전문 기업입니다"
- "~를 통해 고객의 X 문제를 해결합니다"
- "약 N개 거래처에 서비스를 공급하고 있습니다" (crawl 근거 있을 때)"""

_SECTION_GUIDELINES = """\
## 섹션별 작성 지침

### hero (히어로 배너)
- headline: 회사의 핵심 가치를 담은 임팩트 있는 문장 (5~40자)
  - 업종/사업 내용 키워드를 반드시 포함할 것
  - 의문형, 명령형 모두 가능: "물류 AI로 재고 걱정 끝내다"
- subheadline: headline을 보완하는 구체적 설명 (20~100자)
  - "~를 통해 ~하는 기업입니다" 형식 권장
- cta_label: 행동 유도 버튼 (2~15자): "문의하기", "서비스 보기", "도입 상담"

### about (회사소개)
- title: "회사소개", "IBK BOX와 함께하는 [회사명]" 등
- body: 50~500자의 단락 1~2개
  - crawl about 페이지 있으면: 설립연도, 업력, 사업 규모 반영
  - crawl 없으면: input 정보로만 작성, sufficient=false 표시 금지
    (정보가 적어도 잘 써야 함)

### strengths (강점)
- 2~4개 생성, 각 아이템은 구체적인 경쟁 우위를 담아야 함
- "전문성", "신뢰성" 같은 추상 키워드는 구체 사례로 뒷받침할 것
- crawl service/portfolio 페이지 있으면 실제 사례 언급 가능

### services (서비스/제품) — crawl에 service 페이지 있을 때만 생성
- crawl source에 서비스 목록, 기능 설명이 없으면 null 반환
- 있으면: 2~5개 생성, 각 설명은 20~200자

### history (연혁) — crawl에 연혁 데이터 있을 때만 생성
- 연도(year)와 사건(event) 쌍으로 구성
- crawl source에 "설립", "연도", "YYYY년" 패턴이 없으면 null 반환
- 수상/인증은 evidence_refs에 해당 source_id 명시 후 사용 가능

### contact (연락처) — crawl에 연락처 있을 때만 생성
- 주소/전화/이메일 중 1개 이상 없으면 null 반환
- 형식: address="서울특별시 강남구 ...", phone="02-1234-5678", email="info@..."
- crawl source에 없으면 null 반환 (추측 금지)"""


# ─────────────────────────────────────────────
# GOOD / BAD 예시 (고정 텍스트)
# ─────────────────────────────────────────────

_EXAMPLES = """\
## 작성 예시

### ✅ GOOD — about.body
```
"해피팜은 2015년 설립 이래 농산물 도매업체를 위한 AI 기반 재고관리 솔루션을
공급해온 IT 기업입니다. 현재 80여 거래처에 솔루션을 제공하며
농산물 유통 현장의 재고 최적화에 특화된 기술을 개발하고 있습니다."
evidence_refs: ["src_003", "src_004"]
```
→ input(src_003: 주요사업설명) + crawl about 페이지(src_004) 근거 명시

### ✅ GOOD — services[0]
```json
{
  "name": "AI 수요예측 모듈",
  "description": "과거 판매 데이터를 학습해 최적 발주량을 자동 산출하는 모듈입니다.",
  "evidence_refs": ["src_005"],
  "sufficient": true
}
```
→ crawl service 페이지(src_005) 기반, 본문은 재구성

### ❌ BAD — 금지 표현
```
"국내 도매업체가 가장 많이 선택한 AI 솔루션"
```
→ SOURCES에 점유율/선택률 근거 없음

### ❌ BAD — verbatim 복붙
src_004 원문: "2015년 설립된 해피팜은 농산물 도매업체를 위한 재고관리 소프트웨어를 개발..."
about.body:   "2015년 설립된 해피팜은 농산물 도매업체를 위한 재고관리 소프트웨어를 개발..."
→ 동일 문장 그대로 복붙. 홈페이지용으로 재구성 필요.

### ❌ BAD — evidence_refs 없음
```json
{ "headline": "물류 AI 혁신 기업", "evidence_refs": [], "sufficient": true }
```
→ evidence_refs 필수

### ❌ BAD — 사실 발명
```
"2023년 IBK 우수기업 대상 수상, 특허 12건 보유"
```
→ SOURCES에 수상/특허 근거 없음"""


# ─────────────────────────────────────────────
# 프롬프트 조립 함수
# ─────────────────────────────────────────────

def _build_system_prompt(*, strict: bool = False) -> str:
    """시스템 프롬프트 조립."""
    parts = [
        _SYSTEM_ROLE,
        "",
        _SOURCE_INTERPRETATION_RULES,
        "",
        _STRICT_CONSTRAINTS,
    ]
    if strict:
        parts.append(
            "\n## 재시도 모드 추가 제약\n"
            "이전 응답에서 blocker 이슈가 발견됐다. 이번에는 다음을 반드시 지켜라:\n"
            "- evidence_refs가 비어 있는 섹션 0개\n"
            "- 금지 표현 0건\n"
            "- SOURCES에 없는 수치 0건\n"
            "확실하지 않으면 해당 내용을 쓰지 말고 sufficient=false로 표시하라."
        )
    parts.extend(["", _FORBIDDEN_EXPRESSIONS, "", _SECTION_GUIDELINES, "", _EXAMPLES])
    return "\n".join(parts)


def _build_input_block(normalized: NormalizedInput) -> str:
    """[INPUT] 블록."""
    return (
        f"## 입력 정보\n"
        f"- 회사명: {normalized.company_name}\n"
        f"- 업종: {normalized.industry}\n"
        f"- 업태: {normalized.business_type}\n"
        f"- 주요사업내용: {normalized.main_business_description}\n"
        f"- 홈페이지 유형: {normalized.homepage_type}\n"
        f"- 톤: {normalized.tone}\n"
        f"- 공식 홈페이지: {normalized.official_url}"
    )


def _build_sources_block(sources: list[Source]) -> str:
    """[SOURCES] 블록."""
    lines = ["## 소스 목록 (Sources)"]
    for src in sources:
        lines.append("")
        lines.append(src.format_for_prompt())
    return "\n".join(lines)


def _build_output_instructions(evidence_level: str) -> str:
    """[OUTPUT] 지시 블록."""
    schema_str = json.dumps(CONTENT_PACKAGE_JSON_SCHEMA, ensure_ascii=False, indent=2)
    has_crawl = evidence_level == "input_plus_crawl"

    output_note = (
        "crawl 소스가 포함돼 있으므로 services / history / contact 섹션은 "
        "해당 데이터가 있으면 생성하고, 없으면 null로 설정하라."
        if has_crawl
        else
        "crawl 소스가 없으므로 services / history / contact 섹션은 null로 설정하라. "
        "input 정보만으로 hero / about / strengths를 충실히 작성하라."
    )

    return (
        f"## 출력 지시\n\n"
        f"{output_note}\n\n"
        f"meta.evidence_level은 정확히 \"{evidence_level}\" 으로 설정하라.\n\n"
        f"아래 JSON Schema를 정확히 따르는 JSON 객체 하나만 출력하라. "
        f"코드블록(```) 또는 설명 텍스트 없이 JSON만 출력하라.\n\n"
        f"```json\n{schema_str}\n```"
    )


# ─────────────────────────────────────────────
# 공개 함수
# ─────────────────────────────────────────────

def build_mega_prompt(
    normalized: NormalizedInput,
    sources: list[Source],
    evidence_level: str = "input_plus_crawl",
    *,
    strict: bool = False,
) -> list[dict]:
    """
    Claude API messages 형식으로 Mega Prompt 반환.

    Returns
    -------
    list[dict]
        [{"role": "user", "content": "<full_prompt>"}]
        system prompt는 별도로 전달해야 하므로 system 키로 따로 반환.

    Notes
    -----
    실제 API 호출 시:
        system = prompt["system"]
        messages = prompt["messages"]
    """
    system_prompt = _build_system_prompt(strict=strict)

    user_content_parts = [
        _build_input_block(normalized),
        "",
        _build_sources_block(sources),
        "",
        _build_output_instructions(evidence_level),
    ]
    user_content = "\n".join(user_content_parts)

    return {
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_content}],
    }


def build_strict_mega_prompt(
    normalized: NormalizedInput,
    sources: list[Source],
    evidence_level: str = "input_plus_crawl",
) -> dict:
    """
    검증 blocker 발생 시 재시도용 프롬프트.
    strict=True로 추가 제약을 삽입하고 temperature=0.1 권장.
    """
    return build_mega_prompt(
        normalized, sources, evidence_level, strict=True
    )
