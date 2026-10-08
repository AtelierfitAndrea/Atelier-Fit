import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Scales, Clock, Plus, Trash, Warning } from "@phosphor-icons/react";

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("it-IT", { year: "numeric", month: "short", day: "numeric" });
}

export default function WeightTracker({ onChange }) {
  const [data, setData] = useState({ entries: [], status: { due: true, last_check_at: null, next_check_at: null, days_overdue: 0 } });
  const [weight, setWeight] = useState("");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(false);

  const load = async () => {
    try { const { data } = await api.get("/profile/weight-history"); setData(data); } catch (_e) { /* ignore */ }
  };

  useEffect(() => { load(); }, []);

  const add = async () => {
    const w = Number(weight);
    if (!w || w < 25 || w > 300) { toast.error("Inserisci un peso valido in kg"); return; }
    setLoading(true);
    try {
      await api.post("/profile/weight-history", { weight_kg: w, note: note || null });
      setWeight(""); setNote("");
      toast.success("Peso registrato — taglie ricalcolate");
      await load();
      onChange?.();
    } catch { toast.error("Salvataggio non riuscito"); }
    finally { setLoading(false); }
  };

  const del = async (id) => {
    try { await api.delete(`/profile/weight-history/${id}`); await load(); onChange?.(); } catch { toast.error("Eliminazione non riuscita"); }
  };

  const trend = useMemo(() => {
    if (data.entries.length < 2) return null;
    const latest = data.entries[0].weight_kg;
    const prev = data.entries[1].weight_kg;
    const delta = latest - prev;
    return { delta, up: delta > 0.1, down: delta < -0.1 };
  }, [data.entries]);

  const { status } = data;

  return (
    <section className="border hairline p-6 bg-white" data-testid="weight-tracker">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <Scales size={22} weight="duotone" />
          <div>
            <div className="label-caps">Controllo peso</div>
            <div className="font-serif text-xl">Ogni 2 mesi, per una vestibilità sempre perfetta</div>
          </div>
        </div>
        <StatusPill status={status} />
      </div>

      <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
        <Info label="Ultimo aggiornamento" value={fmtDate(status.last_check_at)} />
        <Info label="Prossimo controllo" value={fmtDate(status.next_check_at)} />
        <Info label="Peso attuale" value={data.entries[0] ? `${data.entries[0].weight_kg} kg` : "—"} trend={trend} />
      </div>

      <div className="mt-6 border-t hairline pt-6">
        <div className="label-caps mb-3">Registra un nuovo peso</div>
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
          <div className="md:col-span-3">
            <div className="flex items-center border hairline focus-within:border-[#0A0A0A] transition-colors">
              <input
                type="number"
                step="0.1"
                value={weight}
                onChange={(e) => setWeight(e.target.value)}
                placeholder="—"
                className="w-full px-3 py-3 bg-transparent outline-none font-serif text-xl"
                data-testid="weight-input"
              />
              <span className="px-3 text-xs text-neutral-500">kg</span>
            </div>
          </div>
          <div className="md:col-span-6">
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Nota (opzionale) — es. post vacanze, periodo allenamento"
              className="w-full px-3 py-3 border hairline bg-transparent outline-none focus:border-[#0A0A0A] transition-colors"
              data-testid="weight-note"
            />
          </div>
          <div className="md:col-span-3">
            <button onClick={add} disabled={loading} className="btn-primary w-full" data-testid="save-weight-btn">
              <Plus size={14} weight="bold" /> {loading ? "Salvo..." : "Registra"}
            </button>
          </div>
        </div>
      </div>

      {data.entries.length > 0 && (
        <div className="mt-8">
          <div className="label-caps mb-3">Storico</div>
          <div className="border hairline divide-y">
            {data.entries.map((e) => (
              <div key={e.id} className="flex items-center justify-between px-4 py-3" data-testid={`weight-entry-${e.id}`}>
                <div className="flex items-center gap-4">
                  <Clock size={16} weight="duotone" className="text-neutral-500" />
                  <div>
                    <div className="font-serif text-lg">{e.weight_kg} kg</div>
                    <div className="text-xs text-neutral-500">{fmtDate(e.recorded_at)} {e.note ? `· ${e.note}` : ""}</div>
                  </div>
                </div>
                <button onClick={() => del(e.id)} className="text-neutral-400 hover:text-[#0A0A0A] transition-colors" title="Elimina" data-testid={`del-weight-${e.id}`}>
                  <Trash size={16} weight="bold" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function StatusPill({ status }) {
  if (!status.last_check_at) {
    return (
      <span className="label-caps inline-flex items-center gap-2 px-3 py-1 border hairline bg-[#8C7355] text-white border-[#8C7355]">
        <Warning size={14} weight="fill" /> Inizia a tracciare
      </span>
    );
  }
  if (status.due) {
    return (
      <span className="label-caps inline-flex items-center gap-2 px-3 py-1 border hairline bg-[#0A0A0A] text-white border-[#0A0A0A]">
        <Warning size={14} weight="fill" /> Aggiornamento obbligatorio{status.days_overdue > 0 ? ` · ${status.days_overdue}gg di ritardo` : ""}
      </span>
    );
  }
  return (
    <span className="label-caps inline-flex items-center gap-2 px-3 py-1 border hairline">
      In regola
    </span>
  );
}

function Info({ label, value, trend }) {
  return (
    <div className="border hairline p-3">
      <div className="label-caps">{label}</div>
      <div className="font-serif text-lg mt-1 flex items-center gap-2">
        {value}
        {trend && (
          <span className={`text-xs label-caps ${trend.up ? "text-[#8C7355]" : trend.down ? "text-emerald-700" : "text-neutral-500"}`}>
            {trend.up ? "▲" : trend.down ? "▼" : "·"} {Math.abs(trend.delta).toFixed(1)}kg
          </span>
        )}
      </div>
    </div>
  );
}
