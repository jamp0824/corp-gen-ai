"use client";

import type { AboutSection, Source, ValidationIssue } from "@/types/content";
import { SectionWrapper } from "../SectionWrapper";

interface Props {
  section: AboutSection;
  sourceMap: Map<string, Source>;
  issues: ValidationIssue[];
}

export function AboutRenderer({ section, sourceMap, issues }: Props) {
  return (
    <SectionWrapper
      title="회사소개"
      icon="🏢"
      evidenceRefs={section.evidence_refs}
      sourceMap={sourceMap}
      issues={issues}
      copyText={`${section.title}\n\n${section.body}`}
      sufficient={section.sufficient}
    >
      <div className="space-y-2">
        <h4 className="font-semibold text-gray-800">{section.title}</h4>
        <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-line">
          {section.body}
        </p>
      </div>
    </SectionWrapper>
  );
}
