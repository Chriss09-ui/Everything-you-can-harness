/** sessionsStore — 历史会话列表 slice。
 *
 * Reads/Writes: 见 frontend/STATE.md
 * Persists: localStorage `marvis.sessions.v1`
 */
import { create } from "zustand";
import { readJSON, writeJSON, STORAGE_KEYS } from "@/lib/storage";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
}

export interface Session {
  id: string;
  title: string;
  messages: Message[];
  createdAt: string;
  updatedAt: string;
}

function uid(): string {
  return Math.random().toString(36).slice(2, 10);
}

function nowIso(): string {
  return new Date().toISOString();
}

interface SessionsStore {
  sessions: Session[];
  create: (title: string) => Session;
  appendMessage: (sessionId: string, message: Message) => void;
  patchLastAssistant: (sessionId: string, content: string) => void;
  rename: (id: string, title: string) => void;
  remove: (id: string) => void;
  get: (id: string) => Session | undefined;
}

const seed: Session[] = readJSON<Session[]>(STORAGE_KEYS.sessions, []);

function persist(sessions: Session[]): void {
  writeJSON(STORAGE_KEYS.sessions, sessions);
}

export const useSessionsStore = create<SessionsStore>((set, get) => ({
  sessions: seed,

  create: (title) => {
    const session: Session = {
      id: uid(),
      title: title.slice(0, 60) || "新对话",
      messages: [],
      createdAt: nowIso(),
      updatedAt: nowIso(),
    };
    set((s) => {
      const next = [session, ...s.sessions];
      persist(next);
      return { sessions: next };
    });
    return session;
  },

  appendMessage: (sessionId, message) =>
    set((s) => {
      const next = s.sessions.map((sess) =>
        sess.id === sessionId
          ? {
              ...sess,
              messages: [...sess.messages, message],
              updatedAt: nowIso(),
            }
          : sess,
      );
      persist(next);
      return { sessions: next };
    }),

  patchLastAssistant: (sessionId, content) =>
    set((s) => {
      const next = s.sessions.map((sess) => {
        if (sess.id !== sessionId) return sess;
        const msgs = [...sess.messages];
        for (let i = msgs.length - 1; i >= 0; i--) {
          const m = msgs[i];
          if (m && m.role === "assistant") {
            msgs[i] = { ...m, content };
            break;
          }
        }
        return { ...sess, messages: msgs, updatedAt: nowIso() };
      });
      persist(next);
      return { sessions: next };
    }),

  rename: (id, title) =>
    set((s) => {
      const next = s.sessions.map((sess) =>
        sess.id === id ? { ...sess, title, updatedAt: nowIso() } : sess,
      );
      persist(next);
      return { sessions: next };
    }),

  remove: (id) =>
    set((s) => {
      const next = s.sessions.filter((sess) => sess.id !== id);
      persist(next);
      return { sessions: next };
    }),

  get: (id) => get().sessions.find((s) => s.id === id),
}));

/** 按"今天 / 昨天 / 更早"分组（view 层算，不持久化）。 */
export function groupByDay(sessions: Session[]): Record<string, Session[]> {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const groups: Record<string, Session[]> = { 今天: [], 昨天: [], 更早: [] };
  for (const s of sessions) {
    const created = new Date(s.createdAt);
    const day = new Date(created);
    day.setHours(0, 0, 0, 0);
    if (day.getTime() === today.getTime()) groups["今天"]!.push(s);
    else if (day.getTime() === yesterday.getTime()) groups["昨天"]!.push(s);
    else groups["更早"]!.push(s);
  }
  return groups;
}
