import { useEffect, useState } from "react";
import { fileUrl } from "@/lib/api";
import { PREVIEW_EVENT } from "@/lib/renderJob";

// ANTEPRIMA SUBITO: first photo of the running job, while the final checks finish.
export const RenderPreview = () => {
  const [p, setP] = useState(null);
  useEffect(() => {
    const on = (e) => setP(e.detail);
    window.addEventListener(PREVIEW_EVENT, on);
    return () => window.removeEventListener(PREVIEW_EVENT, on);
  }, []);
  if (!p) return null;
  return (
    <div className="fixed bottom-16 right-4 z-[65] w-40 bg-white shadow-xl border hairline p-2" data-testid="render-preview">
      <img src={fileUrl(p)} alt="Anteprima" className="w-full h-auto" data-testid="render-preview-image" />
      <div className="flex items-center gap-2 mt-2">
        <span className="w-3 h-3 border-2 border-neutral-300 border-t-[#D4AF37] rounded-full animate-spin" />
        <span className="text-[10px] tracking-[0.12em]">Anteprima — rifinisco…</span>
      </div>
    </div>
  );
};
