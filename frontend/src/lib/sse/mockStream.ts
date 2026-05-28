// Phase 1 mock：把一段固定文案按 token 切片，用 setTimeout 假装吐流。
// Phase 2 接真后端时换 lib/sse/index.ts 的导出，UI 一行不动。

import type { SSEEvent, StreamClient, StreamRequest } from "./types";

function buildReply(userMsg: string): string {
  return (
    `收到!关于「${userMsg}」,我来帮你处理。\n\n` +
    `我会先拆解需求、确认细节,再交给对应的子智能体执行。` +
    `稍等片刻,我正在规划具体步骤...`
  );
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    const t = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(t);
      reject(new DOMException("Aborted", "AbortError"));
    });
  });
}

export const mockClient: StreamClient = {
  async *streamEvents(
    req: StreamRequest,
    signal?: AbortSignal,
  ): AsyncIterable<SSEEvent> {
    try {
      await sleep(600, signal);
      const reply = buildReply(req.message);
      const step = 2;
      for (let i = 0; i < reply.length; i += step) {
        await sleep(18, signal);
        yield { type: "token", text: reply.slice(i, i + step) };
      }
      yield { type: "done" };
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        yield { type: "done" };
        return;
      }
      yield { type: "error", message: (err as Error).message };
    }
  },
};
