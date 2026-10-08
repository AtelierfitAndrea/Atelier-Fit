import { useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useSubscription } from "@/lib/subscription";

export default function Settings() {
  const { t } = useI18n();
  const { status, refresh, openPaywall } = useSubscription();
  const [working, setWorking] = useState(false);

  if (!status) return <div className="label-caps">…</div>;

  const planLabel = t(`sub.plans.${status.plan.toLowerCase()}`);
  const memberSince = status.member_since ? new Date(status.member_since).toLocaleDateString() : "—";

  const downgrade = async () => {
    if (!window.confirm(t("sub.settings.confirmCancel"))) return;
    setWorking(true);
    try {
      await api.post("/subscription/cancel");
      toast.success("OK");
      await refresh();
    } catch { toast.error("Error"); }
    finally { setWorking(false); }
  };

  return (
    <div className="max-w-3xl" data-testid="settings-root">
      <div className="label-caps mb-3">{t("sub.settings.title")}</div>
      <h1 className="font-serif text-4xl md:text-5xl tracking-tighter">{t("sub.current")}</h1>

      <div className="mt-10 border hairline bg-white p-6 md:p-8">
        <div className="flex items-start justify-between gap-6 flex-wrap">
          <div>
            <div className="label-caps">{t("sub.settings.currentPlan")}</div>
            <div className="font-serif text-3xl mt-2" translate="no">{planLabel}</div>
            {status.honeymoon_active && (
              <div className="label-caps text-[#8C7355] mt-2" translate="no">
                {t("sub.honeymoonBadge").replace("{n}", status.days_left_honeymoon)}
              </div>
            )}
          </div>
          <div className="flex gap-3">
            {status.plan === "FREE" ? (
              <button onClick={openPaywall} className="btn-primary" data-testid="settings-upgrade-btn">
                {t("sub.settings.upgrade")}
              </button>
            ) : (
              <button onClick={downgrade} disabled={working} className="btn-ghost" data-testid="settings-cancel-btn">
                {t("sub.settings.cancel")}
              </button>
            )}
          </div>
        </div>
        <div className="mt-8 grid grid-cols-1 sm:grid-cols-3 gap-4" translate="no">
          <Info label={t("sub.settings.memberSince")} value={memberSince} />
          <Info label={t("sub.settings.thisMonth")} value={`${status.tryons_used_this_month}${status.tryons_limit ? " / " + status.tryons_limit : ""}`} />
          <Info label={t("sub.settings.extraCredits")} value={String(status.extra_credits)} />
        </div>
      </div>
    </div>
  );
}

function Info({ label, value }) {
  return (
    <div className="border hairline p-3">
      <div className="label-caps">{label}</div>
      <div className="font-serif text-lg mt-1">{value}</div>
    </div>
  );
}
