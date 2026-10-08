import { Lock, Lightning, Infinity as InfIcon } from "@phosphor-icons/react";
import { useI18n } from "@/lib/i18n";
import { useSubscription } from "@/lib/subscription";

export default function TryonCounter() {
  const { t } = useI18n();
  const { status, openPaywall } = useSubscription();
  if (!status) return null;
  const unlimited = status.plan === "SINGLE" || status.plan === "FAMILY" || status.honeymoon_active;
  const remaining = status.tryons_remaining;
  const blocked = status.is_blocked;
  return (
    <div className="inline-flex items-center gap-3 border hairline bg-white px-3 py-2" data-testid="tryon-counter">
      {unlimited ? (
        <>
          <InfIcon size={16} weight="duotone" className="text-[#8C7355]" />
          <span className="text-sm font-medium" translate="no">
            {status.honeymoon_active ? t("sub.honeymoonUnlimited") : t("sub.plans." + status.plan.toLowerCase())}
          </span>
        </>
      ) : blocked ? (
        <>
          <Lock size={14} weight="duotone" className="text-[#B91C1C]" />
          <span className="text-sm font-medium text-[#B91C1C]" translate="no">{t("sub.counterZero")}</span>
          <button onClick={openPaywall} className="label-caps text-[#8C7355] hover:text-[#0A0A0A]" data-testid="counter-unlock">
            →
          </button>
        </>
      ) : (
        <>
          <Lightning size={14} weight="duotone" className="text-[#8C7355]" />
          <span className="text-sm font-medium" translate="no">
            {t("sub.counter").replace("{n}", remaining)}
          </span>
        </>
      )}
      {status.extra_credits > 0 && (
        <span className="label-caps text-[#8C7355]" translate="no">+{status.extra_credits}</span>
      )}
    </div>
  );
}
