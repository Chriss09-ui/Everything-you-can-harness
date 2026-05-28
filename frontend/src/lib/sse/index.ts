// SSE client 入口。Phase 1 直接导出 mock。
// Phase 2 接真后端时改这里，UI 一行不动。
export { mockClient as streamClient } from "./mockStream";
export type { SSEEvent, StreamClient, StreamRequest } from "./types";
