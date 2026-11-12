import { useRef, useState } from "react";
import { toast } from "sonner";
import { Camera, ImageSquare, UserCircle } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import PoseCamera from "@/components/PoseCamera";
import { BookGrid, useBook, BOOK_EVENT } from "@/components/PoseBook";

const SOURCES = [
  { k: "avatar", icon: UserCircle, l: "Usa il mio Avatar fisso", d: "Sempre la stessa foto davanti allo specchio, zero deformazioni", rec: true },
  { k: "gallery", icon: ImageSquare, l: "Carica foto in posa dalla Galleria", d: "Una tua foto in posa già fatta, JPG o PNG" },
  { k: "camera", icon: Camera, l: "Scatta foto in posa ora", d: "Fotocamera posteriore con sagoma a figura intera" },
];

function SaveAsk({ onAnswer }) {
  return (
    <div className="fixed inset-0 z-[85] bg-black/60 flex items-center justify-center p-4" data-testid="book-save-ask">
      <div className="bg-white max-w-sm w-full p-6 text-center">
        <div className="font-serif text-2xl">Vuoi salvarla in Le mie Pose?</div>
        <p className="text-sm text-neutral-600 mt-2">La ritrovi in "Le mie Pose" e la riusi come Avatar quando vuoi.</p>
        <div className="mt-6 flex gap-3">
          <button onClick={() => onAnswer(false)} className="btn-ghost flex-1" data-testid="book-save-no">No, solo ora</button>
          <button onClick={() => onAnswer(true)} className="btn-primary flex-1" data-testid="book-save-yes">Sì, salva</button>
        </div>
      </div>
    </div>
  );
}

// Studio entry: Avatar (static) or a posed photo, shared by Prova Singola and Multibrand.
export default function PersonSource({ mode, setMode, posePath, setPosePath, uploadFile }) {
  const [source, setSource] = useState(mode === "pose" ? "gallery" : "avatar");
  const choose = (k) => {
    setSource(k);
    setMode(k === "avatar" ? "avatar" : "pose");
    if (k === "gallery") gallery.current?.click();
    if (k === "camera") setCamOpen(true);
  };
  const gallery = useRef(null);
  const [camOpen, setCamOpen] = useState(false);
  const [asking, setAsking] = useState(null);
  const [busy, setBusy] = useState(false);
  const [faceError, setFaceError] = useState(null);
  const { photos, remove } = useBook();

  const handleFile = async (f) => {
    if (!f) return;
    if (!["image/jpeg", "image/png"].includes(f.type)) { toast.error("Formato non supportato: usa JPG o PNG"); return; }
    setCamOpen(false);
    setBusy(true);
    try {
      const p = await uploadFile(f, "person");
      if (await faceOk(p)) { setPosePath(p); setAsking(p); }
    } catch (e) {
      if (e?.response?.status === 402) toast.error((typeof e?.response?.data?.detail === "string" && e.response.data.detail) || "Hai esaurito le prove gratuite di oggi: passa a un piano per continuare");
      else if (e?.message !== "blocked") toast.error("Caricamento non riuscito");
    }
    finally { setBusy(false); }
  };
  // SHOW ALWAYS (owner rule): no face pre-check, every photo can start a try-on.
  const faceOk = async () => { setFaceError(null); return true; };
  const pick = async (p) => { try { if (await faceOk(p.path)) setPosePath(p.path); } catch { toast.error("Controllo foto non riuscito"); } };
  const answer = async (save) => {
    const p = asking;
    setAsking(null);
    if (!save) return;
    try { await api.post("/book", { path: p }); window.dispatchEvent(new Event(BOOK_EVENT)); toast.success("Salvata in Le mie Pose"); }
    catch { toast.error("Salvataggio non riuscito"); }
  };
  const removeBook = async (p) => { if (await remove(p) && p.path === posePath) setPosePath(null); };

  return (
    <section className="space-y-5" data-testid="person-source">
      <fieldset className="border hairline bg-white p-5 max-w-2xl" data-testid="photo-source-selector">
        <legend className="label-caps px-1">Foto per la prova</legend>
        <div className="space-y-2">
          {SOURCES.map((o) => (
            <label key={o.k} className={`flex items-start gap-3 p-3 border cursor-pointer transition-colors ${source === o.k ? "border-[#0A0A0A] bg-[#FAF8F5]" : "hairline hover:border-[#0A0A0A]"}`} data-testid={`photo-source-${o.k}`}>
              <input type="radio" name="photo-source" checked={source === o.k} onChange={() => choose(o.k)} className="mt-1 accent-[#0A0A0A]" />
              <o.icon size={22} weight="duotone" className="shrink-0 mt-0.5" />
              <span className="flex-1">
                <span className="text-sm font-medium">{o.l}</span>
                {o.rec && <span className="ml-2 text-[10px] tracking-[0.2em] text-[#8C7355]" data-testid="photo-source-recommended">CONSIGLIATO</span>}
                <span className="block text-xs text-neutral-500 mt-0.5">{o.d}</span>
              </span>
            </label>
          ))}
        </div>
        <p className="text-xs text-neutral-600 mt-4" data-testid="photo-source-subtext">
          Vuoi una posa wow? Scatta una foto a figura intera davanti allo specchio, braccia lungo i fianchi. Non toccheremo mai viso e mani.
        </p>
      </fieldset>
      {mode === "pose" && (
        <div className="space-y-5" data-testid="pose-panel">
          <button onClick={() => (source === "camera" ? setCamOpen(true) : gallery.current?.click())} className="btn-ghost" data-testid="pose-new-photo-btn">
            {source === "camera" ? "Scatta un'altra foto" : "Scegli un'altra foto dalla galleria"}
          </button>
          {busy && <p className="label-caps text-neutral-500" data-testid="pose-uploading">Caricamento foto…</p>}
          {faceError && <p className="text-sm text-red-700 border border-red-200 bg-red-50 px-3 py-2 max-w-2xl" data-testid="pose-face-error">{faceError}</p>}
          {photos.length > 0 && (
            <div className="max-w-2xl">
              <div className="label-caps mb-3">Dalle mie Pose</div>
              <BookGrid photos={photos} onRemove={removeBook} onPick={pick} selected={posePath} testid="studio-book-grid" />
            </div>
          )}
        </div>
      )}
      <input ref={gallery} type="file" accept=".jpg,.jpeg,.png,image/jpeg,image/png" className="hidden" data-testid="pose-gallery-input"
        onChange={(e) => { handleFile(e.target.files?.[0]); e.target.value = ""; }} />
      <PoseCamera open={camOpen} onClose={() => setCamOpen(false)} onShot={handleFile} />
      {asking && <SaveAsk onAnswer={answer} />}
    </section>
  );
}
