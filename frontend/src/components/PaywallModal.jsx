import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, X, Sparkle, Users, Lightning } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useSubscription } from "@/lib/subscription";

export default function PaywallModal() {
  const { t } = useI18n();
  const { paywallOpen, closePaywall, refresh } = useSubscription();
  const [processing, setProcessing] = useState(null); // "extra" | "single" | "family"

  useEffect(() => { if (!paywallOpen) setProcessing(null); }, [paywallOpen]);

  if (!paywallOpen) return null;

  const buy = async (option) => {
    setProcessing(option);
    try {
      const { data } = await api.post("/subscription/checkout", { option });
      // Mock Stripe — immediately confirm
      await new Promise((r) => setTimeout(r, 900));
      await api.post("/subscription/confirm", { session_id: data.session_id });
      toast.success(t("sub.paywall.success"));
      await refresh();
      closePaywall();
    } catch {
      toast.error("Checkout failed");
    } finally {
      setProcessing(null);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md p-4 overflow-auto"
      onClick={closePaywall}
      data-testid="paywall-modal"
    >
      <div
        className="bg-[#0A0A0A] text-white w-full max-w-5xl mx-auto my-10 border border-[#1f1f1f] relative"
        onClick={(e) => e.stopPropagation()}
      >
        <button onClick={closePaywall} className="absolute top-4 right-4 text-white/70 hover:text-white" data-testid="paywall-close">
          <X size={20} weight="bold" />
        </button>
        <div className="px-8 md:px-12 pt-12 pb-6">
          <div className="label-caps !text-white/60">Atelier Fit</div>
          <h2 className="font-serif text-3xl md:text-5xl tracking-tight mt-2" translate="no">{t("sub.paywall.title")}</h2>
          <p className="mt-3 text-white/70 max-w-2xl">{t("sub.paywall.subtitle")}</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-px bg-[#1f1f1f] border-t border-b border-[#1f1f1f]">
          {/* Extra */}
          <div className="bg-white text-[#0A0A0A] p-8 flex flex-col" data-testid="plan-extra">
            <div className="flex items-center justify-between">
              <div className="label-caps">1</div>
              <Lightning size={22} weight="duotone" />
            </div>
            <h3 className="font-serif text-2xl mt-6">{t("sub.paywall.extraTitle")}</h3>
            <div className="font-serif text-4xl mt-2">{t("sub.paywall.extraPrice")}</div>
            <p className="text-sm text-neutral-600 mt-4">{t("sub.paywall.extraNote")}</p>
            <div className="flex-1" />
            <button
              onClick={() => buy("extra")}
              disabled={!!processing}
              className="mt-8 w-full border border-[#0A0A0A] bg-white text-[#0A0A0A] px-5 py-3 label-caps hover:bg-[#0A0A0A] hover:text-white transition-colors disabled:opacity-60"
              data-testid="plan-extra-cta"
            >
              {processing === "extra" ? t("sub.paywall.processing") : t("sub.paywall.extraCta")}
            </button>
          </div>
          {/* Single */}
          <div className="bg-[#0A0A0A] text-white p-8 flex flex-col relative" data-testid="plan-single">
            <span className="absolute -top-3 left-8 bg-[#8C7355] text-white label-caps px-3 py-1">{t("sub.paywall.popular")}</span>
            <div className="flex items-center justify-between">
              <div className="label-caps !text-white/60">2</div>
              <Sparkle size={22} weight="duotone" />
            </div>
            <h3 className="font-serif text-2xl mt-6">{t("sub.paywall.singleTitle")}</h3>
            <div className="font-serif text-4xl mt-2">{t("sub.paywall.singlePrice")}</div>
            <ul className="mt-5 space-y-2 text-sm">
              {t("sub.paywall.singlePerks").map((p, i) => (
                <li key={i} className="flex items-start gap-2"><Check size={14} weight="bold" className="mt-1 text-[#8C7355]" /> {p}</li>
              ))}
            </ul>
            <div className="flex-1" />
            <button
              onClick={() => buy("single")}
              disabled={!!processing}
              className="mt-8 w-full bg-white text-[#0A0A0A] px-5 py-3 label-caps hover:bg-[#8C7355] hover:text-white transition-colors disabled:opacity-60"
              data-testid="plan-single-cta"
            >
              {processing === "single" ? t("sub.paywall.processing") : t("sub.paywall.singleCta")}
            </button>
          </div>
          {/* Family */}
          <div className="bg-white text-[#0A0A0A] p-8 flex flex-col" data-testid="plan-family">
            <div className="flex items-center justify-between">
              <div className="label-caps">3</div>
              <Users size={22} weight="duotone" />
            </div>
            <h3 className="font-serif text-2xl mt-6">{t("sub.paywall.familyTitle")}</h3>
            <div className="font-serif text-4xl mt-2">{t("sub.paywall.familyPrice")}</div>
            <ul className="mt-5 space-y-2 text-sm text-neutral-700">
              {t("sub.paywall.familyPerks").map((p, i) => (
                <li key={i} className="flex items-start gap-2"><Check size={14} weight="bold" className="mt-1 text-[#8C7355]" /> {p}</li>
              ))}
            </ul>
            <div className="flex-1" />
            <button
              onClick={() => buy("family")}
              disabled={!!processing}
              className="mt-8 w-full border border-[#0A0A0A] bg-white text-[#0A0A0A] px-5 py-3 label-caps hover:bg-[#0A0A0A] hover:text-white transition-colors disabled:opacity-60"
              data-testid="plan-family-cta"
            >
              {processing === "family" ? t("sub.paywall.processing") : t("sub.paywall.familyCta")}
            </button>
          </div>
        </div>
        <div className="px-8 md:px-12 py-4 flex items-center justify-end">
          <button onClick={closePaywall} className="label-caps text-white/60 hover:text-white">{t("sub.paywall.close")}</button>
        </div>
      </div>
    </div>
  );
}
