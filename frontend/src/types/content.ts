/**
 * 백엔드 Pydantic 모델과 1:1 대응하는 TypeScript 타입.
 * app/models/schemas.py, app/models/content_package.py 참조.
 */

// ─────────────────────────────────────────────
// 요청
// ─────────────────────────────────────────────

export type HomepageType =
  | "general"
  | "startup"
  | "manufacturing"
  | "finance"
  | "medical"
  | "education"
  | "retail";

export type Tone = "professional" | "friendly" | "formal" | "dynamic";

export interface EnrichmentRequest {
  company_name: string;
  industry: string;
  business_type: string;
  main_business_description: string;
  official_url: string;
  homepage_type: HomepageType;
  tone: Tone;
}

// ─────────────────────────────────────────────
// 소스 (근거)
// ─────────────────────────────────────────────

export type SourceType = "input" | "crawl";

export interface Source {
  source_id: string;          // "src_001"
  source_type: SourceType;
  origin: string;             // input: JSON Pointer, crawl: URL
  page_type: string | null;   // crawl: about/service/…
  text: string;               // 소스 내용 (미리보기용)
  confidence: number;
}

// ─────────────────────────────────────────────
// 콘텐츠 패키지 섹션
// ─────────────────────────────────────────────

export interface HeroSection {
  headline: string;
  subheadline: string;
  cta_label: string;
  evidence_refs: string[];
  sufficient: boolean;
}

export interface AboutSection {
  title: string;
  body: string;
  evidence_refs: string[];
  sufficient: boolean;
}

export interface StrengthItem {
  title: string;
  description: string;
  evidence_refs: string[];
  sufficient: boolean;
}

export interface ServiceItem {
  name: string;
  description: string;
  evidence_refs: string[];
  sufficient: boolean;
}

export interface HistoryItem {
  year: number;
  event: string;
  evidence_refs: string[];
}

export interface ContactSection {
  address: string | null;
  phone: string | null;
  email: string | null;
  evidence_refs: string[];
  sufficient: boolean;
}

export interface ContentSections {
  hero: HeroSection;
  about: AboutSection;
  strengths: StrengthItem[];
  services: ServiceItem[] | null;
  history: HistoryItem[] | null;
  contact: ContactSection | null;
}

export type EvidenceLevel = "input_plus_crawl" | "input_only";

export interface ContentMeta {
  evidence_level: EvidenceLevel;
  warnings: string[];
}

export interface ContentPackage {
  sections: ContentSections;
  meta: ContentMeta;
}

// ─────────────────────────────────────────────
// 검증 결과
// ─────────────────────────────────────────────

export type ValidationCode =
  | "FORBIDDEN_EXPRESSION"
  | "MISSING_EVIDENCE_REF"
  | "VERBATIM_COPY_FROM_CRAWL"
  | "INSUFFICIENT_SECTION"
  | "HALLUCINATION_RISK";

export interface ValidationIssue {
  section: string;
  code: ValidationCode;
  hint: string;
  blocker: boolean;
}

export interface ValidationResult {
  blockers: ValidationIssue[];
  warnings: ValidationIssue[];
}

// ─────────────────────────────────────────────
// API 응답
// ─────────────────────────────────────────────

export interface EnrichmentMeta {
  evidence_level: EvidenceLevel;
  crawled_pages: number;
  crawl_duration_ms: number;
  llm_duration_ms: number;
  total_duration_ms: number;
  retry_count: number;
}

export interface ContentPackageResponse {
  company_id: string;
  package: ContentPackage;
  sources: Source[];
  validation: ValidationResult;
  meta: EnrichmentMeta;
}

// ─────────────────────────────────────────────
// 에러 응답
// ─────────────────────────────────────────────

export interface ApiError {
  code: string;
  message: string;
}

// ─────────────────────────────────────────────
// UI 전용 타입
// ─────────────────────────────────────────────

/** 로딩 단계 메시지 */
export interface LoadingPhase {
  id: string;
  label: string;
  startSec: number;   // 이 메시지를 표시할 경과 시간(초)
  endSec: number;
  icon: string;       // 이모지
}

export const LOADING_PHASES: LoadingPhase[] = [
  { id: "preflight", label: "공식 홈페이지를 확인하고 있어요...",   startSec: 0,  endSec: 3,  icon: "🔍" },
  { id: "crawl",     label: "페이지 내용을 수집하고 있어요...",      startSec: 3,  endSec: 22, icon: "🕷️" },
  { id: "analyze",   label: "홈페이지 문구를 작성하고 있어요...",    startSec: 22, endSec: 46, icon: "✍️" },
  { id: "validate",  label: "근거를 다시 확인하고 있어요...",        startSec: 46, endSec: 56, icon: "✅" },
  { id: "done",      label: "거의 다 됐어요...",                    startSec: 56, endSec: 99, icon: "🎉" },
];

/** 섹션 이름 → 표시 레이블 */
export const SECTION_LABELS: Record<string, string> = {
  hero:      "히어로 배너",
  about:     "회사소개",
  strengths: "핵심 강점",
  services:  "서비스/제품",
  history:   "연혁",
  contact:   "연락처",
};

/** page_type → 한국어 레이블 */
export const PAGE_TYPE_LABELS: Record<string, string> = {
  about:     "회사소개 페이지",
  service:   "서비스 페이지",
  portfolio: "포트폴리오 페이지",
  history:   "연혁 페이지",
  contact:   "문의 페이지",
  other:     "홈페이지",
};
