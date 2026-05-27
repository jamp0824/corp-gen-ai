"use client";

/**
 * Step 2 전체 폼 컴포넌트.
 *
 * 필드:
 *   - company_name     (필수)
 *   - industry         (필수)
 *   - business_type    (필수)
 *   - main_business_description (필수, textarea)
 *   - official_url     (필수, UrlInput 컴포넌트)
 *   - homepage_type    (선택, 기본 general)
 *   - tone             (선택, 기본 professional)
 *
 * 제출 시 onSubmit() 호출.
 * 로딩 중에는 모든 필드 + 버튼 비활성화.
 */

import { useCallback, useState } from "react";
import type { EnrichmentRequest, HomepageType, Tone } from "@/types/content";
import { UrlInput } from "./UrlInput";

interface Props {
  onSubmit: (data: EnrichmentRequest) => void;
  isLoading: boolean;
}

interface FormErrors {
  company_name?: string;
  industry?: string;
  business_type?: string;
  main_business_description?: string;
  official_url?: string;
}

const HOMEPAGE_TYPE_OPTIONS: { value: HomepageType; label: string }[] = [
  { value: "general",       label: "일반 기업" },
  { value: "startup",       label: "스타트업 / 벤처" },
  { value: "manufacturing", label: "제조업" },
  { value: "finance",       label: "금융" },
  { value: "medical",       label: "의료 / 바이오" },
  { value: "education",     label: "교육" },
  { value: "retail",        label: "유통 / 커머스" },
];

const TONE_OPTIONS: { value: Tone; label: string; desc: string }[] = [
  { value: "professional", label: "전문적",  desc: "권위 있고 신뢰감 있는 문체" },
  { value: "friendly",     label: "친근한",  desc: "편안하고 접근하기 쉬운 문체" },
  { value: "formal",       label: "격식체",  desc: "공식적이고 정중한 문체" },
  { value: "dynamic",      label: "역동적",  desc: "활기차고 에너지 넘치는 문체" },
];

// 간단한 필드 유효성 검사
function validate(
  data: Omit<EnrichmentRequest, "homepage_type" | "tone">,
  urlValid: boolean,
): FormErrors {
  const errs: FormErrors = {};
  if (!data.company_name.trim()) errs.company_name = "회사명을 입력해주세요.";
  if (!data.industry.trim())     errs.industry     = "업종을 입력해주세요.";
  if (!data.business_type.trim()) errs.business_type = "업태를 입력해주세요.";
  if (data.main_business_description.trim().length < 10)
    errs.main_business_description = "주요 사업 내용을 10자 이상 입력해주세요.";
  if (!urlValid)                 errs.official_url = "올바른 URL을 입력해주세요.";
  return errs;
}

// 재사용 가능한 텍스트 필드
function Field({
  label,
  required,
  error,
  children,
}: {
  label: string;
  required?: boolean;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium text-gray-700">
        {label}
        {required && <span className="ml-1 text-ibk-500">*</span>}
      </label>
      {children}
      {error && (
        <p className="text-xs text-red-500 animate-fade-in">{error}</p>
      )}
    </div>
  );
}

function TextInput({
  value,
  onChange,
  placeholder,
  disabled,
  hasError,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  disabled?: boolean;
  hasError?: boolean;
}) {
  return (
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      disabled={disabled}
      className={`w-full rounded-lg border px-4 py-3 text-sm
        placeholder:text-gray-300 outline-none transition-all
        focus:ring-2 focus:ring-offset-0 disabled:bg-gray-50 disabled:text-gray-400
        ${hasError
          ? "border-red-400 focus:ring-red-200 bg-red-50"
          : "border-gray-200 focus:ring-ibk-200 focus:border-ibk-400"
        }`}
    />
  );
}

