import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api, fileUrl } from "@/lib/api";
import { useAvatar } from "@/lib/avatar";
import { Link } from "react-router-dom";
import { useSubscription } from "@/lib/subscription";
import TryonCounter from "@/components/TryonCounter";
import { CloudArrowUp, Sparkle, ArrowRight } from "@phosphor-icons/react";
import PrivacyBox from "@/components/PrivacyBox";
import AccountPersonalBox from "@/components/AccountPersonalBox";
import OutfitGrid from "@/components/OutfitGrid";
import IncludedNote from "@/components/IncludedNote";

const CATEGORIES = [
  { k: "top", l: "Top" },
  { k: "bottom", l: "Bottom" },
  { k: "dress", l: "Dress" },
  { k: "outerwear", l: "Outerwear" },
  { k: "shoes", l: "Shoes" },
];

export default function Studio() {
  const { status: subStatus, openPaywall, refresh: refreshSub } = useSubscription();
  const location = useLocation();
  const preset = location.state?.preset || null;
  const { avatar } = useAvatar();
  const personPath = avatar?.path || null;
  const [garmentPath, setGarmentPath] = useState(preset?.garment_path || null);
  const [garmentPreview, setGarmentPreview] = useState(preset?.garment_path ? fileUrl(preset.garment_path) : null);
  const [category, setCategory] = useState(preset?.category || "top");
  const [name, setName] = useState(preset?.name || "");
  const [chosenSize, setChosenSize] = useState(preset?.chosen_size || "");
  const [generating, setGenerating] = useState(false);
  const navigate = useNavigate();

  // Load the user's saved base photo once, so future try-ons don't ask for it.
  useEffect(() => {
    if (preset?.chosen_size || preset?.name) {
      toast.success(`Capo pronto: ${preset?.name || "prodotto"} · taglia ${preset?.chosen_size || "—"}`);
    }
     
  }, []);

  const uploadFile = async (file, kind) => {
    if (subStatus?.is_blocked) { openPaywall(); throw new Error("blocked"); }
    const fd = new FormData();
    fd.append("file", file);
    const { data } = await api.post(`/upload?kind=${kind}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
    return data.path;
  };

  const generate = async () => {
    if (!personPath || !garmentPath) {
      toast.error(personPath ? "Carica prima il capo" : "Crea prima il tuo Avatar nella Home");
      return;
    }
    if (subStatus?.is_blocked) { openPaywall(); return; }
    setGenerating(true);
    try {
      const { data } = await api.post("/tryon/generate", {
        person_path: personPath,
        garment_path: garmentPath,
        garment_category: category,
        garment_name: name || null,
        chosen_size: chosenSize || null,
      });
      toast.success("Prova pronta");
      refreshSub();
      navigate(`/tryon/${data.id}`);
    } catch (e) {
      if (e?.response?.status === 402) { openPaywall(); }
      else { toast.error(e?.response?.data?.detail || "Generazione non riuscita"); }
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="space-y-10" data-testid="studio-root">
      <header className="flex items-end justify-between flex-wrap gap-6">
        <div>
          <div className="label-caps mb-3">Atelier Fit</div>
          <h1 className="font-serif text-4xl md:text-5xl tracking-tighter">Prova taglia</h1>
          <p className="mt-3 text-neutral-600 max-w-xl leading-relaxed">
            Carica una foto e il capo che vuoi provare. Ti vestiamo in un attimo.
          </p>
        </div>
        <TryonCounter />
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <UploadBox
          title="Il capo"
          hint="Foto prodotto dal tuo e-commerce preferito."
          preview={garmentPreview}
          onFile={async (f) => {
            if (subStatus?.is_blocked) { openPaywall(); return; }
            setGarmentPreview(URL.createObjectURL(f));
            try {
              const p = await uploadFile(f, "garment");
              setGarmentPath(p);
            } catch (e) { if (e?.response?.status !== 402) toast.error("Upload failed"); }
          }}
          testid="upload-garment"
          className="lg:col-span-5"
        />
        <AvatarPanel path={personPath} />
        <div className="lg:col-span-2 flex items-center justify-center">
          <Sparkle size={56} weight="duotone" className="text-[#8C7355]" />
        </div>
      </div>

      <section className="border hairline p-6 md:p-8 bg-white">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
          <div className="md:col-span-4">
            <div className="label-caps mb-2">Categoria</div>
            <div className="flex flex-wrap gap-2">
              {CATEGORIES.map((c) => (
                <button
                  key={c.k}
                  onClick={() => setCategory(c.k)}
                  className={`px-3 py-2 label-caps border hairline transition-colors ${
                    category === c.k ? "bg-[#0A0A0A] text-white border-[#0A0A0A]" : "hover:border-[#0A0A0A]"
                  }`}
                  data-testid={`cat-${c.k}`}
                >
                  {c.l}
                </button>
              ))}
            </div>
          </div>
          <div className="md:col-span-3">
            <div className="label-caps mb-2">Nome capo (opzionale)</div>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="es. Trench lino — Toteme"
              className="w-full px-4 py-3 border hairline bg-transparent outline-none focus:border-[#0A0A0A] transition-colors font-serif text-lg"
              data-testid="garment-name-input"
            />
          </div>
          <div className="md:col-span-2">
            <div className="label-caps mb-2">Taglia scelta</div>
            <input
              value={chosenSize}
              onChange={(e) => setChosenSize(e.target.value.toUpperCase())}
              placeholder="S / 40"
              className="w-full px-4 py-3 border hairline bg-transparent outline-none focus:border-[#0A0A0A] transition-colors font-serif text-lg text-center"
              data-testid="chosen-size-input"
            />
          </div>
          <div className="md:col-span-3 flex flex-col justify-end gap-2">
            <IncludedNote testid="included-note-tryon" />
            <button
              onClick={generate}
              disabled={generating || !personPath || !garmentPath}
              className="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
              data-testid="generate-tryon-btn"
            >
              {generating ? "Provo..." : (<>Provalo <ArrowRight size={16} weight="bold" /></>)}
            </button>
          </div>
        </div>
      </section>

      {generating && (
        <div className="border hairline p-10 text-center bg-white" data-testid="generating-indicator">
          <div className="label-caps">Atelier at work</div>
          <h3 className="font-serif text-2xl mt-2">Fitting your garment…</h3>
          <p className="text-neutral-500 mt-3 text-sm">This takes about 20–40 seconds.</p>
          <div className="mt-6 h-1 w-full bg-neutral-100 overflow-hidden">
            <div className="h-full w-1/3 bg-[#0A0A0A] animate-pulse" />
          </div>
        </div>
      )}

      <OutfitGrid personPath={personPath} uploadFile={uploadFile} />

      <div className="space-y-3">
        <PrivacyBox testid="privacy-box-bottom" />
        <AccountPersonalBox />
      </div>
    </div>
  );
}

function AvatarPanel({ path }) {
  return (
    <div className="upload-zone p-6 min-h-[380px] flex flex-col lg:col-span-5" data-testid="studio-avatar">
      <div className="label-caps">Il Mio Avatar</div>
      <p className="text-xs text-neutral-500 mt-1">La tua foto unica, usata per tutte le prove.</p>
      <div className="flex-1 mt-6 relative overflow-hidden" style={{ aspectRatio: "4/5" }}>
        {path ? (
          <img src={fileUrl(path)} alt="" className="absolute inset-0 w-full h-full object-cover" data-testid="studio-avatar-photo" />
        ) : (
          <Link to="/dashboard#il-mio-avatar" className="absolute inset-0 flex flex-col items-center justify-center text-neutral-500 text-center px-6" data-testid="studio-avatar-create">
            <span className="font-serif text-lg">Crea il tuo Avatar</span>
            <span className="text-xs mt-2">Una foto in Home, poi è pronta per ogni prova</span>
          </Link>
        )}
      </div>
    </div>
  );
}

function UploadBox({ title, hint, preview, onFile, testid, className = "", topRight = null }) {
  const ref = useRef();
  const [drag, setDrag] = useState(false);
  return (
    <div
      className={`upload-zone ${drag ? "active" : ""} p-6 min-h-[380px] flex flex-col ${className}`}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault(); setDrag(false);
        const f = e.dataTransfer.files?.[0];
        if (f) onFile(f);
      }}
      onClick={() => ref.current?.click()}
      data-testid={testid}
    >
      <input ref={ref} type="file" accept="image/*" className="hidden" onChange={(e) => {
        const f = e.target.files?.[0]; if (f) onFile(f);
      }} />
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="label-caps">{title}</div>
          <p className="text-xs text-neutral-500 mt-1 max-w-xs">{hint}</p>
        </div>
        <div className="flex items-center gap-2">
          {topRight}
          <CloudArrowUp size={22} weight="duotone" />
        </div>
      </div>
      <div className="flex-1 mt-6 relative overflow-hidden" style={{ aspectRatio: "4/5" }}>
        {preview ? (
          <img src={preview} alt="" className="absolute inset-0 w-full h-full object-cover" />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-neutral-400">
            <CloudArrowUp size={46} weight="thin" />
            <div className="label-caps mt-3">Trascina o clicca per caricare</div>
          </div>
        )}
      </div>
    </div>
  );
}
