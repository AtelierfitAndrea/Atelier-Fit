import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Trash } from "@phosphor-icons/react";
import { api, fileUrl } from "@/lib/api";
import { priceFmt } from "@/components/OutfitGrid";

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
        {looks.map((lk) => <LookCard key={lk.id} look={lk} onRemove={() => remove(lk.id)} />)}
      </div>
    </section>
  );
}

function LookCard({ look, onRemove }) {
  return (
    <article className="border hairline bg-white flex fade-up" data-testid={`model-look-${look.id}`}>
      <img src={fileUrl(look.model_path)} alt="Look del modello" className="w-2/5 shrink-0 object-cover bg-neutral-50" style={{ aspectRatio: "3/4" }} />
      <div className="flex-1 min-w-0 p-4 flex flex-col">
        <div className="flex items-baseline justify-between gap-2">
          <div className="label-caps">{look.garments.length} capi</div>
          <div className="font-serif text-2xl" data-testid={`model-look-total-${look.id}`}>{look.total != null ? priceFmt(look.total, look.currency) : "—"}</div>
        </div>
        {look.priced_count < look.garments.length && <div className="text-xs text-neutral-500">Alcuni capi senza prezzo</div>}
        <ul className="mt-3 space-y-2 flex-1">
          {look.garments.map((g) => (
            <li key={g.id} className="flex items-center gap-2 text-sm">
              {g.image_path && <img src={fileUrl(g.image_path)} alt="" className="w-9 h-9 object-contain bg-neutral-50 border hairline shrink-0" />}
              <span className="flex-1 min-w-0 truncate">{g.name} · {g.brand}</span>
              <a href={g.source_url} target="_blank" rel="noopener noreferrer" className="underline hover:text-[#8C7355] shrink-0" data-testid={`model-look-buy-${g.id}`}>
                {g.price != null ? priceFmt(g.price, g.currency) : "Acquista"}
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
