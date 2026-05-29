// localStorage 封装。版本号 bump 后旧数据自动失效。
// 后续替换为 IndexedDB / 远端 DB 时只动这一层。

const SAFE_PREFIX = "marvis";

export function readJSON<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(`${SAFE_PREFIX}.${key}`);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function writeJSON<T>(key: string, value: T): void {
  try {
    localStorage.setItem(`${SAFE_PREFIX}.${key}`, JSON.stringify(value));
  } catch {
    // 配额满或私密模式 — 静默失败，UI 应已显示其他错误
  }
}

export function readString(key: string, fallback = ""): string {
  return localStorage.getItem(`${SAFE_PREFIX}.${key}`) ?? fallback;
}

export function writeString(key: string, value: string): void {
  try {
    localStorage.setItem(`${SAFE_PREFIX}.${key}`, value);
  } catch {
    /* noop */
  }
}

export function remove(key: string): void {
  localStorage.removeItem(`${SAFE_PREFIX}.${key}`);
}

export const STORAGE_KEYS = {
  config: "config.v1",
  apiKey: "apiKey.v1",
  sessions: "sessions.v1",
  profile: "profile.v1",
} as const;
