import { useRef, useState } from "react";
import { toast } from "sonner";
import { Camera, ImageSquare, UserCircle, PersonSimpleWalk } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import PoseCamera from "@/components/PoseCamera";
import { BookGrid, useBook, BOOK_EVENT } from "@/components/PoseBook";

const Choice = ({ active, onClick, icon: Icon, label, testid }) => (
  <button onClick={onClick} data-testid={testid}
    className={`flex-1 flex items-center justify-center gap-2 px-4 py-4 label-caps border transition-colors ${active ? "bg-[#0A0A0A] !text-white border-[#0A0A0A]" : "hairline hover:border-[#0A0A0A]"}`}>
    <Icon size={20} weight="duotone" /> {label}
  </button>
);

const BigBox = ({ icon: Icon, title, hint, onClick, testid }) => (
  <button onClick={onClick} data-testid={testid}
    className="upload-zone flex flex-col items-center justify-center text-center p-6 min-h-[180px] hover:border-[#0A0A0A] transition-colors">
    <Icon size={40} weight="thin" />
    <span className="font-serif text-xl mt-3">{title}</span>
    <span className="text-xs text-neutral-500 mt-1">{hint}</span>
  </button>
);

function SaveAsk({ onAnswer }) {
  return (
    <div className="fixed inset-0 z-[85] bg-black/60 flex items-center justify-center p-4" data-testid="book-save-ask">
      <div className="bg-white max-w-sm w-full p-6 text-center">
        <div className="font-serif text-2xl">Vuoi salvarla nel tuo Book?</div>
        <p className="text-sm text-neutral-600 mt-2">La ritrovi in "Il Mio Book" per le prossime prove.</p>
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
  const gallery = useRef(null);
  const [camOpen, setCamOpen] = useState(false);
  const [asking, setAsking] = useState(null);
  const [busy, setBusy] = useState(false);
  const { photos, remove } = useBook();

  const handleFile = async (f) => {
    if (!f) return;
    if (!["image/jpeg", "image/png"].includes(f.type)) { toast.error("Formato non supportato: usa JPG o PNG"); return; }
    setCamOpen(false);
    setBusy(true);
    try {
      const p = await uploadFile(f, "person");
      setPosePath(p);
      setAsking(p);
    } catch (e) { if (e?.message !== "blocked" && e?.response?.status !== 402) toast.error("Caricamento non riuscito"); }
    finally { setBusy(false); }
  };
  const answer = async (save) => {
    const p = asking;
    setAsking(null);
    if (!save) return;
    try { await api.post("/book", { path: p }); window.dispatchEvent(new Event(BOOK_EVENT)); toast.success("Salvata nel tuo Book"); }
    catch { toast.error("Salvataggio non riuscito"); }
  };
  const removeBook = async (p) => { await remove(p); if (p.path === posePath) setPosePath(null); };

  return (
    <section className="space-y-5" data-testid="person-source">
      <div className="flex flex-col sm:flex-row gap-3 max-w-2xl">
        <Choice active={mode === "avatar"} onClick={() => setMode("avatar")} icon={UserCircle} label="Usa il mio Avatar" testid="person-source-avatar" />
        <Choice active={mode === "pose"} onClick={() => setMode("pose")} icon={PersonSimpleWalk} label="Usa Foto in Posa" testid="person-source-pose" />
      </div>
      {mode === "pose" && (
        <div className="space-y-5" data-testid="pose-panel">
          <div className="grid grid-cols-2 gap-4 max-w-2xl">
            <BigBox icon={Camera} title="Scatta Foto" hint="Fotocamera posteriore, sagoma a figura intera" onClick={() => setCamOpen(true)} testid="pose-take-photo" />
            <BigBox icon={ImageSquare} title="Carica da Galleria" hint="Una tua foto in posa, JPG o PNG" onClick={() => gallery.current?.click()} testid="pose-upload-gallery" />
          </div>
          <input ref={gallery} type="file" accept=".jpg,.jpeg,.png,image/jpeg,image/png" className="hidden" data-testid="pose-gallery-input"
            onChange={(e) => { handleFile(e.target.files?.[0]); e.target.value = ""; }} />
          {busy && <p className="label-caps text-neutral-500" data-testid="pose-uploading">Caricamento foto…</p>}
          {photos.length > 0 && (
            <div className="max-w-2xl">
              <div className="label-caps mb-3">Dal tuo Book</div>
              <BookGrid photos={photos} onRemove={removeBook} onPick={(p) => setPosePath(p.path)} selected={posePath} testid="studio-book-grid" />
            </div>
          )}
        </div>
      )}
      <PoseCamera open={camOpen} onClose={() => setCamOpen(false)} onShot={handleFile} />
      {asking && <SaveAsk onAnswer={answer} />}
    </section>
  );
}
