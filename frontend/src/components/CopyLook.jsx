import { useRef, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import { UserFocus, Scissors, ArrowRight, BookmarkSimple, Check } from "@phosphor-icons/react";
import { api, fileUrl } from "@/lib/api";
import { useSubscription } from "@/lib/subscription";
import TryOnProgress from "@/components/TryOnProgress";
import { notifyTabReady } from "@/lib/tabNotify";
import { SaveLinkRow, OutfitTotal } from "@/components/OutfitGrid";

const API_SLOT = { top: "top", bottom: "bottom", dress: "dress", outerwear: "jacket", shoes: "shoes" };
const CAT_IT = { top: "Top", bottom: "Pantaloni/Gonna", dress: "Abito", outerwear: "Capospalla", shoes: "Scarpe" };

function ItemCard({ item, selected, onToggle, onSave, saved }) {
  return (
    <div className={`border p-3 bg-white transition-colors ${selected ? "border-[#0A0A0A]" : "hairline opacity-60"}`} data-testid={`copylook-item-${item.idx}`}>
      <button type="button" onClick={onToggle} className="w-full text-left" data-testid={`copylook-item-toggle-${item.idx}`}>
        <div className="aspect-square bg-neutral-50 overflow-hidden flex items-center justify-center">
          {item.image_path ? <img src={fileUrl(item.image_path)} alt={item.name} className="w-full h-full object-contain" /> : <Scissors size={28} weight="thin" />}
        </div>
        <div className="mt-2 flex items-start justify-between gap-2">
          <div>
            <div className="text-sm font-medium leading-tight" data-testid={`copylook-item-name-${item.idx}`}>{item.name}</div>
            <div className="label-caps text-[#8C7355] mt-1">{CAT_IT[item.category] || item.category} · {item.recommended_size === "Completa le tue misure" ? item.recommended_size : `tua taglia ${item.recommended_size}`}</div>
          </div>
          <span className={`w-5 h-5 shrink-0 border flex items-center justify-center ${selected ? "bg-[#0A0A0A] text-white" : ""}`}>{selected && <Check size={12} weight="bold" />}</span>
        </div>
      </button>
      {item.image_path && (
        <button type="button" onClick={onSave} disabled={saved} className="mt-2 text-xs underline flex items-center gap-1 disabled:no-underline disabled:text-emerald-700" data-testid={`copylook-save-${item.idx}`}>
          <BookmarkSimple size={12} /> {saved ? "Salvato nell'armadio" : "Salva nell'armadio"}
        </button>
      )}
    </div>
  );
}

export default function CopyLook({ personPath, uploadFile }) {
  const { status, openPaywall, refresh } = useSubscription();
  const navigate = useNavigate();
  const ref = useRef();
  const [model, setModel] = useState(null);
  const [items, setItems] = useState([]);
  const [sel, setSel] = useState({});
  const [saved, setSaved] = useState({});
  const [phase, setPhase] = useState("idle");
  const [linked, setLinked] = useState({});

  const onFile = async (f) => {
    if (status?.is_blocked) { openPaywall(); return; }
    setModel({ preview: URL.createObjectURL(f) }); setItems([]); setSaved({}); setLinked({}); setPhase("extracting");
    try {
      const path = await uploadFile(f, "garment");
      setModel({ preview: URL.createObjectURL(f), path });
      const { data } = await api.post("/copylook/extract", { model_path: path });
      const list = data.items.map((it, idx) => ({ ...it, idx }));
      setItems(list); setSel(Object.fromEntries(list.map((i) => [i.idx, true])));
      toast.success(`${list.length} capi isolati dal modello`);
    } catch (e) {
      if (e?.response?.status === 402) openPaywall();
      else if (e?.message !== "blocked") toast.error(e?.response?.data?.detail || "Analisi non riuscita");
    } finally { setPhase("idle"); }
  };

  const save = async (it) => {
    try { await api.post("/copylook/save-garment", { image_path: it.image_path, name: it.name, category: it.category }); setSaved((s) => ({ ...s, [it.idx]: true })); toast.success("Capo salvato nell'armadio"); }
    catch { toast.error("Salvataggio non riuscito"); }
  };

  const apply = async () => {
    if (!personPath) { toast.error("Crea prima il tuo Avatar nella Home"); return; }
    if (status?.is_blocked) { openPaywall(); return; }
    setPhase("applying");
    try {
      const chosen = items.filter((i) => sel[i.idx]).map(({ name, category, image_path }) => ({ name, category, image_path }));
      const { data } = await api.post("/copylook/apply", { model_path: model.path, items: chosen });
      toast.success("Look copiato sul tuo Avatar"); notifyTabReady(); refresh(); setPhase("idle");
      await new Promise((r) => setTimeout(r, 800));
      navigate(`/tryon/${data.id}`);
    } catch (e) {
      if (e?.response?.status === 402) openPaywall(); else toast.error(e?.response?.data?.detail || "Generazione non riuscita");
    } finally { setPhase("idle"); }
  };

  const count = items.filter((i) => sel[i.idx]).length;
  return (
    <section className="border hairline p-6 md:p-8 bg-white" data-testid="copylook-section">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="label-caps mb-2">Novità</div>
          <h2 className="font-serif text-3xl tracking-tighter">Copia Look da Modello</h2>
          <p className="mt-2 text-sm text-neutral-600 max-w-xl">Carica la foto di un modello: l'AI isola i capi che indossa e li applica sul tuo Avatar con la vestibilità delle tue taglie.</p>
        </div>
        <input ref={ref} type="file" accept="image/*" className="hidden" data-testid="copylook-file-input" onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) onFile(f); }} />
        <button onClick={() => ref.current?.click()} disabled={phase !== "idle"} className="btn-primary disabled:opacity-50" data-testid="copylook-upload-btn">
          <UserFocus size={16} /> Carica foto modello
        </button>
      </div>
      {model && (
        <div className="mt-6 grid grid-cols-1 md:grid-cols-12 gap-6">
          <div className="md:col-span-3 relative border hairline overflow-hidden" style={{ aspectRatio: "3/4" }}>
            <img src={model.preview} alt="Modello" className="absolute inset-0 w-full h-full object-cover" data-testid="copylook-model-preview" />
            {phase === "extracting" && <div className="absolute inset-0 bg-white/75 flex items-center justify-center label-caps" data-testid="copylook-extracting">Isolo i capi…</div>}
          </div>
          <div className="md:col-span-9">
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3" data-testid="copylook-items">
              {items.map((it) => (
                <ItemCard key={it.idx} item={it} selected={!!sel[it.idx]} saved={!!saved[it.idx]}
                  onToggle={() => setSel((s) => ({ ...s, [it.idx]: !s[it.idx] }))} onSave={() => save(it)} />
              ))}
            </div>
            {items.length > 0 && (
              <div className="mt-5 flex items-center gap-4 flex-wrap">
                <button onClick={apply} disabled={phase !== "idle" || !count} className="btn-primary disabled:opacity-50" data-testid="copylook-apply-btn">
                  {phase === "applying" ? "Ti vesto…" : <>Applica {count} capi al mio Avatar <ArrowRight size={16} weight="bold" /></>}
                </button>
                <span className="text-xs text-neutral-500">Usa 1 prova · 20–40 secondi</span>
              </div>
            )}
            <TryOnProgress active={phase === "applying"} className="mt-5" testid="copylook-progress" />
            {items.some((it) => it.image_path) && <ModelLinks items={items} linked={linked} setLinked={setLinked} modelPath={model?.path} />}
          </div>
        </div>
      )}
    </section>
  );
}

