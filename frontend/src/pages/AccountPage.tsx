import { useState, useEffect } from "react";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useProfileStore } from "@/stores/profileStore";
import { toast } from "@/components/ui/toast";

const LANGUAGE_OPTIONS = [
  { value: "zh-CN", label: "简体中文" },
  { value: "en-US", label: "English" },
];

const THEME_OPTIONS = [
  { value: "system", label: "跟随系统" },
  { value: "light", label: "浅色" },
  { value: "dark", label: "深色" },
];

export function AccountPage() {
  const profile = useProfileStore((s) => s.profile);
  const update = useProfileStore((s) => s.update);
  const save = useProfileStore((s) => s.save);
  const reset = useProfileStore((s) => s.reset);

  const [name, setName] = useState(profile.displayName);
  const [bio, setBio] = useState(profile.bio);

  useEffect(() => {
    setName(profile.displayName);
    setBio(profile.bio);
  }, [profile.displayName, profile.bio]);

  const handleSave = () => {
    update({ displayName: name, bio });
    save();
    toast("个人信息已保存");
  };

  const handleReset = () => {
    reset();
    setName("用户");
    setBio("");
    toast("已恢复默认");
  };

  const initial = (name.trim()[0] ?? "U").toUpperCase();

  return (
    <div className="max-w-[720px] mx-auto px-12 pt-[54px] pb-[80px]">
      <div className="mb-9 animate-fade-up">
        <h2 className="font-display text-[30px] font-extrabold tracking-[-0.02em]">
          账号与设置
        </h2>
        <p className="text-ink-muted text-[15px] mt-2">
          管理你的个人信息与偏好
        </p>
      </div>

      {/* 个人资料 */}
      <div
        className="bg-surface border border-line rounded-lg p-7 mb-5 animate-fade-up"
        style={{ animationDelay: "0.06s" }}
      >
        <h3 className="text-[17px] font-bold mb-1">个人资料</h3>
        <p className="text-[13.5px] text-ink-muted mb-5">展示给你自己的身份信息</p>

        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 rounded-full bg-ink text-white grid place-items-center text-[26px] font-display font-extrabold shrink-0">
            {initial}
          </div>
          <div className="text-[13px] text-ink-muted">
            头像由昵称首字母生成
            <div className="text-ink-faint mt-0.5">Phase 2 支持自定义上传</div>
          </div>
        </div>

        <Field label="昵称">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="你的昵称"
          />
        </Field>

        <Field label="邮箱">
          <Input
            type="email"
            value={profile.email}
            onChange={(e) => update({ email: e.target.value })}
            placeholder="you@example.com"
          />
          <Hint>仅本地保存，用于 Phase 2 账号同步</Hint>
        </Field>

        <Field label="个人简介">
          <Textarea
            value={bio}
            onChange={(e) => setBio(e.target.value)}
            placeholder="一句话介绍自己"
            rows={3}
            className="bg-canvas border border-line-strong rounded-md px-3.5 py-2.5 text-[14.5px] transition-[background,border-color,box-shadow] duration-150 focus:bg-surface focus:border-ink-faint focus:shadow-[0_0_0_3px_rgba(0,0,0,0.03)]"
          />
        </Field>
      </div>

      {/* 偏好 */}
      <div
        className="bg-surface border border-line rounded-lg p-7 animate-fade-up"
        style={{ animationDelay: "0.12s" }}
      >
        <h3 className="text-[17px] font-bold mb-1">偏好</h3>
        <p className="text-[13.5px] text-ink-muted mb-5">界面语言与主题</p>

        <Field label="语言">
          <Select
            value={profile.language}
            onValueChange={(v) => update({ language: v as typeof profile.language })}
            options={LANGUAGE_OPTIONS}
          />
        </Field>

        <Field label="主题">
          <Select
            value={profile.theme}
            onValueChange={(v) => update({ theme: v as typeof profile.theme })}
            options={THEME_OPTIONS}
          />
          <Hint>深色主题在 Phase 2 接入</Hint>
        </Field>
      </div>

      <div
        className="mt-7 flex items-center gap-3 animate-fade-up"
        style={{ animationDelay: "0.18s" }}
      >
        <Button variant="primary" onClick={handleSave}>
          保存
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
