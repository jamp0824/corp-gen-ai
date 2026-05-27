"""
Phase D: LLM 클라이언트.

Claude API (Anthropic SDK)를 래핑.
- structured JSON output 강제 (tool use + json schema)
- prompt caching (system prompt cache_control)
- 자동 재시도 (SDK 기본 max_retries=2)
"""
from __future__ import annotations

import json
import logging

from app.core.config import settings
from app.models.content_package import ContentPackage
from app.services.prompt_builder import CONTENT_PACKAGE_JSON_SCHEMA

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Anthropic Claude API 클라이언트 래퍼.

    사용 예:
        client = LLMClient()
        package = await client.complete_package(prompt_dict, temperature=0.2)
    """

    def __init__(self) -> None:
        try:
            import anthropic  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "anthropic 패키지가 필요합니다: pip install anthropic"
            ) from e

        self._client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            max_retries=2,
        )
        self._model = settings.llm_model

    async def complete_package(
        self,
        prompt: dict,
        *,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> ContentPackage:
        """
        Mega Prompt → ContentPackage.

        Tool use (structured output) 방식으로 JSON을 강제한다.
        실패 시 anthropic.APIError를 그대로 올린다.

        Parameters
        ----------
        prompt      : build_mega_prompt() 반환값 {"system": ..., "messages": ...}
        temperature : 기본 0.2, 재시도는 0.1
        max_tokens  : 최대 출력 토큰 (4096으로도 충분)

        Returns
        -------
        ContentPackage
            Pydantic 검증 완료된 콘텐츠 패키지
        """
        import anthropic

        # system prompt에 prompt caching 적용
        # (system 내용이 동일하면 Anthropic이 캐시 히트로 처리)
        system_with_cache: list[dict] = [
            {
                "type": "text",
                "text": prompt["system"],
                "cache_control": {"type": "ephemeral"},
            }
        ]

        # structured output 강제: tool_use 방식
        # ContentPackage JSON Schema를 tool input_schema로 전달
        tools = [
            {
                "name": "output_content_package",
                "description": (
                    "홈페이지 콘텐츠 패키지를 JSON 형식으로 출력하는 도구. "
                    "반드시 이 도구를 사용해 응답해야 한다."
                ),
                "input_schema": CONTENT_PACKAGE_JSON_SCHEMA,
            }
        ]

        logger.debug("LLM 호출: model=%s temperature=%.1f", self._model, temperature)

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_with_cache,
            tools=tools,  # type: ignore[arg-type]
            tool_choice={"type": "tool", "name": "output_content_package"},
            messages=prompt["messages"],
        )

        # tool_use 블록에서 JSON 추출
        tool_result = None
        for block in response.content:
            if block.type == "tool_use" and block.name == "output_content_package":
                tool_result = block.input
                break

        if tool_result is None:
            # tool_use가 없으면 text 응답에서 JSON 파싱 시도 (폴백)
            logger.warning("tool_use 블록 없음, text 응답에서 JSON 파싱 시도")
            for block in response.content:
                if hasattr(block, "text"):
                    raw = block.text.strip()
                    # 마크다운 코드블록 제거
                    if raw.startswith("```"):
                        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
                    tool_result = json.loads(raw)
                    break

        if tool_result is None:
            raise ValueError("LLM이 유효한 JSON을 반환하지 않았습니다.")

        logger.debug(
            "LLM 완료: input_tokens=%d output_tokens=%d",
            response.usage.input_tokens,
            response.usage.output_tokens,
        )

        return ContentPackage.model_validate(tool_result)
