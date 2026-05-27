"use client";

import type { HistoryItem, Source, ValidationIssue } from "@/types/content";
import { SectionWrapper } from "../SectionWrapper";
import { SourceTooltip } from "../SourceTooltip";

interface Props {
  items: HistoryItem[];
  sourceMap: Map<string, Source>;
  issues: ValidationIssue[];
}

export function HistoryRenderer({ items, sourceMap, issues }: Props) {
  const sorted = [...items].sort((a, b) => a.year - b.year);
  const copyText = sorted.map((h) => `${h.year}  ${h.event}`).join("\n");

  return (
    <SectionWrapper
      title="연혁"
      icon="📅"
      sourceMap={sourceMap}
      issues={issues}
      copyText={copyText}
    >
      <ol className="relative border-l-2 border-ibk-100 space-y-4 ml-2">
        {sorted.map((item, idx) => (
          <li key={idx} className="pl-5 relative">
            {/* 타임라인 점 */}
            <span className="absolute -left-[9px] top-1 w-4 h-4 rounded-full
              bg-ibk-500 border-2 border-white shadow-sm" />

            <div className="flex items-start justify-between gap-2">
              <div>
                <span className="text-xs font-bold text-ibk-600">{item.year}</span>
                <p className="text-sm text-gray-700 mt-0.5 leading-snug">{item.event}</p>
              </div>
              <SourceTooltip refs={item.evidence_refs} sourceMap={sourceMap} />
            </div>
          </li>
        ))}
      </ol>
    </SectionWrapper>
  );
}
