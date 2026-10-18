import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Trash, DeviceMobile, SignOut } from "@phosphor-icons/react";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { api, basePhotoKey, setActiveProfile } from "@/lib/api";
import { useAvatar } from "@/lib/avatar";

function Confirm({ trigger, title, text, action, onConfirm, testid }) {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>{trigger}</AlertDialogTrigger>
      <AlertDialogContent className="rounded-none" translate="no" data-testid={`${testid}-dialog`}>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{text}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel className="rounded-none" data-testid={`${testid}-cancel`}>Annulla</AlertDialogCancel>
          <AlertDialogAction className="rounded-none bg-[#0A0A0A]" onClick={onConfirm} data-testid={`${testid}-confirm`}>
            {action}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export function DeletePhotosSection() {
  const { setAvatar } = useAvatar();
  const [working, setWorking] = useState(false);
  const run = async () => {
    setWorking(true);
    try {
      const { data } = await api.post("/photos/delete-all");
      try { localStorage.removeItem(basePhotoKey()); } catch (_e) { /* ignore */ }
      setAvatar(null);
      toast.success(`Fatto: ${data.deleted_photos} foto cancellate`);
    } catch { toast.error("Cancellazione non riuscita"); }
    finally { setWorking(false); }
  };
  return (
    <section className="mt-8 border hairline bg-white p-6 md:p-8" translate="no" data-testid="delete-photos-section">
      <div className="label-caps">Le tue foto</div>
      <p className="mt-2 text-sm text-neutral-600 leading-relaxed">
        Cancella la tua foto base e tutte le immagini delle prove e degli outfit, con il loro storico.
        I capi dell&apos;armadio e le misure restano.
      </p>
      <Confirm
        testid="delete-photos"
        title="Cancellare tutte le tue foto?"
        text="La foto base e tutte le immagini di prove e outfit verranno cancellate per sempre. L'operazione non si può annullare."
        action="Sì, cancella tutto"
        onConfirm={run}
        trigger={
          <button disabled={working} className="mt-5 btn-ghost" data-testid="delete-photos-btn">
            <Trash size={16} /> {working ? "Cancellazione…" : "Cancella tutte le mie foto"}
          </button>
        }
      />
    </section>
  );
}

export function DevicesSection() {
  const [devices, setDevices] = useState(null);
  useEffect(() => { api.get("/auth/devices").then(({ data }) => setDevices(data)).catch(() => setDevices([])); }, []);
  const logoutAll = async () => {
    try { await api.post("/auth/logout-all"); } catch (_e) { /* ignore */ }
    setActiveProfile(null);
    window.location.href = "/";
  };
  return (
    <section className="mt-8 border hairline bg-white p-6 md:p-8" translate="no" data-testid="devices-section">
      <div className="label-caps">Dispositivi attivi</div>
      <ul className="mt-4 divide-y hairline border hairline">
        {(devices || []).map((d, i) => (
          <li key={i} className="flex items-center gap-3 px-4 py-3" data-testid={`device-row-${i}`}>
            <DeviceMobile size={18} weight="duotone" />
            <span className="text-sm">{d.label}</span>
            {d.current && <span className="label-caps text-[#2E7D32]" data-testid="device-current-badge">Questo dispositivo</span>}
            <span className="ml-auto text-xs text-neutral-500">
              {d.signed_in_at ? `Accesso: ${new Date(d.signed_in_at).toLocaleString()}` : ""}
            </span>
          </li>
        ))}
        {devices && devices.length === 0 && <li className="px-4 py-3 text-sm text-neutral-500">Nessun dispositivo</li>}
      </ul>
      <Confirm
        testid="logout-all"
        title="Uscire da tutti i dispositivi?"
        text="Verrai disconnesso ovunque, anche qui. Potrai rientrare subito con Google."
        action="Esci da tutti"
        onConfirm={logoutAll}
        trigger={
          <button className="mt-5 btn-ghost" data-testid="logout-all-btn">
            <SignOut size={16} /> Esci da tutti
          </button>
        }
      />
    </section>
  );
}
