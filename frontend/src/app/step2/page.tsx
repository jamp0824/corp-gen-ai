"use client";

/**
 * Step 2 페이지 — SSE 버전.
 *
 * 흐름:
 * 1. EnrichmentForm 제출
 * 2. POST /content-enrichment → job_id (즉시)
 * 3. LoadingOverlay 표시
 * 4. SSE /stream/{job_id} 구독 → 실시간 phase 메시지
 * 5. complete 이벤트 수신 → sessionStorage 저장 → /step3 이동
 * 6. error 이벤트 수신 → 에러 배너 표시
 */

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { EnrichmentForm } from "@/components/step2/EnrichmentForm";
import { LoadingOverlay }  from "@/components/loading/LoadingOverlay";
import {
  connectEnrichmentSSE,
  saveResult,
  startEnrichment,
  EnrichmentApiError,
  type PhaseUpdate,
} from "@/lib/api";
import type { EnrichmentRequest } from "@/types/content";

const ERROR_MESSAGES: Record<string, string> = {
  invalid_url:      "URL 형식이 올바르지 않습니다. 다시 확인해주세요.",
  invalid_scheme:   "https:// 또는 http://로 시작하는 URL을 입력해주세요.",
  blocked_domain:   "공식 홈페이지가 아닌 SNS·블로그 URL입니다. 기업 공식 도메인을 입력해주세요.",
  robots_disallow:  "이 홈페이지는 자동 수집을 허용하지 않습니다. 다른 URL을 시도해주세요.",
  llm_timeout:      "AI 응답이 지연되고 있습니다. 잠시 후 다시 시도해주세요.",
  llm_error:        "AI 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
  sse_closed:       "서버 연결이 끊겼습니다. 다시 시도해주세요.",
  internal_error:   "서버 내부 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
};

export default function Step2Page() {
  const router    = useRouter();
  const [isLoading, setIsLoading]   = useState(false);
  const [startedAt, setStartedAt]   = useState(0);
  const [errorMsg, setErrorMsg]     = useState<string | null>(null);
  const [currentPhase, setCurrentPhase] = useState<PhaseUpdate | null>(null);
  const cleanupSseRef = useRef<(() => void) | null>(null);

  const handleSubmit = useCallback(async (data: EnrichmentRequest) => {
    setErrorMsg(null);
    setCurrentPhase(null);
    setIsLoading(true);
    setStartedAt(Date.now());

    let jobId: string;
    try {
      // ── Step 1: POST → job_id ──────────────────
      jobId = await startEnrichment(data);
    } catch (err) {
      setIsLoading(false);
      if (err instanceof EnrichmentApiError) {
        setErrorMsg(ERROR_MESSAGES[err.code] ?? err.message);
      } else {
        setErrorMsg("네트워크 오류가 발생했습니다. 인터넷 연결을 확인해주세요.");
      }
      return;
    }

    // ── Step 2: SSE 구독 ───────────────────────────
    const cleanup = connectEnrichmentSSE(jobId, {
      onPhase: (update) => {
        setCurrentPhase(update);
      },
      onComplete: (result) => {
        saveResult(result);
        router.push("/step3");
        // isLoading은 페이지 전환 후 자동 해제
      },
      onError: (code, message) => {
        setIsLoading(false);
        setCurrentPhase(null);
        setErrorMsg(ERROR_MESSAGES[code] ?? message);
        cleanupSseRef.current = null;
      },
    });

    cleanupSseRef.current = cleanup;

    // ── Step 3: 안전망 timeout (65s) ──────────────
    setTimeout(() => {
      if (!isLoading) return;
      cleanup();
      setIsLoading(false);
      setCurrentPhase(null);
      setErrorMsg("요청 시간이 초과됐습니다. 다시 시도해주세요.");
    }, 65_000);
  }, [router, isLoading]);

  const handleDismissError = () => {
    setErrorMsg(null);
    cleanupSseRef.current?.();
    cleanupSseRef.current = null;
  };

  return (
    <>
      {/* 로딩 오버레이 */}
      {isLoading && (
        <LoadingOverlay
          startedAt={startedAt}
          realPhase={currentPhase}
        />
      )}

      <div className="max-w-2xl mx-auto space-y-8">
        {/* 스텝 인디케이터 */}
        <StepIndicator current={2} />

        {/* 제목 */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">공식 홈페이지 정보 입력</h1>
          <p className="text-sm text-gray-500 mt-1">
            AI가 홈페이지를 분석해 최적의 콘텐츠를 자동으로 생성합니다.
          </p>
        </div>

        {/* 에러 배너 */}
        {errorMsg && (
          <div className="flex items-start gap-3 bg-red-50 border border-red-200
            rounded-xl px-4 py-3 animate-fade-in">
            <span className="text-red-400 mt-0.5 shrink-0">⚠️</span>
            <div className="min-w-0">
              <p className="text-sm text-red-700 font-medium">요청 실패</p>
              <p className="text-xs text-red-600 mt-0.5">{errorMsg}</p>
            </div>
            <button
              type="button"
              onClick={handleDismissError}
              className="ml-auto text-red-300 hover:text-red-500 text-xl leading-none shrink-0"
            >
              ×
            </button>
          </div>
        )}

        {/* 폼 */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 sm:p-8">
          <EnrichmentForm onSubmit={handleSubmit} isLoading={isLoading} />
        </div>
      </div>
    </>
  );
}

// ─────────────────────────────────────────────
// 공통 스텝 인디케이터
// ─────────────────────────────────────────────

function StepIndicator({ current }: { current: number }) {
  const steps = [
    { n: 1, label: "기본 정보" },
    { n: 2, label: "홈페이지 정보" },
    { n: 3, label: "콘텐츠 확인" },
  ];
  return (
    <div className="flex items-center gap-3 text-sm">
      {steps.map(({ n, label }) => {
        const done   = n < current;
        const active = n === current;
        return (
          <div key={n} className="flex items-center gap-2">
            {n > 1 && (
              <div className={`w-6 h-px ${done ? "bg-ibk-400" : "bg-gray-200"}`} />
            )}
            <div className={`flex items-center gap-1.5 ${
              active ? "text-ibk-700" : done ? "text-ibk-500" : "text-gray-400"
            }`}>
              <span className={`w-6 h-6 rounded-full text-xs font-semibold
                flex items-center justify-center
                ${active ? "bg-ibk-600 text-white" : done ? "bg-ibk-100 text-ibk-600" : "bg-gray-200 text-gray-400"}`}>
                {done ? "✓" : n}
              </span>
              <span className="hidden sm:block text-xs font-medium">{label}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
