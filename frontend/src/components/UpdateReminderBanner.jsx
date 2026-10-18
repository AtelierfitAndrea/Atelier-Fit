import { toast } from "sonner";
import { ArrowsClockwise } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { useAvatar } from "@/lib/avatar";

export default function UpdateReminderBanner({ name }) {
  const { reminderDue, setReminderDue, requestUpdate } = useAvatar();
  if (!reminderDue) return null;

  const later = async () => {
    try { await api.post("/profile/reminder/snooze"); setReminderDue(false); toast("Te lo ricordiamo tra qualche giorno"); }
    catch { toast.error("Riprova"); }
  };

  return (
    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-[#0A0A0A] text-white px-5 py-4 fade-up" translate="no" data-testid="update-reminder-banner">
      <div className="flex items-center gap-3">
        <ArrowsClockwise size={20} />
        <p className="font-serif text-lg leading-snug" data-testid="update-reminder-text">
          Ciao{name ? ` ${name}` : ""}, vuoi aggiornare foto/peso per mantenere la precisione al 98%?
        </p>
      </div>
      <div className="flex gap-3 shrink-0">
        <button onClick={requestUpdate} className="bg-white text-[#0A0A0A] px-5 py-2.5 label-caps !text-[#0A0A0A] hover:bg-[#D4AF37] transition-colors" data-testid="update-reminder-now">Aggiorna ora</button>
        <button onClick={later} className="border border-white/40 px-5 py-2.5 label-caps !text-white/80 hover:border-white transition-colors" data-testid="update-reminder-later">Ricorda più tardi</button>
      </div>
    </div>
  );
}
