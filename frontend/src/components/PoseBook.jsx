import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { X, Images, UserCircle, Trash } from "@phosphor-icons/react";
import { api, fileUrl } from "@/lib/api";
import ShareLook from "@/components/ShareLook";

export const BOOK_EVENT = "atelier-book-changed";
const ASK_EVENT = "atelier-ask-book";
const POSE_KEY = "atelier_use_pose";

// Call at the end of every try-on: the SaveBookBar under the result asks "Vuoi salvare questo outfit nel tuo Book?".
const pendingAsks = new Set();
export const askBook = (kind, refId) => {
  pendingAsks.add(`${kind}:${refId}`);
  window.dispatchEvent(new CustomEvent(ASK_EVENT, { detail: { kind, ref_id: refId } }));
};
export const takePoseForStudio = () => { const p = sessionStorage.getItem(POSE_KEY); sessionStorage.removeItem(POSE_KEY); return p; };

function useList(url, key, deletedMsg = "Foto eliminata") {
  const [rows, setRows] = useState([]);
  const load = useCallback(() => api.get(url).then(({ data }) => setRows(data[key])).catch(() => {}), [url, key]);
  useEffect(() => {
    load();
    window.addEventListener(BOOK_EVENT, load);
    return () => window.removeEventListener(BOOK_EVENT, load);
  }, [load]);
  const remove = async (id) => {
    try {
      await api.delete(`${url}/${id}`);
      window.dispatchEvent(new Event(BOOK_EVENT));
      toast.success(deletedMsg);
      return true;
    } catch { toast.error("Eliminazione non riuscita"); return false; }
  };
  return { rows, remove };
}

export function useBook() {
  const { rows, remove } = useList("/book", "photos", "Foto eliminata da Le mie Pose");
  return { photos: rows, remove: (p) => remove(p.id) };
}

const confirmDelete = () => window.confirm("Eliminare definitivamente questa foto?");

const DeleteX = ({ onClick }) => (
  <button onClick={() => { if (confirmDelete()) onClick(); }} aria-label="Elimina"
    className="absolute top-1.5 right-1.5 w-7 h-7 rounded-full bg-black/70 text-white flex items-center justify-center hover:bg-black" data-testid="book-photo-delete">
    <X size={14} weight="bold" />
  </button>
);

export function BookGrid({ photos, onRemove, onPick, selected, testid = "book-grid" }) {
  if (!photos.length) return <p className="text-sm text-neutral-500" data-testid={`${testid}-empty`}>Nessuna foto in Le mie Pose</p>;
  return (
    <div className="grid grid-cols-3 sm:grid-cols-4 gap-3" data-testid={testid}>
      {photos.map((p) => (
        <div key={p.id} className={`relative aspect-[3/4] overflow-hidden bg-neutral-100 ${selected === p.path ? "ring-2 ring-[#D4AF37]" : ""}`} data-testid="book-photo">
          <img src={`${fileUrl(p.path)}?thumb=480`} alt="" onClick={() => onPick?.(p)}
            className={`w-full h-full object-cover ${onPick ? "cursor-pointer hover:scale-105 transition-transform duration-300" : ""}`} />
          <DeleteX onClick={() => onRemove(p)} />
        </div>
      ))}
    </div>
  );
}

function Card({ path, onRemove, children, testid, what }) {
  return (
    <div className="bg-white border hairline" data-testid={testid}>
      <div className="relative aspect-[3/4] overflow-hidden bg-neutral-100">
        <img src={`${fileUrl(path)}?thumb=640`} alt="" className="w-full h-full object-cover" />
      </div>
      <div className="p-2 space-y-2">
        {children}
        <ShareLook path={path} label="Ripubblica" />
        <button onClick={() => { if (window.confirm(`Eliminare definitivamente questo ${what}?`)) onRemove(); }} data-testid="book-item-delete-btn"
          className="w-full inline-flex items-center justify-center gap-2 border border-red-700 text-red-700 px-5 py-3 text-xs font-semibold uppercase tracking-[0.18em] hover:bg-red-700 hover:text-white transition-colors duration-300">
          <Trash size={15} /> Elimina
        </button>
      </div>
    </div>
  );
}

