import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Camera, CheckCircle, Trash, Images } from "@phosphor-icons/react";
import GalleryWarning, { photoAgeDays } from "@/components/GalleryWarning";
import { api, fileUrl } from "@/lib/api";
import { useAvatar } from "@/lib/avatar";
import AvatarCamera from "@/components/AvatarCamera";

// iOS asks permission for the motion sensors (needed by the phone level) inside a tap.
const askLevelPermission = () => { try { window.DeviceOrientationEvent?.requestPermission?.().catch(() => {}); } catch (_e) { /* not needed */ } };

function Notes() {
  return (
    <div className="mt-4 space-y-1.5" data-testid="avatar-notes">
      <p className="text-sm text-neutral-800" data-testid="avatar-purpose-note">La foto avatar serve solo per la prova vestiti</p>
      <p className="text-xs text-neutral-600" data-testid="avatar-modes-note"><b>1 foto intera</b>, dalla testa ai piedi con un po' di spazio sopra e sotto: telefono a 1,5-2 metri, zoom 1x (0.5x solo se serve).</p>
      <p className="text-xs text-neutral-600" data-testid="avatar-measures-note">Le taglie sono calcolate solo dalle tue <Link to="/profile" className="underline" data-testid="avatar-measures-link">misure reali</Link>.</p>
      <p className="text-[11px] text-neutral-400" data-testid="avatar-privacy-note">🔒 La foto è criptata e visibile solo dal tuo account Atelier. Non la mostriamo a nessuno. Puoi cancellarla quando vuoi.</p>
    </div>
  );
}

export default function AvatarBox({ manage = false }) {
  const { avatar, setAvatar, profileName } = useAvatar();
  const [camOpen, setCamOpen] = useState(false);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [gallery, setGallery] = useState(null);
  const galleryRef = useRef();

  const onCapture = async (file) => {
    setCamOpen(false);
    setPreview(URL.createObjectURL(file));
    setBusy(true);
    try {
      const fd = new FormData(); fd.append("photo", file);
      const { data } = await api.post("/profile/avatar", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setAvatar(data.avatar);
      toast.success("Avatar pronto per la prova vestiti");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Salvataggio non riuscito");
    } finally { setPreview(null); setBusy(false); }
  };

  const openCam = () => { if (busy) return; askLevelPermission(); setCamOpen(true); };
  const remove = async () => {
    if (!window.confirm("Eliminare la foto del tuo Avatar?")) return;
    try { await api.delete("/profile/avatar"); setAvatar(null); toast.success("Foto eliminata"); }
    catch { toast.error("Eliminazione non riuscita"); }
  };

  const shown = preview || (avatar?.path ? fileUrl(avatar.path) : null);
  return (
    <section id="il-mio-avatar" className="border hairline bg-white p-6 md:p-8" translate="no" data-testid={manage ? "avatar-settings" : "avatar-box"}>
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <h2 className="font-serif text-3xl md:text-4xl tracking-tighter leading-[1]">Il Mio Avatar{profileName ? <span className="text-[#8C7355]"> · {profileName}</span> : null}</h2>
        {avatar?.path && !busy && (
          <span className="flex items-center gap-2 text-xs text-emerald-700" data-testid="avatar-ready">
            <CheckCircle size={16} weight="fill" /> Pronto per la prova vestiti
          </span>
        )}
      </div>
      <div className="mt-6 flex flex-col sm:flex-row gap-6 items-start">
        <button type="button" onClick={openCam}
          className="upload-zone relative overflow-hidden w-full sm:w-60 shrink-0 cursor-pointer" style={{ aspectRatio: "3/4" }}
          data-testid="avatar-tap-zone">
          {shown ? (
            <img src={shown} alt="Il mio avatar" className="absolute inset-0 w-full h-full object-cover" data-testid="avatar-photo" />
          ) : (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-center px-4">
              <Camera size={40} weight="thin" />
              <span className="mt-3 font-serif text-lg leading-tight" data-testid="avatar-empty-text">Tocca per creare il tuo Avatar</span>
            </div>
          )}
          {busy && <div className="absolute inset-0 bg-white/70 flex items-center justify-center label-caps" data-testid="avatar-busy">Salvo la foto…</div>}
        </button>
        <div className="flex-1">
          <div className="flex gap-3 flex-wrap mb-4">
            <button type="button" disabled={busy} onClick={openCam} className="btn-primary disabled:opacity-50" data-testid="avatar-shoot-now-btn"><Camera size={14} /> Scatta ora</button>
            <button type="button" disabled={busy} onClick={() => galleryRef.current?.click()} className="btn-ghost disabled:opacity-50" data-testid="avatar-gallery-btn"><Images size={14} /> Carica da galleria</button>
            <input ref={galleryRef} type="file" accept="image/*" className="hidden" data-testid="avatar-gallery-input"
              onChange={async (e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) setGallery({ file: f, ...(await photoAgeDays(f)) }); }} />
          </div>
          {avatar?.path && !manage && (
            <p className="text-sm text-neutral-700">Per cambiarla o eliminarla vai in <Link to="/settings" className="underline" data-testid="avatar-settings-link">Impostazioni</Link>.</p>
          )}
          {manage && avatar?.path && (
            <button onClick={remove} className="btn-ghost mt-2" data-testid="avatar-delete-btn"><Trash size={14} /> Elimina foto</button>
          )}
          <Notes />
        </div>
      </div>
      {gallery && <GalleryWarning info={gallery} onCancel={() => setGallery(null)} onAccept={() => { const f = gallery.file; setGallery(null); onCapture(f); }} />}
      <AvatarCamera open={camOpen} initialMode="single" onClose={() => setCamOpen(false)} onCapture={(shot) => onCapture(shot.upper || shot)} />
    </section>
  );
}
