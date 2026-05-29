import { useT } from "@/lib/i18n/useT";

export function OfficePage() {
  const t = useT();
  return (
    <div className="max-w-[720px] mx-auto px-12 pt-[54px] pb-[80px]">
      <div className="mb-9 animate-fade-up">
        <h2 className="font-display text-[30px] font-extrabold tracking-[-0.02em]">
          {t("nav.office")}
        </h2>
        <p className="text-ink-muted text-[15px] mt-2">
          {t("office.subtitle")}
        </p>
      </div>

      <div
        className="bg-surface border border-line rounded-lg p-7 text-center animate-fade-up"
        style={{ animationDelay: "0.06s" }}
      >
        <div className="text-5xl mb-4">🏢</div>
        <p className="text-[15px] text-ink-muted">{t("office.placeholder")}</p>
      </div>
    </div>
  );
}
