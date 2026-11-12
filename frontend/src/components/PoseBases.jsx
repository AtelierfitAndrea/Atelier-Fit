import { useEffect, useState } from "react";
import { api, fileUrl } from "@/lib/api";

// Definitive bases (seated pose): A = sleeved garments, B = bare arms. The server swaps A/B automatically from the garments.
export const PoseBases = ({ selected, onPick }) => {
  const [bases, setBases] = useState([]);
  useEffect(() => { api.get("/pose-bases").then((r) => setBases(r.data)).catch(() => {}); }, []);
  if (!bases.length) return null;
  return (
    <div className="max-w-2xl" data-testid="pose-bases">
      <div className="label-caps mb-1">Basi definitive</div>
      <p className="text-xs text-neutral-500 mb-3">Scegline una: con maniche uso la A, braccia scoperte la B, in automatico.</p>
      <div className="grid grid-cols-2 gap-3">
        {bases.map((b) => (
          <button key={b.code} onClick={() => onPick({ path: b.path })} data-testid={`pose-base-${b.kind}`}
            className={`text-left border p-2 transition-colors ${selected === b.path ? "border-[#0A0A0A] bg-[#FAF8F5]" : "hairline hover:border-[#0A0A0A]"}`}>
            <img src={fileUrl(b.path)} alt={b.label} className="w-full aspect-[3/4] object-cover object-top" />
            <span className="block text-xs font-medium mt-2">{b.label}</span>
            <span className="block text-[10px] tracking-[0.2em] text-[#8C7355]" data-testid={`pose-base-code-${b.kind}`}>{b.code}</span>
          </button>
        ))}
      </div>
    </div>
  );
};
