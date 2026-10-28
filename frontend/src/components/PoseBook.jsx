import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { toast } from "sonner";
import { X, Images } from "@phosphor-icons/react";
import { api, fileUrl } from "@/lib/api";

export const BOOK_EVENT = "atelier-book-changed";

export function useBook() {
  const [photos, setPhotos] = useState([]);
  const load = useCallback(() => api.get("/book").then(({ data }) => setPhotos(data.photos)).catch(() => {}), []);
  useEffect(() => {
    load();
    window.addEventListener(BOOK_EVENT, load);
    return () => window.removeEventListener(BOOK_EVENT, load);
  }, [load]);
  const remove = async (p) => {
    try {
      await api.delete(`/book/${p.id}`);
      window.dispatchEvent(new Event(BOOK_EVENT));
      toast.success("Foto eliminata dal Book");
      return true;
    } catch { toast.error("Eliminazione non riuscita"); return false; }
  };
  return { photos, remove };
}

export function BookGrid({ photos, onRemove, onPick, selected, testid = "book-grid" }) {
  if (!photos.length) return <p className="text-sm text-neutral-500" data-testid={`${testid}-empty`}>Nessuna foto nel tuo Book</p>;
  return (
    <div className="grid grid-cols-3 sm:grid-cols-4 gap-3" data-testid={testid}>
      {photos.map((p) => (
        <div key={p.id} className={`relative aspect-[3/4] overflow-hidden bg-neutral-100 ${selected === p.path ? "ring-2 ring-[#D4AF37]" : ""}`} data-testid="book-photo">
          <img src={`${fileUrl(p.path)}?thumb=480`} alt="" onClick={() => onPick?.(p)}
            className={`w-full h-full object-cover ${onPick ? "cursor-pointer hover:scale-105 transition-transform duration-300" : ""}`} />
          <button onClick={() => { if (window.confirm("Eliminare definitivamente questa foto?")) onRemove(p); }} aria-label="Elimina"
            className="absolute top-1.5 right-1.5 w-7 h-7 rounded-full bg-black/70 text-white flex items-center justify-center hover:bg-black" data-testid="book-photo-delete">
            <X size={14} weight="bold" />
          </button>
        </div>
      ))}
    </div>
  );
}

export default function BookButton() {
  const [open, setOpen] = useState(false);
  const { photos, remove } = useBook();
  return (
    <>
      <button onClick={() => setOpen(true)} title="Il Mio Book" className="hover:text-[#D4AF37] transition-colors shrink-0" data-testid="book-btn">
        <Images size={22} weight="duotone" />
      </button>
      {open && createPortal(
        <div className="fixed inset-0 z-[70] bg-[#F5F2EC] overflow-y-auto text-[#0A0A0A]" data-testid="book-modal">
          <div className="max-w-3xl mx-auto px-4 py-8">
            <div className="flex items-center justify-between mb-6">
              <div>
                <div className="label-caps">Foto in posa salvate</div>
                <h2 className="font-serif text-3xl tracking-tight mt-1">Il Mio Book</h2>
              </div>
              <button onClick={() => setOpen(false)} aria-label="Chiudi" data-testid="book-modal-close"><X size={26} /></button>
            </div>
            <BookGrid photos={photos} onRemove={remove} />
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
