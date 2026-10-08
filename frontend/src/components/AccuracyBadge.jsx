import { useEffect, useState } from "react";
import { api } from "@/lib/api";

/**
 * Compact Fitting Accuracy badge with circular progress — for Dashboard header.
 */
export default function AccuracyBadge({ nonce = 0 }) {
  const [state, setState] = useState(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    (async () => {
      try { const { data } = await api.get("/profile/fitting-accuracy"); setState(data); } catch (_e) { /* ignore */ }
    })();
  }, [nonce]);

  if (!state) return null;
  const pct = state.accuracy;
  const reliable = state.reliable;
  const ring = reliable ? "#059669" : pct >= 50 ? "#8C7355" : "#B91C1C";
  const size = 44;
  const stroke = 4;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (pct / 100) * c;

  return (
    <div
      className="relative inline-flex items-center gap-3 border hairline bg-white px-3 py-2"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      data-testid="accuracy-badge"
    >
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="rotate-[-90deg]">
          <circle cx={size/2} cy={size/2} r={r} stroke="#EEE" strokeWidth={stroke} fill="none" />
          <circle
            cx={size/2} cy={size/2} r={r}
            stroke={ring} strokeWidth={stroke} fill="none"
            strokeDasharray={c} strokeDashoffset={offset} strokeLinecap="round"
            style={{ transition: "stroke-dashoffset 0.6s ease" }}
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center font-serif text-sm" data-testid="accuracy-badge-pct">
          {pct}
        </span>
      </div>
      <div className="pr-1">
        <div className="label-caps">Fitting Accuracy</div>
        <div className="text-sm font-medium" style={{ color: ring }}>
          {pct}% · {reliable ? "Affidabile" : "Non affidabile"}
        </div>
      </div>
      {open && pct < 70 && (
        <div
          className="absolute left-0 top-full mt-2 z-20 w-72 bg-[#0A0A0A] text-white px-3 py-2 border hairline shadow-lg"
          data-testid="accuracy-tooltip"
        >
          <div className="label-caps !text-white/80">Attenzione</div>
          <div className="text-sm leading-snug mt-1">Profilo non affidabile per reso garantito. Completa misure e aggiorna il peso.</div>
        </div>
      )}
    </div>
  );
}
