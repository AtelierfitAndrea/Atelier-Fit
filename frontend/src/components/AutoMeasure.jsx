import { useRef, useState } from "react";
import { toast } from "sonner";
import { CloudArrowUp, LockKey, ArrowRight } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { extractBodyRatios } from "@/lib/pose";

const POSE_ERRORS = {
  no_pose: "Non vediamo bene la tua figura. Riprova con una foto più luminosa, frontale e intera.",
  not_full_body: "Serve la foto intera: dalla testa ai piedi, ben visibili.",
};

function Step({ n, title, children }) {
  return (
    <div className="flex gap-5">
      <div className="w-8 h-8 shrink-0 border border-[#0A0A0A] flex items-center justify-center font-serif">{n}</div>
      <div className="flex-1">
        <div className="label-caps mb-3">{title}</div>
        {children}
      </div>
    </div>
  );
}

function Result({ data }) {
  const m = data.measurements;
  const rows = [["Torace", m.chest_cm], ["Vita", m.waist_cm], ["Fianchi", m.hips_cm], ["Spalle", m.shoulder_cm], ["Lunghezza gamba", m.inseam_cm]];
  return (
    <div className="mt-10 border hairline bg-white p-6" translate="no" data-testid="auto-measure-result">
      <div className="flex items-baseline justify-between flex-wrap gap-2">
        <div className="label-caps">La tua taglia per brand</div>
        <div className="text-xs text-neutral-500" data-testid="auto-measure-precision">
          Precisione stimata fino al {data.precision}% · stima AI
        </div>
      </div>
      <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 gap-3">
        {data.brand_sizes.map((b) => (
          <div key={b.brand} className="border hairline p-3" data-testid={`brand-size-${b.brand}`}>
            <div className="label-caps">{b.brand}</div>
            <div className="font-serif text-2xl mt-1">{b.top}</div>
            <div className="text-xs text-neutral-500">Sopra {b.top} · Sotto {b.bottom}</div>
          </div>
        ))}
      </div>
      <div className="mt-6 label-caps">Misure stimate</div>
      <ul className="mt-2 divide-y hairline">
        {rows.map(([l, v]) => (
          <li key={l} className="flex justify-between py-2 text-sm">
            <span>{l}</span>
            <span><span className="font-serif text-lg">{v} cm</span> <span className="text-xs text-neutral-500">±2cm stima AI</span></span>
          </li>
        ))}
      </ul>
      <p className="mt-4 text-xs text-neutral-500">
        Tabelle taglie standard indicative dei brand. Per un capo preciso usa "Calcola taglia dal link".
      </p>
    </div>
  );
}

