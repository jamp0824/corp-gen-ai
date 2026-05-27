"use client";

/**
 * 섹션 공통 래퍼.
 * - 섹션 제목 + 복사 버튼 + 출처 툴팁 + 검증 경고 배지를 일관되게 렌더링
 * - children이 실제 섹션 콘텐츠
 */

import { useState } from "react";
import type { Source, ValidationIssue } from "@/types/content";
import { SourceTooltip } from "./SourceTooltip";

interface Props {
  title: string;
  icon?: string;
  evidenceRefs?: string[];
  sourceMap: Map<string, Source>;
  issues?: ValidationIssue[];
  copyText?: string;     // 클립보드 복사 시 사용할 텍스트
  sufficient?: boolean;
  children: React.ReactNode;
}

function IssueBadge({ issue }: { issue: ValidationIssue }) {
  const isBlocker = issue.blocker;
  return (
    <span
      title={issue.hint}
      className={`inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5
        rounded-full cursor-help ${
        isBlocker
          ? "bg-red-100 text-red-600"
          : "bg-yellow-100 text-yellow-700"
      }`}
    >
      {isBlocker ? "🚫" : "⚠️"}
      {issue.code === "FORBIDDEN_EXPRESSION"    && "금지 표현"}
      {issue.code === "MISSING_EVIDENCE_REF"    && "근거 누락"}
      {issue.code === "VERBATIM_COPY_FROM_CRAWL" && "복붙 의심"}
      {issue.code === "INSUFFICIENT_SECTION"    && "정보 부족"}
      {issue.code === "HALLUCINATION_RISK"      && "수치 확인 필요"}
    </span>
  );
}

export function SectionWrapper({
  title, icon, evidenceRefs = [], sourceMap,
  issues = [], copyText, sufficient = true, children,
}: Props) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!copyText) return;
    navigator.clipboard.writeText(copyText).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  const hasIssues = issues.length > 0;

  return (
    <div className={`rounded-2xl border bg-white p-6 space-y-4 transition-all
      ${hasIssues
        ? issues.some((i) => i.blocker)
          ? "border-red-200 bg-red-50/30"
          : "border-yellow-200 bg-yellow-50/30"
        : "border-gray-100 hover:border-ibk-200 hover:shadow-sm"
      }`}
    >
      {/* 헤더 */}
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-1.5">
          {icon && <span>{icon}</span>}
          {title}
          {!sufficient && (
            <span className="text-[10px] text-gray-400 font-normal">(정보 보완 가능)</span>
          )}
        </h3>

        <div className="flex items-center gap-2 shrink-0">
          {/* 검증 이슈 배지 */}
          {issues.map((issue, i) => <IssueBadge key={i} issue={issue} />)}

          {/* 출처 툴팁 */}
          {evidenceRefs.length > 0 && (
            <SourceTooltip refs={evidenceRefs} sourceMap={sourceMap} />
          )}

          {/* 복사 버튼 */}
          {copyText && (
            <button
              type="button"
              onClick={handleCopy}
              className="text-[11px] text-gray-400 hover:text-ibk-600
                transition-colors px-1.5 py-0.5 rounded hover:bg-ibk-50"
            >
              {copied ? "✅ 복사됨" : "📋 복사"}
            </button>
          )}
        </div>
      </div>

      {/* 콘텐츠 */}
      <div className="animate-slide-up">{children}</div>
    </div>
  );
}
