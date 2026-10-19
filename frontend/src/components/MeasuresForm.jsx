import { useEffect, useState } from "react";
import { toast } from "sonner";
import { PlayCircle } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { useAvatar } from "@/lib/avatar";
import MeasureGuide, { GUIDES } from "@/components/MeasureGuide";

const REQUIRED = [["height_cm", 120, 230], ["chest_cm", 60, 170], ["waist_cm", 45, 170], ["hips_cm", 60, 180], ["shoulder_cm", 30, 70], ["inseam_cm", 50, 110]];
const OPTIONAL = [["weight_kg", "Peso", "kg", 35, 200], ["age", "Età", "anni", 14, 100]];

function NumField({ id, label, unit, value, onChange, bad, onGuide }) {
  return (
    <label className="block">
      <span className="label-caps block mb-2 whitespace-nowrap">{label}</span>
      <div className={`flex items-center border focus-within:border-[#0A0A0A] ${bad ? "border-[#B91C1C]" : "hairline"}`}>
        <input type="number" inputMode="decimal" step="0.5" value={value ?? ""} placeholder="—" onChange={(e) => onChange(e.target.value)}
          className="w-full px-3 py-3 bg-transparent outline-none font-serif text-lg" data-testid={`measure-input-${id}`} />
        <span className="px-3 text-xs text-neutral-500">{unit}</span>
      </div>
      {onGuide && (
        <button type="button" onClick={onGuide} className="mt-1.5 flex items-center gap-1 text-xs text-[#8C7355] hover:underline" data-testid={`guide-btn-${id}`}>
          <PlayCircle size={14} /> Guarda come
        </button>
      )}
    </label>
  );
}

export default function MeasuresForm({ onSaved }) {
  const { setReminderDue } = useAvatar();
  const [v, setV] = useState({ gender: "female" });
  const [guide, setGuide] = useState(null);
  const [saving, setSaving] = useState(false);
  const [tried, setTried] = useState(false);

  useEffect(() => {
    api.get("/profile/measurements").then(({ data }) => {
      const keys = [...REQUIRED.map((r) => r[0]), "weight_kg", "age"];
      // Photo-based estimates are never pre-filled: only real tape measures.
      const real = data?.method === "tape";
      setV({ gender: data?.gender === "male" ? "male" : "female", ...Object.fromEntries(keys.filter((k) => real || k === "weight_kg" || k === "age").map((k) => [k, data?.[k] ?? ""])) });
    }).catch(() => {});
  }, []);

  const invalid = (k, lo, hi) => { const n = Number(v[k]); return v[k] === "" || v[k] == null || isNaN(n) || n < lo || n > hi; };
  const badOpt = (k, lo, hi) => v[k] !== "" && v[k] != null && invalid(k, lo, hi);
  const set = (k) => (val) => setV((p) => ({ ...p, [k]: val }));

  const save = async () => {
    setTried(true);
    if (REQUIRED.some(([k, lo, hi]) => invalid(k, lo, hi)) || OPTIONAL.some(([k, , , lo, hi]) => badOpt(k, lo, hi))) { toast.error("Controlla i campi evidenziati"); return; }
    setSaving(true);
    try {
      const body = { gender: v.gender, ...Object.fromEntries(REQUIRED.map(([k]) => [k, Number(v[k])])) };
      OPTIONAL.forEach(([k]) => { if (v[k] !== "" && v[k] != null) body[k] = Number(v[k]); });
      const { data } = await api.put("/profile/real-measurements", body);
      setReminderDue(false);
      window.dispatchEvent(new Event("atelier-measures-updated"));
      toast.success("Misure salvate sul tuo account");
      onSaved?.(data);
    } catch (e) { toast.error(e?.response?.status === 422 ? "Controlla i campi evidenziati" : "Salvataggio non riuscito"); }
    finally { setSaving(false); }
  };

  return (
    <div className="border hairline bg-white p-6" translate="no" data-testid="measures-form">
      <div className="label-caps">Obbligatorie · con il metro da sarta</div>
      <div className="mt-4 grid grid-cols-2 md:grid-cols-3 gap-4">
        {REQUIRED.map(([k, lo, hi]) => (
          <NumField key={k} id={k} label={GUIDES[k].title} unit="cm" value={v[k]} onChange={set(k)} bad={tried && invalid(k, lo, hi)} onGuide={() => setGuide(k)} />
        ))}
      </div>
      <div className="mt-8 label-caps">Facoltative</div>
      <div className="mt-4 grid grid-cols-2 md:grid-cols-3 gap-4 items-end">
        {OPTIONAL.map(([k, l, u, lo, hi]) => (
          <NumField key={k} id={k} label={l} unit={u} value={v[k]} onChange={set(k)} bad={badOpt(k, lo, hi)} />
        ))}
        <div className="flex gap-2">
          {[["female", "Donna"], ["male", "Uomo"]].map(([k, l]) => (
            <button key={k} type="button" onClick={() => setV((p) => ({ ...p, gender: k }))}
              className={`flex-1 px-3 py-3 label-caps border hairline ${v.gender === k ? "bg-[#0A0A0A] !text-white" : "bg-white"}`} data-testid={`measure-gender-${k}`}>{l}</button>
          ))}
        </div>
      </div>
      <button onClick={save} disabled={saving} className="btn-primary mt-8 disabled:opacity-50" data-testid="measures-save-btn">
        {saving ? "Salvo…" : "Salva le mie misure"}
      </button>
      <MeasureGuide field={guide} onClose={() => setGuide(null)} />
    </div>
  );
}
