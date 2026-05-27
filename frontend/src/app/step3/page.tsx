"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ResultsView } from "@/components/step3/ResultsView";
import { loadResult, clearResult } from "@/lib/api";
import type { ContentPackageResponse } from "@/types/content";

export default function Step3Page() {
  const router = useRouter();
  const [result, setResult] = useState<ContentPackageResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = loadResult();
    if (!stored) { router.replace("/step2"); return; }
    setResult(stored);
    setLoading(false);
  }, [router]);

  const handleBack = () => { clearResult(); router.push("/step2"); };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-ibk-500/30 border-t-ibk-500
          rounded-full animate-spin" />
      </div>
    );
  }
  if (!result) return null;

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <StepIndicator current={3} />

      <div>
        <h1 className="text-2xl font-bold text-gray-900">생성된 홈페이지 콘텐츠</h1>
        <p className="text-sm text-gray-500 mt-1">
          각 섹션을 검토하고 수정해 사용하세요.
          마우스를 올리면 근거 출처를 확인할 수 있습니다.
        </p>
      </div>

      <ResultsView result={result} onBack={handleBack} />
    </div>
  );
}

function StepIndicator({ current }: { current: number }) {
  const steps = [
    { n: 1, label: "기본 정보" },
    { n: 2, label: "홈페이지 정보" },
    { n: 3, label: "콘텐츠 확인" },
  ];
  return (
    <div className="flex items-center gap-3 text-sm">
      {steps.map(({ n, label }) => {
        const done   = n < current;
        const active = n === current;
        return (
          <div key={n} className="flex items-center gap-2">
            {n > 1 && <div className={`w-6 h-px ${done ? "bg-ibk-400" : "bg-gray-200"}`} />}
            <div className={`flex items-center gap-1.5 ${
              active ? "text-ibk-700" : done ? "text-ibk-500" : "text-gray-400"
            }`}>
              <span className={`w-6 h-6 rounded-full text-xs font-semibold
                flex items-center justify-center
                ${active ? "bg-ibk-600 text-white" : done ? "bg-ibk-100 text-ibk-600" : "bg-gray-200 text-gray-400"}`}>
                {done ? "✓" : n}
              </span>
              <span className="hidden sm:block text-xs font-medium">{label}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
