import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Ruler } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { useAvatar } from "@/lib/avatar";

const TEXT_YOUNG = "Sei ancora in fase di crescita. Vuoi verificare le tue misure per mantenere la taglia perfetta?";
const TEXT_ADULT = "Per garantirti sempre la taglia perfetta, vuoi controllare se peso o misure sono cambiati?";

export default function ReminderPopup() {
  const { reminderDue, setReminderDue, reminderYoung } = useAvatar();
  const navigate = useNavigate();

  // Shown at most once every 7 days: mark it as shown as soon as it appears.
  useEffect(() => { if (reminderDue) api.post("/profile/reminder/snooze").catch(() => {}); }, [reminderDue]);
  if (!reminderDue) return null;

  const close = () => setReminderDue(false);
  const now = () => { close(); navigate("/profile"); };

  return (
    <div className="fixed inset-0 z-[85] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4" translate="no" data-testid="measures-reminder-popup">
      <div className="bg-[#0A0A0A] text-white max-w-md w-full border border-[#D4AF37]/40 p-8 md:p-10 fade-up">
        <Ruler size={26} weight="thin" className="text-[#D4AF37]" />
        <div className="mt-5 h-px w-12 bg-[#D4AF37]" />
        <h3 className="font-serif text-3xl tracking-tight mt-5" data-testid="measures-reminder-title">Le tue misure sono cambiate?</h3>
        <p className="mt-3 text-white/75 leading-relaxed" data-testid="measures-reminder-text">{reminderYoung ? TEXT_YOUNG : TEXT_ADULT}</p>
        <div className="mt-8 flex gap-3 flex-wrap">
          <button onClick={now} className="bg-[#D4AF37] px-6 py-3 label-caps !text-[#0A0A0A] hover:bg-white transition-colors" data-testid="measures-reminder-edit">Aggiorna ora</button>
          <button onClick={close} className="border border-white/40 px-6 py-3 label-caps !text-white/85 hover:border-[#D4AF37] transition-colors" data-testid="measures-reminder-later">Ricordamelo tra 7 giorni</button>
        </div>
      </div>
    </div>
  );
}
