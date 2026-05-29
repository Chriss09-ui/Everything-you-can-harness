import { useState, useEffect } from "react";
import { Eye, EyeOff } from "lucide-react";
import { Select } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useConfigStore } from "@/stores/configStore";
import { toast } from "@/components/ui/toast";

const PROVIDER_OPTIONS = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "local", label: "本地 (Ollama / vLLM)" },
  { value: "custom", label: "自定义 OpenAI 兼容端点" },
];

const MODEL_OPTIONS = [
  { value: "gpt-4o", label: "GPT-4o" },
  { value: "gpt-4o-mini", label: "GPT-4o mini" },
  { value: "claude-opus-4", label: "Claude Opus 4" },
  { value: "claude-sonnet-4", label: "Claude Sonnet 4" },
  { value: "deepseek-chat", label: "DeepSeek Chat" },
];

export function ApiConfigPage() {
  const config = useConfigStore((s) => s.config);
  const apiKey = useConfigStore((s) => s.apiKey);
  const connState = useConfigStore((s) => s.connState);
  const update = useConfigStore((s) => s.update);
  const setApiKey = useConfigStore((s) => s.setApiKey);
  const save = useConfigStore((s) => s.save);
  const reset = useConfigStore((s) => s.reset);
  const testConnection = useConfigStore((s) => s.testConnection);

  const [showKey, setShowKey] = useState(false);
  const [temp, setTemp] = useState(config.temperature);

  useEffect(() => {
    setTemp(config.temperature);
  }, [config.temperature]);

  const handleSave = () => {
    update({ temperature: temp });
    save();
    toast("配置已保存");
  };

  const handleReset = () => {
    reset();
    setTemp(0.7);
    toast("已恢复默认");
  };

  const handleTest = () => {
    void testConnection();
  };

  const isConnOk = connState === "ok";
  const isConnConnecting = connState === "connecting";

  return (
    <div className="max-w-[720px] mx-auto px-12 pt-[54px] pb-[80px]">
      <div className="mb-9 animate-fade-up">
        <h2 className="font-display text-[30px] font-extrabold tracking-[-0.02em]">
          API 配置
        </h2>
        <p className="text-ink-muted text-[15px] mt-2">
          设置模型服务的连接方式与参数
        </p>
      </div>

      {/* 模型服务 */}
      <div
        className="bg-surface border border-line rounded-lg p-7 mb-5 animate-fade-up"
        style={{ animationDelay: "0.06s" }}
      >
        <h3 className="text-[17px] font-bold mb-1">模型服务</h3>
        <p className="text-[13.5px] text-ink-muted mb-5">
          选择服务提供商并填入凭证
        </p>

        <Field label="服务提供商">
          <Select
            value={config.provider}
            onValueChange={(v) => update({ provider: v as typeof config.provider })}
            options={PROVIDER_OPTIONS}
          />
        </Field>

        <Field label="API Key">
          <div className="relative">
            <Input
              type={showKey ? "text" : "password"}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-..."
              className="pr-11"
            />
            <button
              type="button"
              onClick={() => setShowKey((v) => !v)}
              className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-sm grid place-items-center text-ink-muted hover:bg-surface-hover transition-colors"
            >
              {showKey ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
          <Hint>密钥仅存储在本地浏览器,不会上传服务器</Hint>
        </Field>

        <Field label="API 端点">
          <Input
            type="url"
            value={config.endpoint}
            onChange={(e) => update({ endpoint: e.target.value })}
            placeholder="https://..."
          />
          <Hint>指向你的 backend/server.py 或第三方兼容地址</Hint>
        </Field>

        <Field label="连接状态">
          <div className="flex items-center gap-3">
            <span
              className={`inline-flex items-center gap-2 text-[13px] font-medium px-3 py-1.5 rounded-full ${
                isConnOk
                  ? "bg-ok-soft text-ok"
                  : "bg-surface-hover text-ink-muted"
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  isConnOk ? "bg-ok-dot" : "bg-[#ccc]"
                }`}
              />
              {isConnConnecting ? "连接中..." : isConnOk ? "已连接" : "未测试"}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleTest}
              disabled={isConnConnecting}
              className="text-[13px]"
            >
              {isConnConnecting ? "测试中..." : "测试连接"}
            </Button>
          </div>
        </Field>
      </div>

      {/* 模型与参数 */}
      <div
        className="bg-surface border border-line rounded-lg p-7 animate-fade-up"
        style={{ animationDelay: "0.12s" }}
      >
        <h3 className="text-[17px] font-bold mb-1">模型与参数</h3>
        <p className="text-[13.5px] text-ink-muted mb-5">控制生成行为</p>

        <Field label="模型">
          <Select
            value={config.model}
            onValueChange={(v) => update({ model: v })}
            options={MODEL_OPTIONS}
          />
        </Field>

        <Field label="Temperature">
          <div className="flex items-center gap-4">
            <Slider
              value={[temp]}
              min={0}
              max={2}
              step={0.1}
              onValueChange={([v]) => setTemp(v ?? 0.7)}
              className="flex-1"
            />
            <span className="text-sm font-semibold tabular-nums min-w-[36px] text-right">
              {temp.toFixed(1)}
            </span>
          </div>
          <Hint>越低越稳定严谨,越高越发散有创意</Hint>
        </Field>

        <Field label="最大输出 Tokens">
          <Input
            type="number"
            value={config.maxTokens}
            onChange={(e) => update({ maxTokens: Number(e.target.value) })}
            min={1}
            max={100000}
          />
        </Field>
      </div>

      <div className="mt-7 flex items-center gap-3 animate-fade-up" style={{ animationDelay: "0.18s" }}>
        <Button variant="primary" onClick={handleSave}>
          保存配置
        </Button>
        <Button variant="ghost" onClick={handleReset}>
          恢复默认
        </Button>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-5 last:mb-0">
      <label className="block text-sm font-semibold mb-2">{label}</label>
      {children}
    </div>
  );
}

function Hint({ children }: { children: React.ReactNode }) {
  return <p className="text-[12.5px] text-ink-faint mt-1.5">{children}</p>;
}
