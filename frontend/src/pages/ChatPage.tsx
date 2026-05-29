import { useState, useEffect, useRef } from "react";
import { ArrowUp, MessageSquare } from "lucide-react";
import { useChatStore } from "@/stores/chatStore";
import { MarvisAvatar } from "@/assets/MarvisAvatar";
import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n/useT";

export function ChatPage() {
  const messages = useChatStore((s) => s.messages);
  const isHome = messages.length === 0;
  return isHome ? <HomeView /> : <ConversationView />;
}

function HomeView() {
  const t = useT();
  const [input, setInput] = useState("");
  const startNewSession = useChatStore((s) => s.startNewSession);
  const ready = input.trim().length > 0;

  const submit = () => {
    if (!ready) return;
    void startNewSession(input.trim());
    setInput("");
  };

  return (
    <div className="relative min-h-full flex flex-col items-center justify-center px-12 py-12">
      <div className="w-full max-w-[720px]">
        <div className="flex items-center gap-5 pb-9 animate-fade-up">
          <div className="w-[92px] h-[92px] rounded-full bg-surface shadow-soft-md grid place-items-center shrink-0">
            <MarvisAvatar size={64} />
          </div>
          <div>
            <h1 className="font-display text-[44px] font-extrabold tracking-[-0.02em] leading-none">
              Marvis
            </h1>
            <div className="flex items-center gap-2 mt-3 text-[17px] text-ink-muted font-medium">
              <MessageSquare size={20} />
              {t("chat.tagline")}
            </div>
          </div>
        </div>

        <div className="glow-wrap relative animate-fade-up" style={{ animationDelay: "0.06s" }}>
          <div className="glow-halo absolute inset-0 rounded-xl" aria-hidden />
          <div className="relative bg-surface rounded-xl pt-5 px-6 pb-4">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submit();
              }}
              placeholder={t("chat.placeholder")}
              className="w-full resize-none border-none bg-transparent text-ink text-[18px] leading-[1.5] min-h-[88px] max-h-[220px] focus:outline-none placeholder:text-ink-faint"
            />
            <div className="flex items-center justify-end mt-2">
              <button
                type="button"
                onClick={submit}
                className={cn(
                  "w-[42px] h-[42px] rounded-full grid place-items-center text-white transition-[background,transform]",
                  ready
                    ? "bg-ink hover:scale-105"
                    : "bg-[#e7e5e0] cursor-not-allowed",
                  "active:scale-95",
                )}
              >
                <ArrowUp size={18} strokeWidth={2.2} />
              </button>
            </div>
          </div>
        </div>

        <div
          className="mt-3 text-center text-[12px] text-ink-faint animate-fade-up"
          style={{ animationDelay: "0.12s" }}
        >
          {t("chat.sendHint1")} <kbd className="px-1.5 py-0.5 mx-0.5 rounded bg-surface border border-line text-[11px] font-mono">⌘</kbd>
          <kbd className="px-1.5 py-0.5 mx-0.5 rounded bg-surface border border-line text-[11px] font-mono">Enter</kbd>
          {t("chat.sendHint2")}
        </div>
      </div>
    </div>
  );
}

function ConversationView() {
  const t = useT();
  const messages = useChatStore((s) => s.messages);
  const streamingState = useChatStore((s) => s.streamingState);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "auto", block: "end" });
  }, [messages]);

  const submit = () => {
    const v = input.trim();
    if (!v) return;
    setInput("");
    void sendMessage(v);
  };

  const isBusy = streamingState === "connecting" || streamingState === "streaming";

  return (
    <>
      <div className="max-w-[760px] mx-auto px-6 pt-10 pb-[140px]">
        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            role={msg.role}
            content={msg.content}
            showTyping={
              msg.role === "assistant" &&
              msg.content === "" &&
              isBusy
            }
          />
        ))}
        <div ref={scrollRef} />
      </div>

      <div className="fixed bottom-0 left-sidebar right-0 px-6 pt-4 pb-6 bg-gradient-to-t from-canvas via-canvas/95 to-transparent">
        <div className="max-w-[760px] mx-auto bg-surface rounded-xl shadow-input flex items-center gap-3 pl-5 pr-3 py-3">
          <textarea
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              const el = e.currentTarget;
              el.style.height = "auto";
              el.style.height = `${el.scrollHeight}px`;
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            rows={1}
            placeholder={t("chat.continuePlaceholder")}
            className="flex-1 resize-none border-none bg-transparent text-[16px] leading-[1.5] max-h-[120px] min-h-[24px] focus:outline-none placeholder:text-ink-faint"
          />
          <button
            type="button"
            onClick={submit}
            disabled={!input.trim() || isBusy}
            className="w-[42px] h-[42px] rounded-full bg-ink text-white grid place-items-center transition-transform hover:scale-105 active:scale-95 disabled:opacity-40 disabled:hover:scale-100"
          >
            <ArrowUp size={18} strokeWidth={2.2} />
          </button>
        </div>
      </div>
    </>
  );
}

function MessageBubble({
  role,
  content,
  showTyping,
}: {
  role: "user" | "assistant";
  content: string;
  showTyping: boolean;
}) {
  const isUser = role === "user";
  return (
    <div className={cn("flex gap-3.5 mb-7", isUser && "flex-row-reverse")}>
      <div
        className={cn(
          "w-9 h-9 rounded-full shrink-0 grid place-items-center",
          isUser ? "bg-[#e8e6e1] text-ink-muted" : "bg-ink",
        )}
      >
        {isUser ? <UserSilhouette /> : <MarvisAvatar size={24} />}
      </div>
      <div
        className={cn(
          "px-[18px] py-3.5 text-[15.5px] leading-[1.65] max-w-[80%] shadow-soft-sm",
          isUser
            ? "bg-ink text-white rounded-lg rounded-br-[4px]"
            : "bg-surface border border-line rounded-lg rounded-bl-[4px] whitespace-pre-wrap",
        )}
      >
        {showTyping ? <TypingDots /> : content}
      </div>
    </div>
  );
}

function TypingDots() {
  return (
    <span className="inline-flex gap-1 items-center py-1">
      <span className="w-[7px] h-[7px] rounded-full bg-ink-faint animate-blink" />
      <span
        className="w-[7px] h-[7px] rounded-full bg-ink-faint animate-blink"
        style={{ animationDelay: "0.2s" }}
      />
      <span
        className="w-[7px] h-[7px] rounded-full bg-ink-faint animate-blink"
        style={{ animationDelay: "0.4s" }}
      />
    </span>
  );
}

function UserSilhouette() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21a8 8 0 0 1 16 0" />
    </svg>
  );
}
