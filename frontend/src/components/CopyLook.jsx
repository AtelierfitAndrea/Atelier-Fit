import { useRef, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import { UserFocus, Scissors, ArrowRight, BookmarkSimple, Check } from "@phosphor-icons/react";
import { api, fileUrl } from "@/lib/api";
import { useSubscription } from "@/lib/subscription";
import TryOnProgress from "@/components/TryOnProgress";
import { notifyTabReady } from "@/lib/tabNotify";
import { priceFmt } from "@/components/OutfitGrid";
import { LookPrice } from "@/components/ModelLooks";
import { postRender } from "@/lib/renderJob";

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
      const { data } = await postRender("/copylook/apply", { model_path: model.path, items: chosen });
      toast.success("Look copiato sul tuo Avatar"); notifyTabReady(); refresh(); setPhase("idle");
      await new Promise((r) => setTimeout(r, 800));
      navigate(`/tryon/${data.id}`, { state: { fresh: true } });
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

// "Salva link outfit modello": ONE link for the whole look; the isolated garments inherit it, saved as "Totale Look Modello".
function ModelLinks({ items, linked, setLinked, modelPath }) {
  const [url, setUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const look = linked.look;
  const save = async (e) => {
    e.preventDefault();
    if (!url.trim() || !modelPath) return;
    setSaving(true);
    try {
      const chosen = items.filter((it) => it.image_path).map(({ image_path, name, category }) => ({ image_path, name, category }));
      const { data } = await api.post("/wardrobe/looks/from-link", { model_path: modelPath, url: url.trim(), items: chosen });
      setLinked({ look: data });
      toast.success(`Look salvato nell'armadio con ${data.garments.length} capi`);
    } catch (err) { toast.error(err?.response?.data?.detail || "Salvataggio non riuscito"); }
    finally { setSaving(false); }
  };
  return (
    <div className="mt-8 border-t hairline pt-6 space-y-4" data-testid="copylook-links">
      <div>
        <div className="label-caps">Salva link outfit modello</div>
        <p className="text-xs text-neutral-500 mt-1">Incolla il link del look (es. Zalando): lo salviamo come "Totale Look Modello" con la foto del modello, e tutti i capi isolati usano lo stesso link.</p>
      </div>
      {!look ? (
        <form onSubmit={save} className="flex items-center gap-3">
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="Incolla link del look per salvare in armadio"
            className="flex-1 border hairline px-3 py-2 text-sm outline-none focus:border-[#0A0A0A]" data-testid="copylook-look-input" />
          <button type="submit" disabled={saving || !url.trim()} className="border hairline px-4 py-2 label-caps disabled:opacity-40" data-testid="copylook-look-save-btn">
            {saving ? "Leggo il link…" : "Salva"}
          </button>
        </form>
      ) : (
        <div className="border hairline p-4 space-y-2" data-testid="copylook-look-saved">
          <div className="flex items-baseline justify-between gap-3">
            <div className="label-caps">Totale Look Modello · {look.brand}</div>
            <div className="font-serif text-2xl" data-testid="copylook-look-total">{look.price != null ? priceFmt(look.price, look.currency) : "—"}</div>
          </div>
          <div className="text-sm truncate">{look.title} · {look.garments.length} capi con lo stesso link</div>
          {look.price == null && <LookPrice lookId={look.id} onSaved={(price) => setLinked({ look: { ...look, price } })} />}
          <div className="flex gap-4 text-sm">
            <a href={look.url} target="_blank" rel="noopener noreferrer" className="underline hover:text-[#8C7355]" data-testid="copylook-look-buy">Acquista</a>
            <Link to="/wardrobe" className="underline hover:text-[#8C7355]" data-testid="copylook-look-link">Vedi il look completo nell'armadio</Link>
          </div>
        </div>
      )}
    </div>
  );
}
