import { useState, useEffect } from "react";
import { Eye, EyeOff } from "lucide-react";
import { Select } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useConfigStore } from "@/stores/configStore";
import { toast } from "@/components/ui/toast";
import { useT } from "@/lib/i18n/useT";

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
  const t = useT();
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
    toast(t("api.saved"));
  };

  const handleReset = () => {
    reset();
    setTemp(0.7);
    toast(t("account.resetDone"));
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
          {t("api.title")}
        </h2>
        <p className="text-ink-muted text-[15px] mt-2">
          {t("api.subtitle")}
        </p>
      </div>

      {/* 模型服务 */}
      <div
        className="bg-surface border border-line rounded-lg p-7 mb-5 animate-fade-up"
        style={{ animationDelay: "0.06s" }}
      >
        <h3 className="text-[17px] font-bold mb-1">{t("api.service")}</h3>
        <p className="text-[13.5px] text-ink-muted mb-5">
          {t("api.serviceDesc")}
        </p>

        <Field label={t("api.provider")}>
          <Select
            value={config.provider}
            onValueChange={(v) => update({ provider: v as typeof config.provider })}
            options={PROVIDER_OPTIONS}
          />
        </Field>

        <Field label={t("api.key")}>
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
          <Hint>{t("api.keyHint")}</Hint>
        </Field>

        <Field label={t("api.endpoint")}>
          <Input
            type="url"
            value={config.endpoint}
            onChange={(e) => update({ endpoint: e.target.value })}
            placeholder="https://..."
          />
          <Hint>{t("api.endpointHint")}</Hint>
        </Field>

        <Field label={t("api.connState")}>
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
              {isConnConnecting ? t("api.connecting") : isConnOk ? t("api.connected") : t("api.untested")}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleTest}
              disabled={isConnConnecting}
              className="text-[13px]"
            >
              {isConnConnecting ? t("api.testing") : t("api.test")}
            </Button>
          </div>
        </Field>
      </div>

      {/* 模型与参数 */}
      <div
        className="bg-surface border border-line rounded-lg p-7 animate-fade-up"
        style={{ animationDelay: "0.12s" }}
      >
        <h3 className="text-[17px] font-bold mb-1">{t("api.modelParams")}</h3>
        <p className="text-[13.5px] text-ink-muted mb-5">{t("api.modelParamsDesc")}</p>

        <Field label={t("api.model")}>
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
          <Hint>{t("api.tempHint")}</Hint>
        </Field>

        <Field label={t("api.maxTokens")}>
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
          {t("api.saveConfig")}
        </Button>
        <Button variant="ghost" onClick={handleReset}>
          {t("common.reset")}
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
