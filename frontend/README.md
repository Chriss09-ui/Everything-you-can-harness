# Marvis Frontend — README

## 起步

```bash
cd frontend
npm install
npm run dev
# http://localhost:5173
```

## 技术栈

- Vite 5 + React 18 + TypeScript strict
- Zustand 5（状态管理）
- react-router-dom v6（路由）
- Tailwind CSS + shadcn/ui（UI）
- @microsoft/fetch-event-source（SSE）
- lucide-react（图标）

## 目录结构

```
src/
├─ layout/         Sidebar + MainShell
├─ pages/          ChatPage / HistoryPage / SettingsPage
├─ features/       按功能域分（chat / history / settings）
├─ stores/         zustand slices
├─ lib/
│  ├─ sse/         SSE 抽象（types + mockStream + 未来真 client）
│  ├─ storage.ts   localStorage 封装
│  └─ cn.ts        cn() 工具
└─ components/ui/  shadcn/ui 组件（button/input/select/slider/toast/dialog）
```

## 改动同步纪律

> 照搬 backend 三层开发规范："改代码必须同步改文档"

| 你改了什么 | 必须同步改 |
|---|---|
| 路由 | `App.tsx` + `PAGES.md` |
| zustand slice | `src/stores/` 同文件 + `STATE.md` |
| design token | `tailwind.config.ts` + `STYLE.md` |
| SSE 事件 | `src/lib/sse/types.ts` + `STATE.md` streaming 段 |

## Phase 路线图

- **Phase 1（当前）**：API 配置 + 聊天 UI（mock SSE）+ 历史会话
- **Phase 2**：消息渲染优化（Markdown / 代码块 / 工具调用卡片）
- **Phase 3**：3D 办公室可视化（R3F），`agentStore` 现已占位

## localStorage 结构

```
marvis.config.v1   — API 配置（不含 key）
marvis.apiKey.v1   — API key（单独存）
marvis.sessions.v1 — 会话列表 [{id, title, messages[], createdAt, updatedAt}]
```

## Mock SSE（Phase 1）

`src/lib/sse/mockStream.ts` 实现伪 token 流。
Phase 2 接入真后端时，只替换 `src/lib/sse/index.ts` 的导出，不动 UI。

## 常用命令

```bash
npm run dev      # 开发
npm run build    # 构建
npm run lint     # 类型检查
```
