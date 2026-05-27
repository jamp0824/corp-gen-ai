import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "IBK BOX — AI 홈페이지 콘텐츠 생성",
  description: "AI가 공식 홈페이지를 분석해 홈페이지 콘텐츠를 자동으로 생성합니다.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="bg-gray-50 min-h-screen text-gray-900">
        {/* 앱 쉘 */}
        <header className="border-b border-gray-200 bg-white sticky top-0 z-40">
          <div className="max-w-4xl mx-auto px-4 h-14 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-ibk-700 flex items-center
                justify-center text-white text-xs font-bold">
                IBK
              </div>
              <span className="font-semibold text-gray-800">BOX</span>
            </div>
            <span className="text-xs text-gray-400">AI 홈페이지 콘텐츠 생성</span>
          </div>
        </header>

        <main className="max-w-4xl mx-auto px-4 py-8">
          {children}
        </main>
      </body>
    </html>
  );
}
