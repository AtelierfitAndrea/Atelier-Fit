import { useRef, useState } from "react";
import { toast } from "sonner";
import { Globe, CloudArrowUp, ArrowRight } from "@phosphor-icons/react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { api } from "@/lib/api";

// "Domanda fatidica": no brand size chart found -> international average (default) or optional screenshot.
export default function SizeFallbackDualChoice({ open, onOpenChange, url, analysis, onResult, onScreenshot, screenshotLoading }) {
  const fileRef = useRef();
  const [working, setWorking] = useState(false);

  const useAverage = async () => {
    setWorking(true);
    try {
      const { data } = await api.post("/product/size-fallback", {
        url: url || null,
        category: analysis?.category || null,
        product_name: analysis?.product_name || null,
        brand: analysis?.brand || null,
        product_image_url: analysis?.product_image_url || null,
      });
      onResult(data);
      onOpenChange(false);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Calcolo non riuscito, riprova");
    } finally {
      setWorking(false);
    }
  };

  const pickScreenshot = (f) => {
    if (!f) return;
    onOpenChange(false);
    onScreenshot(f);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="rounded-none max-w-lg p-8" data-testid="size-fallback-dialog" translate="no">
        <DialogHeader className="text-left">
          <div className="label-caps text-[#8C7355]">Atelier Fit</div>
          <DialogTitle className="font-serif text-2xl md:text-3xl tracking-tight leading-tight" data-testid="size-fallback-title">
            Non ho trovato la tabella di questo brand.
          </DialogTitle>
          <DialogDescription className="text-neutral-600" data-testid="size-fallback-subtitle">Come vuoi procedere?</DialogDescription>
        </DialogHeader>

        <div className="mt-4 space-y-3">
          <ChoiceButton
            primary onClick={useAverage} disabled={working || screenshotLoading} testid="size-fallback-average-btn"
            icon={<Globe size={22} weight="duotone" />}
            title={working ? "Calcolo in corso…" : "Usa media internazionale (consigliato)"}
            desc="Calcolo con le tue misure già salvate all'inizio + standard internazionale. 2 secondi."
          />
          <ChoiceButton
            onClick={() => fileRef.current?.click()} disabled={working || screenshotLoading} testid="size-fallback-screenshot-btn"
            icon={<CloudArrowUp size={22} weight="duotone" />}
            title={screenshotLoading ? "Leggo la tabella…" : "Carica screenshot tabella"}
            desc="Se ce l'hai sottomano, la leggo io. Opzionale."
          />
          <input ref={fileRef} type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" className="hidden"
            onChange={(e) => { pickScreenshot(e.target.files?.[0]); e.target.value = ""; }} data-testid="size-fallback-screenshot-input" />
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ChoiceButton({ primary, onClick, disabled, testid, icon, title, desc }) {
  const tone = primary
    ? "bg-[#0A0A0A] text-white border-[#0A0A0A] hover:bg-[#8C7355] hover:border-[#8C7355]"
    : "bg-neutral-100 text-[#0A0A0A] border-neutral-200 hover:border-[#0A0A0A]";
  return (
    <button type="button" onClick={onClick} disabled={disabled} data-testid={testid}
      className={`group w-full text-left border px-5 py-4 flex items-start gap-4 transition-colors duration-200 disabled:opacity-60 ${tone}`}>
      <span className="mt-0.5 shrink-0">{icon}</span>
      <span className="flex-1">
        <span className="block text-sm font-semibold tracking-[0.12em] uppercase">{title}</span>
        <span className={`block text-sm mt-1 ${primary ? "text-white/75" : "text-neutral-600"}`}>{desc}</span>
      </span>
      <ArrowRight size={16} weight="bold" className="mt-1 shrink-0 transition-transform duration-200 group-hover:translate-x-1" />
    </button>
  );
}
