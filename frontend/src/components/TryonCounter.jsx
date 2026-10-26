import { Lightning, Crown, Gift } from "@phosphor-icons/react";
import { useSubscription } from "@/lib/subscription";

const goInvite = () => {
  const el = document.getElementById("invite-friend");
  if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
  else window.location.assign("/dashboard#invite-friend");
};

// FREE: "Ti restano X/3 prove oggi" (reset at midnight Rome) + CTA when finished. PRO/Family: gold badge.
export default function TryonCounter() {
  const { status, openPaywall } = useSubscription();
  if (!status || status.honeymoon_active && !["SINGLE", "FAMILY"].includes(status.plan)) return null;
  if (status.plan === "SINGLE" || status.plan === "FAMILY") return <ProBadge plan={status.plan} />;

  const left = status.tryons_remaining ?? 0;
  const bonus = (status.boost_credits || 0) + (status.extra_credits || 0);
  if (left > 0) {
    return (
      <div className="inline-flex flex-wrap items-center justify-center gap-x-3 gap-y-1 border hairline bg-white px-4 py-2.5 text-center" data-testid="tryon-counter">
        <Lightning size={16} weight="duotone" className="text-[#8C7355]" />
        <span className="text-sm font-medium" translate="no" data-testid="tryon-counter-text">Ti restano {left}/{status.tryons_limit} prove oggi. Tornano domani a mezzanotte</span>
        {bonus > 0 && <span className="text-xs text-[#8C7355]" data-testid="tryon-counter-bonus">+{bonus} bonus</span>}
      </div>
    );
  }
  return (
    <div className="w-full border border-[#0A0A0A] bg-white px-5 py-4 text-center" data-testid="tryon-counter-finished">
      <p className="font-serif text-lg md:text-xl leading-snug" translate="no">Hai finito le 3 di oggi! Invita un&apos;amica per +5 extra oggi o passa a PRO</p>
      {bonus > 0 && <p className="mt-1 text-xs text-[#8C7355]" data-testid="tryon-counter-bonus">Hai ancora {bonus} prove bonus da usare</p>}
      <div className="mt-3 flex flex-wrap justify-center gap-3">
        <button onClick={goInvite} className="btn-ghost" data-testid="counter-invite-btn"><Gift size={14} /> Invita un&apos;amica</button>
        <button onClick={openPaywall} className="btn-primary" data-testid="counter-unlock">Passa a PRO</button>
      </div>
    </div>
  );
}

export function ProBadge({ plan = "SINGLE", small = false }) {
  return (
    <span className={`inline-flex items-center gap-1.5 bg-[#0A0A0A] text-[#D4AF37] border border-[#D4AF37]/60 font-semibold uppercase tracking-[0.2em] ${small ? "px-2 py-0.5 text-[10px]" : "px-3 py-1.5 text-xs"}`}
      data-testid="pro-badge">
      <Crown size={small ? 11 : 14} weight="fill" /> {plan === "FAMILY" ? "Family" : "PRO"}
    </span>
  );
}
