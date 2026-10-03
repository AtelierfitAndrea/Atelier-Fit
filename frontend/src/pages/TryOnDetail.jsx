import { useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { toast } from "sonner";
import { api, fileUrl } from "@/lib/api";
import { ArrowLeft, Trash, ArrowsLeftRight } from "@phosphor-icons/react";

export default function TryOnDetail() {
  const { id } = useParams();
  const [t, setT] = useState(null);
  const [view, setView] = useState("after");
  const navigate = useNavigate();

  useEffect(() => {
    (async () => {
      try { const { data } = await api.get(`/tryons/${id}`); setT(data); } catch { toast.error("Not found"); }
    })();
  }, [id]);

  const del = async () => {
    if (!confirm("Delete this fitting?")) return;
    try { await api.delete(`/tryons/${id}`); toast.success("Deleted"); navigate("/wardrobe"); } catch { toast.error("Could not delete"); }
  };

  if (!t) return <div className="label-caps">Loading</div>;

  const imgSrc = view === "after" ? fileUrl(t.result_path) : fileUrl(t.person_path);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-10" data-testid="tryon-detail-root">
      <div className="lg:col-span-7">
        <Link to="/wardrobe" className="label-caps inline-flex items-center gap-2 mb-4 hover:text-[#8C7355]" data-testid="back-to-wardrobe">
          <ArrowLeft size={14} weight="bold" /> Wardrobe
        </Link>
        <div className="relative border hairline overflow-hidden" style={{ aspectRatio: "3/4" }}>
          <img src={imgSrc} alt="" className="absolute inset-0 w-full h-full object-cover" data-testid="tryon-main-image" />
          <button
            onClick={() => setView(view === "after" ? "before" : "after")}
            className="absolute left-4 bottom-4 bg-white/95 backdrop-blur-sm px-4 py-2 border hairline label-caps inline-flex items-center gap-2 hover:bg-white"
            data-testid="toggle-before-after"
          >
            <ArrowsLeftRight size={14} weight="bold" /> {view === "after" ? "Before" : "After"}
          </button>
        </div>
      </div>
      <div className="lg:col-span-5">
        <div className="label-caps">Fitting №</div>
        <h1 className="font-serif text-3xl md:text-5xl tracking-tighter mt-1">{t.garment_name || "Untitled piece"}</h1>
        <div className="label-caps mt-2 text-[#8C7355]">{t.garment_category || "piece"}</div>

        <div className="mt-10 border hairline divide-y">
          <Row label="Recommended size" value={t.recommended_size || "—"} />
          <Row label="Generated" value={new Date(t.created_at).toLocaleString()} />
          <Row label="Category" value={t.garment_category || "—"} />
        </div>

        <div className="mt-6 grid grid-cols-2 gap-3">
          <div className="border hairline p-3">
            <div className="label-caps">Garment</div>
            <div className="mt-2 relative overflow-hidden" style={{ aspectRatio: "4/5" }}>
              <img src={fileUrl(t.garment_path)} alt="" className="absolute inset-0 w-full h-full object-cover" />
            </div>
          </div>
          <div className="border hairline p-3">
            <div className="label-caps">You</div>
            <div className="mt-2 relative overflow-hidden" style={{ aspectRatio: "4/5" }}>
              <img src={fileUrl(t.person_path)} alt="" className="absolute inset-0 w-full h-full object-cover" />
            </div>
          </div>
        </div>

        <div className="mt-8 flex gap-3">
          <button onClick={() => navigate("/studio")} className="btn-primary" data-testid="try-another-btn">
            Try another
          </button>
          <button onClick={del} className="btn-ghost" data-testid="delete-tryon-btn">
            <Trash size={16} weight="bold" /> Delete
          </button>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex items-center justify-between px-4 py-3">
      <span className="label-caps">{label}</span>
      <span className="font-serif text-lg">{value}</span>
    </div>
  );
}
