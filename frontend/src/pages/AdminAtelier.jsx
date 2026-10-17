import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const GOLD = "#D4AF37";
const eur = (n) => new Intl.NumberFormat("it-IT", { style: "currency", currency: "EUR" }).format(n);
const num = (n) => new Intl.NumberFormat("it-IT").format(n);

function Login({ onOk }) {
  const [pwd, setPwd] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr("");
    try { await api.post("/admin/login", { password: pwd }); onOk(); }
    catch (e2) { const d = e2?.response?.data?.detail; setErr(typeof d === "string" ? d : "Accesso non riuscito"); }
    finally { setBusy(false); }
  };
  return (
    <form onSubmit={submit} className="w-full max-w-sm" data-testid="admin-login-form">
      <h1 className="text-center tracking-[0.5em] text-2xl font-light" style={{ color: GOLD }}>MY ATELIER</h1>
      <p className="mt-2 text-center text-xs tracking-[0.3em] text-white/50">AREA FONDATORE</p>
      <input type="password" value={pwd} onChange={(e) => setPwd(e.target.value)} autoFocus placeholder="Password"
        className="mt-10 w-full bg-transparent border px-4 py-3 text-white outline-none" style={{ borderColor: `${GOLD}66` }}
        data-testid="admin-password-input" />
      {err && <p className="mt-3 text-sm text-red-400" data-testid="admin-login-error">{err}</p>}
      <button type="submit" disabled={busy || !pwd} className="mt-6 w-full py-3 text-xs tracking-[0.3em] text-black disabled:opacity-50"
        style={{ background: GOLD }} data-testid="admin-login-btn">{busy ? "…" : "ENTRA"}</button>
    </form>
  );
}

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
      {items.length === 0 ? <p className="mt-4 text-sm text-white/40">Nessun prodotto sopra soglia</p> : (
        <table className="mt-4 w-full text-sm">
          <thead><tr className="text-left text-[10px] tracking-[0.2em] text-white/40">
            <th className="py-2 font-normal">PRODOTTO</th><th className="font-normal text-right">VIEWS</th>
            <th className="font-normal text-right">VENDITE</th><th className="font-normal text-right">CONV.</th>
          </tr></thead>
          <tbody>
            {items.map((p) => (
              <tr key={p.name} className="border-t border-white/10">
                <td className="py-2"><span className="text-white/50">{p.brand}</span> · {p.name}</td>
                <td className="text-right">{num(p.views)}</td>
                <td className="text-right">{num(p.sales)}</td>
                <td className="text-right" style={{ color: GOLD }}>{p.conversion.toLocaleString("it-IT")}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function AdminAtelier() {
  const [stats, setStats] = useState(null);
  const [state, setState] = useState("loading");

  const load = async () => {
    try { const { data } = await api.get("/admin/stats"); setStats(data); setState("in"); }
    catch { setState("login"); }
  };
  useEffect(() => { load(); }, []);

  const logout = async () => { try { await api.post("/admin/logout"); } catch (_e) { /* ignore */ } setStats(null); setState("login"); };

  return (
    <div className="min-h-screen bg-black text-white" translate="no" data-testid="admin-page">
      {state === "login" && <div className="min-h-screen flex items-center justify-center px-6"><Login onOk={load} /></div>}
      {state === "in" && stats && (
        <div className="max-w-6xl mx-auto px-6 py-12">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="tracking-[0.5em] text-2xl font-light" style={{ color: GOLD }}>MY ATELIER</h1>
              <p className="mt-1 text-xs tracking-[0.3em] text-white/50">DASHBOARD FONDATORE</p>
            </div>
            <button onClick={logout} className="text-xs tracking-[0.3em] border px-4 py-2" style={{ borderColor: GOLD, color: GOLD }} data-testid="admin-logout-btn">ESCI</button>
          </div>
          {stats.demo && (
            <div className="mt-8 py-3 text-center text-sm tracking-[0.4em] font-semibold text-black" style={{ background: GOLD }} data-testid="admin-demo-banner">
              DATI DIMOSTRATIVI
            </div>
          )}
          <div className="mt-8 grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Kpi label="ISCRITTI TOTALI" value={num(stats.kpi.subscribers_total)} testid="admin-kpi-subscribers" />
            <Kpi label="VISITE OGGI" value={num(stats.kpi.visits_today)} testid="admin-kpi-visits" />
            <Kpi label="ABBONATI PAGANTI" value={num(stats.kpi.paying_subscribers)} testid="admin-kpi-paying" />
            <Kpi label="INCASSO TOTALE" value={eur(stats.kpi.revenue_total)} testid="admin-kpi-revenue" />
          </div>
          <h2 className="mt-14 text-sm tracking-[0.4em]" style={{ color: GOLD }}>PRODOTTI HOT</h2>
          <p className="mt-1 text-xs text-white/40">Solo prodotti con almeno {num(stats.min_views)} visualizzazioni · conversione = vendite / views</p>
          <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-4">
            {Object.entries(stats.hot_products).map(([cat, items]) => <HotCategory key={cat} name={cat} items={items} />)}
          </div>
        </div>
      )}
    </div>
  );
}
