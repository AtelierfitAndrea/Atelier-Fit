import { useState } from "react";
import { toast } from "sonner";
import { ArrowCounterClockwise, HandPalm } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import TryOnProgress from "@/components/TryOnProgress";
import { notifyTabReady } from "@/lib/tabNotify";
import { postRender } from "@/lib/renderJob";
import { askBook } from "@/components/PoseBook";
import { useAuth } from "@/lib/auth";

const REASONS = [["mani_viso", "Mani o volto strani"], ["sfondo", "Sfondo cambiato"], ["viso", "Viso diverso"], ["capo", "Capo sbagliato"], ["altro", "Altro"]];
const DAY = 24 * 3600 * 1000;

const ZONES = [["viso", "Viso"], ["scarpe", "Scarpe / piedi"], ["maniche", "Maniche"], ["busto", "Busto"], ["gambe", "Gambe"]];

// MODALITÀ EDIT (owner): rebuild only the chosen zones of the current result, everything else stays pixel by pixel.
function EditZones({ kind, item, onDone }) {
  const [zones, setZones] = useState([]);
  const [busy, setBusy] = useState(false);
  const toggle = (z) => setZones((a) => (a.includes(z) ? a.filter((x) => x !== z) : [...a, z]));
  const go = async () => {
    setBusy(true);
    try {
      const { data } = await postRender(`/${kind}/${item.id}/retry`, { mode: "edit", zones });
      toast.success("Zone rifatte, il resto è invariato");
      notifyTabReady(); setZones([]); onDone(data);
    } catch (e) { toast.error(e?.response?.data?.detail || "Modifica non riuscita"); }
    finally { setBusy(false); }
  };
  return (
    <div className="border hairline bg-white p-4 mb-3" data-testid="edit-zones-panel">
      <div className="label-caps">Modalità edit · rifai solo le zone scelte</div>
      <div className="mt-3 flex flex-wrap gap-2">
        {ZONES.map(([k, l]) => (
          <button key={k} onClick={() => toggle(k)} disabled={busy}
            className={`px-3 py-1.5 text-xs border hairline ${zones.includes(k) ? "bg-[#0A0A0A] text-white" : "bg-white"}`} data-testid={`edit-zone-${k}`}>{l}</button>
        ))}
      </div>
      <button onClick={go} disabled={!zones.length || busy} className="btn-primary mt-4 disabled:opacity-40" data-testid="edit-zones-confirm">
        {busy ? "Rifaccio le zone…" : "Rifai solo queste zone"}
      </button>
      <TryOnProgress active={busy} className="mt-4" testid="edit-zones-progress" />
    </div>
  );
}

export default function FreeRetry(props) {
  const isOwner = useAuth()?.user?.is_owner === true;
  return (
    <>
      {isOwner && <EditZones {...props} />}
      <FreeRetryInner {...props} />
    </>
  );
}

function FreeRetryInner({ kind, item, onDone }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState(null);
  const [busy, setBusy] = useState(false);
  const expired = Date.now() - new Date(item.created_at).getTime() > DAY;

  if (item.retry_used) return <p className="text-xs text-neutral-500" data-testid="free-retry-used">Riprova gratuita già usata</p>;
  if (expired) return <p className="text-xs text-neutral-400" data-testid="free-retry-expired">Riprova gratuita scaduta (24 ore)</p>;

  const go = async (why = reason) => {
    setBusy(true);
    try {
      const { data } = await postRender(`/${kind}/${item.id}/retry`, { reason: why });
      toast.success("Nuova prova pronta, senza consumare credito");
      notifyTabReady();
      setBusy(false);
      await new Promise((r) => setTimeout(r, 800));
      setOpen(false); onDone(data);
      askBook(kind === "tryons" ? "tryon" : "outfit", item.id);
    } catch (e) { toast.error(e?.response?.data?.detail || "Riprova non riuscita"); }
    finally { setBusy(false); }
  };

  if (!open) {
    return (
      <div className="flex flex-wrap items-start gap-3">
        <button onClick={() => { setReason("mani_viso"); setOpen(true); go("mani_viso"); }} className="btn-ghost" data-testid="report-hands-face-btn">
          <HandPalm size={14} /> Mani o volto strani
        </button>
        <button onClick={() => setOpen(true)} className="btn-ghost" data-testid="free-retry-btn">
          <ArrowCounterClockwise size={14} /> Riprova gratis
        </button>
      </div>
    );
  }
  return (
    <div className="border hairline bg-white p-4" data-testid="free-retry-panel">
      <div className="label-caps">{reason === "mani_viso" && busy ? "Correggo mani e volto · riprova gratuita" : "Cosa non va? · 1 riprova gratis entro 24 ore"}</div>
      <div className="mt-3 flex flex-wrap gap-2">
        {REASONS.map(([k, l]) => (
          <button key={k} onClick={() => setReason(k)} className={`px-3 py-1.5 text-xs border hairline ${reason === k ? "bg-[#0A0A0A] text-white" : "bg-white"}`} data-testid={`free-retry-reason-${k}`}>{l}</button>
        ))}
      </div>
      <div className="mt-4 flex gap-3">
        <button onClick={() => go()} disabled={!reason || busy} className="btn-primary disabled:opacity-40" data-testid="free-retry-confirm">{busy ? "Rigenero gratis…" : "Rigenera senza credito"}</button>
        <button onClick={() => setOpen(false)} disabled={busy} className="btn-ghost" data-testid="free-retry-cancel">Annulla</button>
      </div>
      <TryOnProgress active={busy} className="mt-4" testid="free-retry-progress" />
    </div>
  );
}
