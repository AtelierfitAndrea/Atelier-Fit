import { useEffect, useState } from "react";
import { X, Heart } from "@phosphor-icons/react";
import { useI18n } from "@/lib/i18n";
import { useSubscription } from "@/lib/subscription";

const KEY = "vfit_honeymoon_banner_dismissed";

export default function HoneymoonBanner() {
  const { t } = useI18n();
  const { status } = useSubscription();
  const [dismissed, setDismissed] = useState(() => {
    try { return localStorage.getItem(KEY) === "1"; } catch { return false; }
  });

  useEffect(() => {
    try { if (dismissed) localStorage.setItem(KEY, "1"); } catch (_e) { /* ignore */ }
  }, [dismissed]);

  if (!status || !status.honeymoon_active || dismissed) return null;

  return (
    <div
      className="relative border hairline bg-white/70 backdrop-blur-md px-5 py-3 flex items-center gap-3 fade-up"
      data-testid="honeymoon-banner"
    >
      <Heart size={16} weight="duotone" className="text-[#8C7355] shrink-0" />
      <div className="text-sm leading-snug flex-1" translate="no">{t("sub.honeymoonBanner")}</div>
      <span className="hidden sm:inline label-caps text-[#8C7355]">
        {t("sub.honeymoonBadge").replace("{n}", status.days_left_honeymoon)}
      </span>
      <button
        onClick={() => setDismissed(true)}
        className="text-neutral-500 hover:text-black transition-colors"
        aria-label="dismiss"
        data-testid="honeymoon-banner-close"
      >
        <X size={16} weight="bold" />
      </button>
    </div>
  );
}
