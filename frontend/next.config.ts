import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    // FastAPI 백엔드 프록시 (개발 환경)
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
