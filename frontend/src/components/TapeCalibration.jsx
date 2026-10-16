import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Ruler, CaretDown } from "@phosphor-icons/react";
import { api } from "@/lib/api";

const FIELDS = [
  { k: "chest_cm", l: "Torace" },
  { k: "waist_cm", l: "Vita" },
  { k: "hips_cm", l: "Fianchi" },
  { k: "shoulder_cm", l: "Spalle" },
];

export default function TapeCalibration() {
  const [open, setOpen] = useState(false);
  const [m, setM] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    api.get("/profile/measurements").then(({ data }) => {
      setM(Object.fromEntries(FIELDS.map((f) => [f.k, data?.[f.k] ?? ""])));
    }).catch(() => {});
  }, [open]);

  const save = async () => {
    const payload = Object.fromEntries(Object.entries(m).filter(([, v]) => v !== "" && v != null).map(([k, v]) => [k, Number(v)]));
    if (!Object.keys(payload).length) { toast.error("Inserisci almeno una misura"); return; }
    setSaving(true);
    try {
      await api.put("/profile/measurements", { ...payload, method: "tape" });
      toast.success("Misure verificate: useremo queste per le tue taglie");
    } catch { toast.error("Salvataggio non riuscito"); }
    finally { setSaving(false); }
  };

  return (
    <section className="mt-16 border hairline bg-white" translate="no" data-testid="tape-calibration">
      <button onClick={() => setOpen((o) => !o)} className="w-full flex items-center justify-between px-6 py-5 text-left"
        data-testid="tape-calibration-toggle">
        <span className="flex items-center gap-3">
          <Ruler size={18} weight="duotone" />
          <span className="label-caps !text-[#0A0A0A]">Verifica con metro (opzionale)</span>
        </span>
        <CaretDown size={14} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="px-6 pb-6" data-testid="tape-calibration-body">
          <p className="text-sm text-neutral-600">Se vuoi, misura con il metro e correggi la stima: le tue taglie diventeranno ancora più precise.</p>
          <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
            {FIELDS.map((f) => (
              <label key={f.k} className="block">
                <span className="label-caps block mb-2">{f.l}</span>
                <div className="flex items-center border hairline focus-within:border-[#0A0A0A]">
                  <input type="number" step="0.5" value={m[f.k] ?? ""} placeholder="—"
                    onChange={(e) => setM((p) => ({ ...p, [f.k]: e.target.value }))}
                    className="w-full px-3 py-3 bg-transparent outline-none font-serif text-lg" data-testid={`tape-${f.k}`} />
                  <span className="px-3 text-xs text-neutral-500">cm</span>
                </div>
              </label>
            ))}
          </div>
          <button onClick={save} disabled={saving} className="btn-primary mt-5" data-testid="tape-save-btn">
            {saving ? "Salvataggio…" : "Salva misure verificate"}
          </button>
        </div>
      )}
    </section>
  );
}
