import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Ruler, CheckCircle } from "@phosphor-icons/react";
import { api } from "@/lib/api";

// One-time tape calibration: real chest/waist align every future photo estimate.
export default function MetroCalibration({ onDone }) {
  const [info, setInfo] = useState(null);
  const [edit, setEdit] = useState(false);
  const [chest, setChest] = useState("");
  const [waist, setWaist] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => { api.get("/profile/tape-calibration").then(({ data }) => setInfo(data)).catch(() => {}); }, []);
  if (!info?.has_photo) return null;
  const ok = Number(chest) >= 60 && Number(chest) <= 170 && Number(waist) >= 45 && Number(waist) <= 170;

  const save = async () => {
    setSaving(true);
    try {
      const { data } = await api.post("/profile/tape-calibration", { chest_cm: Number(chest), waist_cm: Number(waist) });
      setInfo({ ...info, done: true, chest_cm: Number(chest), waist_cm: Number(waist) });
      setEdit(false);
      toast.success("Taratura salvata: le prossime foto useranno le tue misure reali");
      onDone?.(data.measurements);
    } catch (e) { toast.error(e?.response?.data?.detail || "Salvataggio non riuscito"); }
    finally { setSaving(false); }
  };

  return (
    <div className="border hairline bg-white p-6" data-testid="metro-calibration">
      <div className="flex items-center gap-2 label-caps"><Ruler size={16} /> Taratura metro · una tantum</div>
      {info.done && !edit ? (
        <div className="mt-3 flex flex-wrap items-center gap-4">
          <span className="flex items-center gap-2 text-sm text-emerald-700" data-testid="metro-calibration-done">
            <CheckCircle size={16} weight="fill" /> Fatta: torace {Math.round(info.chest_cm)} cm · vita {Math.round(info.waist_cm)} cm
          </span>
          <button onClick={() => setEdit(true)} className="text-xs underline" data-testid="metro-calibration-redo">Rifai</button>
        </div>
      ) : (
        <>
          <p className="mt-2 text-sm text-neutral-600">Misura una sola volta torace e vita con il metro da sarta: allineiamo per sempre le stime della tua foto.</p>
          <div className="mt-4 flex flex-wrap gap-3 items-center">
            {[["Torace", chest, setChest, "metro-chest-input"], ["Vita", waist, setWaist, "metro-waist-input"]].map(([l, v, set, id]) => (
              <label key={l} className="flex items-center border hairline w-40">
                <span className="px-3 text-xs text-neutral-500">{l}</span>
                <input type="number" inputMode="numeric" value={v} onChange={(e) => set(e.target.value)} placeholder="cm"
                  className="w-full px-2 py-2 bg-transparent outline-none font-serif text-lg" data-testid={id} />
              </label>
            ))}
            <button onClick={save} disabled={!ok || saving} className="btn-primary disabled:opacity-40" data-testid="metro-calibration-save">
              {saving ? "Salvo…" : "Salva taratura"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
