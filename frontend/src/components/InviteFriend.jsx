import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Gift, Copy, ShareNetwork, Crown } from "@phosphor-icons/react";
import { api } from "@/lib/api";

const RULES = [
  "Sei FREE: 5 prove extra per te e 5 prove bonus per la tua amica",
  "Sei abbonata: 7 giorni di abbonamento gratis in più",
  "Se la tua amica si abbona: 1 mese gratis in più per te",
];

// Personal invite link (?ref=CODE) with rewards, counters and the "Atelierista TOP" badge.
export default function InviteFriend() {
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/referral/me").then(({ data }) => setD(data)).catch(() => {}); }, []);
  if (!d) return null;
  const link = `${window.location.origin}/?ref=${d.code}`;
  const text = `Ti regalo 5 prove bonus su My Atelier: provati i vestiti dei tuoi brand preferiti addosso. ${link}`;

  const copy = async () => {
    try { await navigator.clipboard.writeText(link); toast.success("Link copiato"); } catch { toast.error("Copia non riuscita"); }
  };
  const share = async () => {
    if (navigator.share) { try { await navigator.share({ text, title: "My Atelier" }); } catch (_e) { /* annullato */ } return; }
    window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, "_blank", "noopener");
  };

  return (
    <section className="border hairline bg-white p-6 md:p-8" data-testid="invite-friend">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <Gift size={26} weight="duotone" className="text-[#8C7355]" />
          <h2 className="font-serif text-2xl md:text-3xl tracking-tight">Invita un&apos;amica</h2>
        </div>
        {d.is_top && (
          <span className="inline-flex items-center gap-1.5 bg-[#0A0A0A] text-[#D4AF37] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.2em]" data-testid="atelierista-top-badge">
            <Crown size={14} weight="fill" /> Atelierista TOP
          </span>
        )}
      </div>
      <ul className="mt-4 space-y-1.5 text-sm text-neutral-700">
        {RULES.map((r) => <li key={r} className="flex gap-2"><span className="text-[#8C7355]">—</span>{r}</li>)}
      </ul>
      <p className="mt-2 text-xs text-neutral-500">Il premio arriva quando la tua amica crea la sua prima foto.</p>
      <div className="mt-5 flex flex-col sm:flex-row gap-3">
        <div className="flex-1 border hairline bg-[#FAF8F5] px-4 py-3 text-sm truncate" data-testid="invite-link">{link}</div>
        <button onClick={copy} className="btn-ghost" data-testid="invite-copy-btn"><Copy size={14} /> Copia</button>
        <button onClick={share} className="btn-primary" data-testid="invite-share-btn"><ShareNetwork size={14} /> Invia</button>
      </div>
      <div className="mt-5 grid grid-cols-3 gap-3 text-center" data-testid="invite-stats">
        <Stat n={d.invited} label="Invitate" testid="invite-count-invited" />
        <Stat n={d.qualified} label="Hanno provato" testid="invite-count-qualified" />
        <Stat n={d.paid} label="Abbonate" testid="invite-count-paid" />
      </div>
      {!d.is_top && <p className="mt-3 text-xs text-neutral-500" data-testid="invite-top-progress">Porta {Math.max(0, d.top_at - d.qualified)} amiche in più per diventare Atelierista TOP.</p>}
    </section>
  );
}

function Stat({ n, label, testid }) {
  return (
    <div className="border hairline py-3" data-testid={testid}>
      <div className="font-serif text-2xl">{n}</div>
      <div className="text-[10px] uppercase tracking-[0.18em] text-neutral-500">{label}</div>
    </div>
  );
}
