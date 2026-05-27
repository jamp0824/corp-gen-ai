"use client";

import type { ContactSection, Source, ValidationIssue } from "@/types/content";
import { SectionWrapper } from "../SectionWrapper";

interface Props {
  section: ContactSection;
  sourceMap: Map<string, Source>;
  issues: ValidationIssue[];
}

export function ContactRenderer({ section, sourceMap, issues }: Props) {
  const lines = [section.address, section.phone, section.email].filter(Boolean);
  const copyText = lines.join("\n");

  return (
    <SectionWrapper
      title="연락처"
      icon="📞"
      evidenceRefs={section.evidence_refs}
      sourceMap={sourceMap}
      issues={issues}
      copyText={copyText}
      sufficient={section.sufficient}
    >
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {section.address && (
          <ContactItem icon="📍" label="주소" value={section.address} />
        )}
        {section.phone && (
          <ContactItem icon="📞" label="전화" value={section.phone} href={`tel:${section.phone}`} />
        )}
        {section.email && (
          <ContactItem icon="✉️" label="이메일" value={section.email} href={`mailto:${section.email}`} />
        )}
      </div>
    </SectionWrapper>
  );
}

function ContactItem({ icon, label, value, href }: {
  icon: string; label: string; value: string; href?: string;
}) {
  return (
    <div className="bg-gray-50 rounded-xl p-4 space-y-1">
      <p className="text-[10px] text-gray-400 uppercase tracking-wide">{icon} {label}</p>
      {href ? (
        <a href={href} className="text-sm text-ibk-600 hover:underline break-all">
          {value}
        </a>
      ) : (
        <p className="text-sm text-gray-700 leading-snug">{value}</p>
      )}
    </div>
  );
}
