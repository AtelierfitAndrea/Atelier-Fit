import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";

const GOLD = "#D4AF37";
const eur = (n) => new Intl.NumberFormat("it-IT", { style: "currency", currency: "EUR", useGrouping: "always" }).format(n);
const num = (n) => new Intl.NumberFormat("it-IT", { useGrouping: "always" }).format(n);

function Kpi({ label, value, testid }) {
  return (
    <div className="border p-6" style={{ borderColor: `${GOLD}40` }} data-testid={testid}>
      <div className="text-[11px] tracking-[0.25em] text-white/50">{label}</div>
      <div className="mt-3 text-3xl font-light" style={{ color: GOLD }}>{value}</div>
    </div>
  );
}

function HotCategory({ name, items }) {
  return (
    <div className="border p-6" style={{ borderColor: `${GOLD}40` }} data-testid={`admin-hot-${name.toLowerCase()}`}>
      <div className="text-xs tracking-[0.3em]" style={{ color: GOLD }}>{name.toUpperCase()}</div>
      {items.length === 0 ? <p className="mt-4 text-sm text-white/40">Nessun prodotto analizzato</p> : (
        <table className="mt-4 w-full text-sm">
          <thead><tr className="text-left text-[10px] tracking-[0.2em] text-white/40">
            <th className="py-2 font-normal">PRODOTTO</th><th className="font-normal text-right">ANALISI</th>
          </tr></thead>
          <tbody>
            {items.map((p) => (
              <tr key={`${p.brand}-${p.name}`} className="border-t border-white/10">
                <td className="py-2"><span className="text-white/50">{p.brand}</span> · {p.name}</td>
                <td className="text-right" style={{ color: GOLD }}>{num(p.views)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function TopReferrers({ rows }) {
  return (
    <div className="mt-6 border p-6" style={{ borderColor: `${GOLD}40` }} data-testid="admin-top-referrers">
      {rows.length === 0 ? <p className="text-sm text-white/40" data-testid="admin-top-referrers-empty">Nessuna amica invitata questo mese</p> : (
        <table className="w-full text-sm">
          <thead><tr className="text-left text-[10px] tracking-[0.2em] text-white/40">
            <th className="py-2 font-normal w-10">#</th><th className="font-normal">ATELIERISTA</th>
            <th className="font-normal text-right">INVITATE</th><th className="font-normal text-right">HANNO PROVATO</th>
          </tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={`${r.email}-${i}`} className="border-t border-white/10" data-testid={`admin-top-referrer-${i + 1}`}>
                <td className="py-2" style={{ color: GOLD }}>{i + 1}</td>
                <td>{r.name} <span className="text-white/40">{r.email}</span>{r.is_top && <span className="ml-2 text-[10px] tracking-[0.2em]" style={{ color: GOLD }}>TOP</span>}</td>
                <td className="text-right">{num(r.invited)}</td>
                <td className="text-right" style={{ color: GOLD }}>{num(r.qualified)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function SharesChart({ data, referrals }) {
  const rows = (data || []).map((d) => ({ ...d, label: d.date.slice(8, 10) + "/" + d.date.slice(5, 7) }));
  const total = rows.reduce((a, d) => a + d.count, 0);
  const today = rows.length ? rows[rows.length - 1].count : 0;
  return (
    <>
      <div className="mt-6 grid grid-cols-2 lg:grid-cols-5 gap-4">
        <Kpi label="CONDIVISIONI OGGI" value={num(today)} testid="admin-kpi-shares-today" />
        <Kpi label="CONDIVISIONI 30 GG" value={num(total)} testid="admin-kpi-shares-30" />
        <Kpi label="AMICHE INVITATE" value={num(referrals?.invited || 0)} testid="admin-kpi-ref-invited" />
        <Kpi label="HANNO PROVATO" value={num(referrals?.qualified || 0)} testid="admin-kpi-ref-qualified" />
        <Kpi label="AMICHE ABBONATE" value={num(referrals?.paid || 0)} testid="admin-kpi-ref-paid" />
      </div>
      <div className="mt-4 border p-6" style={{ borderColor: `${GOLD}40` }} data-testid="admin-shares-chart">
        <div className="text-xs tracking-[0.3em]" style={{ color: GOLD }}>FOTO CONDIVISE AL GIORNO</div>
        <div className="mt-6 h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows}>
              <CartesianGrid stroke="#ffffff14" vertical={false} />
              <XAxis dataKey="label" tick={{ fill: "#ffffff80", fontSize: 10 }} axisLine={false} tickLine={false} interval={2} />
              <YAxis allowDecimals={false} tick={{ fill: "#ffffff80", fontSize: 10 }} axisLine={false} tickLine={false} width={30} />
              <Tooltip cursor={{ fill: "#ffffff0d" }} contentStyle={{ background: "#000", border: `1px solid ${GOLD}`, color: "#fff" }}
                formatter={(v) => [`${v} foto`, "Condivise"]} labelStyle={{ color: GOLD }} />
              <Bar dataKey="count" fill={GOLD} radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </>
  );
}

function RevenueChart({ data }) {
  const rows = data.map((d) => ({ ...d, label: d.date.slice(8, 10) + "/" + d.date.slice(5, 7) }));
  const total = data.reduce((a, d) => a + d.total, 0);
  return (
    <div className="mt-6 border p-6" style={{ borderColor: `${GOLD}40` }} data-testid="admin-revenue-chart">
      <div className="flex justify-between text-xs tracking-[0.3em]">
        <span style={{ color: GOLD }}>INCASSI ULTIMI 30 GIORNI</span>
        <span className="text-white/60" data-testid="admin-revenue-chart-total">{eur(total)}</span>
      </div>
      <div className="mt-6 h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows}>
            <CartesianGrid stroke="#ffffff14" vertical={false} />
            <XAxis dataKey="label" tick={{ fill: "#ffffff80", fontSize: 10 }} axisLine={false} tickLine={false} interval={2} />
            <YAxis tick={{ fill: "#ffffff80", fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v}€`} width={40} />
            <Tooltip cursor={{ fill: "#ffffff0d" }} contentStyle={{ background: "#000", border: `1px solid ${GOLD}`, color: "#fff" }}
              formatter={(v, _n, p) => [`${eur(v)} · ${p.payload.count} pagamenti`, "Incasso"]} labelStyle={{ color: GOLD }} />
            <Bar dataKey="total" fill={GOLD} radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function Payments({ byPlan, last }) {
  return (
    <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div className="border p-6" style={{ borderColor: `${GOLD}40` }} data-testid="admin-by-plan">
        <div className="text-xs tracking-[0.3em]" style={{ color: GOLD }}>ACQUISTI PER PIANO</div>
        {byPlan.map((p) => (
          <div key={p.label} className="mt-4 flex justify-between text-sm border-t border-white/10 pt-3">
            <span>{p.label}</span><span className="text-white/60">{num(p.count)} · <span style={{ color: GOLD }}>{eur(p.total)}</span></span>
          </div>
        ))}
      </div>
      <div className="lg:col-span-2 border p-6" style={{ borderColor: `${GOLD}40` }} data-testid="admin-last-payments">
        <div className="text-xs tracking-[0.3em]" style={{ color: GOLD }}>ULTIMI 10 PAGAMENTI</div>
        {last.length === 0 ? <p className="mt-4 text-sm text-white/40">Nessun pagamento ancora</p> : (
          <table className="mt-4 w-full text-sm">
            <tbody>
              {last.map((x, i) => (
                <tr key={i} className="border-t border-white/10">
                  <td className="py-2 text-white/50">{new Date(x.date).toLocaleString("it-IT", { dateStyle: "short", timeStyle: "short" })}</td>
                  <td>{x.email}</td><td>{x.plan}</td>
                  <td className="text-right" style={{ color: GOLD }}>{eur(x.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

const REASON_IT = { mani_viso: "Mani o volto strani", sfondo: "Sfondo cambiato", viso: "Viso diverso", capo: "Capo sbagliato", altro: "Altro" };

function FreeRetries() {
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/admin/free-retries").then(({ data }) => setD(data)).catch(() => {}); }, []);
  if (!d) return null;
  return (
    <div className="mt-6" data-testid="admin-free-retries">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {Object.entries(d.counts).map(([k, n]) => <Kpi key={k} label={(REASON_IT[k] || k).toUpperCase()} value={n} testid={`admin-retry-count-${k}`} />)}
      </div>
      <table className="mt-6 w-full text-sm">
        <thead><tr className="text-left text-[10px] tracking-[0.2em] text-white/40"><th className="py-2 font-normal">DATA</th><th className="font-normal">UTENTE</th><th className="font-normal">PROVA</th><th className="font-normal">MOTIVO</th></tr></thead>
        <tbody>
          {d.last.length === 0 ? <tr><td colSpan={4} className="py-4 text-white/40">Nessuna riprova gratuita</td></tr> : d.last.map((r) => (
            <tr key={r.id} className="border-t border-white/10" data-testid={`admin-retry-row-${r.id}`}>
              <td className="py-2 text-white/60">{new Date(r.created_at).toLocaleString("it-IT", { dateStyle: "short", timeStyle: "short" })}</td>
              <td className="text-white/80">{r.email}</td>
              <td className="text-white/80 truncate max-w-[280px]">{r.kind === "outfit" ? "Outfit · " : ""}{r.name}</td>
              <td style={{ color: GOLD }}>{REASON_IT[r.reason] || r.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function AdminAtelier() {
  const [stats, setStats] = useState(null);
  const [state, setState] = useState("loading");

  useEffect(() => {
    api.get("/admin/stats").then(({ data }) => { setStats(data); setState("in"); }).catch(() => setState("error"));
  }, []);

  return (
    <div className="min-h-screen bg-black text-white" translate="no" data-testid="admin-page">
      {state === "loading" && <div className="min-h-screen flex items-center justify-center text-xs tracking-[0.3em] text-white/50">CARICAMENTO…</div>}
      {state === "error" && <div className="min-h-screen flex items-center justify-center text-sm text-white/60" data-testid="admin-error">Dati non disponibili, riprova.</div>}
      {state === "in" && stats && (
        <div className="max-w-6xl mx-auto px-6 py-12">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="tracking-[0.5em] text-2xl font-light" style={{ color: GOLD }}>MY ATELIER</h1>
              <p className="mt-1 text-xs tracking-[0.3em] text-white/50">DASHBOARD FONDATORE</p>
            </div>
            <Link to="/stanza/assistenza" className="text-xs tracking-[0.3em] border px-4 py-2 mr-3" style={{ borderColor: GOLD, color: GOLD }} data-testid="admin-support-link">ASSISTENZA</Link>
            <Link to="/dashboard" className="text-xs tracking-[0.3em] border px-4 py-2" style={{ borderColor: GOLD, color: GOLD }} data-testid="admin-back-btn">TORNA ALL'APP</Link>
          </div>
          {stats.demo && (
            <div className="mt-8 py-3 text-center text-sm tracking-[0.4em] font-semibold text-black" style={{ background: GOLD }} data-testid="admin-demo-banner">
              DATI DIMOSTRATIVI
            </div>
          )}
          <div className="mt-8 grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Kpi label="ISCRITTI TOTALI" value={num(stats.kpi.subscribers_total)} testid="admin-kpi-subscribers" />
            <Kpi label="ACCESSI OGGI" value={num(stats.kpi.logins_today)} testid="admin-kpi-visits" />
            <Kpi label="ABBONATI PAGANTI" value={num(stats.kpi.paying_subscribers)} testid="admin-kpi-paying" />
            <Kpi label="INCASSO TOTALE" value={eur(stats.kpi.revenue_total)} testid="admin-kpi-revenue" />
          </div>
          <div className="mt-4 grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Kpi label="INCASSO DEL MESE" value={eur(stats.kpi.revenue_month)} testid="admin-kpi-revenue-month" />
          </div>
          <h2 className="mt-14 text-sm tracking-[0.4em]" style={{ color: GOLD }}>PAGAMENTI STRIPE</h2>
          <RevenueChart data={stats.daily_revenue} />
          <Payments byPlan={stats.by_plan} last={stats.last_payments} />
          <h2 className="mt-14 text-sm tracking-[0.4em]" style={{ color: GOLD }}>LOOK CONDIVISI E INVITI</h2>
          <p className="mt-1 text-xs text-white/40">Foto firmate condivise dagli utenti e amiche portate col link personale</p>
          <SharesChart data={stats.daily_shares} referrals={stats.referrals} />
          <h2 className="mt-14 text-sm tracking-[0.4em]" style={{ color: GOLD }}>CLASSIFICA ATELIERISTE</h2>
          <p className="mt-1 text-xs text-white/40">Le 10 persone che hanno portato più amiche questo mese</p>
          <TopReferrers rows={stats.top_referrers || []} />
          <h2 className="mt-14 text-sm tracking-[0.4em]" style={{ color: GOLD }}>RIPROVE GRATUITE</h2>
          <p className="mt-1 text-xs text-white/40">Prove rigenerate senza credito e motivo indicato dall&apos;utente</p>
          <FreeRetries />
          <h2 className="mt-14 text-sm tracking-[0.4em]" style={{ color: GOLD }}>PRODOTTI HOT</h2>
          <p className="mt-1 text-xs text-white/40">I prodotti più analizzati dagli utenti, per categoria</p>
          <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-4">
            {Object.entries(stats.hot_products).map(([cat, items]) => <HotCategory key={cat} name={cat} items={items} />)}
          </div>
        </div>
      )}
    </div>
  );
}
