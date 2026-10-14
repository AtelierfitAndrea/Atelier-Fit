import { useRef, useState } from "react";
import { toast } from "sonner";
import { CloudArrowUp, X, Check, ArrowRight } from "@phosphor-icons/react";
import { api, fileUrl } from "@/lib/api";
import { useSubscription } from "@/lib/subscription";

const SLOTS = [
  { k: "top", n: 1, l: "Maglia / Top" },
  { k: "bottom", n: 2, l: "Pantaloni / Bottom" },
  { k: "jacket", n: 3, l: "Giacca" },
  { k: "shoes", n: 4, l: "Scarpe" },
];
const ACCEPT = ["image/jpeg", "image/png", "image/webp"];

function SlotBox({ slot, item, onFile, onClear }) {
  const ref = useRef();
  const [drag, setDrag] = useState(false);
  const pick = (f) => {
    if (!f) return;
    if (!ACCEPT.includes(f.type)) { toast.error("Formato non supportato: usa jpg, png o webp"); return; }
    onFile(f);
  };
  return (
    <div
      className={`upload-zone ${drag ? "active" : ""} relative p-3 flex flex-col cursor-pointer`}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files?.[0]); }}
      onClick={() => ref.current?.click()}
      data-testid={`grid-slot-${slot.k}`}
    >
      <input ref={ref} type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" className="hidden"
        onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} data-testid={`grid-slot-${slot.k}-input`} />
      <div className="flex items-center justify-between">
        <div className="label-caps">{slot.n}) {slot.l}</div>
        {item && (
          <button onClick={(e) => { e.stopPropagation(); onClear(); }} className="text-neutral-500 hover:text-[#0A0A0A]"
            data-testid={`grid-slot-${slot.k}-clear`} aria-label="Rimuovi">
            <X size={14} />
          </button>
        )}
      </div>
      <div className="mt-2 relative overflow-hidden" style={{ aspectRatio: "1/1" }}>
        {item?.preview ? (
          <img src={item.preview} alt="" className="absolute inset-0 w-full h-full object-contain bg-neutral-50" />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-neutral-400 text-center px-2">
            <CloudArrowUp size={30} weight="thin" />
            <div className="text-xs mt-2">{item?.uploading ? "Caricamento…" : "Trascina screenshot o clicca"}</div>
          </div>
        )}
      </div>
    </div>
  );
}

function SaveLinkRow({ slot, item }) {
  const [url, setUrl] = useState("");
  const [state, setState] = useState("idle");
  const save = async (e) => {
    e.preventDefault();
    if (!url.trim()) return;
    setState("saving");
    try {
      await api.post("/wardrobe/garments/from-screenshot", { image_path: item.path, url: url.trim(), slot: slot.k });
      setState("saved");
      toast.success(`${slot.l} salvato nell'armadio`);
    } catch (err) {
      setState("idle");
      toast.error(err?.response?.data?.detail || "Salvataggio non riuscito");
    }
  };
  return (
    <form onSubmit={save} className="flex items-center gap-3" data-testid={`grid-save-${slot.k}`}>
      <img src={item.preview} alt="" className="w-12 h-12 object-contain bg-neutral-50 border hairline shrink-0" />
      <div className="flex-1">
        <div className="label-caps mb-1">{slot.l}</div>
        <input value={url} onChange={(e) => setUrl(e.target.value)} disabled={state === "saved"}
          placeholder="Incolla link per salvare in armadio"
          className="w-full border hairline px-3 py-2 text-sm outline-none focus:border-[#0A0A0A]"
          data-testid={`grid-save-${slot.k}-input`} />
      </div>
      <button type="submit" disabled={state !== "idle" || !url.trim()}
        className="self-end border hairline px-3 py-2 label-caps disabled:opacity-40" data-testid={`grid-save-${slot.k}-btn`}>
        {state === "saved" ? <Check size={14} /> : state === "saving" ? "…" : "Salva"}
      </button>
    </form>
  );
}

export default function OutfitGrid({ personPath, uploadFile }) {
  const { status, openPaywall, refresh } = useSubscription();
  const [items, setItems] = useState({});
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState(null);

  const setSlot = async (k, file) => {
    const preview = URL.createObjectURL(file);
    setItems((s) => ({ ...s, [k]: { preview, uploading: true } }));
    try {
      const path = await uploadFile(file, "garment");
      setItems((s) => ({ ...s, [k]: { preview, path } }));
    } catch {
      setItems((s) => { const n = { ...s }; delete n[k]; return n; });
      toast.error("Caricamento non riuscito");
    }
  };
  const clearSlot = (k) => setItems((s) => { const n = { ...s }; delete n[k]; return n; });

  const ready = SLOTS.filter((s) => items[s.k]?.path);
  const busy = SLOTS.some((s) => items[s.k]?.uploading);

  const generate = async () => {
    if (!personPath) { toast.error("Carica prima la tua foto in \"La tua foto\""); return; }
    if (!ready.length) { toast.error("Carica almeno 1 capo"); return; }
    if (status?.is_blocked) { openPaywall(); return; }
    setGenerating(true);
    setResult(null);
    try {
      const { data } = await api.post("/outfit/generate-from-uploads", {
        person_path: personPath,
        items: ready.map((s) => ({ slot: s.k, image_path: items[s.k].path })),
      });
      setResult({ ...data, used: ready.map((s) => ({ slot: s, item: items[s.k] })) });
      refresh();
      toast.success("Outfit pronto");
    } catch (e) {
      if (e?.response?.status === 402) openPaywall();
      else toast.error(e?.response?.data?.detail || "Generazione non riuscita");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <section className="border hairline p-6 md:p-8 bg-white" translate="no" data-testid="outfit-grid-section">
      <h2 className="label-caps text-sm">COMPONI IL TUO OUTFIT MULTI-BRAND - FINO A 4 CAPI</h2>
      <p className="mt-2 text-sm text-neutral-600">Carica da 1 a 4 screenshot dei capi, anche di brand diversi. Usiamo la tua foto base.</p>
      <div className="mt-6 grid grid-cols-2 gap-4 max-w-xl">
        {SLOTS.map((s) => (
          <SlotBox key={s.k} slot={s} item={items[s.k]} onFile={(f) => setSlot(s.k, f)} onClear={() => clearSlot(s.k)} />
        ))}
      </div>
      <button onClick={generate} disabled={generating || busy || !ready.length}
        className="mt-6 btn-primary w-full max-w-xl justify-center disabled:opacity-50 disabled:cursor-not-allowed"
        data-testid="grid-generate-btn">
        {generating ? "Ti sto vestendo…" : (<>VESTIMI CON I CAPI SCELTI - CREA OUTFIT <ArrowRight size={16} weight="bold" /></>)}
      </button>

      {generating && (
        <div className="mt-6 max-w-xl h-1 bg-neutral-100 overflow-hidden" data-testid="grid-generating">
          <div className="h-full w-1/3 bg-[#0A0A0A] animate-pulse" />
        </div>
      )}

      {result && (
        <div className="mt-10 grid grid-cols-1 lg:grid-cols-2 gap-8" data-testid="grid-result">
          <img src={fileUrl(result.result_path)} alt="Outfit" className="w-full border hairline" data-testid="grid-result-image" />
          <div className="space-y-5">
            <div className="label-caps">Salva i capi nel tuo armadio (opzionale)</div>
            {result.used.map(({ slot, item }) => <SaveLinkRow key={slot.k} slot={slot} item={item} />)}
          </div>
        </div>
      )}
    </section>
  );
}
