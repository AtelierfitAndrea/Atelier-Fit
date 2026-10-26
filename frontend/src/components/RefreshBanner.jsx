import { toast } from "sonner";
import { CalendarCheck } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { useAvatar } from "@/lib/avatar";

export default function RefreshBanner({ onWeight }) {
  const { refreshDue, setRefreshDue } = useAvatar();
  if (!refreshDue) return null;

  const later = async () => {
    try { await api.post("/profile/refresh/snooze"); setRefreshDue(false); toast("Te lo ricordiamo tra 7 giorni"); }
    catch { toast.error("Riprova"); }
  };
  const photo = () => window.dispatchEvent(new Event("atelier-open-avatar"));

  return (
    <div className="flex items-center gap-4 flex-wrap border border-[#8B7355]/40 bg-[#FAF8F5] px-5 py-4" data-testid="refresh-banner">
      <CalendarCheck size={22} weight="thin" className="text-[#8B7355] shrink-0" />
      <div className="flex-1 min-w-[220px]">
        <div className="font-serif text-lg leading-tight">Sono passati 2 mesi: aggiorna peso e foto avatar</div>
        <p className="text-xs text-neutral-600 mt-0.5">Così la prova vestiti resta fedele a come sei oggi.</p>
      </div>
      <div className="flex gap-2 flex-wrap">
        <button onClick={photo} className="btn-primary" data-testid="refresh-banner-photo">Aggiorna foto</button>
        <button onClick={onWeight} className="btn-ghost" data-testid="refresh-banner-weight">Aggiorna peso</button>
        <button onClick={later} className="text-xs underline text-neutral-500 px-2" data-testid="refresh-banner-later">Più tardi</button>
      </div>
    </div>
  );
}
