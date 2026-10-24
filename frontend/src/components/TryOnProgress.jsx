import { useEffect, useRef, useState } from "react";
import { fileUrl } from "@/lib/api";
import { useAvatar } from "@/lib/avatar";

const STEPS = [
  [20, "Analizzo la tua silhouette..."],
  [50, "Sto provando il capo su di te..."],
  [80, "Sistemo vestibilità, pieghe e ombre..."],
  [95, "Quasi fatto, rifinisco i dettagli..."],
  [101, "Ecco il risultato!"],
];
const TAU = 14000; // ~48% at 10s, ~72% at 20s, ~88% at 30s, then creeps towards 95%

const label = (p) => STEPS.find(([max]) => p < max)?.[1] || STEPS[STEPS.length - 1][1];

// Perceived-progress bar for 30-40s AI generations: eases towards 95% while `active`, jumps to 100% when it ends.
export default function TryOnProgress({ active, className = "", testid = "tryon-progress", photoPath }) {
  const { avatar } = useAvatar() || {};
  const photo = photoPath || avatar?.path;
  const [p, setP] = useState(0);
  const [visible, setVisible] = useState(active);
  const pRef = useRef(0);

  useEffect(() => {
    if (active) {
      setVisible(true);
      const start = performance.now();
      let raf;
      const tick = (now) => {
        pRef.current = 95 * (1 - Math.exp(-(now - start) / TAU));
        setP(pRef.current);
        raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
      return () => cancelAnimationFrame(raf);
    }
    if (!pRef.current) return undefined;
    setP(100);
    const t = setTimeout(() => { setVisible(false); pRef.current = 0; setP(0); }, 900);
    return () => clearTimeout(t);
  }, [active]);

  if (!visible) return null;
  const pct = Math.min(100, Math.round(p));
  // Avatar sharpens as progress rises: blur 22px -> 0, quantised so the filter is not recomputed every frame.
  const blur = Math.round(22 * (1 - p / 100));
  return (
    <div className={`relative overflow-hidden border hairline bg-white ${photo ? "min-h-[420px] flex flex-col justify-end" : ""} ${className}`}
      data-testid={testid} role="status" aria-live="polite">
      {photo && (
        <>
          <img src={fileUrl(photo)} alt="" aria-hidden="true" data-testid={`${testid}-avatar`} data-blur={blur}
            className="absolute inset-0 w-full h-full object-cover object-top scale-110"
            style={{ filter: `blur(${blur}px)`, opacity: 0.6 + 0.4 * (p / 100), transition: "filter 600ms linear, opacity 600ms linear" }} />
          <div className="absolute inset-0 bg-gradient-to-t from-white/80 via-transparent to-transparent" />
        </>
      )}
      <div className={`relative p-5 md:p-6 ${photo ? "m-3 md:m-4 bg-white/85 backdrop-blur-md" : ""}`}>
        <div className="flex items-baseline justify-between gap-4">
          <div className="label-caps text-[#8C7355]">Atelier al lavoro</div>
          <div className="font-serif text-2xl tabular-nums" data-testid={`${testid}-percent`}>{pct}%</div>
        </div>
        <div key={label(p)} className="font-serif text-xl md:text-2xl mt-2 fade-up" data-testid={`${testid}-step`}>{label(p)}</div>
        <div className="mt-5 h-1.5 w-full bg-[#EFE9E1] overflow-hidden">
          <div className="h-full w-full origin-left bg-[#0A0A0A] relative"
            style={{ transform: `scaleX(${p / 100})`, transition: p === 100 ? "transform 500ms ease-out" : "none" }}>
            <div className="absolute inset-y-0 right-0 w-24 bg-gradient-to-r from-transparent to-[#8C7355]/70" />
          </div>
        </div>
        <p className="mt-3 text-sm text-neutral-500" data-testid={`${testid}-note`}>
          Il risultato realistico richiede qualche secondo in più - ne varrà la pena
        </p>
      </div>
    </div>
  );
}
