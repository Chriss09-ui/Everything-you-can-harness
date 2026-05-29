/** Sidebar — 左侧导航。
 *
 * Phase 1 主导航：新建对话 / 历史对话 / API 配置 / 办公室；底部：账号与设置。
 * 改导航必须同步 frontend/PAGES.md。
 */
import { NavLink, useNavigate, useLocation } from "react-router-dom";
import { Plus, History, SlidersHorizontal, Building2, User } from "lucide-react";
import { cn } from "@/lib/cn";
import { useChatStore } from "@/stores/chatStore";
import { useProfileStore } from "@/stores/profileStore";
import { useT } from "@/lib/i18n/useT";

export function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const resetToHome = useChatStore((s) => s.resetToHome);
  const profile = useProfileStore((s) => s.profile);
  const t = useT();

  const startNew = () => {
    resetToHome();
    navigate("/");
  };

  const isHome = location.pathname === "/";
  const initial = (profile.displayName.trim()[0] ?? "U").toUpperCase();

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
          {t("nav.newChat")}
        </button>

        <NavLink
          to="/history"
          className={({ isActive }) =>
            cn(navItemBase, isActive && navItemActive)
          }
        >
          <History size={19} className="shrink-0 text-ink" />
          {t("nav.history")}
        </NavLink>

        <NavLink
          to="/api-config"
          className={({ isActive }) =>
            cn(navItemBase, isActive && navItemActive)
          }
        >
          <SlidersHorizontal size={19} className="shrink-0 text-ink" />
          {t("nav.apiConfig")}
        </NavLink>

        <NavLink
          to="/office"
          className={({ isActive }) =>
            cn(navItemBase, isActive && navItemActive)
          }
        >
          <Building2 size={19} className="shrink-0 text-ink" />
          {t("nav.office")}
        </NavLink>
      </nav>

      <div className="flex-1" />

      <div className="border-t border-line pt-3.5 pb-4 px-1">
        <NavLink
          to="/account"
          className={({ isActive }) =>
            cn(
              "flex items-center gap-3 rounded-md py-2 px-2 transition-colors hover:bg-surface-hover",
              isActive && "bg-surface shadow-soft-sm",
            )
          }
        >
          <span className="w-[26px] h-[26px] rounded-full overflow-hidden bg-[#e8e6e1] grid place-items-center text-ink-muted text-[12px] font-display font-bold">
            {profile.avatar ? (
              <img src={profile.avatar} alt="" className="w-full h-full object-cover" />
            ) : profile.displayName.trim() ? (
              initial
            ) : (
              <User size={15} />
            )}
          </span>
          <span className="text-sm font-medium truncate">
            {profile.displayName.trim() || t("nav.account")}
          </span>
        </NavLink>
      </div>
    </aside>
  );
}

const navItemBase =
  "flex items-center gap-3 px-3 py-2.5 rounded-md text-[14.5px] font-medium text-ink transition-colors text-left w-full hover:bg-surface-hover";
const navItemActive = "bg-surface shadow-soft-sm";
