# Marvis 前端 — 视觉风格规范

> 所有 design token 集中在此文件。**改 token 必须同步改 `tailwind.config.ts` 同名字段。**

## 颜色

| Token | 值 | Tailwind class | 用途 |
|---|---|---|---|
| `canvas` | `#f4f3f0` | `bg-canvas` | 主背景 |
| `sidebar` | `#fbfaf8` | `bg-sidebar` | 侧栏背景 |
| `surface` | `#ffffff` | `bg-surface` | 卡片 / 输入框 |
| `surface-hover` | `#f3f2ef` | `bg-surface-hover` | hover 态 |
| `ink` | `#1a1a1a` | `text-ink` | 主文字 |
| `ink-muted` | `#8a8a85` | `text-ink-muted` | 次要文字 |
| `ink-faint` | `#b4b4ae` | `text-ink-faint` | placeholder / 三级文字 |
| `line` | `#eceae6` | `border-line` | 边框 |
| `line-strong` | `#e2e0db` | `border-line-strong` | hover 边框 |
| `accent` | `#e5362b` | `text-accent` / `bg-accent` | Marvis 围巾红（点睛） |
| `accent-soft` | `#fdecea` | `bg-accent-soft` | accent 背景 |
| `ok` | `#1f9d3a` | `text-ok` | 连接成功文字 |
| `ok-soft` | `#eaf7ec` | `bg-ok-soft` | 连接成功背景 |
| `ok-dot` | `#28c840` | `bg-ok-dot` | 连接成功点 |

## 圆角

| Token | 值 | Tailwind class |
|---|---|---|
| `radius-sm` | 8px | `rounded-sm` |
| `radius-md` | 12px | `rounded-md` |
| `radius-lg` | 16px | `rounded-lg` |
| `radius-xl` | 22px | `rounded-xl` |
| `radius-full` | 9999px | `rounded-full` |

## 阴影

| Token | 值 | Tailwind class | 用途 |
|---|---|---|---|
| `shadow-soft-sm` | 0 1px 2px rgba(0,0,0,0.04) | `shadow-soft-sm` | nav-item active |
| `shadow-soft-md` | 0 2px 12px rgba(0,0,0,0.05) | `shadow-soft-md` | history item hover |
| `shadow-soft-lg` | 0 8px 36px rgba(0,0,0,0.07) | `shadow-soft-lg` | card hover |
| `shadow-input` | 0 2px 20px rgba(0,0,0,0.05) + 0 0 0 1px var(--border) | `shadow-input` | 输入框默认 |
| `shadow-input-focus` | 0 4px 28px rgba(0,0,0,0.07) + 0 0 0 1px var(--border-strong) | `shadow-input-focus` | 输入框聚焦 |

## 字体

| Token | Tailwind class | 值 |
|---|---|---|
| display | `font-display` | Bricolage Grotesque, 400/600/700/800 |
| body | `font-body` | 系统字体栈 |

## 布局

| Token | 值 | 用途 |
|---|---|---|
| sidebar width | 264px | `w-sidebar` |

## 动画

| Name | Keyframes | Tailwind class |
|---|---|---|
| fade-up | opacity 0→1, translateY 12px→0, 0.5s cubic-bezier(.2,.7,.3,1) | `animate-fade-up` |
| blink | typing 三点 | `animate-blink` |
| halo-blink | 输入框蓝色光晕呼吸 opacity 0.3↔0.7, 3s | `.glow-halo`（自定义 CSS，非 Tailwind） |

### 输入框光晕（`.glow-wrap` / `.glow-halo`）

首页 composer 的蓝色呼吸光晕。结构与约束（踩过的坑）：

- 光晕是独立装饰层 `.glow-halo`（`absolute inset-0`），内容层 `.relative` 分离 —— 这样聚焦时给光晕加 `brightness` 不会连带提亮输入文字。
- 单一 `halo-blink` 动画常驻，**聚焦不切换 animation / box-shadow**（切换会重启动画造成闪烁），聚焦态只靠 `.glow-wrap:focus-within .glow-halo { filter: brightness(1.5) }` 增强。
- 不要给输入框加 `focus-within:shadow-*`，会覆盖光晕 box-shadow。

## 视觉约束（不可破坏）

- **accent 红只能用于**：toast 背景、删除按钮 hover、历史项 hover 时的边框消失效果、连接状态"已连接"
- **阴影必须极柔**：不要用 `shadow-lg`（太重），只能用 `soft-sm/md/lg`
- **不要用 `gray-*` 系统色**：所有灰色必须从上面的 ink-faint / ink-muted / line / line-strong 选
- **Phase 3 R3F**：canvas 背景色不能被 shader 覆盖时，用 `bg-canvas` 而非 `#f4f3f0` 硬编码
