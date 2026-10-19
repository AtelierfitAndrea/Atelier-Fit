import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import Avatar3D from "@/components/Avatar3D";
import WeightTracker from "@/components/WeightTracker";
import FittingAccuracy from "@/components/FittingAccuracy";
import MeasureResult from "@/components/AutoMeasure";
import MeasuresForm from "@/components/MeasuresForm";

const INCOMPLETE = "Completa le tue misure";

export default function Profile() {
  const [m, setM] = useState({ gender: "female" });
  const [nonce, setNonce] = useState(0);

  const load = () => api.get("/profile/measurements").then(({ data }) => setM({ gender: "female", ...(data || {}) })).catch(() => {});
  useEffect(() => { window.scrollTo(0, 0); load(); }, []);

  const std = m.complete ? m.brand_sizes?.find((b) => b.brand === "H&M") : null;
  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-10" data-testid="profile-root">
      <div className="lg:col-span-7">
        <div className="label-caps mb-3">Le tue misure</div>
        <h1 className="font-serif text-4xl md:text-5xl tracking-tighter leading-[1.05]" data-testid="profile-title">Dacci le tue misure reali, le salviamo noi per te!</h1>
        <p className="mt-4 text-neutral-600 max-w-lg leading-relaxed">
          Restano salvate sul tuo account per sempre. La taglia per ogni brand è calcolata solo da queste misure.
        </p>
        <p className="mt-2 text-sm text-neutral-500" data-testid="profile-avatar-note">La foto avatar serve solo per la prova vestiti</p>

        <div className="mt-8"><FittingAccuracy nonce={nonce} /></div>
        <div className="mt-10 space-y-10">
          <MeasuresForm onSaved={() => { load(); setNonce((n) => n + 1); }} />
          {m.complete && m.brand_sizes ? (
            <MeasureResult data={{ brand_sizes: m.brand_sizes }} />
          ) : (
            <div className="border hairline p-6 bg-white" data-testid="profile-incomplete">
              <div className="font-serif text-xl">{INCOMPLETE}</div>
              <p className="text-sm text-neutral-600 mt-1">Compila i 7 campi obbligatori: poi ti indichiamo la taglia per ogni brand.</p>
            </div>
          )}
          <WeightTracker key={nonce} onChange={() => { load(); setNonce((n) => n + 1); }} />
        </div>
      </div>

      <div className="lg:col-span-5">
        <div className="sticky top-28">
          <div className="label-caps mb-3">La tua silhouette</div>
          <div className="border hairline p-6 bg-white">
            <Avatar3D measurements={m} />
            <div className="mt-6 grid grid-cols-2 gap-3 text-sm">
              <Info label="Taglia top" value={std?.top || INCOMPLETE} testid="profile-size-top" />
              <Info label="Taglia bottom" value={std?.bottom || INCOMPLETE} testid="profile-size-bottom" />
              <Info label="Scarpe (EU)" value={std?.shoes || INCOMPLETE} testid="profile-size-shoes" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Info({ label, value, testid }) {
  return (
    <div className="border hairline p-3" data-testid={testid}>
      <div className="label-caps">{label}</div>
      <div className={`font-serif mt-1 ${value === INCOMPLETE ? "text-sm text-neutral-500" : "text-lg"}`}>{value}</div>
    </div>
  );
}
