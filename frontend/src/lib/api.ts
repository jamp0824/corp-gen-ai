/**
 * FastAPI 백엔드 API 클라이언트.
 * Next.js rewrites를 통해 /api/v1/* → FastAPI 프록시.
 */
import type {
  ApiError,
  ContentPackageResponse,
  EnrichmentRequest,
} from "@/types/content";

const BASE = "/api/v1";

// ─────────────────────────────────────────────
// 커스텀 에러
// ─────────────────────────────────────────────

export class EnrichmentApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "EnrichmentApiError";
  }
}

// ─────────────────────────────────────────────
// 공개 함수
// ─────────────────────────────────────────────

/**
 * POST /api/v1/content-enrichment
 *
 * @param payload  EnrichmentRequest (Step 2 폼 데이터)
 * @param signal   AbortController.signal (취소용)
 * @returns        ContentPackageResponse
 * @throws         EnrichmentApiError (4xx) | Error (network/timeout)
 */
export async function enrichContent(
  payload: EnrichmentRequest,
  signal?: AbortSignal,
): Promise<ContentPackageResponse> {
  const resp = await fetch(`${BASE}/content-enrichment`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
    // 브라우저 fetch timeout은 AbortSignal.timeout으로 처리
  });

  if (!resp.ok) {
    let errDetail: ApiError = { code: "unknown_error", message: resp.statusText };
    try {
      const body = await resp.json();
      if (body.detail) {
        errDetail = typeof body.detail === "string"
          ? { code: "api_error", message: body.detail }
          : body.detail;
      }
    } catch {
      // JSON 파싱 실패 → 기본 에러 사용
    }
    throw new EnrichmentApiError(errDetail.code, errDetail.message, resp.status);
  }

  return resp.json() as Promise<ContentPackageResponse>;
}

/**
 * GET /health — 백엔드 상태 확인
 */
export async function checkHealth(): Promise<boolean> {
  try {
    const resp = await fetch("/health", { method: "GET" });
    return resp.ok;
  } catch {
    return false;
  }
}

// ─────────────────────────────────────────────
// 로컬스토리지 헬퍼 (Step 2 → Step 3 결과 전달)
// ─────────────────────────────────────────────

const RESULT_KEY = "ibkbox_enrichment_result";

export function saveResult(result: ContentPackageResponse): void {
  try {
    sessionStorage.setItem(RESULT_KEY, JSON.stringify(result));
  } catch {
    // private browsing 등 스토리지 쓰기 실패 무시
  }
}

export function loadResult(): ContentPackageResponse | null {
  try {
    const raw = sessionStorage.getItem(RESULT_KEY);
    return raw ? (JSON.parse(raw) as ContentPackageResponse) : null;
  } catch {
    return null;
  }
}

export function clearResult(): void {
  try {
    sessionStorage.removeItem(RESULT_KEY);
  } catch {}
}
