/** agentStore — Phase 3 占位 slice。
 *
 * Phase 3 R3F 办公室会订阅这里的 agent 状态（位置 / 房间 / 当前任务）。
 * 不能与 chatStore 合并：消息流的高频 setState 会引发 R3F 重渲染雪崩。
 */
import { create } from "zustand";

interface AgentStore {
  // Phase 3 填充
  _placeholder: true;
}

export const useAgentStore = create<AgentStore>(() => ({
  _placeholder: true,
}));
