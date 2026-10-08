import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import Avatar3D from "@/components/Avatar3D";
import WeightTracker from "@/components/WeightTracker";

const FIELDS = [
  { group: "Upper", items: [
    { k: "height_cm", l: "Height", u: "cm" },
    { k: "shoulder_cm", l: "Shoulder", u: "cm" },
    { k: "chest_cm", l: "Chest", u: "cm" },
  ]},
  { group: "Lower", items: [
    { k: "waist_cm", l: "Waist", u: "cm" },
    { k: "hips_cm", l: "Hips", u: "cm" },
    { k: "inseam_cm", l: "Inseam", u: "cm" },
  ]},
  { group: "Other", items: [
    { k: "weight_kg", l: "Weight", u: "kg" },
    { k: "foot_cm", l: "Foot length", u: "cm" },
  ]},
];

export default function Profile() {
  const [m, setM] = useState({ gender: "female" });
  const [saving, setSaving] = useState(false);

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
      toast.success("Measurements saved");
    } catch {
      toast.error("Could not save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-10" data-testid="profile-root">
      <div className="lg:col-span-7">
        <div className="label-caps mb-3">Your silhouette</div>
        <h1 className="font-serif text-4xl md:text-5xl tracking-tighter">Body measurements</h1>
        <p className="mt-4 text-neutral-600 max-w-lg leading-relaxed">
          Precise numbers mean precise fit. These are used to generate your avatar and suggest sizes.
        </p>

        <div className="mt-10 space-y-10">
          <div>
            <div className="label-caps mb-3">Gender</div>
            <div className="flex gap-2">
              {["female", "male", "unisex"].map((g) => (
                <button
                  key={g}
                  onClick={() => updateStr("gender", g)}
                  className={`px-4 py-2 label-caps border hairline transition-colors ${
                    m.gender === g ? "bg-[#0A0A0A] text-white border-[#0A0A0A]" : "bg-white text-[#0A0A0A] hover:border-[#0A0A0A]"
                  }`}
                  data-testid={`gender-${g}`}
                >
                  {g}
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
            {saving ? "Saving..." : "Save measurements"}
          </button>

          <WeightTracker />
        </div>
      </div>

      <div className="lg:col-span-5">
        <div className="sticky top-28">
          <div className="label-caps mb-3">Live avatar</div>
          <div className="border hairline p-6 bg-white">
            <Avatar3D measurements={m} />
            <div className="mt-6 grid grid-cols-2 gap-3 text-sm">
              <Info label="Suggested top" value={m.chest_cm ? sizeFromChest(m.chest_cm) : "—"} />
              <Info label="Suggested bottom" value={m.waist_cm ? sizeFromWaist(m.waist_cm) : "—"} />
              <Info label="Shoe (EU)" value={m.foot_cm ? Math.round(m.foot_cm * 1.5 + 2) : "—"} />
              <Info label="BMI" value={m.height_cm && m.weight_kg ? (m.weight_kg / ((m.height_cm/100)**2)).toFixed(1) : "—"} />
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
