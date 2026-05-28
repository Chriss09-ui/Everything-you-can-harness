import { Outlet } from "react-router-dom";
import { Bell } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { Toaster } from "@/components/ui/toast";

export function MainShell() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto relative">
        <button
          type="button"
          className="absolute top-5 right-7 text-ink hover:text-accent transition-colors z-10"
          aria-label="通知"
        >
          <Bell size={22} />
        </button>
        <Outlet />
      </main>
      <Toaster />
    </div>
  );
}
