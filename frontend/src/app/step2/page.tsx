"use client";

/**
 * Step 2 페이지.
 *
 * 흐름:
 * 1. EnrichmentForm 렌더
 * 2. 제출 → LoadingOverlay 표시 + POST /api/v1/content-enrichment
 * 3. 성공 → sessionStorage 저장 후 /step3 이동
 * 4. 실패 → 에러 배너 표시 (폼 유지)
 */

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { EnrichmentForm } from "@/components/step2/EnrichmentForm";
import { LoadingOverlay }  from "@/components/loading/LoadingOverlay";
import {
  enrichContent,
  saveResult,
  EnrichmentApiError,
} from "@/lib/api";
import type { EnrichmentRequest } from "@/types/content";

// 에러 코드 → 사용자 친화적 메시지
const ERROR_MESSAGES: Record<string, string> = {
  invalid_url:      "URL 형식이 올바르지 않습니다. 다시 확인해주세요.",
  invalid_scheme:   "https:// 또는 http://로 시작하는 URL을 입력해주세요.",
  blocked_domain:   "공식 홈페이지가 아닌 SNS·블로그 URL입니다. 기업 공식 도메인을 입력해주세요.",
  robots_disallow:  "이 홈페이지는 자동 수집을 허용하지 않습니다. 다른 URL을 시도하거나 정보를 직접 입력해주세요.",
  llm_timeout:      "AI 응답이 지연되고 있습니다. 잠시 후 다시 시도해주세요.",
  llm_error:        "AI 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
};

export default function Step2Page() {
  const router = useRouter();
  const [isLoading, setIsLoading]     = useState(false);
  const [startedAt, setStartedAt]     = useState(0);
  const [errorMsg, setErrorMsg]       = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const handleSubmit = async (data: EnrichmentRequest) => {
    setErrorMsg(null);
    setIsLoading(true);
    setStartedAt(Date.now());

    const controller = new AbortController();
    abortRef.current = controller;

    // 브라우저 레벨 timeout: 65s (서버보다 5s 여유)
    const timeoutId = setTimeout(() => controller.abort(), 65_000);

    try {
      const result = await enrichContent(data, controller.signal);
      saveResult(result);
      router.push("/step3");
    } catch (err) {
      if (err instanceof EnrichmentApiError) {
        setErrorMsg(
          ERROR_MESSAGES[err.code] ??
          err.message ??
          "오류가 발생했습니다. 다시 시도해주세요.",
        );
      } else if (err instanceof DOMException && err.name === "AbortError") {
        setErrorMsg("요청 시간이 초과됐습니다. 다시 시도해주세요.");
      } else {
        setErrorMsg("네트워크 오류가 발생했습니다. 인터넷 연결을 확인해주세요.");
      }
    } finally {
      clearTimeout(timeoutId);
      setIsLoading(false);
    }
  };

  return (
    <>
      {/* 로딩 오버레이 */}
      {isLoading && <LoadingOverlay startedAt={startedAt} />}

      <div className="max-w-2xl mx-auto space-y-8">
        {/* 스텝 인디케이터 */}
        <div className="flex items-center gap-3 text-sm">
          {[
            { n: 1, label: "기본 정보" },
            { n: 2, label: "홈페이지 정보", active: true },
            { n: 3, label: "콘텐츠 확인" },
          ].map(({ n, label, active }) => (
            <div key={n} className="flex items-center gap-2">
              {n > 1 && <div className="w-6 h-px bg-gray-200" />}
              <div className={`flex items-center gap-1.5 ${
                active ? "text-ibk-700" : "text-gray-400"
              }`}>
                <span className={`w-6 h-6 rounded-full text-xs font-semibold
                  flex items-center justify-center
                  ${active
                    ? "bg-ibk-600 text-white"
                    : "bg-gray-200 text-gray-400"
                  }`}>
                  {n}
                </span>
                <span className={`hidden sm:block text-xs font-medium ${
                  active ? "text-ibk-700" : "text-gray-400"
                }`}>
                  {label}
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* 제목 */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            공식 홈페이지 정보 입력
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            AI가 홈페이지를 분석해 최적의 콘텐츠를 자동으로 생성합니다.
          </p>
        </div>

        {/* 에러 배너 */}
        {errorMsg && (
          <div className="flex items-start gap-3 bg-red-50 border border-red-200
            rounded-xl px-4 py-3 animate-fade-in">
            <span className="text-red-400 mt-0.5">⚠️</span>
            <div>
              <p className="text-sm text-red-700 font-medium">요청 실패</p>
              <p className="text-xs text-red-600 mt-0.5">{errorMsg}</p>
            </div>
            <button
              type="button"
              onClick={() => setErrorMsg(null)}
              className="ml-auto text-red-300 hover:text-red-500 text-lg leading-none"
            >
              ×
            </button>
          </div>
        )}

        {/* 폼 카드 */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 sm:p-8">
          <EnrichmentForm onSubmit={handleSubmit} isLoading={isLoading} />
        </div>
      </div>
    </>
  );
}
