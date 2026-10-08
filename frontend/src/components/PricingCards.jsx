import { useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useSubscription } from "@/lib/subscription";

const CARDS = [
  { key: "extra",  option: "extra",  variant: "white", kicker: "extraKicker",  price: "extraTitle",  sub: "extraSub",  cta: "extraCta"  },
  { key: "single", option: "single", variant: "black", kicker: "singleKicker", price: "singleTitle", sub: "singleSub", cta: "singleCta", popular: true },
  { key: "family", option: "family", variant: "white", kicker: "familyKicker", price: "familyTitle", sub: "familySub", cta: "familyCta" },
];

export default function PricingCards() {
  const { t } = useI18n();
  const { status, refresh } = useSubscription();
  const [loading, setLoading] = useState(null);

  // Hide for paid plans — nothing more to upsell.
  if (status && (status.plan === "SINGLE" || status.plan === "FAMILY")) return null;

  const buy = async (option) => {
    setLoading(option);
    try {
      const { data } = await api.post("/subscription/checkout", { option });
      // Mock Stripe redirect — ~900ms then confirm.
      await new Promise((r) => setTimeout(r, 900));
      await api.post("/subscription/confirm", { session_id: data.session_id });
      toast.success(t("sub.paywall.success"));
      await refresh();
    } catch {
      toast.error("Checkout failed");
    } finally {
      setLoading(null);
    }
  };

  return (
    <section className="w-full" data-testid="pricing-cards" translate="no">
      <div className="flex items-end justify-between gap-6 flex-wrap">
        <h2 className="font-serif text-3xl md:text-5xl tracking-tighter leading-[1]">
          {t("sub.pricing.title")}
        </h2>
        <span className="label-caps text-neutral-500">{t("sub.pricing.subtitle")}</span>
      </div>

      <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
        {CARDS.map((c) => {
          const isBlack = c.variant === "black";
          const base = isBlack
            ? "bg-[#0A0A0A] text-white border-[#0A0A0A]"
            : "bg-white text-[#0A0A0A] border-[#E5E5E5] hover:border-[#0A0A0A]";
          return (
            <button
              key={c.key}
              onClick={() => buy(c.option)}
              disabled={loading === c.option}
              className={`relative text-left border p-6 flex flex-col gap-5 transition-all duration-200 ${base} disabled:opacity-70`}
              data-testid={`pricing-card-${c.key}`}
            >
              {c.popular && (
                <span className="absolute -top-3 left-6 bg-[#8C7355] text-white label-caps px-2 py-1">
                  {t("sub.pricing.popular")}
                </span>
              )}
              <div className={`label-caps ${isBlack ? "!text-white/60" : "text-neutral-500"}`}>
                {t(`sub.pricing.${c.kicker}`)}
              </div>
              <div>
                <div className="font-serif text-5xl leading-none">
                  {t(`sub.pricing.${c.price}`)}
                </div>
                <div className={`mt-2 text-sm ${isBlack ? "text-white/80" : "text-neutral-600"}`}>
                  {t(`sub.pricing.${c.sub}`)}
                </div>
              </div>
              <div
                className={`mt-auto inline-flex items-center justify-center w-full px-5 py-4 label-caps border transition-colors ${
                  isBlack
                    ? "bg-white text-[#0A0A0A] border-white hover:bg-[#8C7355] hover:text-white hover:border-[#8C7355]"
                    : "bg-[#0A0A0A] text-white border-[#0A0A0A] hover:bg-[#8C7355] hover:border-[#8C7355]"
                }`}
              >
                {loading === c.option ? t("sub.pricing.processing") : t(`sub.pricing.${c.cta}`)}
              </div>
            </button>
          );
        })}
      </div>

      <p className="mt-5 text-sm text-neutral-500" data-testid="pricing-footnote">
        {t("sub.pricing.footnote")}
      </p>
    </section>
  );
}
