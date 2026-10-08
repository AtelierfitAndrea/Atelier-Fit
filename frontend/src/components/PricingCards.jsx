import { CheckCircle } from "@phosphor-icons/react";
import { useI18n } from "@/lib/i18n";
import { useSubscription } from "@/lib/subscription";

const CARDS = [
  { key: "extra",  variant: "white", kicker: "extraKicker",  price: "extraTitle",  sub: "extraSub",  cta: "extraCta"  },
  { key: "single", variant: "black", kicker: "singleKicker", price: "singleTitle", sub: "singleSub", cta: "singleCta", popular: true },
  { key: "family", variant: "white", kicker: "familyKicker", price: "familyTitle", sub: "familySub", cta: "familyCta" },
];

export default function PricingCards() {
  const { t } = useI18n();
  const { status, openPaywall } = useSubscription();

  // Already on a paid plan — show a calm confirmation strip instead of hiding the section.
  if (status && (status.plan === "SINGLE" || status.plan === "FAMILY")) {
    const planLabel = t(`sub.plans.${status.plan.toLowerCase()}`);
    return (
      <section className="w-full" data-testid="pricing-cards" translate="no">
        <div className="border hairline bg-white p-6 flex items-center justify-between gap-6 flex-wrap">
          <div className="flex items-center gap-4">
            <CheckCircle size={28} weight="duotone" className="text-emerald-700" />
            <div>
              <div className="label-caps text-neutral-500">{t("sub.current")}</div>
              <div className="font-serif text-2xl mt-1">{planLabel}</div>
            </div>
          </div>
          <a href="/settings" className="btn-ghost" data-testid="pricing-manage-link">
            {t("sub.settings.title")}
          </a>
        </div>
      </section>
    );
  }

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
              type="button"
              onClick={openPaywall}
              className={`relative text-left border p-6 flex flex-col gap-5 transition-all duration-200 ${base}`}
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
                    ? "bg-white text-[#0A0A0A] border-white"
                    : "bg-[#0A0A0A] text-white border-[#0A0A0A]"
                }`}
              >
                {t(`sub.pricing.${c.cta}`)}
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
