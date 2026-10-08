import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Target, CheckCircle, Warning } from "@phosphor-icons/react";

export default function FittingAccuracy({ nonce = 0 }) {
  const [state, setState] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/profile/fitting-accuracy");
        setState(data);
      } catch (_e) { /* ignore */ }
    })();
  }, [nonce]);

  if (!state) return null;

  const { accuracy, reliable, weight_stale, missing_fields } = state;
  const barColor = accuracy >= 80 ? "bg-emerald-700" : accuracy >= 60 ? "bg-[#8C7355]" : "bg-[#0A0A0A]";
  const labelMap = {
    height_cm: "altezza",
    weight_kg: "peso",
    chest_cm: "torace",
    waist_cm: "vita",
    hips_cm: "fianchi",
  };

  let message;
  if (accuracy === 100) {
    message = "Vestibilità massima — pronta per i brand più esigenti.";
  } else if (weight_stale && missing_fields.length === 0) {
    message = "Aggiorna il peso per arrivare al 100%";
  } else if (missing_fields.length > 0) {
    message = `Aggiungi ${missing_fields.map((f) => labelMap[f] || f).join(", ")}${weight_stale ? " e aggiorna il peso" : ""} per arrivare al 100%`;
  } else {
    message = "Dati completi.";
  }

  return (
    <div className="border hairline bg-white p-5" data-testid="fitting-accuracy">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <Target size={22} weight="duotone" />
          <div>
            <div className="label-caps">Fitting Accuracy</div>
            <div className="font-serif text-2xl leading-tight" data-testid="accuracy-value">{accuracy}%</div>
          </div>
        </div>
        <span
          className={`label-caps inline-flex items-center gap-2 px-3 py-1 border hairline ${
            reliable ? "bg-emerald-700 text-white border-emerald-700" : "bg-[#8C7355] text-white border-[#8C7355]"
          }`}
          data-testid="accuracy-reliable"
        >
          {reliable ? <CheckCircle size={14} weight="fill" /> : <Warning size={14} weight="fill" />}
          Affidabile: {reliable ? "SÌ" : "NO"}
        </span>
      </div>
      <div className="mt-4 h-1.5 w-full bg-neutral-100 overflow-hidden">
        <div
          className={`h-full ${barColor} transition-[width] duration-500`}
          style={{ width: `${accuracy}%` }}
        />
      </div>
      <p className="mt-3 text-sm text-neutral-600" data-testid="accuracy-message">{message}</p>
    </div>
  );
}
