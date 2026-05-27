"use client";

/**
 * Step 3: 생성된 콘텐츠 패키지 전체 표시 컴포넌트.
 *
 * 레이아웃:
 *   1. 상단 메타 바 (evidence_level, 크롤 페이지 수, 소요 시간)
 *   2. 검증 이슈 요약 배너 (blocker / warning)
 *   3. 섹션별 카드 (hero / about / strengths / services / history / contact)
 *   4. 하단 소스 목록 (펼침/접힘)
 */

import { useMemo, useState } from "react";
import type {
  ContentPackageResponse,
  Source,
  ValidationIssue,
} from "@/types/content";

import { HeroRenderer }      from "./sections/HeroRenderer";
import { AboutRenderer }     from "./sections/AboutRenderer";
import { StrengthsRenderer } from "./sections/StrengthsRenderer";
import { ServicesRenderer }  from "./sections/ServicesRenderer";
import { HistoryRenderer }   from "./sections/HistoryRenderer";
import { ContactRenderer }   from "./sections/ContactRenderer";

interface Props {
  result: ContentPackageResponse;
  onBack: () => void;
}

// ─────────────────────────────────────────────
// 유틸
// ─────────────────────────────────────────────

function buildSourceMap(sources: Source[]): Map<string, Source> {
  return new Map(sources.map((s) => [s.source_id, s]));
}

function getIssuesForSection(
  issues: ValidationIssue[],
  prefix: string,
): ValidationIssue[] {
  return issues.filter((i) => i.section === prefix || i.section.startsWith(`${prefix}[`));
}

// ─────────────────────────────────────────────
// 서브 컴포넌트
// ─────────────────────────────────────────────

function MetaBar({ result }: { result: ContentPackageResponse }) {
  const { meta } = result;
  const crawlSec  = (meta.crawl_duration_ms / 1000).toFixed(1);
  const llmSec    = (meta.llm_duration_ms   / 1000).toFixed(1);
  const totalSec  = (meta.total_duration_ms / 1000).toFixed(1);

  return (
    <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500
      bg-gray-50 rounded-xl px-4 py-3 border border-gray-100">
      {/* evidence level */}
      <span className={`font-medium px-2 py-0.5 rounded-full text-[11px] ${
        meta.evidence_level === "input_plus_crawl"
          ? "bg-emerald-100 text-emerald-700"
          : "bg-gray-200 text-gray-600"
      }`}>
        {meta.evidence_level === "input_plus_crawl"
          ? `🕷️ 홈페이지 ${meta.crawled_pages}페이지 분석`
          : "📝 입력 정보 기반"}
      </span>

      <span className="text-gray-300">|</span>
      <span>🕷️ 크롤 {crawlSec}s</span>
      <span>🤖 LLM {llmSec}s</span>
      <span>⏱ 총 {totalSec}s</span>
      {meta.retry_count > 0 && (
        <span className="text-yellow-600">🔄 재시도 {meta.retry_count}회</span>
      )}
    </div>
  );
}

