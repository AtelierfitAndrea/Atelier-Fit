import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, fileUrl } from "@/lib/api";
import { TShirt } from "@phosphor-icons/react";

const FILTERS = ["all", "top", "bottom", "dress", "outerwear", "shoes"];

export default function Wardrobe() {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    (async () => {
      try { const { data } = await api.get("/tryons"); setItems(data || []); } catch (_e) { /* ignore */ }
    })();
  }, []);

  const filtered = useMemo(() =>
    filter === "all" ? items : items.filter((i) => (i.garment_category || "") === filter),
  [items, filter]);

  return (
    <div className="space-y-8" data-testid="wardrobe-root">
      <header className="flex items-end justify-between flex-wrap gap-6">
        <div>
          <div className="label-caps mb-3">Atelier Fit</div>
          <h1 className="font-serif text-4xl md:text-5xl tracking-tighter">Il tuo armadio</h1>
          <p className="mt-3 text-neutral-600">Ogni prova, salvata com'era. {items.length} capi.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-2 label-caps border hairline transition-colors ${
                filter === f ? "bg-[#0A0A0A] text-white border-[#0A0A0A]" : "hover:border-[#0A0A0A]"
              }`}
              data-testid={`filter-${f}`}
            >
              {f}
            </button>
          ))}
        </div>
      </header>

      {filtered.length === 0 ? (
        <div className="border hairline p-16 text-center" data-testid="wardrobe-empty">
          <TShirt size={44} weight="duotone" className="mx-auto text-neutral-400" />
          <div className="label-caps mt-4">Niente qui</div>
          <p className="text-neutral-500 mt-2">Nessun capo in questa categoria.</p>
          <Link to="/studio" className="btn-primary mt-6 inline-flex">Apri la prova taglia</Link>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {filtered.map((t) => (
            <Link
              key={t.id}
              to={`/tryon/${t.id}`}
              className="group block relative overflow-hidden border hairline fade-up"
              style={{ aspectRatio: "3/4" }}
              data-testid={`wardrobe-item-${t.id}`}
            >
              <img src={fileUrl(t.result_path)} alt="" className="absolute inset-0 w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" />
              <div className="absolute left-3 bottom-3 right-3 bg-white/90 backdrop-blur-sm px-3 py-2 border hairline">
                <div className="flex items-center justify-between">
                  <span className="label-caps">{t.garment_category || "piece"}</span>
                  <span className="label-caps text-[#8C7355]">{t.recommended_size || ""}</span>
                </div>
                <div className="font-serif text-base truncate mt-0.5">{t.garment_name || "Untitled"}</div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
