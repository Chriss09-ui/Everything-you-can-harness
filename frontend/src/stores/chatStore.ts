/** chatStore — 当前会话内存 slice + streaming 状态机。
 *
 * Reads/Writes: 见 frontend/STATE.md
 * 不持久化（落盘走 sessionsStore）。
 */
import { create } from "zustand";
import { streamClient } from "@/lib/sse";
import { useSessionsStore, type Message } from "./sessionsStore";

export type StreamingState =
  | "idle"
  | "connecting"
  | "streaming"
  | "done"
  | "error"
  | "interrupted";

interface ChatStore {
  currentSessionId: string | null;
  messages: Message[];
  streamingState: StreamingState;
  streamingContent: string;

  startNewSession: (firstMessage: string) => Promise<void>;
  loadSession: (sessionId: string) => void;
  resetToHome: () => void;
  sendMessage: (text: string) => Promise<void>;
  abort: () => void;
}

let abortController: AbortController | null = null;

function uid(): string {
  return Math.random().toString(36).slice(2, 10);
}

function nowIso(): string {
  return new Date().toISOString();
}

export const useChatStore = create<ChatStore>((set, get) => ({
  currentSessionId: null,
  messages: [],
  streamingState: "idle",
  streamingContent: "",

  startNewSession: async (firstMessage) => {
    const session = useSessionsStore.getState().create(firstMessage);
    set({
      currentSessionId: session.id,
      messages: [],
      streamingState: "idle",
      streamingContent: "",
    });
    await get().sendMessage(firstMessage);
  },

  loadSession: (sessionId) => {
    const session = useSessionsStore.getState().get(sessionId);
    if (!session) return;
    set({
      currentSessionId: session.id,
      messages: session.messages,
      streamingState: "idle",
      streamingContent: "",
    });
  },

  resetToHome: () => {
    abortController?.abort();
    abortController = null;
    set({
      currentSessionId: null,
      messages: [],
      streamingState: "idle",
      streamingContent: "",
    });
  },

  sendMessage: async (text) => {
    const sessionId = get().currentSessionId;
    if (!sessionId) return;

    const userMsg: Message = {
      id: uid(),
      role: "user",
      content: text,
      createdAt: nowIso(),
    };
    const assistantMsg: Message = {
      id: uid(),
      role: "assistant",
      content: "",
      createdAt: nowIso(),
    };

    const sessions = useSessionsStore.getState();
    sessions.appendMessage(sessionId, userMsg);
    sessions.appendMessage(sessionId, assistantMsg);

    set((s) => ({
      messages: [...s.messages, userMsg, assistantMsg],
      streamingState: "connecting",
      streamingContent: "",
    }));

    abortController = new AbortController();
    try {
      let buffer = "";
      for await (const event of streamClient.streamEvents(
        { message: text },
        abortController.signal,
      )) {
        if (event.type === "token") {
          if (get().streamingState === "connecting") {
            set({ streamingState: "streaming" });
          }
          buffer += event.text;
          set({ streamingContent: buffer });
          sessions.patchLastAssistant(sessionId, buffer);
          set((s) => ({
            messages: s.messages.map((m, i) =>
              i === s.messages.length - 1 ? { ...m, content: buffer } : m,
            ),
          }));
        } else if (event.type === "done") {
          set({ streamingState: "done", streamingContent: buffer });
          break;
        } else if (event.type === "error") {
          set({ streamingState: "error" });
          break;
        }
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        set({ streamingState: "interrupted" });
      } else {
        set({ streamingState: "error" });
      }
    } finally {
      abortController = null;
      // 短暂停留后回 idle，UI 看到 done 一帧
      setTimeout(() => {
        const cur = get().streamingState;
        if (cur === "done" || cur === "error" || cur === "interrupted") {
          set({ streamingState: "idle" });
        }
      }, 80);
    }
  },

  abort: () => {
    abortController?.abort();
  },
}));
