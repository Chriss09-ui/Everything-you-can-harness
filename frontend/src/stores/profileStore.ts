/** profileStore — 用户个人信息 slice。
 *
 * Reads/Writes: 见 frontend/STATE.md
 * Persists: localStorage `marvis.profile.v1`
 */
import { create } from "zustand";
import { readJSON, writeJSON, STORAGE_KEYS } from "@/lib/storage";

export interface Profile {
  displayName: string;
  email: string;
  bio: string;
  avatar: string; // base64 data URL，空串表示用首字母占位
  language: "zh-CN" | "en-US";
}

const DEFAULT_PROFILE: Profile = {
  displayName: "用户",
  email: "",
  bio: "",
  avatar: "",
  language: "zh-CN",
};

interface ProfileStore {
  profile: Profile;
  update: (partial: Partial<Profile>) => void;
  save: () => void;
  reset: () => void;
}

export const useProfileStore = create<ProfileStore>((set, get) => ({
  profile: readJSON<Profile>(STORAGE_KEYS.profile, DEFAULT_PROFILE),

  update: (partial) => set((s) => ({ profile: { ...s.profile, ...partial } })),

  save: () => writeJSON(STORAGE_KEYS.profile, get().profile),

  reset: () => set({ profile: DEFAULT_PROFILE }),
}));
