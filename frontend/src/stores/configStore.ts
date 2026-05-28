/** configStore — API 配置 slice。
 *
 * Reads/Writes: 见 frontend/STATE.md
 * Persists: localStorage `marvis.config.v1` + `marvis.apiKey.v1`
 */
import { create } from "zustand";
import { readJSON, writeJSON, readString, writeString, STORAGE_KEYS } from "@/lib/storage";

export type Provider = "openai" | "anthropic" | "local" | "custom";
export type ConnState = "untested" | "connecting" | "ok" | "error";

export interface Config {
  provider: Provider;
  endpoint: string;
  model: string;
  temperature: number;
  maxTokens: number;
}

const DEFAULT_CONFIG: Config = {
  provider: "openai",
  endpoint: "http://localhost:8000/v1",
  model: "gpt-4o",
  temperature: 0.7,
  maxTokens: 4096,
};

interface ConfigStore {
  config: Config;
  apiKey: string;
  connState: ConnState;
  update: (partial: Partial<Config>) => void;
  setApiKey: (key: string) => void;
  save: () => void;
  reset: () => void;
  testConnection: () => Promise<void>;
}

export const useConfigStore = create<ConfigStore>((set, get) => ({
  config: readJSON<Config>(STORAGE_KEYS.config, DEFAULT_CONFIG),
  apiKey: readString(STORAGE_KEYS.apiKey, "sk-marvis-demo-0a1b2c3d4e5f6g7h"),
  connState: "untested",

  update: (partial) =>
    set((s) => ({ config: { ...s.config, ...partial }, connState: "untested" })),

  setApiKey: (key) => set({ apiKey: key, connState: "untested" }),

  save: () => {
    const { config, apiKey } = get();
    writeJSON(STORAGE_KEYS.config, config);
    writeString(STORAGE_KEYS.apiKey, apiKey);
  },

  reset: () => set({ config: DEFAULT_CONFIG, connState: "untested" }),

  testConnection: async () => {
    set({ connState: "connecting" });
    // Phase 1: mock — 真实健康检查在 Phase 2 接后端时实现
    await new Promise((r) => setTimeout(r, 1100));
    set({ connState: "ok" });
  },
}));
