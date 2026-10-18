import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Camera, CheckCircle, Trash } from "@phosphor-icons/react";
import { api, fileUrl } from "@/lib/api";
import { useAvatar } from "@/lib/avatar";
import { extractBodyRatios, extractTwoPartRatios } from "@/lib/pose";
import AvatarCamera from "@/components/AvatarCamera";

const POSE_ERRORS = {
  too_dark: ["Foto troppo buia", "Accendi una luce o mettiti davanti a una finestra, poi riscatta."],
  no_head: ["Non vediamo la testa", "Inquadra tutto il corpo: la testa deve essere dentro la foto."],
  no_feet: ["Non vediamo i piedi", "Allontana il telefono o abbassalo: i piedi devono essere visibili."],
  cut_top: ["Foto tagliata in alto", "Lascia un po' di spazio sopra la testa."],
  cut_bottom: ["Foto tagliata in basso", "Lascia un po' di spazio sotto i piedi."],
  too_far: ["Sei troppo lontano", "Avvicinati: il corpo deve riempire quasi tutta l'altezza della foto."],
  upper_no_hips: ["Foto 1/2: non vediamo i fianchi", "Nel busto inquadra dalla testa fino ai fianchi, con i fianchi sulla linea dorata."],
  lower_no_hips: ["Foto 2/2: non vediamo i fianchi", "Nelle gambe parti dai fianchi, sulla linea dorata, fino ai piedi."],
  no_pose: ["Non vediamo bene la tua figura", "Mettiti in piedi, frontale, a corpo intero e con più luce."],
};

function PhotoIssue({ code, onRetake }) {
  const [title, hint] = POSE_ERRORS[code] || POSE_ERRORS.no_pose;
  return (
    <div className="mt-4 border-2 border-[#B91C1C] bg-[#FEF2F2] p-4 fade-up" data-testid="avatar-photo-issue">
      <div className="font-serif text-lg text-[#991B1B]" data-testid="avatar-photo-issue-title">{title}</div>
      <p className="text-sm text-[#7F1D1D] mt-1">{hint} La foto non è stata salvata.</p>
      <button onClick={onRetake} className="btn-primary mt-3" data-testid="avatar-retake-btn">Riscatta la foto</button>
    </div>
  );
}

function BodyForm({ initial, onSubmit, onCancel }) {
  const [h, setH] = useState(initial.height_cm || "");
  const [w, setW] = useState(initial.weight_kg || "");
  const [g, setG] = useState(initial.gender === "male" ? "male" : "female");
  const ok = Number(h) >= 120 && Number(h) <= 230 && Number(w) >= 40 && Number(w) <= 150;
  return (
    <div className="mt-4 border hairline p-4 bg-white fade-up" data-testid="avatar-body-form">
      <div className="label-caps mb-3">Controlla altezza e peso</div>
      <div className="flex flex-wrap gap-3 items-center">
        {[["cm", h, setH, "182", "avatar-height-input"], ["kg", w, setW, "70", "avatar-weight-input"]].map(([u, v, set, ph, id]) => (
          <div key={u} className="flex items-center border hairline w-32">
            <input type="number" inputMode="numeric" value={v} placeholder={ph} onChange={(e) => set(e.target.value)}
              className="w-full px-3 py-2 bg-transparent outline-none font-serif text-lg" data-testid={id} />
            <span className="px-2 text-xs text-neutral-500">{u}</span>
          </div>
        ))}
        {[["female", "Donna"], ["male", "Uomo"]].map(([k, l]) => (
          <button key={k} type="button" onClick={() => setG(k)}
            className={`px-3 py-2 label-caps border hairline ${g === k ? "bg-[#0A0A0A] !text-white" : "bg-white"}`} data-testid={`avatar-gender-${k}`}>{l}</button>
        ))}
      </div>
      <div className="mt-4 flex gap-3">
        <button disabled={!ok} onClick={() => onSubmit({ height_cm: Number(h), weight_kg: Number(w), gender: g })} className="btn-primary disabled:opacity-40" data-testid="avatar-body-submit">Calcola le mie misure</button>
        <button onClick={onCancel} className="btn-ghost" data-testid="avatar-body-cancel">Annulla</button>
      </div>
    </div>
  );
}

function Notes() {
  return (
    <div className="mt-4 space-y-1.5" data-testid="avatar-notes">
      <p className="text-xs text-neutral-600">👙 Consiglio Atelier: con abbigliamento aderente o costume attendibilità 98%.</p>
      <p className="text-[11px] text-neutral-400" data-testid="avatar-privacy-note">🔒 La foto è criptata e visibile solo dal tuo account Atelier. Non la mostriamo a nessuno. Puoi cancellarla quando vuoi.</p>
    </div>
  );
}

