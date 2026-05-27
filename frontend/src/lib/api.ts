/**
 * FastAPI 백엔드 API 클라이언트.
 * Next.js rewrites → /api/v1/* → FastAPI 프록시.
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
// POST — 작업 시작
// ─────────────────────────────────────────────

/**
 * POST /api/v1/content-enrichment
 * → {job_id} 즉시 반환 (202 Accepted)
 */
export async function startEnrichment(
  payload: EnrichmentRequest,
): Promise<string> {
  const resp = await fetch(`${BASE}/content-enrichment`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
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
    } catch { /* ignore */ }
    throw new EnrichmentApiError(errDetail.code, errDetail.message, resp.status);
  }

  const { job_id } = await resp.json();
  return job_id as string;
}

// ─────────────────────────────────────────────
// GET /stream — SSE 연결
// ─────────────────────────────────────────────

/** SSE 이벤트 콜백 인터페이스 */
export interface SSECallbacks {
  onPhase: (update: PhaseUpdate) => void;
  onComplete: (result: ContentPackageResponse) => void;
  onError: (code: string, message: string) => void;
}

export interface PhaseUpdate {
  phase: string;
  message: string;
  elapsed_ms?: number;
  crawled_pages?: number;
  crawl_duration_ms?: number;
  evidence_level?: string;
  budget_sec?: number;
  from_cache?: boolean;
}

/**
 * SSE 스트림에 연결해 실시간 이벤트를 수신한다.
 *
 * @returns cleanup 함수 (unmount 시 호출)
 */
export function connectEnrichmentSSE(
  jobId: string,
  callbacks: SSECallbacks,
): () => void {
  const es = new EventSource(`${BASE}/content-enrichment/stream/${jobId}`);

  es.addEventListener("phase", (e: MessageEvent<string>) => {
    try {
      callbacks.onPhase(JSON.parse(e.data) as PhaseUpdate);
    } catch { /* ignore parse error */ }
  });

  es.addEventListener("complete", (e: MessageEvent<string>) => {
    try {
      const { result } = JSON.parse(e.data) as { result: ContentPackageResponse };
      callbacks.onComplete(result);
    } catch { /* ignore */ }
    es.close();
  });

  es.addEventListener("error", (e: MessageEvent<string>) => {
    // ※ 이름 충돌: EventSource 자체 오류 이벤트와 구분
    // sse-starlette가 보내는 커스텀 "error" 이벤트
    try {
      const { code, message } = JSON.parse(e.data) as {
        code: string;
        message: string;
      };
      callbacks.onError(code, message);
    } catch {
      callbacks.onError("sse_error", "SSE 연결 오류");
    }
    es.close();
  });

  // EventSource 자체 연결 오류 (네트워크 단절 등)
  es.onerror = () => {
    // readyState 2 = CLOSED
    if (es.readyState === EventSource.CLOSED) {
      callbacks.onError("sse_closed", "서버 연결이 끊겼습니다.");
    }
  };

  return () => es.close();
}

// ─────────────────────────────────────────────
// GET /result — 저장된 결과 폴링 (폴백용)
// ─────────────────────────────────────────────

export async function getEnrichmentResult(
  jobId: string,
): Promise<ContentPackageResponse> {
  const resp = await fetch(`${BASE}/content-enrichment/result/${jobId}`);
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new EnrichmentApiError(
      body.detail?.code ?? "fetch_error",
      body.detail?.message ?? resp.statusText,
      resp.status,
    );
  }
  return resp.json() as Promise<ContentPackageResponse>;
}

// ─────────────────────────────────────────────
// sessionStorage 헬퍼
// ─────────────────────────────────────────────

const RESULT_KEY = "ibkbox_enrichment_result";

export function saveResult(result: ContentPackageResponse): void {
  try { sessionStorage.setItem(RESULT_KEY, JSON.stringify(result)); } catch { /* ignore */ }
}

export function loadResult(): ContentPackageResponse | null {
  try {
    const raw = sessionStorage.getItem(RESULT_KEY);
    return raw ? (JSON.parse(raw) as ContentPackageResponse) : null;
  } catch { return null; }
}

export function clearResult(): void {
  try { sessionStorage.removeItem(RESULT_KEY); } catch { /* ignore */ }
}
