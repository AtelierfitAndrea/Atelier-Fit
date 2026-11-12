import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { CloudArrowUp, X, Check, ArrowRight } from "@phosphor-icons/react";
import { api, fileUrl } from "@/lib/api";
import { useSubscription } from "@/lib/subscription";
import IncludedNote from "@/components/IncludedNote";
import HemCard from "@/components/HemCard";
import FreeRetry from "@/components/FreeRetry";
import TryOnProgress from "@/components/TryOnProgress";
import { notifyTabReady } from "@/lib/tabNotify";
import { postRender } from "@/lib/renderJob";
import SaveToGallery from "@/components/SaveToGallery";
import ShareLook from "@/components/ShareLook";
import { askBook, SaveBookBar } from "@/components/PoseBook";
import { ResultNote } from "./ResultNote";

const SLOTS = [
  { k: "top", n: 1, l: "Maglia / Top" },
  { k: "bottom", n: 2, l: "Pantaloni / Bottom" },
  { k: "jacket", n: 3, l: "Giacca" },
  { k: "shoes", n: 4, l: "Scarpe" },
  { k: "bag", n: 5, l: "Borsa" },
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

export function priceFmt(n, cur = "EUR") {
  try { return new Intl.NumberFormat("it-IT", { style: "currency", currency: cur || "EUR" }).format(n); }
  catch { return `${n} ${cur}`; }
}

export function SaveLinkRow({ slot, item, saved, onSaved, prefix = "grid", extra }) {
  const [url, setUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const save = async (e) => {
    e.preventDefault();
    if (!url.trim()) return;
    setSaving(true);
    try {
      const { data } = await api.post("/wardrobe/garments/from-screenshot", { image_path: item.path, url: url.trim(), slot: slot.api || slot.k, name: slot.name, ...extra });
      onSaved(data);
      toast.success(`${slot.l} salvato nell'armadio`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Salvataggio non riuscito");
    } finally {
      setSaving(false);
    }
  };
  return (
    <form onSubmit={save} className="flex items-center gap-3" data-testid={`${prefix}-save-${slot.k}`}>
      <img src={item.preview} alt="" className="w-12 h-12 object-contain bg-neutral-50 border hairline shrink-0" />
      <div className="flex-1">
        <div className="label-caps mb-1">{slot.l}</div>
        {saved ? (
          <div className="text-sm text-[#2E7D32]" data-testid={`${prefix}-save-${slot.k}-done`}>
            Salvato · {saved.brand} — {saved.price != null ? priceFmt(saved.price, saved.currency) : "prezzo non disponibile"}
          </div>
        ) : (
          <input value={url} onChange={(e) => setUrl(e.target.value)}
            placeholder="Incolla link per salvare in armadio"
            className="w-full border hairline px-3 py-2 text-sm outline-none focus:border-[#0A0A0A]"
            data-testid={`${prefix}-save-${slot.k}-input`} />
        )}
      </div>
      {!saved && (
        <button type="submit" disabled={saving || !url.trim()}
          className="self-end border hairline px-3 py-2 label-caps disabled:opacity-40" data-testid={`${prefix}-save-${slot.k}-btn`}>
          {saving ? "…" : "Salva"}
        </button>
      )}
      {saved && <Check size={16} className="text-[#2E7D32]" />}
    </form>
  );
}

export function OutfitTotal({ used, saved, prefix = "grid", title = "Totale outfit" }) {
  const rows = used.map(({ slot }) => ({ slot, g: saved[slot.k] })).filter((r) => r.g);
  if (!rows.length) return null;
  const priced = rows.filter((r) => r.g.price != null);
  const total = priced.reduce((sum, r) => sum + Number(r.g.price), 0);
  const currency = priced[0]?.g.currency || "EUR";
  return (
    <div className="border-t hairline pt-5" data-testid={`${prefix}-total`}>
      <div className="flex items-baseline justify-between">
        <div className="label-caps">{title}</div>
        <div className="font-serif text-2xl" data-testid={`${prefix}-total-price`}>{priced.length ? priceFmt(total, currency) : "—"}</div>
      </div>
      {priced.length < rows.length && (
        <div className="text-xs text-neutral-500 mt-1">Alcuni capi hanno prezzo non disponibile</div>
      )}
      <ul className="mt-3 space-y-2">
        {rows.map(({ slot, g }) => (
          <li key={slot.k} className="flex items-center justify-between text-sm">
            <span>{slot.l} · {g.brand}</span>
            <a href={g.source_url} target="_blank" rel="noopener noreferrer" className="underline hover:text-[#8C7355]"
              data-testid={`${prefix}-buy-${slot.k}`}>
              Acquista {g.price != null ? `— ${priceFmt(g.price, g.currency)}` : ""}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function OutfitGrid({ personPath, preservePose = false, uploadFile, restoreItems, onItemsChange, onGenerated }) {
  const { status, openPaywall, refresh } = useSubscription();
  const [items, setItems] = useState({});

  useEffect(() => {
    if (restoreItems?.length) setItems(Object.fromEntries(restoreItems.map((i) => [i.id, { preview: fileUrl(i.image), path: i.image }])));
  }, [restoreItems]);
  useEffect(() => {
    onItemsChange?.(SLOTS.filter((s) => items[s.k]?.path).map((s) => ({ id: s.k, image: items[s.k].path, link: null, brand: null })));
  }, [items]); // eslint-disable-line react-hooks/exhaustive-deps
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState(null);
  const [savedBySlot, setSavedBySlot] = useState({});

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
  const changed = !!result && (ready.length !== result.used.length
    || result.used.some(({ slot, item }) => items[slot.k]?.path !== item.path));
  // Saved wardrobe info only applies while the slot still holds the same screenshot.
  const savedFor = (k) => (savedBySlot[k] && savedBySlot[k].path === items[k]?.path ? savedBySlot[k].garment : null);
  const savedMap = Object.fromEntries(SLOTS.map((s) => [s.k, savedFor(s.k)]).filter(([, g]) => g));
  const busy = SLOTS.some((s) => items[s.k]?.uploading);

  const generate = async () => {
    if (!personPath) { toast.error(preservePose ? "Scatta o carica prima la tua foto in posa" : "Crea prima il tuo Avatar nella Home"); return; }
    if (!ready.length) { toast.error("Carica almeno 1 capo"); return; }
    if (status?.is_blocked) { openPaywall(); return; }
    setGenerating(true);
    setResult(null);
    try {
      const { data } = await postRender("/outfit/generate-from-uploads", {
        person_path: personPath,
        preserve_pose: preservePose,
        items: ready.map((s) => ({ slot: s.k, image_path: items[s.k].path })),
      });
      setResult({ ...data, used: ready.map((s) => ({ slot: s, item: items[s.k] })) });
      askBook("outfit", data.id);
      refresh();
      onGenerated?.();
      notifyTabReady();
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
      <h2 className="label-caps text-sm">COMPONI IL TUO OUTFIT MULTI-BRAND - FINO A 4 CAPI + BORSA</h2>
      <p className="mt-2 text-sm text-neutral-600">Carica da 1 a 4 screenshot dei capi, anche di brand diversi, e se vuoi la tua borsa da qualsiasi sito. Usiamo la tua foto base.</p>
      <div className="mt-6 grid grid-cols-2 gap-4 max-w-xl">
        {SLOTS.map((s) => (
          <div key={s.k} className={s.k === "bag" ? "col-span-2 w-1/2 justify-self-center" : ""}>
            <SlotBox slot={s} item={items[s.k]} onFile={(f) => setSlot(s.k, f)} onClear={() => clearSlot(s.k)} />
          </div>
        ))}
      </div>
      <button onClick={generate} disabled={generating || busy || !ready.length}
        className="mt-6 btn-primary w-full max-w-xl justify-center disabled:opacity-50 disabled:cursor-not-allowed"
        data-testid="grid-generate-btn">
        {generating ? "Ti sto vestendo…" : changed
          ? (<>RIGENERA OUTFIT CON IL CAPO NUOVO <ArrowRight size={16} weight="bold" /></>)
          : (<>VESTIMI CON I CAPI SCELTI - CREA OUTFIT <ArrowRight size={16} weight="bold" /></>)}
      </button>
      <IncludedNote className="mt-2" testid="included-note-grid" />
      {result && !changed && (
        <p className="mt-2 text-xs text-neutral-500" data-testid="grid-retry-hint">
          Vuoi cambiare un capo? Clicca il suo riquadro, carica il nuovo screenshot e rigenera: gli altri restano.
        </p>
      )}

      <TryOnProgress active={generating} className="mt-6 max-w-xl" testid="grid-generating" />

      {result && (
        <div className="mt-10 grid grid-cols-1 lg:grid-cols-2 gap-8" data-testid="grid-result">
          <div className="space-y-4">
            <img src={fileUrl(result.result_path)} alt="Outfit" className="w-full border hairline" data-testid="grid-result-image" />
            <ResultNote testid="grid-result-note" />
            <SaveBookBar kind="outfit" refId={result.id} />
            <SaveToGallery path={result.result_path} />
            <ShareLook path={result.result_path} />
            <HemCard url={`/outfits/${result.id}/hem`} />
            <FreeRetry kind="outfits" item={result} onDone={(d) => setResult((r) => ({ ...r, ...d, used: r.used }))} />
          </div>
          <div className="space-y-5">
            <div className="label-caps">Salva i capi nel tuo armadio (opzionale)</div>
            {result.used.map(({ slot, item }) => (
              <SaveLinkRow key={`${slot.k}-${item.path}`} slot={slot} item={item} saved={savedMap[slot.k] && savedBySlot[slot.k].path === item.path ? savedMap[slot.k] : null}
                onSaved={(g) => setSavedBySlot((m) => ({ ...m, [slot.k]: { path: item.path, garment: g } }))} />
            ))}
            <OutfitTotal used={result.used} saved={savedMap} />
          </div>
        </div>
      )}
    </section>
  );
}
