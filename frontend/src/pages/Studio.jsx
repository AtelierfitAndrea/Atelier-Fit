import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api, fileUrl } from "@/lib/api";
import { useAvatar } from "@/lib/avatar";
import { Link } from "react-router-dom";
import { useSubscription } from "@/lib/subscription";
import TryonCounter from "@/components/TryonCounter";
import { CloudArrowUp, ArrowRight } from "@phosphor-icons/react";
import PrivacyBox from "@/components/PrivacyBox";
import AccountPersonalBox from "@/components/AccountPersonalBox";
import OutfitGrid from "@/components/OutfitGrid";
import PersonSource from "@/components/PersonSource";
import { useAuth } from "@/lib/auth";
import { takePoseForStudio } from "@/components/PoseBook";
import IncludedNote from "@/components/IncludedNote";
import CopyLook from "@/components/CopyLook";
import TryOnProgress from "@/components/TryOnProgress";
import { notifyTabReady } from "@/lib/tabNotify";
import PendingOutfitModal from "@/components/PendingOutfitModal";
import { usePendingDraft } from "@/lib/pendingOutfit";
import { postRender } from "@/lib/renderJob";

export default function Studio() {
  const { status: subStatus, openPaywall, refresh: refreshSub } = useSubscription();
  const location = useLocation();
  const preset = location.state?.preset || null;
  const { avatar } = useAvatar();
  const avatarPath = avatar?.path || null;
  const [startPose] = useState(() => takePoseForStudio());
  const [personMode, setPersonMode] = useState(startPose ? "pose" : "avatar");
  const [posePath, setPosePath] = useState(startPose);
  useEffect(() => {
    const p = location.state?.posePath;
    if (p) { takePoseForStudio(); setPersonMode("pose"); setPosePath(p); }
  }, [location.state]);
  const { user } = useAuth();
  const poseAllowed = user?.is_owner === true;
  const posed = poseAllowed && personMode === "pose";
  const personPath = posed ? posePath : avatarPath;
  const [garmentPath, setGarmentPath] = useState(preset?.garment_path || null);
  const [garmentPreview, setGarmentPreview] = useState(preset?.garment_path ? fileUrl(preset.garment_path) : null);
  const [category, setCategory] = useState(preset?.category || null);
  const [name, setName] = useState(preset?.name || "");
  const [chosenSize, setChosenSize] = useState(preset?.chosen_size || "");
  const [generating, setGenerating] = useState(false);
  const navigate = useNavigate();
  const [gridItems, setGridItems] = useState([]);
  const [restoreItems, setRestoreItems] = useState(null);
  const single = garmentPath ? { garment_path: garmentPath, category, name, chosen_size: chosenSize } : null;
  const pending = usePendingDraft({ avatarPath: personPath, selectedItems: gridItems, single }, !!preset, (d) => {
    if (d.single?.garment_path) {
      setGarmentPath(d.single.garment_path);
      setGarmentPreview(fileUrl(d.single.garment_path));
      setCategory(d.single.category || null);
      setName(d.single.name || "");
      setChosenSize(d.single.chosen_size || "");
    }
    setRestoreItems(d.selectedItems || []);
  });

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
      toast.error(personPath ? "Carica prima il capo" : (posed ? "Scatta o carica prima la tua foto in posa" : "Crea prima il tuo Avatar nella Home"));
      return;
    }
    if (subStatus?.is_blocked) { openPaywall(); return; }
    setGenerating(true);
    try {
      const { data } = await postRender("/tryon/generate", {
        person_path: personPath,
        garment_path: garmentPath,
        garment_category: category,
        garment_name: name || null,
        chosen_size: chosenSize || null,
        preserve_pose: posed,
      });
      pending.markDone();
      notifyTabReady();
      toast.success("Prova pronta");
      refreshSub();
      setGenerating(false);
      await new Promise((r) => setTimeout(r, 800));
      navigate(`/tryon/${data.id}`, { state: { fresh: true } });
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
            {posed ? "Carica il capo: lo proviamo sulla tua foto in posa, senza cambiare la posa." : "Carica il capo: usiamo il tuo Avatar e ti vestiamo in un attimo."}
          </p>
        </div>
        <TryonCounter />
      </header>

      {poseAllowed && <PersonSource mode={personMode} setMode={setPersonMode} posePath={posePath} setPosePath={setPosePath} uploadFile={uploadFile} />}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <UploadBox
          title="Il capo"
          hint="Foto prodotto dal tuo e-commerce preferito."
          preview={garmentPreview}
          onFile={async (f) => {
            if (subStatus?.is_blocked) { openPaywall(); return; }
            setGarmentPreview(URL.createObjectURL(f));
            setCategory(null); setName(""); setChosenSize("");
            try {
              const p = await uploadFile(f, "garment");
              setGarmentPath(p);
            } catch (e) {
              if (e?.response?.status === 402) toast.error((typeof e?.response?.data?.detail === "string" && e.response.data.detail) || "Hai esaurito le prove gratuite di oggi: passa a un piano per continuare");
              else if (e?.message !== "blocked") toast.error("Upload failed");
            }
          }}
          testid="upload-garment"
          className="lg:col-span-6"
        />
        <AvatarPanel path={personPath} posed={posed} />
      </div>

      <section className="border hairline p-6 md:p-8 bg-white" data-testid="tryon-action">
        <div className="max-w-md flex flex-col gap-2">
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
      </section>

      <TryOnProgress active={generating} testid="generating-indicator" />

      <CopyLook personPath={avatarPath} uploadFile={uploadFile} />

      <OutfitGrid personPath={personPath} preservePose={posed} uploadFile={uploadFile} restoreItems={restoreItems}
        onItemsChange={setGridItems} onGenerated={pending.markDone} />
      <PendingOutfitModal draft={pending.draft} onResume={pending.resume} onDiscard={pending.discard} />

      <div className="space-y-3">
        <PrivacyBox testid="privacy-box-bottom" />
        <AccountPersonalBox />
      </div>
    </div>
  );
}

function AvatarPanel({ path, posed }) {
  return (
    <div className="upload-zone p-6 min-h-[380px] flex flex-col lg:col-span-6" data-testid="studio-avatar">
      <div className="label-caps">{posed ? "La tua Foto in Posa" : "Il Mio Avatar"}</div>
      <p className="text-xs text-neutral-500 mt-1">{posed ? "Manteniamo la tua posa: cambiamo solo i vestiti." : "La tua foto unica, usata per tutte le prove."}</p>
      <div className="flex-1 mt-6 relative overflow-hidden" style={{ aspectRatio: "4/5" }}>
        {path ? (
          <img src={fileUrl(path)} alt="" className="absolute inset-0 w-full h-full object-cover" data-testid="studio-avatar-photo" />
        ) : posed ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-neutral-500 text-center px-6" data-testid="studio-pose-empty">
            <span className="font-serif text-lg">Scatta o carica la tua foto in posa</span>
          </div>
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
