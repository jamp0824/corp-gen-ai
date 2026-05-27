"use client";

/**
 * 크롤링 + LLM 처리 중 보여주는 전체화면 로딩 오버레이.
 *
 * - 타이머 기반 단계별 메시지 (0~3s / 3~22s / 22~46s / 46~56s / 56s~)
 * - 실제 Phase 기준 더미 메시지이므로 SSE 없이도 자연스럽게 동작
 * - 경과 시간 표시 + 진행 바
 */

import { useEffect, useRef, useState } from "react";
import { LOADING_PHASES, type LoadingPhase } from "@/types/content";

interface Props {
  /** 요청 시작 시각 (Date.now()) */
  startedAt: number;
  /** 예상 최대 완료 시간(초) — 진행 바 계산에 사용 */
  estimatedSec?: number;
}

function getPhase(elapsedSec: number): LoadingPhase {
  // 경과 시간에 맞는 단계 찾기 (마지막 단계까지 fallback)
  return (
    LOADING_PHASES.findLast((p) => elapsedSec >= p.startSec) ??
    LOADING_PHASES[0]
  );
}

function formatElapsed(ms: number): string {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  if (m > 0) return `${m}분 ${s % 60}초`;
  return `${s}초`;
}

// 3개의 점이 순차적으로 커지는 애니메이션
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

export function LoadingOverlay({ startedAt, estimatedSec = 55 }: Props) {
  const [elapsed, setElapsed] = useState(0);
  const frameRef = useRef<number>(0);

  useEffect(() => {
    const tick = () => {
      setElapsed(Date.now() - startedAt);
      frameRef.current = requestAnimationFrame(tick);
    };
    frameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameRef.current);
  }, [startedAt]);

  const elapsedSec = elapsed / 1000;
  const phase = getPhase(elapsedSec);
  const progress = Math.min((elapsedSec / estimatedSec) * 100, 97); // 97%까지만 (완료 전 100% 방지)

  // 완료된 단계 인덱스
  const currentPhaseIdx = LOADING_PHASES.findIndex((p) => p.id === phase.id);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-white/90 backdrop-blur-sm">
      <div className="w-full max-w-md px-8 text-center">

        {/* 아이콘 + 메시지 */}
        <div
          key={phase.id}
          className="animate-fade-in mb-8"
        >
          <div className="text-5xl mb-4">{phase.icon}</div>
          <p className="text-xl font-medium text-gray-800 flex items-center justify-center">
            {phase.label}
            <PulseDots />
          </p>
          <p className="text-sm text-gray-400 mt-2">
            {formatElapsed(elapsed)} 경과
          </p>
        </div>

        {/* 진행 바 */}
        <div className="w-full bg-gray-100 rounded-full h-2 mb-6 overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-ibk-500 to-ibk-400
                       transition-all duration-500 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* 단계 표시기 */}
        <div className="flex justify-between items-center px-1">
          {LOADING_PHASES.slice(0, -1).map((p, idx) => {
            const isDone    = idx < currentPhaseIdx;
            const isCurrent = idx === currentPhaseIdx;
            return (
              <div key={p.id} className="flex flex-col items-center gap-1">
                <div
                  className={`w-2.5 h-2.5 rounded-full transition-all duration-300 ${
                    isDone
                      ? "bg-ibk-500 scale-100"
                      : isCurrent
                        ? "bg-ibk-400 scale-125 ring-4 ring-ibk-100"
                        : "bg-gray-200"
                  }`}
                />
                <span className={`text-[10px] hidden sm:block ${
                  isCurrent ? "text-ibk-600 font-medium" : "text-gray-400"
                }`}>
                  {p.icon}
                </span>
              </div>
            );
          })}
        </div>

        {/* 안내 문구 */}
        <p className="text-xs text-gray-400 mt-6 leading-relaxed">
          공식 홈페이지를 분석하고 최적의 문구를 생성 중입니다.
          <br />
          평균 30~50초 소요됩니다.
        </p>
      </div>
    </div>
  );
}
