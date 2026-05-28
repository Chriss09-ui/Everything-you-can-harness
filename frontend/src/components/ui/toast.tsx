/** 极简 toast：底部居中，自动消失。
 *
 * 不引入 sonner，避免 v1 多一个依赖；视觉与 marvis-demo.html 完全一致。
 */
import * as React from "react";
import { Check } from "lucide-react";
import { cn } from "@/lib/cn";

interface Toast {
  id: number;
  message: string;
}

const listeners: Array<(t: Toast) => void> = [];

export function toast(message: string): void {
  const t: Toast = { id: Date.now() + Math.random(), message };
  listeners.forEach((l) => l(t));
}

export function Toaster() {
  const [active, setActive] = React.useState<Toast | null>(null);

  React.useEffect(() => {
    const handler = (t: Toast) => {
      setActive(t);
      window.setTimeout(() => {
        setActive((prev) => (prev?.id === t.id ? null : prev));
      }, 2200);
    };
    listeners.push(handler);
    return () => {
      const i = listeners.indexOf(handler);
      if (i >= 0) listeners.splice(i, 1);
    };
  }, []);

  return (
    <div
      className={cn(
        "fixed bottom-8 left-1/2 -translate-x-1/2 z-[100]",
        "flex items-center gap-2.5 px-5 py-3 rounded-md bg-ink text-white shadow-soft-lg text-sm font-medium",
        "transition-[opacity,transform] duration-200",
        active
          ? "opacity-100 translate-y-0"
          : "pointer-events-none opacity-0 translate-y-3",
      )}
    >
      <Check size={17} strokeWidth={2.5} />
      {active?.message}
    </div>
  );
}
