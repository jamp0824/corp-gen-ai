"use client";

import type { ServiceItem, Source, ValidationIssue } from "@/types/content";
import { SectionWrapper } from "../SectionWrapper";
import { SourceTooltip } from "../SourceTooltip";

interface Props {
  items: ServiceItem[];
  sourceMap: Map<string, Source>;
  issues: ValidationIssue[];
}

const SERVICE_COLORS = [
  "from-blue-50 to-indigo-50 border-blue-100",
  "from-emerald-50 to-teal-50 border-emerald-100",
  "from-violet-50 to-purple-50 border-violet-100",
  "from-orange-50 to-amber-50 border-orange-100",
  "from-pink-50 to-rose-50 border-pink-100",
];

export function ServicesRenderer({ items, sourceMap, issues }: Props) {
  const copyText = items.map((s) => `${s.name}\n${s.description}`).join("\n\n");

  return (
    <SectionWrapper
      title="서비스 / 제품"
      icon="🛠️"
      sourceMap={sourceMap}
      issues={issues.filter((i) => !i.section.includes("["))}
      copyText={copyText}
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {items.map((item, idx) => {
          const itemIssues = issues.filter((i) => i.section === `services[${idx}]`);
          return (
            <div
              key={idx}
              className={`rounded-xl border bg-gradient-to-br p-4 space-y-2
                ${SERVICE_COLORS[idx % SERVICE_COLORS.length]}`}
            >
              <div className="flex items-start justify-between gap-1">
                <h5 className="text-sm font-semibold text-gray-800">{item.name}</h5>
                <SourceTooltip refs={item.evidence_refs} sourceMap={sourceMap} />
              </div>
              <p className="text-xs text-gray-600 leading-relaxed">{item.description}</p>
              {itemIssues.length > 0 && (
                <p className="text-[10px] text-yellow-600">
                  ⚠️ {itemIssues[0].hint}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </SectionWrapper>
  );
}
