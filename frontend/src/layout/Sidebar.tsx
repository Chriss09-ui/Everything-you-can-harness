/** Sidebar — 左侧导航。
 *
 * Phase 1 只保留三项：新建对话 / 历史对话 / 账号与设置。
 * 改导航必须同步 frontend/PAGES.md。
 */
import { NavLink, useNavigate, useLocation } from "react-router-dom";
import { Plus, History, User, Smartphone } from "lucide-react";
import { cn } from "@/lib/cn";
import { useChatStore } from "@/stores/chatStore";

export function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const resetToHome = useChatStore((s) => s.resetToHome);

  const startNew = () => {
    resetToHome();
    navigate("/");
  };

  const isHome = location.pathname === "/";

  return (
    <aside className="w-sidebar shrink-0 bg-sidebar border-r border-line flex flex-col px-3.5">
      <div className="flex gap-2 pt-5 pl-2">
        <span className="w-3 h-3 rounded-full bg-[#ff5f57]" />
        <span className="w-3 h-3 rounded-full bg-[#febc2e]" />
        <span className="w-3 h-3 rounded-full bg-[#28c840]" />
      </div>

      <div className="font-display font-extrabold text-[30px] tracking-[-0.02em] px-2 pt-5 pb-6">
        Marvis
      </div>

      <nav className="flex flex-col gap-0.5">
        <button
          type="button"
          onClick={startNew}
          className={cn(navItemBase, isHome && navItemActive)}
        >
          <Plus size={19} className="shrink-0 text-ink" />
          新建对话
        </button>

        <NavLink
          to="/history"
          className={({ isActive }) =>
            cn(navItemBase, isActive && navItemActive)
          }
        >
          <History size={19} className="shrink-0 text-ink" />
          历史对话
        </NavLink>
      </nav>

      <div className="flex-1" />

      <div className="border-t border-line pt-3.5 pb-4 px-1">
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            cn(
              "flex items-center gap-3 rounded-md py-2 px-2 transition-colors hover:bg-surface-hover",
              isActive && "bg-surface shadow-soft-sm",
            )
          }
        >
          <span className="w-[26px] h-[26px] rounded-full bg-[#e8e6e1] grid place-items-center text-ink-muted">
            <User size={15} />
          </span>
          <span className="text-sm font-medium">账号与设置</span>
          <Smartphone size={17} className="ml-auto text-ink-faint" />
        </NavLink>
      </div>
    </aside>
  );
}

const navItemBase =
  "flex items-center gap-3 px-3 py-2.5 rounded-md text-[14.5px] font-medium text-ink transition-colors text-left w-full hover:bg-surface-hover";
const navItemActive = "bg-surface shadow-soft-sm";
