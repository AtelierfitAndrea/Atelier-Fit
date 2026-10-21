import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Scissors } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { BODY } from "@/components/MeasureGuide";

const HEAD_TOP = 11;
const FLOOR = 245;

function Silhouette({ ratio }) {
  const y = FLOOR - ratio * (FLOOR - HEAD_TOP);
  return (
    <svg viewBox="0 0 120 262" className="w-28 h-auto shrink-0" data-testid="hem-silhouette">
      <circle cx="60" cy="22" r="11" fill="none" stroke="#0A0A0A" strokeWidth="0.8" />
      <path d={BODY} fill="none" stroke="#0A0A0A" strokeWidth="0.8" strokeLinejoin="round" />
      <path d="M4 246 L116 246" stroke="#0A0A0A" strokeWidth="0.4" strokeDasharray="2 3" />
      <path d={`M14 ${y} L106 ${y}`} stroke="#B8962E" strokeWidth="1.8" strokeLinecap="round" data-testid="hem-line" />
      <circle cx="14" cy={y} r="2" fill="#B8962E" />
      <circle cx="106" cy={y} r="2" fill="#B8962E" />
    </svg>
  );
}

export default function HemCard({ url }) {
  const [h, setH] = useState(null);
  useEffect(() => { setH(null); api.get(url).then(({ data }) => setH(data)).catch(() => setH({ applicable: false })); }, [url]);
  if (!h) return <div className="border hairline bg-white p-5 text-xs text-neutral-400" data-testid="hem-loading">Calcolo la lunghezza dell&apos;abito…</div>;
  if (!h.applicable) return null;
  if (h.needs_height) {
    return (
      <div className="border hairline bg-white p-5 text-sm" data-testid="hem-needs-height">
        <div className="label-caps text-[#8B7355]">Lunghezza abito reale · {h.style_label}</div>
        <p className="mt-2">Inserisci la tua altezza in <Link to="/profile" className="underline">Profilo</Link> per vedere dove cade l&apos;orlo.</p>
      </div>
    );
  }
  return (
    <div className="border hairline bg-white p-5 flex gap-5 items-center" data-testid="hem-card">
      <Silhouette ratio={h.ratio} />
      <div className="min-w-0">
        <div className="label-caps text-[#8B7355]">Lunghezza abito reale</div>
        <div className="font-serif text-2xl mt-1 leading-tight" data-testid="hem-position">L&apos;orlo {/terra$/.test(h.position_label) ? h.position_label : `cade ${h.position_label}`}</div>
        <p className="mt-2 text-xs text-neutral-600" data-testid="hem-details">
          Su di te ({h.height_cm} cm) · {h.style_label} · lunghezza ~{h.length_cm} cm {h.length_source === "product" ? "dalla scheda prodotto" : "stimata dalla foto"}
        </p>
        {h.hem_advice_cm && (
          <div className="mt-3 flex items-start gap-2 border border-[#B8962E]/50 bg-[#FAF8F5] px-3 py-2 text-sm" data-testid="hem-advice">
            <Scissors size={16} className="text-[#8B7355] shrink-0 mt-0.5" />
            <span>Valuta un orlo di circa {h.hem_advice_cm} cm{h.touches_floor ? ": così com'è tocca terra" : ""}.</span>
          </div>
        )}
      </div>
    </div>
  );
}
