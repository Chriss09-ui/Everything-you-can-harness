# Marvis 前端 — State 与持久化规范

> 改 zustand slice 必须同步改本文件 + `src/stores/` 同文件。
> 这份文档是前端版 NODES.md 的 State 字段表。

## Slice 总览

| Slice | 文件 | 持久化 | 用途 |
|---|---|---|---|
| `configStore` | `stores/configStore.ts` | ✅ localStorage | API 配置 |
| `profileStore` | `stores/profileStore.ts` | ✅ localStorage | 用户个人信息 |
| `sessionsStore` | `stores/sessionsStore.ts` | ✅ localStorage | 历史会话列表 |
| `chatStore` | `stores/chatStore.ts` | ❌（内存） | 当前会话消息 + 流状态 |
| `agentStore` | `stores/agentStore.ts` | ❌（Phase 3 占位） | 3D 办公室 agent 状态 |

## Streaming 状态机

```
idle
  │ sendMessage()
  ▼
connecting
  │ stream 开始
  ▼
streaming ──► done ──► idle (下一轮可发)
  │                  ▲
  │ stream 错误
  ▼                  │
error ───────────────┘
  │
  │ 用户中断
  ▼
interrupted ──────► idle
```

事件流向：
- `idle → connecting`：用户点发送，`chatStore.setStreamingState('connecting')`
- `connecting → streaming`：SSE 开始吐 token
- `streaming → done`：SSE 收到 `[DONE]`
- `streaming → error`：SSE 连接失败 / HTTP 错误
- `streaming → interrupted`：用户在 streaming 中途点取消（Phase 2）
- `error / interrupted → idle`：UI 允许重发

## configStore

```typescript
interface Config {
  provider: "openai" | "anthropic" | "local" | "custom";
  endpoint: string;
  model: string;
  temperature: number; // 0~2
  maxTokens: number;
}
```

**持久化 key**：`marvis.config.v1`（不含 key），API key 单独存 `marvis.apiKey.v1`

## profileStore

```typescript
interface Profile {
  displayName: string;
  email: string;
  bio: string;
  avatar: string; // base64 data URL，空串表示用首字母占位
  language: "zh-CN" | "en-US";
}
```

**持久化 key**：`marvis.profile.v1`

## sessionsStore

```typescript
interface Session {
  id: string;
  title: string;
  messages: Message[];
  createdAt: string; // ISO
  updatedAt: string; // ISO
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string; // ISO
}
```

**持久化 key**：`marvis.sessions.v1`
**分组逻辑**（非持久化，按 createdAt 在 view 层算）：
- `今天`：createdAt 日期 === 今天
- `昨天`：createdAt 日期 === 昨天
- `更早`：其余

## chatStore（非持久化）

```typescript
// 只存内存，会话落盘由 sessionsStore 代理
interface ChatState {
  currentSessionId: string | null;
  messages: Message[];
  streamingState: StreamingState; // "idle"|"connecting"|"streaming"|"done"|"error"|"interrupted"
  streamingContent: string; // 正在 streaming 的累积文本
}
```

**与 sessionsStore 的关系**：
- 发消息时：chatStore 写内存，**同时** sessionsStore 更新对应 session 的 messages
- 切换会话时：sessionsStore.load(id) → chatStore.loadSession(id)

## agentStore（Phase 3 占位）

```typescript
// Phase 3 使用，v1 是空 slice
interface AgentState {
  // TODO
}
```

**Phase 3 约束**：agentStore 必须**独立**于 chatStore。消息流的高频 setState 会引发 R3F 重渲染雪崩，
两个 store 必须分离订阅。

## 改动同步清单

| 你改了什么 | 必须同步改 |
|---|---|
| 加 / 改 zustand slice | 本文件 slice 表 + `src/stores/` 同文件 |
| 加 / 改持久化字段 | 本文件对应 Slice 持久化段 + storage 版本号 bump |
| 加 / 改 SSE 事件类型 | `src/lib/sse/types.ts` + 本文件 streaming 状态机 |
| 加 / 改流状态 | 本文件 streaming 状态机图 + `chatStore.setStreamingState` 枚举 |