export default function AutoMeasure({ initial = {}, onDone }) {
  const fileRef = useRef();
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [height, setHeight] = useState(initial.height_cm || "");
  const [gender, setGender] = useState(initial.gender === "male" ? "male" : "female");
  const [useWeight, setUseWeight] = useState(true);
  const [weight, setWeight] = useState(initial.weight_kg || 70);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(
    initial.method === "auto_photo" && initial.brand_sizes ? { measurements: initial, brand_sizes: initial.brand_sizes, precision: initial.precision } : null
  );

  const pick = (f) => {
    if (!f) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(f.type)) { toast.error("Usa una foto jpg, png o webp"); return; }
    setFile(f);
    setPreview(URL.createObjectURL(f));
  };

  const heightOk = Number(height) >= 120 && Number(height) <= 230;

  const calc = async () => {
    if (!file) { toast.error("Carica la tua foto intera"); return; }
    if (!heightOk) { toast.error("Inserisci l'altezza in cm (120-230)"); return; }
    setBusy(true);
    try {
      let ratios;
      try { ratios = await extractBodyRatios(file); }
      catch (e) { toast.error(POSE_ERRORS[e.message] || "Analisi della foto non riuscita, riprova"); return; }
      const params = new URLSearchParams({ height_cm: String(Number(height)), gender, features: JSON.stringify(ratios) });
      if (useWeight) params.set("weight_kg", String(weight));
      else params.set("forget_weight", "true");
      const fd = new FormData();
      fd.append("photo", file);
      const { data } = await api.post(`/profile/auto-measure?${params}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      setResult(data);
      onDone?.(data.measurements);
      toast.success("Taglia calcolata");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Calcolo non riuscito");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section translate="no" data-testid="auto-measure">
      <h2 className="font-serif text-3xl tracking-tight">Calcolo Automatico Taglia 98%</h2>
      <div className="mt-8 space-y-8">
        <Step n="1" title="Foto intera frontale">
          <p className="text-sm text-neutral-600 mb-3">Metti il telefono a terra, in piedi, braccia leggermente aperte</p>
          <div
            onClick={() => fileRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); pick(e.dataTransfer.files?.[0]); }}
            className="upload-zone cursor-pointer w-full max-w-xs relative overflow-hidden"
            style={{ aspectRatio: "3/4" }}
            data-testid="auto-measure-photo-zone"
          >
            {preview ? (
              <img src={preview} alt="" className="absolute inset-0 w-full h-full object-contain bg-neutral-50" data-testid="auto-measure-photo-preview" />
            ) : (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-neutral-400">
                <CloudArrowUp size={36} weight="thin" />
                <span className="text-xs mt-2">Carica o trascina la foto</span>
              </div>
            )}
            <input ref={fileRef} type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" className="hidden"
              onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} data-testid="auto-measure-photo-input" />
          </div>
        </Step>

        <Step n="2" title="Altezza (obbligatoria)">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center border hairline focus-within:border-[#0A0A0A] w-40">
              <input type="number" inputMode="numeric" min={120} max={230} value={height} placeholder="182"
                onChange={(e) => setHeight(e.target.value)}
                className="w-full px-3 py-3 bg-transparent outline-none font-serif text-xl" data-testid="auto-measure-height" />
              <span className="px-3 text-xs text-neutral-500">cm</span>
            </div>
            <div className="flex">
              {[["female", "Donna"], ["male", "Uomo"]].map(([k, l]) => (
                <button key={k} type="button" onClick={() => setGender(k)}
                  className={`px-4 py-3 label-caps border hairline ${gender === k ? "bg-[#0A0A0A] !text-white border-[#0A0A0A]" : "bg-white"}`}
                  data-testid={`auto-measure-gender-${k}`}>{l}</button>
              ))}
            </div>
          </div>
        </Step>

        <Step n="3" title="Peso (opzionale ma consigliato)">
          <div className="flex flex-wrap items-center gap-4">
            <input type="range" min={40} max={150} step={1} value={weight} disabled={!useWeight}
              onChange={(e) => setWeight(Number(e.target.value))}
              className="w-64 accent-[#0A0A0A] disabled:opacity-30" data-testid="auto-measure-weight" />
            <span className="font-serif text-xl w-20" data-testid="auto-measure-weight-value">{useWeight ? `${weight} kg` : "—"}</span>
            <span className="text-xs text-[#2E7D32]">Consigliato per +10% precisione</span>
          </div>
          <label className="mt-3 flex items-center gap-2 text-xs text-neutral-500 cursor-pointer">
            <input type="checkbox" checked={!useWeight} onChange={(e) => setUseWeight(!e.target.checked)}
              className="accent-[#0A0A0A]" data-testid="auto-measure-no-weight" />
            Preferisco non indicare il peso
          </label>
        </Step>
      </div>

      <button onClick={calc} disabled={busy}
        className="mt-10 w-full bg-[#0A0A0A] !text-white py-5 label-caps text-sm flex items-center justify-center gap-2 hover:bg-neutral-800 transition-colors disabled:opacity-60"
        data-testid="auto-measure-submit">
        {busy ? "Sto prendendo le misure…" : (<>CALCOLA LA MIA TAGLIA AL 98% <ArrowRight size={16} weight="bold" /></>)}
      </button>

      <p className="mt-4 flex items-start gap-2 text-xs text-neutral-500 leading-relaxed" data-testid="auto-measure-privacy">
        <LockKey size={14} className="shrink-0 mt-0.5" aria-hidden="true" />
        I tuoi dati sono solo tuoi. Foto, altezza e peso sono criptati, privati e visibili solo dal tuo account. Non li mostriamo a nessuno, mai. In futuro potremo condividere con i brand solo statistiche anonime e aggregate, mai i tuoi dati personali.
      </p>

      {result && <div className={busy ? "opacity-40 pointer-events-none transition-opacity" : "transition-opacity"}><Result data={result} /></div>}
    </section>
  );
}
