import { useEffect, useState } from "react";
import { toast } from "sonner";
import { EnvelopeSimple, PaperPlaneTilt } from "@phosphor-icons/react";
import { api } from "@/lib/api";

const CATS = [["maglie", "Maglie"], ["giacche", "Giacche"], ["pantaloni", "Pantaloni"], ["scarpe", "Scarpe"], ["outfit", "Outfit completo"], ["foto", "Foto"], ["misure", "Misure"], ["privacy", "Privacy"], ["altro", "Altro"]];
const STATUS = { open: "In lavorazione", answered: "Risposta inviata", needs_human: "Presa in carico dal team", closed: "Chiusa" };
const fmt = (d) => new Date(d).toLocaleString("it-IT", { dateStyle: "short", timeStyle: "short" });

function Thread({ t, onSent }) {
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const send = async () => {
    setBusy(true);
    try { await api.post(`/support/tickets/${t.id}/messages`, { message: msg }); setMsg(""); toast.success("Messaggio inviato"); onSent(); }
    catch { toast.error("Invio non riuscito"); } finally { setBusy(false); }
  };
  return (
    <div className="border hairline bg-white p-5" data-testid={`support-ticket-${t.id}`}>
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <div className="font-serif text-xl">{t.subject}</div>
          <div className="label-caps text-[#8C7355] mt-1">{t.category} · {fmt(t.created_at)}</div>
        </div>
        <span className="label-caps border hairline px-2 py-1" data-testid={`support-ticket-status-${t.id}`}>{STATUS[t.status] || t.status}</span>
      </div>
      <div className="mt-4 space-y-3">
        {t.messages.map((m) => (
          <div key={m.id} className={`p-3 text-sm whitespace-pre-line ${m.author === "user" ? "bg-[#FAF8F5] ml-8" : "border-l-2 border-[#8B7355] pl-4 mr-8"}`} data-testid={`support-msg-${m.id}`}>
            <div className="label-caps mb-1 text-neutral-500">{m.author === "user" ? "Tu" : "My Atelier"} · {fmt(m.created_at)}</div>
            {m.body}
          </div>
        ))}
        {t.status === "open" && <p className="text-xs italic text-[#8B7355]" data-testid="support-waiting">Stiamo preparando la risposta, la riceverai anche via email…</p>}
      </div>
      {t.status !== "closed" && (
        <div className="mt-4 flex gap-2">
          <input value={msg} onChange={(e) => setMsg(e.target.value)} placeholder="Scrivi un altro messaggio…" className="flex-1 border hairline px-3 py-2 text-sm outline-none focus:border-[#0A0A0A]" data-testid={`support-followup-input-${t.id}`} />
          <button onClick={send} disabled={busy || !msg.trim()} className="btn-primary disabled:opacity-40" data-testid={`support-followup-send-${t.id}`}><PaperPlaneTilt size={14} /></button>
        </div>
      )}
    </div>
  );
}

export default function Support() {
  const [cat, setCat] = useState("maglie");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [tickets, setTickets] = useState([]);

  const load = () => api.get("/support/tickets").then(({ data }) => setTickets(data)).catch(() => {});
  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (!tickets.some((t) => t.status === "open")) return undefined;
    const id = setInterval(load, 6000);
    return () => clearInterval(id);
  }, [tickets]);

  const submit = async (e) => {
    e.preventDefault();
    if (subject.trim().length < 3 || message.trim().length < 5) { toast.error("Scrivi oggetto e messaggio"); return; }
    setBusy(true);
    try {
      await api.post("/support/tickets", { category: cat, subject, message });
      setSubject(""); setMessage(""); toast.success("Richiesta inviata: ti rispondiamo qui e via email"); load();
    } catch { toast.error("Invio non riuscito"); } finally { setBusy(false); }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-10" data-testid="support-root">
      <div className="lg:col-span-5">
        <div className="label-caps mb-3">Assistenza</div>
        <h1 className="font-serif text-4xl md:text-5xl tracking-tighter leading-[1.05]">Come possiamo aiutarti?</h1>
        <p className="mt-4 text-neutral-600 leading-relaxed">Maglie, giacche, pantaloni, scarpe, foto, misure o privacy: scrivici, ti rispondiamo qui e via email da studio@myatelierapp.it.</p>
        <form onSubmit={submit} className="mt-8 border hairline bg-white p-6 space-y-5" data-testid="support-form">
          <div className="flex flex-wrap gap-2">
            {CATS.map(([k, l]) => (
              <button type="button" key={k} onClick={() => setCat(k)} className={`px-3 py-1.5 text-xs border hairline ${cat === k ? "bg-[#0A0A0A] text-white" : "bg-white"}`} data-testid={`support-cat-${k}`}>{l}</button>
            ))}
          </div>
          <input value={subject} onChange={(e) => setSubject(e.target.value)} maxLength={160} placeholder="Oggetto" className="w-full border hairline px-3 py-3 outline-none focus:border-[#0A0A0A]" data-testid="support-subject-input" />
          <textarea value={message} onChange={(e) => setMessage(e.target.value)} maxLength={4000} rows={6} placeholder="Descrivi la tua richiesta…" className="w-full border hairline px-3 py-3 outline-none focus:border-[#0A0A0A] resize-y" data-testid="support-message-input" />
          <button disabled={busy} className="btn-primary disabled:opacity-50" data-testid="support-submit-btn"><EnvelopeSimple size={14} /> {busy ? "Invio…" : "Invia richiesta"}</button>
        </form>
      </div>
      <div className="lg:col-span-7">
        <div className="label-caps mb-3">Le tue richieste</div>
        {tickets.length === 0 ? (
          <p className="text-sm text-neutral-500 border hairline p-6 bg-white" data-testid="support-empty">Non hai ancora inviato richieste.</p>
        ) : (
          <div className="space-y-4" data-testid="support-list">{tickets.map((t) => <Thread key={t.id} t={t} onSent={load} />)}</div>
        )}
      </div>
    </div>
  );
}
