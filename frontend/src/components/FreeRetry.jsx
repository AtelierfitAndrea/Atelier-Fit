import { useState } from "react";
import { toast } from "sonner";
import { ArrowCounterClockwise } from "@phosphor-icons/react";
import { api } from "@/lib/api";

const REASONS = [["sfondo", "Sfondo cambiato"], ["viso", "Viso diverso"], ["capo", "Capo sbagliato"], ["altro", "Altro"]];
const DAY = 24 * 3600 * 1000;

export default function FreeRetry({ kind, item, onDone }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState(null);
  const [busy, setBusy] = useState(false);
  const expired = Date.now() - new Date(item.created_at).getTime() > DAY;

  if (item.retry_used) return <p className="text-xs text-neutral-500" data-testid="free-retry-used">Riprova gratuita già usata</p>;
  if (expired) return <p className="text-xs text-neutral-400" data-testid="free-retry-expired">Riprova gratuita scaduta (24 ore)</p>;

  const go = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`/${kind}/${item.id}/retry`, { reason });
      toast.success("Nuova prova pronta, senza consumare credito");
      setOpen(false); onDone(data);
    } catch (e) { toast.error(e?.response?.data?.detail || "Riprova non riuscita"); }
    finally { setBusy(false); }
  };

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="btn-ghost" data-testid="free-retry-btn">
        <ArrowCounterClockwise size={14} /> Riprova gratis
      </button>
    );
  }
  return (
    <div className="border hairline bg-white p-4" data-testid="free-retry-panel">
      <div className="label-caps">Cosa non va? · 1 riprova gratis entro 24 ore</div>
      <div className="mt-3 flex flex-wrap gap-2">
        {REASONS.map(([k, l]) => (
          <button key={k} onClick={() => setReason(k)} className={`px-3 py-1.5 text-xs border hairline ${reason === k ? "bg-[#0A0A0A] text-white" : "bg-white"}`} data-testid={`free-retry-reason-${k}`}>{l}</button>
        ))}
      </div>
      <div className="mt-4 flex gap-3">
        <button onClick={go} disabled={!reason || busy} className="btn-primary disabled:opacity-40" data-testid="free-retry-confirm">{busy ? "Rigenero gratis…" : "Rigenera senza credito"}</button>
        <button onClick={() => setOpen(false)} disabled={busy} className="btn-ghost" data-testid="free-retry-cancel">Annulla</button>
      </div>
    </div>
  );
}
