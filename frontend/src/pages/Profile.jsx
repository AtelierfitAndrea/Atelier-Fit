import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import Avatar3D from "@/components/Avatar3D";
import WeightTracker from "@/components/WeightTracker";
import FittingAccuracy from "@/components/FittingAccuracy";

const FIELDS = [
  { group: "Parte Superiore", items: [
    { k: "height_cm", l: "Altezza", u: "cm" },
    { k: "shoulder_cm", l: "Spalle", u: "cm" },
    { k: "chest_cm", l: "Torace", u: "cm" },
  ]},
  { group: "Parte Inferiore", items: [
    { k: "waist_cm", l: "Vita", u: "cm" },
    { k: "hips_cm", l: "Fianchi", u: "cm" },
    { k: "inseam_cm", l: "Cavallo", u: "cm" },
  ]},
  { group: "Altro", items: [
    { k: "weight_kg", l: "Peso", u: "kg" },
    { k: "foot_cm", l: "Lunghezza piede", u: "cm" },
  ]},
];

export default function Profile() {
  const [m, setM] = useState({ gender: "female" });
  const [saving, setSaving] = useState(false);
  const [accuracyNonce, setAccuracyNonce] = useState(0);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/profile/measurements");
        if (data && Object.keys(data).length) setM({ gender: "female", ...data });
      } catch (_e) { /* ignore */ }
    })();
  }, []);

  const update = (k, v) => setM((prev) => ({ ...prev, [k]: v === "" ? "" : Number(v) }));
  const updateStr = (k, v) => setM((prev) => ({ ...prev, [k]: v }));

  const save = async () => {
    setSaving(true);
    try {
      const payload = Object.fromEntries(Object.entries(m).filter(([_, v]) => v !== "" && v !== null && v !== undefined));
      await api.put("/profile/measurements", payload);
      toast.success("Misure salvate");
      setAccuracyNonce((n) => n + 1);
    } catch {
      toast.error("Salvataggio non riuscito");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-10" data-testid="profile-root">
      <div className="lg:col-span-7">
        <div className="label-caps mb-3">La tua silhouette</div>
        <h1 className="font-serif text-4xl md:text-5xl tracking-tighter">Misure corporee</h1>
        <p className="mt-4 text-neutral-600 max-w-lg leading-relaxed">
          Numeri precisi significano vestibilità precisa. Vengono usati per generare il tuo avatar e consigliarti la taglia giusta.
        </p>

        <div className="mt-8">
          <FittingAccuracy nonce={accuracyNonce} />
        </div>

        <div className="mt-10 space-y-10">
          <div>
            <div className="label-caps mb-3">Genere</div>
            <div className="flex gap-2">
              {[
                { k: "female", l: "donna" },
                { k: "male", l: "uomo" },
                { k: "unisex", l: "unisex" },
              ].map((g) => (
                <button
                  key={g.k}
                  onClick={() => updateStr("gender", g.k)}
                  className={`px-4 py-2 label-caps border hairline transition-colors ${
                    m.gender === g.k ? "bg-[#0A0A0A] text-white border-[#0A0A0A]" : "bg-white text-[#0A0A0A] hover:border-[#0A0A0A]"
                  }`}
                  data-testid={`gender-${g.k}`}
                >
                  {g.l}
                </button>
              ))}
            </div>
          </div>

          {FIELDS.map((grp) => (
            <div key={grp.group}>
              <div className="label-caps mb-4">{grp.group}</div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {grp.items.map((f) => (
                  <label key={f.k} className="block">
                    <span className="label-caps block mb-2">{f.l}</span>
                    <div className="flex items-center border hairline focus-within:border-[#0A0A0A] transition-colors">
                      <input
                        type="number"
                        step="0.1"
                        value={m[f.k] ?? ""}
                        onChange={(e) => update(f.k, e.target.value)}
                        className="w-full px-3 py-3 bg-transparent outline-none font-serif text-xl"
                        placeholder="—"
                        data-testid={`m-${f.k}`}
                      />
                      <span className="px-3 text-xs text-neutral-500">{f.u}</span>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          ))}

          <button onClick={save} disabled={saving} className="btn-primary" data-testid="save-measurements-btn">
            {saving ? "Salvataggio..." : "Salva misure"}
          </button>

          <WeightTracker onChange={() => setAccuracyNonce((n) => n + 1)} />
        </div>
      </div>

      <div className="lg:col-span-5">
        <div className="sticky top-28">
          <div className="label-caps mb-3">Avatar in tempo reale</div>
          <div className="border hairline p-6 bg-white">
            <Avatar3D measurements={m} />
            <div className="mt-6 grid grid-cols-2 gap-3 text-sm">
              <Info label="Taglia top" value={m.chest_cm ? sizeFromChest(m.chest_cm) : "—"} />
              <Info label="Taglia bottom" value={m.waist_cm ? sizeFromWaist(m.waist_cm) : "—"} />
              <Info label="Scarpa (EU)" value={m.foot_cm ? Math.round(m.foot_cm * 1.5 + 2) : "—"} />
              <Info label="IMC" value={m.height_cm && m.weight_kg ? (m.weight_kg / ((m.height_cm/100)**2)).toFixed(1) : "—"} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Info({ label, value }) {
  return (
    <div className="border hairline p-3">
      <div className="label-caps">{label}</div>
      <div className="font-serif text-lg mt-1">{value}</div>
    </div>
  );
}

function sizeFromChest(c) {
  if (c < 84) return "XS"; if (c < 90) return "S"; if (c < 96) return "M"; if (c < 104) return "L"; if (c < 114) return "XL"; return "XXL";
}
function sizeFromWaist(w) {
  if (w < 68) return "XS"; if (w < 74) return "S"; if (w < 80) return "M"; if (w < 88) return "L"; if (w < 98) return "XL"; return "XXL";
}
