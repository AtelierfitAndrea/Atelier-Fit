import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { LinkSimple, Plus, Trash, ShoppingBag, FloppyDisk, ShareNetwork, X } from "@phosphor-icons/react";
import { api, fileUrl, basePhotoKey } from "@/lib/api";


function priceFmt(n, cur = "EUR") {
  if (n === null || n === undefined) return "—";
  try { return new Intl.NumberFormat("it-IT", { style: "currency", currency: cur }).format(n); }
  catch { return `${n} ${cur}`; }
}

export default function OutfitBuilder() {
  const [url, setUrl] = useState("");
  const [adding, setAdding] = useState(false);
  const [garments, setGarments] = useState([]);
  const [selected, setSelected] = useState([]);
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState(null);
  const [savedName, setSavedName] = useState("");

  const load = async () => {
    try { const { data } = await api.get("/wardrobe/garments"); setGarments(data || []); }
    catch (_e) { /* ignore */ }
  };
  useEffect(() => { load(); }, []);

  const addFromUrl = async () => {
    if (!/^https?:\/\//.test(url.trim())) { toast.error("Incolla un link valido"); return; }
    setAdding(true);
    try {
      await api.post("/wardrobe/garments/from-url", { url: url.trim() });
      setUrl("");
      toast.success("Capo aggiunto");
      await load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Impossibile leggere il link"); }
    finally { setAdding(false); }
  };

  const toggle = (id) => {
    setSelected((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 4) { toast.error("Massimo 4 capi"); return prev; }
      return [...prev, id];
    });
  };

  const total = useMemo(() => {
    return garments
      .filter((g) => selected.includes(g.id))
      .reduce((s, g) => s + (Number(g.price) || 0), 0);
  }, [garments, selected]);

  const canGenerate = selected.length >= 2 && selected.length <= 4;

  const removeGarment = async (id) => {
    try { await api.delete(`/wardrobe/garments/${id}`); setSelected((s) => s.filter((x) => x !== id)); await load(); }
    catch { toast.error("Errore"); }
  };

  const generate = async () => {
    if (!canGenerate) return;
    const noPhoto = garments.filter((g) => selected.includes(g.id) && !g.image_path);
    if (noPhoto.length) {
      toast.error(`Serve una foto reale del capo: ${noPhoto.map((g) => g.name).join(", ")}. Caricala nello Studio o usa un altro capo.`);
      return;
    }
    const personPath = (() => { try { return localStorage.getItem(basePhotoKey()); } catch { return null; } })();
    setGenerating(true); setResult(null);
    try {
      const { data } = await api.post("/outfit/generate", {
        garment_ids: selected,
        person_path: personPath || undefined,
      });
      setResult(data);
      setSelected([]);
      toast.success("Outfit pronto");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Generazione non riuscita");
    } finally { setGenerating(false); }
  };

  const saveOutfit = async () => {
    if (!result) return;
    const name = window.prompt("Dai un nome al tuo outfit", savedName || "Outfit multi-brand");
    if (!name) return;
    try {
      await api.post(`/outfits/${result.id}/save`, { name });
      setSavedName(name);
      toast.success("Outfit salvato");
    } catch { toast.error("Salvataggio non riuscito"); }
  };

  const shareOutfit = async () => {
    if (!result) return;
    const url = `${window.location.origin}/share/outfit/${result.id}`;
    try {
      if (navigator.share) await navigator.share({ title: "Il mio outfit Atelier Fit", url });
      else { await navigator.clipboard.writeText(url); toast.success("Link copiato"); }
    } catch (_e) { /* ignore */ }
  };

  return (
    <section className="space-y-6" data-testid="outfit-builder">
      <div className="border hairline bg-white p-6 md:p-8" translate="no">
        <div className="flex items-end justify-between flex-wrap gap-4">
          <div>
            <div className="label-caps text-brand">Puzzle multi-brand</div>
            <h2 className="font-serif text-3xl md:text-4xl tracking-tighter leading-[1] mt-1">
              Crea il mio outfit
            </h2>
            <p className="text-sm text-neutral-600 mt-2">
              Aggiungi capi da Zara, Amazon, Shein, Zalando. Combina 2–4 pezzi e provali tutti insieme in un'unica foto.
            </p>
          </div>
        </div>

        <div className="mt-5 flex flex-col md:flex-row gap-3">
          <div className="flex-1 flex items-center border hairline focus-within:border-brand transition-colors">
            <LinkSimple size={16} weight="bold" className="ml-3 text-neutral-500" />
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") addFromUrl(); }}
              placeholder="Incolla link capo (Zara, Amazon, Shein, Zalando…)"
              className="w-full px-3 py-4 bg-transparent outline-none font-serif text-lg"
              data-testid="outfit-url-input"
            />
          </div>
          <button onClick={addFromUrl} disabled={adding} className="btn-brand" data-testid="outfit-add-cta">
            {adding ? "Aggiungo…" : (<><Plus size={14} weight="bold" /> Aggiungi al tuo armadio</>)}
          </button>
        </div>
      </div>

      {garments.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4" data-testid="outfit-garments-grid">
          {garments.map((g) => {
            const active = selected.includes(g.id);
            return (
              <div
                key={g.id}
                onClick={() => toggle(g.id)}
                className={`relative border p-3 cursor-pointer transition-all ${active ? "border-brand ring-2 ring-[color:var(--vfit-brand)]" : "hairline hover:border-[#0A0A0A]"}`}
                data-testid={`garment-card-${g.id}`}
              >
                <div className="absolute top-3 left-3 z-10">
                  <span className={`inline-flex items-center justify-center w-5 h-5 border ${active ? "bg-brand border-brand text-white" : "bg-white hairline"}`}>
                    {active && <span className="text-xs">✓</span>}
                  </span>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); removeGarment(g.id); }}
                  className="absolute top-3 right-3 z-10 text-neutral-400 hover:text-[#0A0A0A] bg-white/80 p-1"
                  data-testid={`garment-del-${g.id}`}
                >
                  <Trash size={14} weight="bold" />
                </button>
                <div className="relative overflow-hidden" style={{ aspectRatio: "3/4" }}>
                  {g.image_path ? (
                    <img src={fileUrl(g.image_path)} alt="" className="absolute inset-0 w-full h-full object-cover" />
                  ) : (
                    <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-neutral-100 text-neutral-500" data-testid={`garment-placeholder-${g.id}`}>
                      <ShoppingBag size={32} weight="duotone" />
                      <span className="label-caps">Foto non disponibile</span>
                    </div>
                  )}
                </div>
                <div className="mt-3" translate="no">
                  <div className="label-caps">{g.brand}</div>
                  <div className="font-serif text-base truncate">{g.name}</div>
                  <div className="text-sm text-neutral-700 mt-1">{priceFmt(g.price, g.currency)}</div>
                  {g.source_url && (
                    <a href={g.source_url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}
                      className="text-xs underline text-neutral-500 hover:text-[#0A0A0A]" data-testid={`garment-link-${g.id}`}>
                      Vedi prodotto
                    </a>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {selected.length >= 1 && (
        <div
          className="sticky bottom-4 z-30 mx-auto max-w-3xl bg-brand text-white border-brand border px-5 py-4 flex items-center justify-between gap-4 shadow-xl"
          data-testid="outfit-sticky-bar"
          translate="no"
        >
          <div>
            <div className="label-caps !text-white/70">Outfit in costruzione</div>
            <div className="font-serif text-lg">{selected.length} {selected.length === 1 ? "capo" : "capi"} · {priceFmt(total)}</div>
          </div>
          <button
            onClick={generate}
            disabled={!canGenerate || generating}
            className="bg-white text-[#0A0A0A] px-5 py-3 label-caps hover:bg-[#F4F0FA] transition-colors disabled:opacity-60"
            data-testid="outfit-generate-cta"
          >
            {generating ? "Monto il look…" : `Prova outfit completo (${selected.length})`}
          </button>
        </div>
      )}

      {generating && !result && (
        <div className="border hairline p-10 text-center bg-white" data-testid="outfit-generating">
          <div className="label-caps text-brand">Puzzle multi-brand</div>
          <h3 className="font-serif text-2xl mt-2">Sto vestendo te con questi {selected.length || "…"} capi</h3>
          <p className="text-neutral-500 mt-2 text-sm">Richiede ~30 secondi. Niente modelli stock, solo tu.</p>
          <div className="mt-5 h-1 w-full bg-neutral-100 overflow-hidden">
            <div className="h-full w-1/3 bg-brand animate-pulse" />
          </div>
        </div>
      )}

      {result && <OutfitResult result={result} onSave={saveOutfit} onShare={shareOutfit} onClose={() => setResult(null)} />}
    </section>
  );
}

function OutfitResult({ result, onSave, onShare, onClose }) {
  const total = result.total_price ?? result.items.reduce((s, it) => s + (Number(it.price) || 0), 0);
  return (
    <section className="grid grid-cols-1 lg:grid-cols-12 gap-6 fade-up" data-testid="outfit-result" translate="no">
      <div className="lg:col-span-7 relative border hairline bg-black">
        <button onClick={onClose} className="absolute top-3 right-3 z-10 bg-white/90 p-2" data-testid="outfit-result-close">
          <X size={16} weight="bold" />
        </button>
        <img src={fileUrl(result.result_path)} alt="" className="w-full h-auto block" data-testid="outfit-result-image" />
      </div>
      <div className="lg:col-span-5 border hairline bg-white p-6 md:p-8 flex flex-col">
        <div className="label-caps text-brand">Il tuo outfit</div>
        <h3 className="font-serif text-3xl md:text-4xl tracking-tighter mt-1">
          {result.items.length} capi, 1 look
        </h3>
        <div className="mt-6 space-y-3">
          {result.items.map((it) => (
            <div key={it.garment_id} className="flex items-center gap-3 border hairline p-3">
              <div className="w-14 h-18 overflow-hidden shrink-0" style={{ aspectRatio: "3/4" }}>
                <img src={fileUrl(it.image_path)} alt="" className="w-full h-full object-cover" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="label-caps">{it.brand}</div>
                <div className="font-serif text-base truncate">{it.name}</div>
                <div className="text-xs text-neutral-500">{priceFmt(it.price, it.currency)}</div>
              </div>
              {it.source_url && (
                <a
                  href={it.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-brand !px-3 !py-2 !text-[10px]"
                  data-testid={`buy-${it.garment_id}`}
                >
                  <ShoppingBag size={12} weight="bold" /> Compra su {it.brand}
                </a>
              )}
            </div>
          ))}
        </div>
        <div className="mt-6 flex items-center justify-between border-t hairline pt-5">
          <div>
            <div className="label-caps">Totale outfit</div>
            <div className="font-serif text-3xl">{priceFmt(total)}</div>
          </div>
          <div className="flex gap-2">
            <button onClick={onSave} className="btn-ghost" data-testid="outfit-save-btn">
              <FloppyDisk size={14} weight="bold" /> Salva
            </button>
            <button onClick={onShare} className="btn-brand" data-testid="outfit-share-btn">
              <ShareNetwork size={14} weight="bold" /> Condividi
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