export default function AvatarBox({ manage = false }) {
  const { avatar, setAvatar, profileName, updateRequest, setReminderDue } = useAvatar();
  const [forceBody, setForceBody] = useState(false);
  const [camOpen, setCamOpen] = useState(false);
  const [pending, setPending] = useState(null);
  const [busy, setBusy] = useState(false);
  const [profile, setProfile] = useState({});
  const [issue, setIssue] = useState(null);

  useEffect(() => {
    if (!updateRequest || manage) return;
    document.getElementById("il-mio-avatar")?.scrollIntoView({ behavior: "smooth" });
    setForceBody(true);
    setCamOpen(true);
  }, [updateRequest, manage]);
  useEffect(() => {
    if (!manage && window.location.hash === "#il-mio-avatar") setTimeout(() => document.getElementById("il-mio-avatar")?.scrollIntoView({ behavior: "smooth" }), 300);
  }, [manage]);
  useEffect(() => { api.get("/profile/measurements").then(({ data }) => setProfile(data || {})).catch(() => {}); }, []);

  const upload = async (file, ratios, body = {}) => {
    setBusy(true);
    try {
      const params = new URLSearchParams({ features: JSON.stringify(ratios) });
      Object.entries(body).forEach(([k, v]) => params.set(k, String(v)));
      const fd = new FormData(); fd.append("photo", file);
      const { data } = await api.post(`/profile/avatar?${params}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      setAvatar(data.avatar);
      setProfile(data.measurements || profile);
      setPending(null);
      setForceBody(false);
      setReminderDue(false);
      window.dispatchEvent(new Event("atelier-measures-updated"));
      toast.success("Avatar pronto: misure calcolate e outfit collegati");
    } catch (e) {
      toast.error(e?.response?.data?.detail === "need_height" ? "Inserisci altezza e peso" : (e?.response?.data?.detail || "Salvataggio non riuscito"));
    } finally { setBusy(false); }
  };

  const onCapture = async (shot) => {
    setCamOpen(false);
    setIssue(null);
    let file = shot.upper || shot;
    let preview = URL.createObjectURL(file);
    setPending({ file, preview, ratios: null, ask: false });
    setBusy(true);
    let ratios;
    try {
      if (shot.upper) {
        ({ ratios, file } = await extractTwoPartRatios(shot.upper, shot.lower));
        preview = URL.createObjectURL(file);
      } else {
        ratios = await extractBodyRatios(file);
      }
    } catch (e) { setIssue(e.message); setPending({ file, preview, ratios: null, ask: false, bad: true }); setBusy(false); return; }
    setBusy(false);
    const fresh = (await api.get("/profile/measurements").catch(() => ({ data: profile }))).data || {};
    setProfile(fresh);
    if (forceBody || !fresh.height_cm || !fresh.weight_kg) { setPending({ file, preview, ratios, ask: true }); return; }
    await upload(file, ratios);
  };

  const remove = async () => {
    if (!window.confirm("Eliminare la foto del tuo Avatar?")) return;
    try { await api.delete("/profile/avatar"); setAvatar(null); toast.success("Foto eliminata"); }
    catch { toast.error("Eliminazione non riuscita"); }
  };

  const shown = pending?.preview || (avatar?.path ? fileUrl(avatar.path) : null);
  return (
    <section id="il-mio-avatar" className="border hairline bg-white p-6 md:p-8" translate="no" data-testid={manage ? "avatar-settings" : "avatar-box"}>
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <h2 className="font-serif text-3xl md:text-4xl tracking-tighter leading-[1]">Il Mio Avatar{profileName ? <span className="text-[#8C7355]"> · {profileName}</span> : null}</h2>
        {avatar?.path && !pending && (
          <span className="flex items-center gap-2 text-xs text-emerald-700" data-testid="avatar-ready">
            <CheckCircle size={16} weight="fill" /> Misure e outfit attivi
          </span>
        )}
      </div>
      <div className="mt-6 flex flex-col sm:flex-row gap-6 items-start">
        <button type="button" onClick={() => !busy && setCamOpen(true)}
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
          {busy && <div className="absolute inset-0 bg-white/70 flex items-center justify-center label-caps" data-testid="avatar-busy">Calcolo misure…</div>}
        </button>
        <div className="flex-1">
          {avatar?.path && !pending && (
            <p className="text-sm text-neutral-700">Una sola foto per tutto: le tue misure sono calcolate e la usiamo per ogni prova e outfit.
              {!manage && <> Per cambiarla vai in <Link to="/settings" className="underline" data-testid="avatar-settings-link">Impostazioni</Link>.</>}
            </p>
          )}
          {issue && <PhotoIssue code={issue} onRetake={() => { setIssue(null); setPending(null); setCamOpen(true); }} />}
          {pending?.ask && (
            <BodyForm initial={profile} onCancel={() => setPending(null)} onSubmit={(b) => upload(pending.file, pending.ratios, b)} />
          )}
          {manage && avatar?.path && (
            <div className="mt-4 flex gap-3">
              <button onClick={() => setCamOpen(true)} className="btn-primary" data-testid="avatar-change-btn"><Camera size={14} /> Cambia foto</button>
              <button onClick={remove} className="btn-ghost" data-testid="avatar-delete-btn"><Trash size={14} /> Elimina foto</button>
            </div>
          )}
          <Notes />
        </div>
      </div>
      <AvatarCamera open={camOpen} onClose={() => setCamOpen(false)} onCapture={onCapture} />
    </section>
  );
}
