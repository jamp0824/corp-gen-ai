"use client";

/**
 * URL 입력 필드 — 인라인 실시간 유효성 검사 포함.
 *
 * 검사 항목:
 * 1. http:// 또는 https:// 로 시작하는지
 * 2. 도메인 형식 (최소 점 1개)
 * 3. 차단 도메인 (SNS/블로그 플랫폼) 경고
 */

import { useEffect, useState } from "react";

interface Props {
  value: string;
  onChange: (v: string) => void;
  onValidChange?: (valid: boolean) => void;
  disabled?: boolean;
}

const BLOCKED_HINTS: Record<string, string> = {
  "naver.com":      "블로그·카페가 아닌 기업 공식 도메인을 입력해주세요.",
  "blog.naver.com": "블로그·카페가 아닌 기업 공식 도메인을 입력해주세요.",
  "instagram.com":  "SNS가 아닌 기업 공식 홈페이지 URL을 입력해주세요.",
  "facebook.com":   "SNS가 아닌 기업 공식 홈페이지 URL을 입력해주세요.",
  "tistory.com":    "블로그가 아닌 기업 공식 도메인을 입력해주세요.",
  "youtube.com":    "YouTube가 아닌 기업 공식 홈페이지 URL을 입력해주세요.",
};

const BLOCKED_DOMAINS = Object.keys(BLOCKED_HINTS);

type UrlState = "empty" | "valid" | "invalid_scheme" | "invalid_format" | "blocked";

function checkUrl(raw: string): { state: UrlState; hint?: string } {
  const v = raw.trim();
  if (!v) return { state: "empty" };

  if (!/^https?:\/\//i.test(v)) {
    return { state: "invalid_scheme", hint: "https:// 또는 http://로 시작해야 합니다." };
  }

  let parsed: URL;
  try {
    parsed = new URL(v);
  } catch {
    return { state: "invalid_format", hint: "올바른 URL 형식이 아닙니다." };
  }

  const netloc = parsed.hostname.toLowerCase().replace(/^www\./, "");
  const blocked = BLOCKED_DOMAINS.find(
    (d) => netloc === d || netloc.endsWith("." + d),
  );
  if (blocked) {
    return { state: "blocked", hint: BLOCKED_HINTS[blocked] };
  }

  if (!netloc.includes(".")) {
    return { state: "invalid_format", hint: "도메인 형식이 올바르지 않습니다." };
  }

  return { state: "valid" };
}

export function UrlInput({ value, onChange, onValidChange, disabled }: Props) {
  const [touched, setTouched] = useState(false);
  const { state, hint } = checkUrl(value);

  useEffect(() => {
    onValidChange?.(state === "valid");
  }, [state, onValidChange]);

  const showError = touched && state !== "empty" && state !== "valid";
  const showOk    = touched && state === "valid";

  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium text-gray-700">
        공식 홈페이지 URL
        <span className="ml-1 text-ibk-500">*</span>
      </label>

      <div className="relative">
        <input
          type="url"
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            if (!touched) setTouched(true);
          }}
          onBlur={() => setTouched(true)}
          disabled={disabled}
          placeholder="https://www.example.co.kr"
          autoComplete="url"
          className={`w-full rounded-lg border px-4 py-3 pr-10 text-sm
            placeholder:text-gray-300 outline-none transition-all
            focus:ring-2 focus:ring-offset-0 disabled:bg-gray-50 disabled:text-gray-400
            ${showError
              ? "border-red-400 focus:ring-red-200 bg-red-50"
              : showOk
                ? "border-green-400 focus:ring-green-200"
                : "border-gray-200 focus:ring-ibk-200 focus:border-ibk-400"
            }`}
        />

        {/* 상태 아이콘 */}
        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-lg select-none">
          {showOk    && "✅"}
          {showError && "⚠️"}
        </span>
      </div>

      {/* 인라인 에러 메시지 */}
      {showError && hint && (
        <p className="text-xs text-red-500 flex items-center gap-1 animate-fade-in">
          {hint}
        </p>
      )}

      {/* https 자동완성 힌트 */}
      {touched && state === "invalid_scheme" && value && !value.includes("://") && (
        <button
          type="button"
          className="text-xs text-ibk-500 underline underline-offset-2"
          onClick={() => onChange(`https://${value}`)}
        >
          https://{value} 로 자동 완성
        </button>
      )}

      <p className="text-xs text-gray-400">
        AI가 이 URL에서 회사 정보를 수집해 콘텐츠를 보강합니다.
      </p>
    </div>
  );
}
