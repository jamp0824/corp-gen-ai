"use client";

/**
 * 크롤링 + LLM 처리 중 전체화면 로딩 오버레이.
 *
 * realPhase prop이 있으면 실제 SSE 이벤트 기반으로 표시.
 * 없으면 타이머 기반 더미 메시지로 폴백 (기존 동작 유지).
 */

import { useEffect, useRef, useState } from "react";
import type { PhaseUpdate } from "@/lib/api";
import { LOADING_PHASES } from "@/types/content";

// SSE phase id → 단계 인덱스 매핑
const PHASE_TO_IDX: Record<string, number> = {
  preflight:   0,
  crawl:       1,
  source_pool: 1,   // crawl과 같은 단계로 표시
  llm:         2,
  validate:    3,
  persist:     4,
};

interface Props {
  startedAt: number;
  estimatedSec?: number;
  /** 실제 SSE 이벤트 (없으면 타이머 폴백) */
  realPhase?: PhaseUpdate | null;
}

function PulseDots() {
  return (
    <span className="inline-flex items-center gap-1 ml-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-ibk-500 animate-pulse-dot"
          style={{ animationDelay: `${i * 0.16}s` }}
        />
      ))}
    </span>
  );
}

function formatElapsed(ms: number) {
  const s = Math.floor(ms / 1000);
  return s >= 60 ? `${Math.floor(s / 60)}분 ${s % 60}초` : `${s}초`;
}

export function LoadingOverlay({ startedAt, estimatedSec = 55, realPhase }: Props) {
  const [elapsed, setElapsed]           = useState(0);
  const [currentPhaseIdx, setCurrentPhaseIdx] = useState(0);
  const [displayMessage, setDisplayMessage]   = useState(LOADING_PHASES[0].message);
  const [displayIcon, setDisplayIcon]         = useState(LOADING_PHASES[0].icon);
  const [extraInfo, setExtraInfo]             = useState<string>("");
  const frameRef = useRef<number>(0);

  // 경과 시간 ticker
  useEffect(() => {
    const tick = () => {
      setElapsed(Date.now() - startedAt);
      frameRef.current = requestAnimationFrame(tick);
    };
    frameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameRef.current);
  }, [startedAt]);

  // 실제 Phase 이벤트 수신 시 업데이트
  useEffect(() => {
    if (!realPhase) return;

    const idx = PHASE_TO_IDX[realPhase.phase] ?? currentPhaseIdx;
    setCurrentPhaseIdx(Math.max(idx, currentPhaseIdx));
    setDisplayMessage(realPhase.message);
    setDisplayIcon(LOADING_PHASES[Math.min(idx, LOADING_PHASES.length - 1)].icon);

    // 크롤 단계: 수집 페이지 수 표시
    if (realPhase.crawled_pages !== undefined && realPhase.crawled_pages > 0) {
      setExtraInfo(`${realPhase.crawled_pages}개 페이지 수집됨`);
    } else {
      setExtraInfo("");
    }
  }, [realPhase]); // eslint-disable-line react-hooks/exhaustive-deps

  // SSE 없을 때 타이머 기반 폴백
  useEffect(() => {
    if (realPhase) return;
    const elapsedSec = elapsed / 1000;
    const phase = LOADING_PHASES.findLast((p) => elapsedSec >= p.startSec) ?? LOADING_PHASES[0];
    const idx   = LOADING_PHASES.findIndex((p) => p.id === phase.id);
    setCurrentPhaseIdx(idx);
    setDisplayMessage(phase.label);
    setDisplayIcon(phase.icon);
  }, [elapsed, realPhase]);

  const progress = realPhase
    ? Math.min(((currentPhaseIdx + 1) / (LOADING_PHASES.length - 1)) * 90, 95)
    : Math.min((elapsed / 1000 / estimatedSec) * 100, 97);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-white/90 backdrop-blur-sm">
      <div className="w-full max-w-md px-8 text-center">

        {/* 아이콘 + 메시지 */}
        <div key={`${currentPhaseIdx}-${displayMessage}`} className="animate-fade-in mb-8">
          <div className="text-5xl mb-4">{displayIcon}</div>
          <p className="text-xl font-medium text-gray-800 flex items-center justify-center">
            {displayMessage}
            <PulseDots />
          </p>
          {extraInfo && (
            <p className="text-sm text-ibk-600 mt-1 font-medium animate-fade-in">
              {extraInfo}
            </p>
          )}
          <p className="text-sm text-gray-400 mt-2">{formatElapsed(elapsed)} 경과</p>
        </div>

        {/* 진행 바 */}
        <div className="w-full bg-gray-100 rounded-full h-2 mb-6 overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-ibk-500 to-ibk-400
                       transition-all duration-700 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* 단계 도트 */}
        <div className="flex justify-between items-center px-1">
          {LOADING_PHASES.slice(0, -1).map((p, idx) => {
            const isDone    = idx < currentPhaseIdx;
            const isCurrent = idx === currentPhaseIdx;
            return (
              <div key={p.id} className="flex flex-col items-center gap-1">
                <div className={`w-2.5 h-2.5 rounded-full transition-all duration-300 ${
                  isDone
                    ? "bg-ibk-500"
                    : isCurrent
                      ? "bg-ibk-400 scale-125 ring-4 ring-ibk-100"
                      : "bg-gray-200"
                }`} />
                <span className={`text-[10px] hidden sm:block ${
                  isCurrent ? "text-ibk-600 font-medium" : "text-gray-400"
                }`}>{p.icon}</span>
              </div>
            );
          })}
        </div>

        <p className="text-xs text-gray-400 mt-6 leading-relaxed">
          공식 홈페이지를 분석하고 최적의 문구를 생성 중입니다.
          <br />평균 30~50초 소요됩니다.
        </p>
      </div>
    </div>
  );
}
