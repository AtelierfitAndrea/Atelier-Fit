import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Switch } from "@/components/ui/switch";

const GOLD = "#D4AF37";
const STATUS = { open: "Aperta", answered: "Risposta", needs_human: "Da gestire", closed: "Chiusa" };
const AUTHOR = { user: "CLIENTE", ai: "AI", admin: "TU" };
const fmt = (d) => (d ? new Date(d).toLocaleString("it-IT", { dateStyle: "short", timeStyle: "short" }) : "—");

function TicketRow({ t, active, onClick }) {
  return (
    <button onClick={onClick} className={`w-full text-left p-4 border-b border-white/10 hover:bg-white/5 ${active ? "bg-white/10" : ""}`} data-testid={`admin-support-row-${t.id}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm truncate">{t.unread_admin && <span className="inline-block w-1.5 h-1.5 rounded-full mr-2 align-middle" style={{ background: GOLD }} />}{t.name || t.email}</span>
        <span className="text-[10px] tracking-[0.2em] shrink-0" style={{ color: t.status === "needs_human" ? "#F87171" : GOLD }}>{(STATUS[t.status] || t.status).toUpperCase()}</span>
      </div>
      <div className="text-xs text-white/70 mt-1 truncate">{t.subject}</div>
      <div className="text-[11px] text-white/40 mt-1 truncate">{t.source === "email" ? "Email" : "App"} · {t.category || "—"} · {fmt(t.updated_at)}</div>
    </button>
  );
}

function Message({ m }) {
  const mine = m.author !== "user";
  return (
    <div className={`p-4 text-sm whitespace-pre-line border ${mine ? "ml-10" : "mr-10"} ${m.draft ? "border-dashed" : ""}`} style={{ borderColor: mine ? `${GOLD}60` : "rgba(255,255,255,0.15)" }} data-testid={`admin-support-msg-${m.id}`}>
      <div className="text-[10px] tracking-[0.25em] mb-2" style={{ color: mine ? GOLD : "rgba(255,255,255,0.5)" }}>
        {AUTHOR[m.author] || m.author} · {fmt(m.created_at)}
        {m.draft && " · BOZZA NON INVIATA"}
        {mine && !m.draft && (m.sent ? " · INVIATA" : ` · NON INVIATA${m.send_error ? `: ${m.send_error}` : ""}`)}
      </div>
      {m.body}
    </div>
  );
}

function Detail({ id, onChanged }) {
  const [t, setT] = useState(null);
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState("");
  const load = useCallback((initReply = false) => api.get(`/admin/support/tickets/${id}`).then(({ data }) => {
    setT(data);
    if (initReply) {
      const draft = [...data.messages].reverse().find((m) => m.draft);
      setReply(draft ? draft.body : "");
    }
  }), [id]);
  useEffect(() => { load(true).then(onChanged); }, [load]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!t) return <div className="p-8 text-white/40 text-sm">Caricamento…</div>;

  const send = async () => {
    setBusy("send");
    try { await api.post(`/admin/support/tickets/${id}/reply`, { message: reply }); toast.success("Risposta inviata (CC andremo2014@gmail.com)"); setReply(""); await load(); onChanged(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Invio non riuscito"); } finally { setBusy(""); }
  };
  const draft = async () => {
    setBusy("draft");
    try { const { data } = await api.post(`/admin/support/tickets/${id}/ai-draft`); setReply(data.draft || ""); if (!data.relevant) toast("Per l'AI non è una richiesta di assistenza: rivedi la bozza"); }
    catch (e) { toast.error(e?.response?.data?.detail || "AI non disponibile"); } finally { setBusy(""); }
  };
  const setStatus = async (status) => { await api.patch(`/admin/support/tickets/${id}`, { status }); await load(); onChanged(); };

  return (
    <div className="p-6 flex flex-col h-full" data-testid="admin-support-detail">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="text-lg">{t.subject}</div>
          <div className="text-xs text-white/50 mt-1" data-testid="admin-support-detail-from">{t.name} &lt;{t.email}&gt; · {t.source === "email" ? "Email" : "App"}</div>
        </div>
        <select value={t.status} onChange={(e) => setStatus(e.target.value)} className="bg-black border text-xs px-3 py-2" style={{ borderColor: GOLD, color: GOLD }} data-testid="admin-support-status-select">
          {Object.entries(STATUS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
      </div>
      <div className="mt-6 space-y-3 flex-1 overflow-y-auto">{t.messages.map((m) => <Message key={m.id} m={m} />)}</div>
      <div className="mt-6">
        <textarea value={reply} onChange={(e) => setReply(e.target.value)} rows={7} placeholder="Scrivi la risposta manuale…" className="w-full bg-transparent border p-3 text-sm outline-none" style={{ borderColor: `${GOLD}60` }} data-testid="admin-support-reply-input" />
        <div className="mt-3 flex gap-3 flex-wrap">
          <button onClick={send} disabled={!!busy || !reply.trim()} className="text-xs tracking-[0.3em] px-5 py-3 disabled:opacity-40" style={{ background: GOLD, color: "#0A0A0A" }} data-testid="admin-support-send-btn">{busy === "send" ? "INVIO…" : "INVIA DA STUDIO@"}</button>
          <button onClick={draft} disabled={!!busy} className="text-xs tracking-[0.3em] px-5 py-3 border disabled:opacity-40" style={{ borderColor: GOLD, color: GOLD }} data-testid="admin-support-ai-draft-btn">{busy === "draft" ? "GENERO…" : "BOZZA AI"}</button>
        </div>
      </div>
    </div>
  );
}

export default function AdminSupport() {
  const [data, setData] = useState(null);
  const [filter, setFilter] = useState("");
  const [sel, setSel] = useState(null);
  const [syncing, setSyncing] = useState(false);

  const load = useCallback(() => api.get("/admin/support/tickets", { params: filter ? { status: filter } : {} }).then(({ data: d }) => setData(d)), [filter]);
  useEffect(() => { load(); }, [load]);

  const toggle = async (v) => {
    const { data: s } = await api.put("/admin/support/settings", { auto_reply: v });
    setData((d) => ({ ...d, settings: s }));
    toast.success(v ? "Risposte automatiche AI attive" : "Risposte automatiche disattivate: l'AI prepara solo bozze");
  };
  const sync = async () => {
    setSyncing(true);
    try { await api.post("/admin/support/sync"); toast.success("Controllo della casella avviato"); setTimeout(() => { load(); setSyncing(false); }, 8000); }
    catch { toast.error("Controllo non riuscito"); setSyncing(false); }
  };

  const s = data?.settings || {};
  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white" data-testid="admin-support-root">
      <div className="max-w-[1400px] mx-auto px-6 md:px-10 py-8">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <div className="text-[11px] tracking-[0.4em] text-white/50">STANZA DEL PROPRIETARIO</div>
            <h1 className="tracking-[0.4em] text-2xl font-light mt-2" style={{ color: GOLD }}>ASSISTENZA</h1>
            <div className="text-xs text-white/40 mt-2" data-testid="admin-support-poll-info">studio@myatelierapp.it · ultimo controllo {fmt(s.last_poll_at)}{s.last_poll_error ? ` · errore: ${s.last_poll_error}` : ""}</div>
          </div>
          <div className="flex items-center gap-5 flex-wrap">
            <label className="flex items-center gap-3 text-xs tracking-[0.2em]" style={{ color: GOLD }}>
              RISPOSTE AUTOMATICHE AI
              <Switch checked={!!s.auto_reply} onCheckedChange={toggle} className="data-[state=checked]:bg-[#D4AF37] data-[state=unchecked]:bg-white/20" data-testid="admin-support-autoreply-toggle" />
            </label>
            <button onClick={sync} disabled={syncing} className="text-xs tracking-[0.3em] border px-4 py-2 disabled:opacity-40" style={{ borderColor: GOLD, color: GOLD }} data-testid="admin-support-sync-btn">{syncing ? "CONTROLLO…" : "CONTROLLA MAIL ORA"}</button>
            <Link to="/stanza" className="text-xs tracking-[0.3em] border px-4 py-2" style={{ borderColor: GOLD, color: GOLD }} data-testid="admin-support-back-btn">KPI</Link>
          </div>
        </div>

        <div className="mt-8 flex gap-2 flex-wrap">
          {[["", "TUTTE"], ...Object.entries(STATUS).map(([k, l]) => [k, l.toUpperCase()])].map(([k, l]) => (
            <button key={k || "all"} onClick={() => setFilter(k)} className="text-[11px] tracking-[0.2em] px-3 py-1.5 border" style={{ borderColor: filter === k ? GOLD : "rgba(255,255,255,0.2)", color: filter === k ? GOLD : "rgba(255,255,255,0.6)" }} data-testid={`admin-support-filter-${k || "all"}`}>
              {l}{k && data?.counts ? ` · ${data.counts[k]}` : ""}
            </button>
          ))}
        </div>

        <div className="mt-4 grid grid-cols-1 lg:grid-cols-12 border" style={{ borderColor: `${GOLD}40`, minHeight: 560 }}>
          <div className="lg:col-span-4 border-b lg:border-b-0 lg:border-r overflow-y-auto max-h-[75vh]" style={{ borderColor: `${GOLD}40` }} data-testid="admin-support-list">
            {!data ? <div className="p-6 text-white/40 text-sm">Caricamento…</div> : data.tickets.length === 0 ? (
              <div className="p-6 text-white/40 text-sm" data-testid="admin-support-empty">Nessuna conversazione</div>
            ) : data.tickets.map((t) => <TicketRow key={t.id} t={t} active={sel === t.id} onClick={() => setSel(t.id)} />)}
          </div>
          <div className="lg:col-span-8">
            {sel ? <Detail key={sel} id={sel} onChanged={load} /> : <div className="p-8 text-white/40 text-sm">Seleziona una conversazione</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
