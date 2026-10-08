import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

/**
 * Fitting Accuracy badge.
 * The value, status and reliability are 100% computed server-side.
 * This component only renders what the API returns — no scoring logic here.
 */
const STATUS_RING = { green: "#059669", yellow: "#8C7355", red: "#B91C1C" };

export default function AccuracyBadge({ nonce = 0 }) {
  const { t } = useI18n();
  const [state, setState] = useState(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const { data } = await api.get("/fitting-accuracy");
        if (active) setState(data);
      } catch (_e) { /* ignore */ }
    })();
    return () => { active = false; };
  }, [nonce]);

  if (!state) return null;

  const pct = state.accuracy;
  const reliable = state.reliable;
  const ring = STATUS_RING[state.status] || STATUS_RING.red;
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
            style={{ transition: "stroke-dashoffset 0.9s ease, stroke 0.6s ease" }}
          />
        </svg>
        <span
          className="absolute inset-0 flex items-center justify-center font-serif text-[13px] leading-none"
          data-testid="accuracy-badge-pct"
          style={{ color: ring, transition: "color 0.6s ease" }}
        >
          {pct}%
        </span>
      </div>
      <div className="pr-1" translate="no">
        <div className="label-caps">{t("accuracy.label")}</div>
        <div className="text-sm font-medium" style={{ color: ring, transition: "color 0.6s ease" }}>
          {pct}% · {t("accuracy.reliable")}: {reliable ? t("accuracy.yes") : t("accuracy.no")}
        </div>
      </div>
      {open && !reliable && (
        <div
          className="absolute left-0 top-full mt-2 z-20 w-72 bg-[#0A0A0A] text-white px-3 py-2 border hairline shadow-lg"
          data-testid="accuracy-tooltip"
        >
          <div className="label-caps !text-white/80">{t("accuracy.tooltipTitle")}</div>
          <div className="text-sm leading-snug mt-1">{t("accuracy.tooltipBody")}</div>
        </div>
      )}
    </div>
  );
}
