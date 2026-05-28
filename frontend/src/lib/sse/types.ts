// SSE 事件契约。Mock 与真实 client 都实现 streamEvents() 协议。
// 改这里必须同步 STATE.md "Streaming 状态机" 段。

export type SSEEvent =
  | { type: "token"; text: string }
  | { type: "done" }
  | { type: "error"; message: string };

export interface StreamRequest {
  message: string;
  // Phase 2 接真后端时会扩：sessionId / config / abortSignal
}

export interface StreamClient {
  streamEvents(req: StreamRequest, signal?: AbortSignal): AsyncIterable<SSEEvent>;
}
