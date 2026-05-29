import { useState, useEffect, useRef } from "react";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useProfileStore } from "@/stores/profileStore";
import { toast } from "@/components/ui/toast";
import { useT } from "@/lib/i18n/useT";

const LANGUAGE_OPTIONS = [
  { value: "zh-CN", label: "简体中文" },
  { value: "en-US", label: "English" },
];

const MAX_AVATAR_BYTES = 2 * 1024 * 1024;

export function AccountPage() {
  const t = useT();
  const profile = useProfileStore((s) => s.profile);
  const update = useProfileStore((s) => s.update);
  const save = useProfileStore((s) => s.save);
  const reset = useProfileStore((s) => s.reset);

  const [name, setName] = useState(profile.displayName);
  const [bio, setBio] = useState(profile.bio);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setName(profile.displayName);
    setBio(profile.bio);
  }, [profile.displayName, profile.bio]);

  const handleSave = () => {
    update({ displayName: name, bio });
    save();
    toast(t("account.saved"));
  };

  const handleReset = () => {
    reset();
    setName("用户");
    setBio("");
    toast(t("account.resetDone"));
  };

  const handleAvatarPick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (file.size > MAX_AVATAR_BYTES) {
      toast(t("account.avatarTooLarge"));
      return;
    }
    void resizeToDataUrl(file, 256).then((dataUrl) => {
      update({ avatar: dataUrl });
      save();
    });
  };

  const initial = (name.trim()[0] ?? "U").toUpperCase();

  return (
    <div className="max-w-[720px] mx-auto px-12 pt-[54px] pb-[80px]">
      <div className="mb-9 animate-fade-up">
        <h2 className="font-display text-[30px] font-extrabold tracking-[-0.02em]">
          {t("account.title")}
        </h2>
        <p className="text-ink-muted text-[15px] mt-2">{t("account.subtitle")}</p>
      </div>

      {/* 个人资料 */}
      <div
        className="bg-surface border border-line rounded-lg p-7 mb-5 animate-fade-up"
        style={{ animationDelay: "0.06s" }}
      >
        <h3 className="text-[17px] font-bold mb-1">{t("account.profile")}</h3>
        <p className="text-[13.5px] text-ink-muted mb-5">
          {t("account.profileDesc")}
        </p>

        <input
          ref={fileRef}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          className="hidden"
          onChange={handleAvatarPick}
        />

        <div className="flex items-center gap-4 mb-6">
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            className="w-16 h-16 rounded-full overflow-hidden bg-ink text-white grid place-items-center text-[26px] font-display font-extrabold shrink-0 transition-transform hover:scale-105 active:scale-95"
            title={t("account.uploadAvatar")}
          >
            {profile.avatar ? (
              <img
                src={profile.avatar}
                alt="avatar"
                className="w-full h-full object-cover"
              />
            ) : (
              initial
            )}
          </button>
          <div className="text-[13px] text-ink-muted">
            {t("account.avatarHint")}
            <div className="flex gap-3 mt-2">
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                className="text-ink font-medium hover:text-accent transition-colors"
              >
                {t("account.uploadAvatar")}
              </button>
              {profile.avatar && (
                <button
                  type="button"
                  onClick={() => {
                    update({ avatar: "" });
                    save();
                  }}
                  className="text-ink-faint hover:text-accent transition-colors"
                >
                  {t("account.removeAvatar")}
                </button>
              )}
            </div>
          </div>
        </div>

        <Field label={t("account.name")}>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("account.namePlaceholder")}
          />
        </Field>

        <Field label={t("account.email")}>
          <Input
            type="email"
            value={profile.email}
            onChange={(e) => update({ email: e.target.value })}
            placeholder="you@example.com"
          />
          <Hint>{t("account.emailHint")}</Hint>
        </Field>

        <Field label={t("account.bio")}>
          <Textarea
            value={bio}
            onChange={(e) => setBio(e.target.value)}
            placeholder={t("account.bioPlaceholder")}
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
        <h3 className="text-[17px] font-bold mb-1">{t("account.prefs")}</h3>
        <p className="text-[13.5px] text-ink-muted mb-5">{t("account.prefsDesc")}</p>

        <Field label={t("account.language")}>
          <Select
            value={profile.language}
            onValueChange={(v) => {
              update({ language: v as typeof profile.language });
              save();
            }}
            options={LANGUAGE_OPTIONS}
          />
        </Field>
      </div>

      <div
        className="mt-7 flex items-center gap-3 animate-fade-up"
        style={{ animationDelay: "0.18s" }}
      >
        <Button variant="primary" onClick={handleSave}>
          {t("common.save")}
        </Button>
        <Button variant="ghost" onClick={handleReset}>
          {t("common.reset")}
        </Button>
      </div>
    </div>
  );
}

/** 把图片文件缩到 size×size 居中裁剪，导出 jpeg base64。 */
function resizeToDataUrl(file: File, size: number): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      const canvas = document.createElement("canvas");
      canvas.width = size;
      canvas.height = size;
      const ctx = canvas.getContext("2d");
      if (!ctx) return reject(new Error("no 2d context"));
      const scale = Math.max(size / img.width, size / img.height);
      const w = img.width * scale;
      const h = img.height * scale;
      ctx.drawImage(img, (size - w) / 2, (size - h) / 2, w, h);
      resolve(canvas.toDataURL("image/jpeg", 0.85));
    };
    img.onerror = reject;
    img.src = url;
  });
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
