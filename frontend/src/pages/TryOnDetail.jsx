import { useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { toast } from "sonner";
import { api, fileUrl } from "@/lib/api";
import { ArrowLeft, Trash, ArrowsLeftRight } from "@phosphor-icons/react";
import HemCard from "@/components/HemCard";
import FreeRetry from "@/components/FreeRetry";

const CAT_IT = { top: "Top", bottom: "Pantaloni / Gonna", dress: "Abito", outerwear: "Capospalla", shoes: "Scarpe", look: "Look copiato" };

export default function TryOnDetail() {
  const { id } = useParams();
  const [t, setT] = useState(null);
  const [view, setView] = useState("after");
  const navigate = useNavigate();

  useEffect(() => {
    api.get(`/tryons/${id}`).then(({ data }) => setT(data)).catch(() => toast.error("Prova non trovata"));
  }, [id]);

  const del = async () => {
    if (!window.confirm("Eliminare questa prova?")) return;
    try { await api.delete(`/tryons/${id}`); toast.success("Prova eliminata"); navigate("/wardrobe"); } catch { toast.error("Eliminazione non riuscita"); }
  };

  if (!t) return <div className="label-caps">Caricamento</div>;

  const imgSrc = view === "after" ? fileUrl(t.result_path) : fileUrl(t.person_path);
  const cat = CAT_IT[t.garment_category] || t.garment_category || "—";

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-10" data-testid="tryon-detail-root">
      <div className="lg:col-span-7">
        <Link to="/wardrobe" className="label-caps inline-flex items-center gap-2 mb-4 hover:text-[#8C7355]" data-testid="back-to-wardrobe">
          <ArrowLeft size={14} weight="bold" /> Il tuo armadio
        </Link>
        <div className="relative border hairline overflow-hidden bg-[#FAF8F5]" style={{ aspectRatio: "3/4" }}>
          <img src={imgSrc} alt="" className="absolute inset-0 w-full h-full object-contain" data-testid="tryon-main-image" />
          <button
            onClick={() => setView(view === "after" ? "before" : "after")}
            className="absolute left-4 bottom-4 bg-white/95 backdrop-blur-sm px-4 py-2 border hairline label-caps inline-flex items-center gap-2 hover:bg-white"
            data-testid="toggle-before-after"
          >
            <ArrowsLeftRight size={14} weight="bold" /> {view === "after" ? "Prima" : "Dopo"}
          </button>
        </div>
        <div className="mt-4"><HemCard url={`/tryons/${id}/hem`} /></div>
      </div>
      <div className="lg:col-span-5">
        <div className="label-caps">La tua prova</div>
        <h1 className="font-serif text-3xl md:text-5xl tracking-tighter mt-1">{t.garment_name || "Capo senza nome"}</h1>
        <div className="label-caps mt-2 text-[#8C7355]">{cat}</div>

        <div className="mt-10 border hairline divide-y">
          <Row label="Taglia consigliata" value={t.recommended_size || "—"} testid="tryon-recommended-size" />
          <Row label="Creata il" value={new Date(t.created_at).toLocaleString("it-IT")} />
          <Row label="Categoria" value={cat} />
        </div>

        <div className="mt-6 grid grid-cols-2 gap-3">
          <div className="border hairline p-3">
            <div className="label-caps">Capo</div>
            <div className="mt-2 relative overflow-hidden" style={{ aspectRatio: "4/5" }}>
              <img src={fileUrl(t.garment_path)} alt="" className="absolute inset-0 w-full h-full object-cover" />
            </div>
          </div>
          <div className="border hairline p-3">
            <div className="label-caps">Tu</div>
            <div className="mt-2 relative overflow-hidden" style={{ aspectRatio: "4/5" }}>
              <img src={fileUrl(t.person_path)} alt="" className="absolute inset-0 w-full h-full object-cover" />
            </div>
          </div>
        </div>

        <div className="mt-6"><FreeRetry kind="tryons" item={t} onDone={(d) => { setT(d); setView("after"); }} /></div>

        <div className="mt-6 flex gap-3">
          <button onClick={() => navigate("/studio")} className="btn-primary" data-testid="try-another-btn">Prova un altro capo</button>
          <button onClick={del} className="btn-ghost" data-testid="delete-tryon-btn"><Trash size={16} weight="bold" /> Elimina</button>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, testid }) {
  return (
    <div className="flex items-center justify-between px-4 py-3" data-testid={testid}>
      <span className="label-caps">{label}</span>
      <span className="font-serif text-lg text-right">{value}</span>
    </div>
  );
}
