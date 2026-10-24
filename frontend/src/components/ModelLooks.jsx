import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Trash } from "@phosphor-icons/react";
import { api, fileUrl } from "@/lib/api";
import { priceFmt } from "@/components/OutfitGrid";

// Manual price when the shop blocks automatic reading.
export function LookPrice({ lookId, onSaved }) {
  const [v, setV] = useState("");
  const save = async (e) => {
    e.preventDefault();
    const price = parseFloat(v.replace(",", "."));
    if (!(price > 0)) { toast.error("Inserisci un prezzo valido"); return; }
    try { await api.put(`/wardrobe/looks/${lookId}/price`, { price }); onSaved(price); toast.success("Prezzo salvato"); }
    catch { toast.error("Non riuscito, riprova"); }
  };
  return (
    <form onSubmit={save} className="flex items-center gap-2" data-testid={`look-price-form-${lookId}`}>
      <span className="text-xs text-neutral-500">Il sito non mostra il prezzo:</span>
      <input value={v} onChange={(e) => setV(e.target.value)} inputMode="decimal" placeholder="Prezzo €"
        className="w-24 border hairline px-2 py-1 text-sm outline-none focus:border-[#0A0A0A]" data-testid={`look-price-input-${lookId}`} />
      <button type="submit" className="border hairline px-3 py-1 label-caps" data-testid={`look-price-save-${lookId}`}>Salva</button>
    </form>
  );
}

// "Look completi": garments saved from Copia Look grouped under the model photo, with total and buy links.
export default function ModelLooks() {
  const [looks, setLooks] = useState([]);
  useEffect(() => { api.get("/wardrobe/looks").then(({ data }) => setLooks(data || [])).catch(() => {}); }, []);
  if (!looks.length) return null;

  const remove = async (id) => {
    try { await api.delete(`/wardrobe/looks/${id}`); setLooks((l) => l.filter((x) => x.id !== id)); toast.success("Look rimosso, i capi restano nell'armadio"); }
    catch { toast.error("Non riuscito, riprova"); }
  };

  return (
    <section data-testid="model-looks">
      <div className="label-caps mb-2">Da Copia Look</div>
      <h2 className="font-serif text-3xl tracking-tighter mb-6">Look completi</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {looks.map((lk) => <LookCard key={lk.id} look={lk} onRemove={() => remove(lk.id)}
          onPrice={(price) => setLooks((l) => l.map((x) => (x.id === lk.id ? { ...x, total: price, priced_count: x.garments.length } : x)))} />)}
      </div>
    </section>
  );
}

function LookCard({ look, onRemove, onPrice }) {
  return (
    <article className="border hairline bg-white flex fade-up" data-testid={`model-look-${look.id}`}>
      <img src={fileUrl(look.model_path)} alt="Look del modello" className="w-2/5 shrink-0 object-cover bg-neutral-50" style={{ aspectRatio: "3/4" }} />
      <div className="flex-1 min-w-0 p-4 flex flex-col">
        <div className="flex items-baseline justify-between gap-2">
          <div className="label-caps truncate">{look.url ? `Totale Look Modello · ${look.brand}` : `${look.garments.length} capi`}</div>
          <div className="font-serif text-2xl" data-testid={`model-look-total-${look.id}`}>{look.total != null ? priceFmt(look.total, look.currency) : "—"}</div>
        </div>
        {look.url && <div className="text-sm truncate mt-1">{look.title}</div>}
        {look.url && look.total == null && <div className="mt-2"><LookPrice lookId={look.id} onSaved={onPrice} /></div>}
        {!look.url && look.priced_count < look.garments.length && <div className="text-xs text-neutral-500">Alcuni capi senza prezzo</div>}
        <ul className="mt-3 space-y-2 flex-1">
          {look.garments.map((g) => (
            <li key={g.id} className="flex items-center gap-2 text-sm">
              {g.image_path && <img src={fileUrl(g.image_path)} alt="" className="w-9 h-9 object-contain bg-neutral-50 border hairline shrink-0" />}
              <span className="flex-1 min-w-0 truncate">{g.name} · {g.brand}</span>
              <a href={g.source_url} target="_blank" rel="noopener noreferrer" className="underline hover:text-[#8C7355] shrink-0" data-testid={`model-look-buy-${g.id}`}>
                {g.price != null ? priceFmt(g.price, g.currency) : look.url ? "Link look" : "Acquista"}
              </a>
            </li>
          ))}
        </ul>
        <button onClick={onRemove} className="mt-3 self-start text-xs text-neutral-500 hover:text-[#B91C1C] flex items-center gap-1" data-testid={`model-look-remove-${look.id}`}>
          <Trash size={12} /> Rimuovi look
        </button>
      </div>
    </article>
  );
}
