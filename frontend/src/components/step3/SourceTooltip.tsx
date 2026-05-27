"use client";

/**
 * 출처 뱃지 + 호버 툴팁 컴포넌트.
 *
 * 섹션 우측 하단에 "📎 근거 N개" 뱃지를 표시하고,
 * 호버 시 Source 상세 정보를 띄운다.
 *
 * 표시 정보:
 *   - type=input: "직접 입력 — /company_name" 등
 *   - type=crawl: "회사소개 페이지 — https://example.co.kr/about"
 *   - 본문 미리보기 (50자)
 */

import { useEffect, useRef, useState } from "react";
import type { Source } from "@/types/content";
import { PAGE_TYPE_LABELS } from "@/types/content";

interface Props {
  refs: string[];       // evidence_refs (source_id 목록)
  sourceMap: Map<string, Source>;
}

function SourceCard({ source }: { source: Source }) {
  const isInput = source.source_type === "input";
  const preview = source.text.length > 80
    ? source.text.slice(0, 80) + "…"
    : source.text;

  const originLabel = isInput
    ? `직접 입력 — ${source.origin}`
    : `${PAGE_TYPE_LABELS[source.page_type ?? "other"] ?? "홈페이지"} — ${new URL(source.origin).hostname}`;

  return (
    <div className="p-3 rounded-lg bg-white shadow-md border border-gray-100
      w-72 text-left animate-fade-in">
      <div className="flex items-center gap-2 mb-2">
        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
          isInput
            ? "bg-blue-100 text-blue-700"
            : "bg-emerald-100 text-emerald-700"
        }`}>
          {isInput ? "직접 입력" : "홈페이지"}
        </span>
        <span className="text-[10px] text-gray-400 font-mono">{source.source_id}</span>
      </div>
      <p className="text-xs font-medium text-gray-700 mb-1 truncate">{originLabel}</p>
      <p className="text-xs text-gray-500 leading-relaxed">{preview}</p>
    </div>
  );
}

export function SourceTooltip({ refs, sourceMap }: Props) {
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const timeoutRef   = useRef<ReturnType<typeof setTimeout>>();

  const sources = refs
    .map((id) => sourceMap.get(id))
    .filter((s): s is Source => s !== undefined);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  if (sources.length === 0) return null;

  const handleMouseEnter = () => {
    clearTimeout(timeoutRef.current);
    setOpen(true);
  };
  const handleMouseLeave = () => {
    timeoutRef.current = setTimeout(() => setOpen(false), 200);
  };

  return (
    <div
      ref={containerRef}
      className="relative inline-block"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {/* 뱃지 버튼 */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1 text-[11px] text-gray-400
          hover:text-ibk-600 transition-colors py-0.5 px-1.5 rounded
          hover:bg-ibk-50 select-none"
      >
        <span>📎</span>
        <span>근거 {sources.length}개</span>
      </button>

      {/* 툴팁 패널 */}
      {open && (
        <div className="absolute bottom-full right-0 mb-2 z-30">
          {/* 탭 (여러 소스일 때) */}
          {sources.length > 1 && (
            <div className="flex gap-1 mb-1 justify-end">
              {sources.map((_, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => setActiveIdx(i)}
                  className={`w-2 h-2 rounded-full transition-all ${
                    i === activeIdx ? "bg-ibk-500 scale-125" : "bg-gray-300"
                  }`}
                />
              ))}
            </div>
          )}
          <SourceCard source={sources[activeIdx] ?? sources[0]} />
        </div>
      )}
    </div>
  );
}