// "Salva link outfit modello": one link per isolated garment, saved to the wardrobe with brand and price (like the outfit grid).
function ModelLinks({ items, linked, setLinked, modelPath }) {
  const rows = items.filter((it) => it.image_path).map((it) => ({
    slot: { k: `m${it.idx}`, api: API_SLOT[it.category] || "top", l: it.name, name: it.name },
    item: { path: it.image_path, preview: fileUrl(it.image_path) },
  }));
  return (
    <div className="mt-8 border-t hairline pt-6 space-y-5" data-testid="copylook-links">
      <div>
        <div className="label-caps">Salva link outfit modello</div>
        <p className="text-xs text-neutral-500 mt-1">Incolla il link di ogni capo: lo salviamo nel tuo armadio con brand e prezzo, raggruppato in un unico look completo con la foto del modello.</p>
      </div>
      {rows.map(({ slot, item }) => (
        <SaveLinkRow key={slot.k} slot={slot} item={item} prefix="copylook" saved={linked[slot.k] || null}
          extra={modelPath ? { model_path: modelPath } : undefined}
          onSaved={(g) => setLinked((m) => ({ ...m, [slot.k]: g }))} />
      ))}
      <OutfitTotal used={rows} saved={linked} prefix="copylook" title="Totale look modello" />
      {Object.values(linked).some((g) => g.look_id) && (
        <Link to="/wardrobe" className="text-sm underline hover:text-[#8C7355]" data-testid="copylook-look-link">Vedi il look completo nell'armadio</Link>
      )}
    </div>
  );
}