function OutfitsTab() {
  const { rows, remove } = useList("/outfit-book", "outfits", "Outfit eliminato dal Book");
  if (!rows.length) return <p className="text-sm text-neutral-500" data-testid="outfit-book-empty">Nessun outfit salvato: a fine prova scegli "Salva nel Book"</p>;
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3" data-testid="outfit-book-grid">
      {rows.map((o) => (
        <Card key={o.id} path={o.result_path} onRemove={() => remove(o.id)} testid="outfit-book-item" what="outfit">
          <div className="text-[10px] tracking-[0.2em] text-neutral-500">{new Date(o.created_at).toLocaleDateString("it-IT")}</div>
        </Card>
      ))}
    </div>
  );
}

function PosesTab({ onUse }) {
  const { photos, remove } = useBook();
  if (!photos.length) return <p className="text-sm text-neutral-500" data-testid="pose-book-empty">Nessuna foto in posa salvata</p>;
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3" data-testid="pose-book-grid">
      {photos.map((p) => (
        <Card key={p.id} path={p.path} onRemove={() => remove(p)} testid="pose-book-item" what="foto in posa">
          <button onClick={() => onUse(p)} className="btn-primary w-full !py-2.5 !text-[11px]" data-testid="pose-book-use-btn">
            <UserCircle size={16} /> Usa come Avatar
          </button>
        </Card>
      ))}
    </div>
  );
}

// Thin, non-blocking question right under the result photo (the photo always stays fully visible).
export function SaveBookBar({ kind, refId }) {
  const key = `${kind}:${refId}`;
  const [show, setShow] = useState(() => pendingAsks.has(key));
  useEffect(() => {
    const on = (e) => { if (`${e.detail.kind}:${e.detail.ref_id}` === key) setShow(true); };
    window.addEventListener(ASK_EVENT, on);
    return () => window.removeEventListener(ASK_EVENT, on);
  }, [key]);
  if (!show) return null;
  const close = () => { pendingAsks.delete(key); setShow(false); };
  const save = async () => {
    close();
    try { await api.post("/outfit-book", { kind, ref_id: refId }); window.dispatchEvent(new Event(BOOK_EVENT)); toast.success("Outfit salvato nel tuo Book"); }
    catch { toast.error("Salvataggio non riuscito"); }
  };
  return (
    <div className="flex items-center justify-between gap-3 border hairline bg-white px-3 py-2" data-testid="outfit-book-ask">
      <span className="text-xs text-neutral-700">Vuoi salvare questo outfit nel tuo Book?</span>
      <div className="flex gap-2 shrink-0">
        <button onClick={save} className="px-3 py-1.5 text-[10px] font-semibold tracking-[0.18em] bg-[#0A0A0A] text-white hover:bg-[#333] transition-colors" data-testid="outfit-book-save">SALVA</button>
        <button onClick={close} className="px-3 py-1.5 text-[10px] font-semibold tracking-[0.18em] border hairline hover:border-[#0A0A0A] transition-colors" data-testid="outfit-book-discard">SCARTA</button>
      </div>
    </div>
  );
}

const TABS = [["outfits", "Book"], ["poses", "Le mie Pose"]];

export default function BookButton({ showPoses = false }) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState("outfits");
  const navigate = useNavigate();
  const pickPose = (p) => {
    sessionStorage.setItem(POSE_KEY, p.path);
    setOpen(false);
    navigate("/studio", { state: { posePath: p.path } });
  };
  return (
    <>
      <button onClick={() => setOpen(true)} title="Il Mio Book" className="hover:text-[#D4AF37] transition-colors shrink-0" data-testid="book-btn">
        <Images size={22} weight="duotone" />
      </button>
      {open && createPortal(
        <div className="fixed inset-0 z-[70] bg-[#F5F2EC] overflow-y-auto text-[#0A0A0A]" data-testid="book-modal">
          <div className="max-w-3xl mx-auto px-4 py-8">
            <div className="flex items-center justify-between mb-6">
              <h2 className="font-serif text-3xl tracking-tight">Il Mio Book</h2>
              <button onClick={() => setOpen(false)} aria-label="Chiudi" data-testid="book-modal-close"><X size={26} /></button>
            </div>
            <div className="flex gap-2 mb-6">
              {TABS.filter(([k]) => showPoses || k !== "poses").map(([k, l]) => (
                <button key={k} onClick={() => setTab(k)} data-testid={`book-tab-${k}`}
                  className={`px-4 py-2 label-caps border transition-colors ${tab === k ? "bg-[#0A0A0A] !text-white border-[#0A0A0A]" : "hairline hover:border-[#0A0A0A]"}`}>
                  {l}
                </button>
              ))}
            </div>
            {tab === "outfits" || !showPoses ? <OutfitsTab /> : <PosesTab onUse={pickPose} />}
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