function ValidationBanner({ issues }: { issues: ValidationIssue[] }) {
  const blockers = issues.filter((i) => i.blocker);
  const warnings = issues.filter((i) => !i.blocker);

  if (issues.length === 0) {
    return (
      <div className="flex items-center gap-2 bg-emerald-50 border border-emerald-200
        rounded-xl px-4 py-3 text-sm text-emerald-700">
        ✅ 모든 검증을 통과했습니다.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {blockers.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 space-y-1">
          <p className="text-sm font-semibold text-red-700">
            🚫 수정 권장 항목 {blockers.length}개
          </p>
          {blockers.map((b, i) => (
            <p key={i} className="text-xs text-red-600">
              • [{b.section}] {b.hint}
            </p>
          ))}
        </div>
      )}
      {warnings.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl px-4 py-3 space-y-1">
          <p className="text-sm font-semibold text-yellow-800">
            ⚠️ 검토 권장 항목 {warnings.length}개
          </p>
          {warnings.map((w, i) => (
            <p key={i} className="text-xs text-yellow-700">
              • [{w.section}] {w.hint}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

function SourcesList({ sources }: { sources: Source[] }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-xl border border-gray-100 overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-5 py-4
          bg-gray-50 hover:bg-gray-100 transition-colors text-sm font-medium text-gray-600"
      >
        <span>📎 근거 소스 목록 ({sources.length}개)</span>
        <span className="text-gray-400">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="divide-y divide-gray-50">
          {sources.map((src) => (
            <div key={src.source_id} className="px-5 py-3 flex items-start gap-3">
              <span className={`text-[10px] px-2 py-0.5 rounded-full shrink-0 mt-0.5 font-semibold ${
                src.source_type === "input"
                  ? "bg-blue-100 text-blue-700"
                  : "bg-emerald-100 text-emerald-700"
              }`}>
                {src.source_type === "input" ? "입력" : src.page_type ?? "크롤"}
              </span>
              <div className="min-w-0">
                <p className="text-xs font-mono text-gray-400">{src.source_id}</p>
                <p className="text-xs text-gray-500 truncate">{src.origin}</p>
                <p className="text-xs text-gray-700 mt-0.5 line-clamp-2 leading-relaxed">
                  {src.text.slice(0, 120)}{src.text.length > 120 ? "…" : ""}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────
// 메인
// ─────────────────────────────────────────────

export function ResultsView({ result, onBack }: Props) {
  const { package: pkg, sources, validation } = result;
  const { sections } = pkg;

  const sourceMap = useMemo(() => buildSourceMap(sources), [sources]);
  const allIssues = useMemo(
    () => [...validation.blockers, ...validation.warnings],
    [validation],
  );

  const [copied, setCopied] = useState(false);
  const handleCopyAll = () => {
    const texts = [
      `[히어로]\n${sections.hero.headline}\n${sections.hero.subheadline}`,
      `[회사소개]\n${sections.about.body}`,
      sections.strengths.map((s, i) => `[강점 ${i+1}]\n${s.title}: ${s.description}`).join("\n"),
      sections.services?.map((s) => `[서비스]\n${s.name}: ${s.description}`).join("\n") ?? "",
      sections.history?.map((h) => `${h.year} ${h.event}`).join("\n") ?? "",
      sections.contact
        ? `[연락처]\n${[sections.contact.address, sections.contact.phone, sections.contact.email].filter(Boolean).join(" / ")}`
        : "",
    ].filter(Boolean).join("\n\n");

    navigator.clipboard.writeText(texts).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={onBack}
          className="text-sm text-gray-500 hover:text-ibk-600 flex items-center gap-1
            transition-colors"
        >
          ← 다시 입력
        </button>

        <button
          type="button"
          onClick={handleCopyAll}
          className="text-sm text-ibk-600 hover:text-ibk-800 font-medium
            flex items-center gap-1 transition-colors"
        >
          {copied ? "✅ 전체 복사됨" : "📋 전체 복사"}
        </button>
      </div>

      {/* 메타 정보 */}
      <MetaBar result={result} />

      {/* 검증 배너 */}
      <ValidationBanner issues={allIssues} />

      {/* 섹션 카드들 */}
      <div className="space-y-4">
        {/* Hero */}
        <HeroRenderer
          section={sections.hero}
          sourceMap={sourceMap}
          issues={getIssuesForSection(allIssues, "hero")}
        />

        {/* About */}
        <AboutRenderer
          section={sections.about}
          sourceMap={sourceMap}
          issues={getIssuesForSection(allIssues, "about")}
        />

        {/* Strengths */}
        <StrengthsRenderer
          items={sections.strengths}
          sourceMap={sourceMap}
          issues={getIssuesForSection(allIssues, "strengths")}
        />

        {/* Services (optional) */}
        {sections.services && sections.services.length > 0 && (
          <ServicesRenderer
            items={sections.services}
            sourceMap={sourceMap}
            issues={getIssuesForSection(allIssues, "services")}
          />
        )}

        {/* History (optional) */}
        {sections.history && sections.history.length > 0 && (
          <HistoryRenderer
            items={sections.history}
            sourceMap={sourceMap}
            issues={getIssuesForSection(allIssues, "history")}
          />
        )}

        {/* Contact (optional) */}
        {sections.contact && (
          <ContactRenderer
            section={sections.contact}
            sourceMap={sourceMap}
            issues={getIssuesForSection(allIssues, "contact")}
          />
        )}
      </div>

      {/* 소스 목록 (접힘) */}
      <SourcesList sources={sources} />
    </div>
  );
}
