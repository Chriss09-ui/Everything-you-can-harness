import { Routes, Route } from "react-router-dom";
import { MainShell } from "@/layout/MainShell";
import { ChatPage } from "@/pages/ChatPage";
import { HistoryPage } from "@/pages/HistoryPage";
import { ApiConfigPage } from "@/pages/ApiConfigPage";
import { AccountPage } from "@/pages/AccountPage";

export default function App() {
  return (
    <Routes>
      <Route element={<MainShell />}>
        <Route path="/" element={<ChatPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/api-config" element={<ApiConfigPage />} />
        <Route path="/account" element={<AccountPage />} />
      </Route>
    </Routes>
  );
}
