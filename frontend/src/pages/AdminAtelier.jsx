import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";

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
          <Payments byPlan={stats.by_plan} last={stats.last_payments} />
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
