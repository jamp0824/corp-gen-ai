import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Docker standalone 빌드 활성화
  output: "standalone",

  async rewrites() {
    // FastAPI 백엔드 프록시
    // 개발: http://localhost:8000
    // Docker: http://backend:8000 (빌드 ARG로 주입)
    const apiBase =
      process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiBase}/api/v1/:path*`,
      },
      {
        source: "/health",
        destination: `${apiBase}/health`,
      },
    ];
  },
};

export default nextConfig;
