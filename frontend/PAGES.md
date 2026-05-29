# Marvis 前端 — 路由与页面契约

> 改路由必须同步改 `App.tsx` + 本文件。本文件是前端版 NODES.md。

## 路由表

| 路径 | 组件 | 一句话职责 |
|---|---|---|
| `/` | `ChatPage` | 首页态 ↔ 进行中态（根据 chatStore 判断） |
| `/history` | `HistoryPage` | 历史会话列表 |
| `/api-config` | `ApiConfigPage` | API 配置（模型服务 + 参数） |
| `/account` | `AccountPage` | 账号与设置（个人信息 + 偏好） |

## 页面数据契约

### ChatPage (`/`)

**Reads:**
- `chatStore.messages` — 当前会话消息列表
- `chatStore.streamingState` — `idle | connecting | streaming | done | error | interrupted`
- `sessionsStore.sessions` — 历史列表（用于"继续"跳转）

**Writes:**
- `chatStore.addMessage(role, text)` — 加消息
- `chatStore.setStreamingState(state)` — 改流状态
- `chatStore.startSession(title)` — 开启新会话，写入 sessionsStore

**Persists:**
- 当前会话的 `messages[]` 在 sessionsStore 中持久化

**Routes:**
- `chatStore.messages.length === 0` → 首页态（hero + composer + 推荐卡片）
- `chatStore.messages.length > 0` → 进行中态（消息列表 + 底部 composer）

---

### HistoryPage (`/history`)

**Reads:**
- `sessionsStore.sessions` — 所有历史会话
- `sessionsStore.groupedSessions` — 按"今天 / 昨天 / 更早"分组的计算属性

**Writes:**
- `sessionsStore.deleteSession(id)` — 删除
- `sessionsStore.renameSession(id, title)` — 重命名

**Persists:**
- `sessions[]` 写入 localStorage（`marvis.sessions.v1`）

**Routes:**
- 点击历史项 → navigate(`/`) + `chatStore.loadSession(id)`

---

### ApiConfigPage (`/api-config`)

**Reads:**
- `configStore.config` — API 配置对象

**Writes:**
- `configStore.updateConfig(partial)` — 更新配置
- `configStore.testConnection()` — 测连接
- `configStore.save()` — 保存到 localStorage

**Persists:**
- 配置写入 localStorage（`marvis.config.v1`），API key 写入 `marvis.apiKey.v1`

---

### AccountPage (`/account`)

**Reads:**
- `profileStore.profile` — 用户个人信息对象

**Writes:**
- `profileStore.update(partial)` — 更新个人信息
- `profileStore.save()` — 保存到 localStorage
- `profileStore.reset()` — 恢复默认

**Persists:**
- 个人信息写入 localStorage（`marvis.profile.v1`）

---

## 改动同步清单

| 你改了什么 | 必须同步改 |
|---|---|
| 加 / 删 / 改路由 | `App.tsx` + 本文件路由表 |
| 加页面组件 | `src/pages/` + `App.tsx` import + 本文件 |
| 改页面数据流 | 本文件对应页面 Reads / Writes 段 |
