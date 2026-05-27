"use client";

import type { HeroSection, Source, ValidationIssue } from "@/types/content";
import { SectionWrapper } from "../SectionWrapper";

interface Props {
  section: HeroSection;
  sourceMap: Map<string, Source>;
  issues: ValidationIssue[];
}

export function HeroRenderer({ section, sourceMap, issues }: Props) {
  const copyText = [section.headline, section.subheadline, section.cta_label].join("\n");

  return (
    <SectionWrapper
      title="히어로 배너"
      icon="🎯"
      evidenceRefs={section.evidence_refs}
      sourceMap={sourceMap}
      issues={issues}
      copyText={copyText}
      sufficient={section.sufficient}
    >
      {/* 미리보기 카드 */}
      <div className="rounded-xl bg-gradient-to-br from-ibk-600 to-ibk-800
        p-8 text-white text-center space-y-3">
        <h1 className="text-2xl sm:text-3xl font-bold leading-tight">
          {section.headline}
        </h1>
        <p className="text-ibk-200 text-sm sm:text-base leading-relaxed max-w-md mx-auto">
          {section.subheadline}
        </p>
        <button
          type="button"
          className="mt-2 inline-block rounded-full bg-white text-ibk-700
            px-6 py-2.5 text-sm font-semibold shadow-md"
        >
          {section.cta_label}
        </button>
      </div>

      {/* 텍스트 상세 */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-3">
        {[
          { label: "헤드라인",    value: section.headline },
          { label: "서브 헤드라인", value: section.subheadline },
          { label: "CTA 버튼",   value: section.cta_label },
        ].map(({ label, value }) => (
          <div key={label} className="bg-gray-50 rounded-lg p-3">
            <p className="text-[10px] text-gray-400 uppercase tracking-wide mb-1">{label}</p>
            <p className="text-sm text-gray-800 leading-snug">{value}</p>
          </div>
        ))}
      </div>
    </SectionWrapper>
  );
}
