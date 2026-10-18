import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import Avatar3D from "@/components/Avatar3D";
import WeightTracker from "@/components/WeightTracker";
import FittingAccuracy from "@/components/FittingAccuracy";
import MeasureResult from "@/components/AutoMeasure";
import { Link } from "react-router-dom";

export default function Profile() {
  const [m, setM] = useState({ gender: "female" });
  const [loaded, setLoaded] = useState(false);
  const [accuracyNonce, setAccuracyNonce] = useState(0);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/profile/measurements");
        if (data && Object.keys(data).length) setM({ gender: "female", ...data });
      } catch (_e) { /* ignore */ }
      setLoaded(true);
    })();
  }, []);

  // Same standard table as the brand sizes (H&M = standard, no offset).
  const std = m.brand_sizes?.find((b) => b.brand === "H&M");

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-10" data-testid="profile-root">
      <div className="lg:col-span-7">
        <div className="label-caps mb-3">La tua silhouette</div>
        <h1 className="font-serif text-4xl md:text-5xl tracking-tighter">Misure corporee</h1>
        <p className="mt-4 text-neutral-600 max-w-lg leading-relaxed">
          Calcolate in automatico dalla foto del tuo Avatar. Per cambiarla vai in Impostazioni.
        </p>

        <div className="mt-8">
          <FittingAccuracy nonce={accuracyNonce} />
        </div>

        <div className="mt-10 space-y-10">
          {loaded && (m.brand_sizes ? (
            <MeasureResult data={{ measurements: m, brand_sizes: m.brand_sizes, precision: m.precision }} />
          ) : (
            <Link to="/dashboard#il-mio-avatar" className="block border hairline p-6 bg-white hover:border-[#0A0A0A]" data-testid="profile-create-avatar">
              <div className="font-serif text-xl">Crea il tuo Avatar</div>
              <p className="text-sm text-neutral-600 mt-1">Una sola foto in Home: calcoliamo le misure in automatico.</p>
            </Link>
          ))}

          <WeightTracker onChange={() => setAccuracyNonce((n) => n + 1)} />
        </div>
      </div>

      <div className="lg:col-span-5">
        <div className="sticky top-28">
          <div className="label-caps mb-3">Avatar in tempo reale</div>
          <div className="border hairline p-6 bg-white">
            <Avatar3D measurements={m} />
            <div className="mt-6 grid grid-cols-2 gap-3 text-sm">
              <Info label="Taglia top" value={std?.top || (m.chest_cm ? sizeFromChest(m.chest_cm) : "—")} />
              <Info label="Taglia bottom" value={std?.bottom || (m.waist_cm ? sizeFromWaist(m.waist_cm) : "—")} />
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