export function EnrichmentForm({ onSubmit, isLoading }: Props) {
  const [companyName, setCompanyName]     = useState("");
  const [industry, setIndustry]           = useState("");
  const [businessType, setBusinessType]   = useState("");
  const [mainDesc, setMainDesc]           = useState("");
  const [officialUrl, setOfficialUrl]     = useState("");
  const [urlValid, setUrlValid]           = useState(false);
  const [homepageType, setHomepageType]   = useState<HomepageType>("general");
  const [tone, setTone]                   = useState<Tone>("professional");
  const [errors, setErrors]               = useState<FormErrors>({});
  const [submitted, setSubmitted]         = useState(false);

  const handleUrlChange = useCallback((v: string) => setOfficialUrl(v), []);
  const handleUrlValidChange = useCallback((v: boolean) => setUrlValid(v), []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);

    const errs = validate(
      { company_name: companyName, industry, business_type: businessType,
        main_business_description: mainDesc, official_url: officialUrl },
      urlValid,
    );
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;

    onSubmit({
      company_name: companyName.trim(),
      industry: industry.trim(),
      business_type: businessType.trim(),
      main_business_description: mainDesc.trim(),
      official_url: officialUrl.trim(),
      homepage_type: homepageType,
      tone,
    });
  };

  const disabled = isLoading;
  const showErr = (field: keyof FormErrors) =>
    submitted ? errors[field] : undefined;

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-6">

      {/* 기본 정보 */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
          기본 정보
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label="회사명" required error={showErr("company_name")}>
            <TextInput
              value={companyName}
              onChange={setCompanyName}
              placeholder="예: 해피팜"
              disabled={disabled}
              hasError={!!showErr("company_name")}
            />
          </Field>

          <Field label="업종" required error={showErr("industry")}>
            <TextInput
              value={industry}
              onChange={setIndustry}
              placeholder="예: IT·소프트웨어"
              disabled={disabled}
              hasError={!!showErr("industry")}
            />
          </Field>
        </div>

        <Field label="업태" required error={showErr("business_type")}>
          <TextInput
            value={businessType}
            onChange={setBusinessType}
            placeholder="예: 솔루션 개발 및 공급"
            disabled={disabled}
            hasError={!!showErr("business_type")}
          />
        </Field>

        <Field label="주요 사업 내용" required error={showErr("main_business_description")}>
          <textarea
            value={mainDesc}
            onChange={(e) => setMainDesc(e.target.value)}
            placeholder="주요 제품/서비스, 고객사, 특장점 등을 자유롭게 입력해주세요.&#10;예: AI 기반 재고관리 솔루션을 개발하고 농산물 도매업체에 공급합니다."
            rows={4}
            disabled={disabled}
            className={`w-full rounded-lg border px-4 py-3 text-sm resize-none
              placeholder:text-gray-300 outline-none transition-all
              focus:ring-2 focus:ring-offset-0 disabled:bg-gray-50 disabled:text-gray-400
              ${submitted && errors.main_business_description
                ? "border-red-400 focus:ring-red-200 bg-red-50"
                : "border-gray-200 focus:ring-ibk-200 focus:border-ibk-400"
              }`}
          />
          <p className="text-xs text-gray-400 text-right">{mainDesc.length}/1000</p>
        </Field>
      </div>

      {/* 홈페이지 URL */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
          홈페이지 URL
        </h3>
        <UrlInput
          value={officialUrl}
          onChange={handleUrlChange}
          onValidChange={handleUrlValidChange}
          disabled={disabled}
        />
        {submitted && errors.official_url && (
          <p className="text-xs text-red-500 -mt-2">{errors.official_url}</p>
        )}
      </div>

      {/* 스타일 설정 */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
          스타일 설정 <span className="text-gray-400 font-normal normal-case">(선택)</span>
        </h3>

        {/* 홈페이지 유형 */}
        <Field label="홈페이지 유형">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {HOMEPAGE_TYPE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                disabled={disabled}
                onClick={() => setHomepageType(opt.value)}
                className={`rounded-lg border px-3 py-2 text-sm font-medium transition-all
                  ${homepageType === opt.value
                    ? "border-ibk-500 bg-ibk-50 text-ibk-700"
                    : "border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-50"
                  } disabled:opacity-50`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </Field>

        {/* 톤 */}
        <Field label="문체 톤">
          <div className="grid grid-cols-2 gap-2">
            {TONE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                disabled={disabled}
                onClick={() => setTone(opt.value)}
                className={`rounded-lg border px-4 py-3 text-left transition-all
                  ${tone === opt.value
                    ? "border-ibk-500 bg-ibk-50"
                    : "border-gray-200 hover:border-gray-300 hover:bg-gray-50"
                  } disabled:opacity-50`}
              >
                <span className={`block text-sm font-medium ${
                  tone === opt.value ? "text-ibk-700" : "text-gray-700"
                }`}>
                  {opt.label}
                </span>
                <span className="block text-xs text-gray-400 mt-0.5">
                  {opt.desc}
                </span>
              </button>
            ))}
          </div>
        </Field>
      </div>

      {/* 제출 버튼 */}
      <button
        type="submit"
        disabled={disabled}
        className="w-full rounded-xl bg-ibk-600 px-6 py-4 text-white font-semibold
          text-base transition-all hover:bg-ibk-700 active:scale-[0.98]
          disabled:bg-gray-300 disabled:cursor-not-allowed
          focus:outline-none focus:ring-2 focus:ring-ibk-400 focus:ring-offset-2"
      >
        {isLoading ? (
          <span className="flex items-center justify-center gap-2">
            <span className="w-4 h-4 border-2 border-white/40 border-t-white
              rounded-full animate-spin" />
            콘텐츠 생성 중…
          </span>
        ) : (
          "✨ AI 콘텐츠 생성 시작"
        )}
      </button>

      <p className="text-center text-xs text-gray-400">
        공식 홈페이지를 분석해 홈페이지 콘텐츠를 자동 생성합니다.
        30~60초 소요됩니다.
      </p>
    </form>
  );
}
