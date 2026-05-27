"use client";

import type { Source, StrengthItem, ValidationIssue } from "@/types/content";
import { SectionWrapper } from "../SectionWrapper";
import { SourceTooltip } from "../SourceTooltip";

interface Props {
  items: StrengthItem[];
  sourceMap: Map<string, Source>;
  issues: ValidationIssue[];
}

const STRENGTH_ICONS = ["⚡", "🎯", "🛡️", "🔧", "🌟", "🤝"];

export function StrengthsRenderer({ items, sourceMap, issues }: Props) {
  const sectionIssues = issues.filter((i) => i.section.startsWith("strengths"));
  const copyText = items
    .map((s, i) => `강점 ${i + 1}: ${s.title}\n${s.description}`)
    .join("\n\n");

  return (
    <SectionWrapper
      title="핵심 강점"
      icon="⚡"
      sourceMap={sourceMap}
      issues={sectionIssues.filter((i) => !i.section.includes("["))}
      copyText={copyText}
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {items.map((item, idx) => {
          const itemIssues = sectionIssues.filter((i) => i.section === `strengths[${idx}]`);
          const hasIssue = itemIssues.length > 0;

          return (
            <div
              key={idx}
              className={`rounded-xl p-4 space-y-2 border transition-all
                ${hasIssue
                  ? itemIssues.some((i) => i.blocker)
                    ? "border-red-200 bg-red-50"
                    : "border-yellow-200 bg-yellow-50"
                  : "border-gray-100 bg-gray-50/70"
                }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-xl">{STRENGTH_ICONS[idx % STRENGTH_ICONS.length]}</span>
                  <h5 className="text-sm font-semibold text-gray-800">{item.title}</h5>
                </div>
                <SourceTooltip refs={item.evidence_refs} sourceMap={sourceMap} />
              </div>
              <p className="text-xs text-gray-600 leading-relaxed">{item.description}</p>
            </div>
          );
        })}
      </div>
    </SectionWrapper>
  );
}
