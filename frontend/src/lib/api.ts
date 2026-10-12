// Thin client for the local SharkSight API (`api/`, FastAPI). Every write carries the acting PM in X-Actor;
// the server records it in the append-only audit trail.
import { QueryClient } from "@tanstack/react-query";

const ACTOR_KEY = "successor.actor";
export const DEFAULT_ACTOR = "Atahan (PM)";

export function getActor(): string {
  try {
    return localStorage.getItem(ACTOR_KEY) || DEFAULT_ACTOR;
  } catch {
    return DEFAULT_ACTOR;
  }
}
export function setActor(name: string) {
  try {
    localStorage.setItem(ACTOR_KEY, name);
  } catch {
    /* private mode: fall back to the default actor */
  }
}

// The shared access key of a cloud deployment (D-063): reads are open, changes need it. Kept in this browser only and
// sent with every request; the server compares it (api/access.py). Locally the server needs none.
const ACCESS_KEY = "sharksight.accessKey";
export function getAccessKey(): string {
  try {
    return localStorage.getItem(ACCESS_KEY) || "";
  } catch {
    return "";
  }
}
export function setAccessKey(key: string) {
  try {
    if (key) localStorage.setItem(ACCESS_KEY, key);
    else localStorage.removeItem(ACCESS_KEY);
  } catch {
    /* private mode: the key lasts until reload */
  }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      method,
      headers: { "Content-Type": "application/json", "X-Actor": getActor(), ...(getAccessKey() ? { "X-Access-Key": getAccessKey() } : {}) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "The local API isn't reachable. Start it with `uv run python -m api`.");
  }
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const j = await res.json();
      if (typeof j.detail === "string") msg = j.detail;
      else if (Array.isArray(j.detail)) msg = j.detail.map((d: { msg?: string }) => d.msg).join("; ");
    } catch {
      /* keep status text */
    }
    throw new ApiError(res.status, msg);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T,>(path: string) => request<T>("GET", path),
  post: <T,>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  put: <T,>(path: string, body?: unknown) => request<T>("PUT", path, body ?? {}),
  patch: <T,>(path: string, body?: unknown) => request<T>("PATCH", path, body ?? {}),
  delete: <T,>(path: string) => request<T>("DELETE", path),
};

export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") u.set(k, String(v));
  const s = u.toString();
  return s ? `?${s}` : "";
}

export const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 15_000, refetchOnWindowFocus: false, retry: 1 } },
});

/** Everything a decision can change; refetched after every write. */
export function invalidateAll() {
  return queryClient.invalidateQueries();
}
