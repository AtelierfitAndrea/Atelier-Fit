import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Ruler } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { useAvatar } from "@/lib/avatar";

export default function ReminderPopup() {
  const { reminderDue, setReminderDue, reminderYoung } = useAvatar();
  const navigate = useNavigate();
  if (!reminderDue) return null;

  const later = async () => {
    try { await api.post("/profile/reminder/snooze"); setReminderDue(false); toast("Te lo ricordiamo tra 7 giorni"); }
    catch { toast.error("Riprova"); }
  };
  const now = () => { setReminderDue(false); navigate("/profile"); };

  return (
    <div className="fixed inset-0 z-[85] bg-black/50 backdrop-blur-sm flex items-center justify-center p-4" translate="no" data-testid="measures-reminder-popup">
      <div className="bg-white max-w-md w-full border hairline p-8 fade-up">
        <Ruler size={26} weight="thin" className="text-[#8C7355]" />
        <h3 className="font-serif text-3xl tracking-tight mt-4" data-testid="measures-reminder-title">Le tue misure sono cambiate?</h3>
        <p className="mt-2 text-neutral-600" data-testid="measures-reminder-text">{reminderYoung ? "Sei ancora in fase di crescita, controllale" : "Aggiorna peso e misure"}</p>
        <div className="mt-8 flex gap-3 flex-wrap">
          <button onClick={now} className="btn-primary" data-testid="measures-reminder-edit">Aggiorna ora</button>
          <button onClick={later} className="btn-ghost" data-testid="measures-reminder-later">Ricordamelo tra 7 giorni</button>
        </div>
      </div>
    </div>
  );
}
