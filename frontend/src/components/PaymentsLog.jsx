import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const GOLD = "#D4AF37";
const FILTERS = [{ k: "", l: "TUTTI" }, { k: "success", l: "RIUSCITI" }, { k: "failed", l: "FALLITI" }];
const STATUS = { success: ["RIUSCITO", "#22c55e"], failed: ["FALLITO", "#ef4444"], refunded: ["RIMBORSATO", "#f59e0b"] };
const eur = (n) => new Intl.NumberFormat("it-IT", { style: "currency", currency: "EUR" }).format(n || 0);

export const PaymentsLog = () => {
  const [filter, setFilter] = useState("");
  const [rows, setRows] = useState(null);
  useEffect(() => {
    setRows(null);
    api.get("/admin/payments", { params: filter ? { status: filter } : {} }).then(({ data }) => setRows(data.payments)).catch(() => setRows([]));
  }, [filter]);
  return (
    <div className="mt-6 border p-6" style={{ borderColor: `${GOLD}40` }} data-testid="admin-payments-log">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-xs tracking-[0.3em]" style={{ color: GOLD }}>ULTIMI 50 PAGAMENTI</div>
        <div className="flex gap-2">
          {FILTERS.map((f) => (
            <button key={f.k || "all"} onClick={() => setFilter(f.k)} data-testid={`admin-payments-filter-${f.k || "all"}`}
              className="text-[10px] tracking-[0.3em] border px-3 py-1.5 transition-colors"
              style={filter === f.k ? { background: GOLD, color: "#000", borderColor: GOLD } : { borderColor: `${GOLD}60`, color: GOLD }}>
              {f.l}
            </button>
          ))}
        </div>
      </div>
      {rows === null ? <p className="mt-4 text-sm text-white/40">Caricamento…</p> : rows.length === 0 ? (
        <p className="mt-4 text-sm text-white/40" data-testid="admin-payments-empty">Nessun pagamento</p>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] tracking-[0.25em] text-white/40 text-left">
                <th className="pb-2 pr-3 font-normal">DATA</th><th className="pb-2 pr-3 font-normal">EMAIL</th>
                <th className="pb-2 pr-3 font-normal">TIPO</th><th className="pb-2 pr-3 font-normal">MOTIVO</th>
                <th className="pb-2 pr-3 font-normal text-right">IMPORTO</th><th className="pb-2 font-normal text-right">STATO</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => {
                const [label, color] = STATUS[p.status] || [p.status, "#999"];
                return (
                  <tr key={`${p.id}-${p.status}`} className="border-t border-white/10" data-testid="admin-payment-row">
                    <td className="py-2 pr-3 text-white/50 whitespace-nowrap">{new Date(p.createdAt).toLocaleString("it-IT", { dateStyle: "short", timeStyle: "short" })}</td>
                    <td className="pr-3">{p.email || "—"}</td>
                    <td className="pr-3 text-white/50">{p.type}</td>
                    <td className="pr-3 text-xs text-white/40 max-w-[220px] truncate" title={p.reason}>{p.reason}</td>
                    <td className="pr-3 text-right" style={{ color: GOLD }}>{eur(p.amount)}</td>
                    <td className="text-right"><span className="text-[10px] tracking-[0.2em] px-2 py-1" style={{ color, border: `1px solid ${color}` }} data-testid="admin-payment-status">{label}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
