import { useNavigate } from "react-router-dom";
import { Pencil, Trash2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useSessionsStore, groupByDay } from "@/stores/sessionsStore";
import { useChatStore } from "@/stores/chatStore";
import { useProfileStore } from "@/stores/profileStore";
import { cn } from "@/lib/cn";
import { useState } from "react";
import { useT } from "@/lib/i18n/useT";
import type { Key } from "@/lib/i18n/dict";

const SAMPLE_ICONS = ["📊", "🧾", "📄", "🖥️", "🍿", "📒", "💻", "🎬"];

const GROUP_KEYS: Record<string, Key> = {
  今天: "history.group.today",
  昨天: "history.group.yesterday",
  更早: "history.group.earlier",
};

export function HistoryPage() {
  const t = useT();
  const profile = useProfileStore((s) => s.profile);
  const sessions = useSessionsStore((s) => s.sessions);
  const rename = useSessionsStore((s) => s.rename);
  const remove = useSessionsStore((s) => s.remove);
  const loadSession = useChatStore((s) => s.loadSession);
  const resetToHome = useChatStore((s) => s.resetToHome);
  const navigate = useNavigate();

  const grouped = groupByDay(sessions);

  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [renameTarget, setRenameTarget] = useState<{ id: string; title: string } | null>(null);
  const [renameInput, setRenameInput] = useState("");

  const handleItemClick = (sessionId: string) => {
    resetToHome();
    loadSession(sessionId);
    navigate("/");
  };

  const handleRename = () => {
    if (!renameTarget) return;
    const t = renameInput.trim();
    if (t) rename(renameTarget.id, t);
    setRenameTarget(null);
  };

  const handleDelete = () => {
    if (!deleteTarget) return;
    remove(deleteTarget);
    setDeleteTarget(null);
  };

  return (
    <div className="max-w-[820px] mx-auto px-12 pt-[54px] pb-[60px]">
      <div className="mb-9 animate-fade-up">
        <h2 className="font-display text-[30px] font-extrabold tracking-[-0.02em]">
          {t("history.title")}
        </h2>
        <p className="text-ink-muted text-[15px] mt-2">
          {t("history.subtitle")}
        </p>
      </div>

      {(Object.entries(grouped) as [string, typeof sessions][]).map(([group, items]) =>
        items.length === 0 ? null : (
          <div key={group}>
            <div className="text-[13px] font-semibold text-ink-faint px-1 mb-2.5">
              {GROUP_KEYS[group] ? t(GROUP_KEYS[group]) : group}
            </div>
            {items.map((s, idx) => {
              const icon = SAMPLE_ICONS[idx % SAMPLE_ICONS.length] ?? "💬";
              return (
                <div
                  key={s.id}
                  className={cn(
                    "group flex items-center gap-4",
                    "bg-surface border border-line rounded-md",
                    "px-[18px] py-4 mb-2 cursor-pointer",
                    "transition-[box-shadow,border-color,transform] duration-150",
                    "hover:shadow-soft-md hover:-translate-x-0.5 hover:border-transparent",
                  )}
                  onClick={() => handleItemClick(s.id)}
                >
                  <div className="w-10 h-10 rounded-sm bg-surface-hover grid place-items-center text-[19px] shrink-0">
                    {icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[15.5px] font-semibold mb-0.5 truncate">{s.title}</div>
                    <div className="text-[13.5px] text-ink-muted truncate">
                      {s.messages[s.messages.length - 1]?.content.slice(0, 80) ?? t("history.newChat")}
                    </div>
                  </div>
                  <div className="text-[13px] text-ink-faint shrink-0 group-hover:hidden">
                    {formatTime(s.updatedAt, profile.language)}
                  </div>
                  <div className="hidden group-hover:flex gap-1 shrink-0">
                    <button
                      type="button"
                      title={t("history.rename")}
                      onClick={(e) => {
                        e.stopPropagation();
                        setRenameTarget({ id: s.id, title: s.title });
                        setRenameInput(s.title);
                      }}
                      className="w-8 h-8 rounded-sm grid place-items-center text-ink-muted hover:bg-surface-hover hover:text-ink transition-colors"
                    >
                      <Pencil size={16} />
                    </button>
                    <button
                      type="button"
                      title={t("history.delete")}
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleteTarget(s.id);
                      }}
                      className="w-8 h-8 rounded-sm grid place-items-center text-ink-muted hover:bg-accent-soft hover:text-accent transition-colors"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        ),
      )}

      {sessions.length === 0 && (
        <div className="text-center text-ink-muted py-20 animate-fade-up">
          <div className="text-4xl mb-4">📭</div>
          <p className="text-[15px]">{t("history.empty")}</p>
        </div>
      )}

      {/* Rename Dialog */}
      <Dialog open={!!renameTarget} onOpenChange={(o) => !o && setRenameTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("history.renameTitle")}</DialogTitle>
            <DialogDescription>{t("history.renameDesc")}</DialogDescription>
          </DialogHeader>
          <input
            autoFocus
            value={renameInput}
            onChange={(e) => setRenameInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleRename()}
            className="w-full bg-canvas border border-line-strong rounded-md px-3.5 py-2.5 text-sm text-ink focus:outline-none focus:border-ink-faint"
          />
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="ghost">{t("common.cancel")}</Button>
            </DialogClose>
            <Button variant="primary" onClick={handleRename}>
              {t("common.save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("history.deleteTitle")}</DialogTitle>
            <DialogDescription>{t("history.deleteDesc")}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="ghost">{t("common.cancel")}</Button>
            </DialogClose>
            <Button variant="danger" onClick={handleDelete}>
              {t("history.delete")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function formatTime(iso: string, lang: "zh-CN" | "en-US"): string {
  const d = new Date(iso);
  const now = new Date();
  const today = new Date(now);
  today.setHours(0, 0, 0, 0);
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (d >= today) {
    return d.toLocaleTimeString(lang, { hour: "2-digit", minute: "2-digit" });
  }
  if (d >= yesterday) {
    return lang === "zh-CN" ? "昨天" : "Yesterday";
  }
  return d.toLocaleDateString(lang, { month: "numeric", day: "numeric" });
}
